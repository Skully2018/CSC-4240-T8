"""Stateless household recipe recommendations using TheMealDB V1."""
from concurrent.futures import ThreadPoolExecutor

import json
import re
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from http.client import HTTPException
from diet_rules import ALIASES, DIETS, GF_SIMPLE, GF_QUALIFIED, SIMPLE, base_name, key as ingredient_key, mentions, screen
from happiness import (
    household_happiness_for_recommendations,
    matches,
    ranking_key_for_recommendations,
    score_recipe_for_recommendations,
)


class ProviderError(Exception):
    pass


def fetch(endpoint, params):
    url = "https://www.themealdb.com/api/json/v1/1/" + endpoint + ".php?" + urlencode(params)
    try:
        req = Request(url, headers={"User-Agent": "RMR (Roommate Meal Resolutions)"})
        with urlopen(req, timeout=8) as response:
            data = json.load(response)
        if isinstance(data, dict) and "meals" in data:
            meals = data["meals"]
            if meals is None:
                return []
            if isinstance(meals, list) and all(isinstance(x, dict) for x in meals):
                return meals
    except (OSError, URLError, ValueError, HTTPException) as exc:
        raise ProviderError("TheMealDB could not be reached. Check your connection and try again.") from exc
    raise ProviderError("TheMealDB returned an unexpected response. Please try again.")


def normalized(text):
    plurals = {"tomatoes": "tomato", "potatoes": "potato", "leaves": "leaf"}
    return tuple(plurals.get(w, w[:-1] if len(w) > 3 and w.endswith("s")
                             and not w.endswith(("ss", "us")) else w)
                 for w in re.findall(r"[^\W_]+", text.casefold()))


def terms(data, field):
    items = data.get(field, [])
    if not isinstance(items, list) or len(items) > 20 or any(
        not isinstance(t, str) or not normalized(t) or len(t) > 80 for t in items
    ):
        raise ValueError(f"Enter up to 20 ingredient names for {field}, each up to 80 characters.")
    return list(dict.fromkeys(t.strip().casefold() for t in items))


def household(data):
    if not isinstance(data, dict) or not isinstance(data.get("roommates"), list) or not 1 <= len(data["roommates"]) <= 12:
        raise ValueError("Add between 1 and 12 roommates.")
    people = []
    seen = set()
    for i, row in enumerate(data["roommates"], 1):
        if not isinstance(row, dict):
            raise ValueError("Each roommate must have a profile.")
        name = row.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50:
            raise ValueError(f"Give roommate {i} a name of up to 50 characters.")
        name = name.strip()
        if name.casefold() in seen:
            raise ValueError("Give each roommate a distinct name or nickname.")
        seen.add(name.casefold())
        diet = row.get("diet", "Any")
        if diet not in DIETS:
            raise ValueError("Choose a diet from the menu.")
        prefs = row.get("preferences")
        if prefs is None:
            prefs = [{"ingredient": item, "strength": 1} for item in terms(row, "likes")]
        if not isinstance(prefs, list) or len(prefs) > 20:
            raise ValueError("Enter up to 20 taste preferences for each roommate.")
        preferences = []
        for item in prefs:
            if not isinstance(item, dict):
                raise ValueError("Each taste preference needs an ingredient and strength.")
            ingredient = item.get("ingredient")
            strength = item.get("strength")
            if (not isinstance(ingredient, str) or not ingredient.strip() or not normalized(ingredient)
                    or len(ingredient) > 80 or isinstance(strength, bool)
                    or not isinstance(strength, int) or strength not in (0, 1, 2)):
                raise ValueError("Taste preferences need an ingredient and a strength from 0 to +2.")
            preferences.append({"ingredient": ingredient.strip().casefold(), "strength": strength})
        people.append(dict(name=name, diet=diet, preferences=preferences,
                           likes=[p["ingredient"] for p in preferences if p["strength"] > 0],
                           **{f: terms(row, f) for f in ("avoid", "allergies")}))
    return people


def discover(get):
    # Each first-letter request supplies complete ingredient lists in one call.
    letters = "scabptrmlfgdhkenowiuvjyzqx"
    with ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(letters), 4):
            batch = pool.map(lambda letter: get("search", {"f": letter}), letters[start:start+4])
            yield [row for group in batch for row in group]


def recommend(data, get=fetch):
    people = household(data)
    household_id = data.get("household_id", "")
    if not isinstance(household_id, str) or len(household_id) > 100:
        raise ValueError("Invalid household ID.")
    ratings = data.get("ratings", [])
    if not isinstance(ratings, list) or len(ratings) > 500:
        raise ValueError("Invalid recipe ratings.")
    rating_by_id = {}
    for rating in ratings:
        if not isinstance(rating, dict):
            continue
        meal_id, value = rating.get("meal_id"), rating.get("score")
        if (rating.get("household_id") == household_id and isinstance(meal_id, str)
                and meal_id.isdigit() and isinstance(value, int) and not isinstance(value, bool)
                and 1 <= value <= 5):
            rating_by_id[meal_id] = value
    diets = {p["diet"] for p in people}
    has_positive_preferences = any(
        preference["strength"] > 0
        for person in people for preference in person["preferences"]
    )
    unsupported = sorted({a for p in people for a in p["allergies"] if ingredient_key(a) not in ALIASES})
    has_allergies = any(p["allergies"] for p in people)
    avoid = {ingredient_key(t) for p in people for t in p["avoid"]}
    ranked = []
    review = []
    seen = set()
    excluded = 0
    for rows in discover(get):
        for row in rows:
            mid = str(row.get("idMeal") or "")
            title = row.get("strMeal")
            directions = row.get("strInstructions")
            if mid in seen or not mid.isdigit() or not title or not directions:
                continue
            seen.add(mid)
            ingredients = [{"name": row[f"strIngredient{i}"].strip(), "measure": (row.get(f"strMeasure{i}") or "").strip()}
                           for i in range(1, 21) if (row.get(f"strIngredient{i}") or "").strip()]
            names = [ingredient_key(item["name"]).split() for item in ingredients]
            category = row.get("strCategory") or ""
            if not names:
                continue
            listed = [ingredient_key(item["name"]) for item in ingredients]
            text = ingredient_key(" ".join([title, directions] + [
                item["measure"] + " " + item["name"] for item in ingredients]))
            if mentions(text, avoid) or not screen(people, listed, category, text):
                excluded += 1
                continue
            reasons, scores = score_recipe_for_recommendations(people, names)
            coverage = (sum(bool(reason["matched"]) for reason in reasons) / len(people)
                        if people else 0.0)
            base_key = ranking_key_for_recommendations(scores, title, mid, coverage)
            prior_rating = rating_by_id.get(mid)
            if has_positive_preferences and not any(score > 0 for score in scores) and (prior_rating is None or prior_rating < 4):
                continue
            rating_adjustment = ((prior_rating - 3) * 0.025) if prior_rating is not None else 0
            key = (base_key[0], base_key[1] - rating_adjustment, *base_key[2:])
            checks = []
            if "Gluten Free" in diets:
                uncertain = [item["name"] for item, n in zip(ingredients, listed)
                             if base_name(n) not in GF_SIMPLE and not GF_QUALIFIED.fullmatch(n)]
                if uncertain:
                    checks.append("Verify gluten-free labeling or composition for " + ", ".join(uncertain) + ".")
            if diets.intersection({"Vegan", "Vegetarian", "Pescatarian"}):
                tags = {"Vegan"} if "Vegan" in diets else {"Vegan", "Vegetarian"}
                if diets.isdisjoint({"Vegan","Vegetarian"}):
                    tags.add("Seafood")
                if category not in tags and any(base_name(n) not in SIMPLE for n in listed):
                    checks.append("Check prepared ingredients for the household’s dietary restrictions.")
            if unsupported:
                checks.append("Only literal ingredient names were screened for " + ", ".join(unsupported) +
                              ". Check aliases and derivatives before considering this recipe.")
            if has_allergies:
                uncertain = [item["name"] for item, n in zip(ingredients, listed) if base_name(n) not in SIMPLE]
                if uncertain:
                    checks.append("Check the composition and labels of " + ", ".join(uncertain) + ".")
            destination = review if checks else ranked
            destination.append((key, dict(happiness=household_happiness_for_recommendations(scores, coverage), prior_rating=prior_rating,
                                     review_notes=checks, id=mid, title=title, category=category, area=row.get("strArea"),
                                     photo=row.get("strMealThumb"), ingredients=ingredients, instructions=directions.strip(),
                                     reasons=reasons, url="https://www.themealdb.com/meal/" + mid)))
        if len(ranked) >= 12 and sum(item[1]["prior_rating"] is None for item in ranked) >= 3:
            break
    ranked.sort(key=lambda pair: pair[0])
    selected = ranked[:12]
    selected_ids = {recipe["id"] for _, recipe in selected}
    already_unrated = sum(recipe["prior_rating"] is None for _, recipe in selected)
    needed_unrated = max(0, 3 - already_unrated)
    exploration = [item for item in ranked if item[1]["prior_rating"] is None
                   and item[1]["id"] not in selected_ids][:needed_unrated]
    if exploration:
        selected = selected[:12 - len(exploration)] + exploration
    review.sort(key=lambda pair: pair[0])
    return {"review_recipes": [r for _, r in review[:12]],
            "status": "proposed" if ranked else "needs_review" if review else "no_match", "recipes": [r for _, r in selected],
            "excluded_by_rules": excluded,
            "message": "" if ranked else "Recipes with ingredients to verify are listed below." if review else (
                "No recipes matched the household’s positive taste preferences. Add more liked ingredients or adjust their strengths."
                if has_positive_preferences else
                f"No matches. Household restrictions excluded {excluded} recipe(s)."
                if excluded else "No complete recipes found. Try again later.")}
