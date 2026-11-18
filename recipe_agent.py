"""Stateless household recipe recommendations using TheMealDB V1."""
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

import json
import re
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from http.client import HTTPException
from diet_rules import ALIASES, DIETS, GF_SIMPLE, GF_QUALIFIED, SIMPLE, base_name, key as ingredient_key, mentions, screen


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


def matches(term, ingredients):
    phrase = ingredient_key(term).split()
    return any(name[i:i+len(phrase)] == phrase for name in ingredients for i in range(len(name)))


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
        people.append(dict(name=name, diet=diet, **{f: terms(row, f) for f in ("likes", "avoid", "allergies")}))
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
    diets = {p["diet"] for p in people}
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
            reasons, scores = [], []
            for p in people:
                hits = [t for t in p["likes"] if matches(t, names)]
                reasons.append({"name": p["name"], "matched": hits, "total": len(p["likes"]), "diet": p["diet"]})
                if p["likes"]:
                    scores.append(Fraction(len(hits), len(p["likes"])))
            key = (-min(scores, default=0), -sum(scores)/max(1, len(scores)), title.casefold(), mid)
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
            destination.append((key, dict(review_notes=checks, id=mid, title=title, category=category, area=row.get("strArea"),
                                     photo=row.get("strMealThumb"), ingredients=ingredients, instructions=directions.strip(),
                                     reasons=reasons, url="https://www.themealdb.com/meal/" + mid)))
        if len(ranked) >= 12:
            break
    ranked.sort(key=lambda pair: pair[0])
    review.sort(key=lambda pair: pair[0])
    return {"review_recipes": [r for _, r in review[:12]],
            "status": "proposed" if ranked else "needs_review" if review else "no_match", "recipes": [r for _, r in ranked[:12]],
            "excluded_by_rules": excluded,
            "message": "" if ranked else "Recipes with ingredients to verify are listed below." if review else (
                f"No matches. Household restrictions excluded {excluded} recipe(s)."
                if excluded else "No complete recipes found. Try again later.")}
