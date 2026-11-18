from diet_rules import (ALIASES, GF_QUALIFIED, GF_SIMPLE, SIMPLE, base_name,
                        key, mentions, screen)
from happiness import (
    household_happiness,
    score_recipe,
    ranking_key
)
from recipe_agent import discover, fetch, household


def propose_recipes(get=fetch):
    seen = set()
    for batch in discover(get):
        for row in batch:
            meal_id = str(row.get('idMeal') or '')
            if meal_id.isdigit() and meal_id not in seen:
                seen.add(meal_id)
                yield row


def _ingredients(row):
    return [
        {'name': name.strip(), 'measure': str(row.get(f'strMeasure{i}') or '').strip()}
        for i in range(1, 21)
        if isinstance(name := row.get(f'strIngredient{i}'), str) and name.strip()
    ]


def validate_recipe(row, people):
    ingredients = _ingredients(row)
    title = row.get('strMeal') or ''
    instructions = row.get('strInstructions') or ''
    if not title or not instructions or not ingredients:
        return {'status': 'unsafe', 'reasons': ['Incomplete recipe data.'], 'ingredients': ingredients}
    names = [key(item['name']) for item in ingredients]
    text = key(' '.join([title, instructions] + [
        item['measure'] + ' ' + item['name'] for item in ingredients
    ]))
    reasons = []
    for person in people:
        for allergy in person['allergies']:
            # Report known matches; screen() remains the final authoritative rule.
            from diet_rules import GROUPS
            term = key(allergy)
            family = ALIASES.get(term)
            if mentions(text, GROUPS.get(family, set()) | {term}):
                reasons.append(f"{person['name']}: allergy conflict with {allergy}.")
        for avoided in person['avoid']:
            if mentions(text, {key(avoided)}):
                reasons.append(f"{person['name']}: always-excluded ingredient {avoided}.")
    if not screen(people, names, str(row.get('strCategory') or ''), text):
        if not reasons:
            reasons.append('Recipe conflicts with a household dietary restriction.')
    if reasons:
        return {'status': 'unsafe', 'reasons': reasons, 'ingredients': ingredients}

    checks = []
    unsupported = sorted({a for p in people for a in p['allergies'] if key(a) not in ALIASES})
    if unsupported:
        checks.append('Unrecognized allergy terms require verification: ' + ', '.join(unsupported))
    if any(p['allergies'] for p in people):
        unknown = [item['name'] for item, n in zip(ingredients, names) if base_name(n) not in SIMPLE]
        if unknown:
            checks.append('Verify packaged ingredient composition and labels: ' + ', '.join(unknown))
    diets = {p['diet'] for p in people}
    if 'Gluten Free' in diets:
        unknown = [item['name'] for item, n in zip(ingredients, names)
                   if base_name(n) not in GF_SIMPLE and not GF_QUALIFIED.fullmatch(n)]
        if unknown:
            checks.append('Verify gluten-free composition: ' + ', '.join(unknown))
    if diets.intersection({'Vegan', 'Vegetarian', 'Pescatarian'}):
        category = str(row.get('strCategory') or '')
        accepted = {'Vegan'} if 'Vegan' in diets else {'Vegan', 'Vegetarian'}
        if diets.isdisjoint({'Vegan', 'Vegetarian'}):
            accepted.add('Seafood')
        if category not in accepted and any(base_name(n) not in SIMPLE for n in names):
            checks.append('Verify prepared ingredients for dietary restrictions.')
    return {'status': 'needs_review' if checks else 'safe',
            'reasons': checks, 'ingredients': ingredients}


def evaluate_happiness(row, people):
    ingredients = _ingredients(row)
    tokens = [key(item['name']).split() for item in ingredients]
    reasons, scores = score_recipe(people, tokens)
    return {'happiness': household_happiness(scores), 'roommate_scores': reasons}


def choose_recipe(request, get=fetch, max_attempts=50, max_results=12):
    
    if (isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or max_attempts < 1):
        raise ValueError("max_attempts must be a positive integer.")

    if (isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results < 1):
        raise ValueError("max_results must be a positive integer.")

    people = household(request)

    rejected = []
    safe_recipes = []
    attempts = 0

    # Agent 1 provides different recipe proposals
    for row in propose_recipes(get):

        if attempts >= max_attempts:
            break

        attempts += 1

        # Agent 2 validates the proposed recipe
        validation = validate_recipe(row, people)

        # Reject unsafe or uncertain recipes
        if validation["status"] != "safe":
            rejected.append({
                "id": str(row["idMeal"]),
                "title": row.get("strMeal"),
                "status": validation["status"],
                "reasons": validation["reasons"]
            })
            continue

        # Calculate happiness only for accepted recipes
        score = evaluate_happiness(row, people)

        # Build the recipe object
        recipe = {
            "id": str(row["idMeal"]),
            "title": row["strMeal"],
            "category": row.get("strCategory"),
            "area": row.get("strArea"),
            "photo": row.get("strMealThumb"),
            "ingredients": validation["ingredients"],
            "instructions": row["strInstructions"],
            "url": (
                "https://www.themealdb.com/meal/"
                + str(row["idMeal"])
            ),
            "happiness": score["happiness"],
            "reasons": score["roommate_scores"],
            "roommate_scores": score["roommate_scores"],
            "review_notes": [],
            "prior_rating": None
        }

        # Retain the recipe for comparison
        safe_recipes.append(recipe)

    # Rank every safe recipe by household happiness
    def sort_key(recipe):
        scores = [
            p["happiness"] / 100
            for p in recipe["roommate_scores"]
            if any(
                pref["strength"] > 0
                for person in people
                if person["name"] == p["name"]
                for pref in person["preferences"]
            )
        ]

        if not scores:
            scores = [0.0]

        return ranking_key(
            scores,
            recipe["title"],
            recipe["id"]
        )

    safe_recipes.sort(key=sort_key)

    # Return the highest-ranked recipes
    selected = safe_recipes[:max_results]

    if selected:
        return {
            "status": "proposed",
            "attempts": attempts,
            "rejected": rejected,
            "recipes": selected,
            "recipe": selected[0],
            "review_recipes": [],
            "excluded_by_rules": len(rejected),
            "message": (
                f"Found {len(safe_recipes)} recipes that passed "
                "automated screening. Check labels and "
                "cross-contact before serving."
            )
        }

    return {
        "status": "no_verified_recipe",
        "attempts": attempts,
        "rejected": rejected,
        "recipes": [],
        "recipe": None,
        "review_recipes": [],
        "excluded_by_rules": len(rejected),
        "message": (
            "No recipe passed automated screening "
            "within the search limit."
        )
    }

