"""Validate and score the recipe agent's candidates; never run a second search."""
from diet_rules import (
    ALIASES, GROUPS, GF_QUALIFIED, GF_SIMPLE, SIMPLE, base_name,
    key, food_terms, mentions, screen,
)
from happiness import household_happiness, score_recipe


def normalize_recipe(row):
    """Validate one external MealDB record before any string operations."""
    if not isinstance(row, dict):
        raise ValueError('Recipe record must be an object.')
    raw_id = row.get('idMeal')
    if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)) or not str(raw_id).isdigit():
        raise ValueError('Recipe ID is missing or invalid.')
    for field in ('strMeal', 'strInstructions'):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError('Recipe title or instructions are missing or invalid.')
    optional = {}
    for field in ('strCategory', 'strArea', 'strMealThumb'):
        value = row.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError('Recipe metadata must be text.')
        optional[field] = (value or '').strip()
    ingredients = []
    for index in range(1, 21):
        name = row.get(f'strIngredient{index}')
        if name is None:
            continue
        if not isinstance(name, str):
            raise ValueError('Recipe ingredient names must be text.')
        if not name.strip():
            continue
        measure = row.get(f'strMeasure{index}')
        if measure is not None and not isinstance(measure, str):
            raise ValueError('Recipe ingredient measures must be text.')
        ingredients.append({'name': name.strip(), 'measure': (measure or '').strip()})
    if not ingredients:
        raise ValueError('Recipe has no ingredients.')
    title, instructions = row['strMeal'].strip(), row['strInstructions'].strip()
    return {
        'id': str(raw_id), 'title': title, 'instructions': instructions,
        'category': optional['strCategory'], 'area': optional['strArea'],
        'photo': optional['strMealThumb'], 'ingredients': ingredients,
        'names': [key(item['name']) for item in ingredients],
        'text': key(' '.join([title, instructions] + [
            item['measure'] + ' ' + item['name'] for item in ingredients
        ])),
    }


def _validate_normalized(recipe, people):
    ingredients, names, text = recipe['ingredients'], recipe['names'], recipe['text']
    category = recipe['category']
    reasons = []
    for person in people:
        for allergy in person['allergies']:
            term = key(allergy)
            if mentions(text, GROUPS.get(ALIASES.get(term), set()) | {term}):
                reasons.append(f"{person['name']}: allergy conflict with {allergy}.")
        for avoided in person['avoid']:
            if mentions(text, food_terms(avoided)):
                reasons.append(f"{person['name']}: always-excluded ingredient {avoided}.")
    if not screen(people, names, category, text) and not reasons:
        reasons.append('Recipe conflicts with a household dietary restriction.')
    if reasons:
        return {'status': 'unsafe', 'reasons': reasons, 'ingredients': ingredients}

    checks = []
    diets = {person['diet'] for person in people}
    unsupported = sorted({allergy for person in people for allergy in person['allergies']
                          if key(allergy) not in ALIASES})
    if unsupported:
        checks.append('Unrecognized allergy terms require verification: ' + ', '.join(unsupported))
    if any(person['allergies'] for person in people):
        unknown = [item['name'] for item, name in zip(ingredients, names) if base_name(name) not in SIMPLE]
        if unknown:
            checks.append('Verify packaged ingredient composition and labels: ' + ', '.join(unknown))
    if 'Gluten Free' in diets:
        unknown = [item['name'] for item, name in zip(ingredients, names)
                   if base_name(name) not in GF_SIMPLE and not GF_QUALIFIED.fullmatch(name)]
        if unknown:
            checks.append('Verify gluten-free composition: ' + ', '.join(unknown))
    if diets.intersection({'Vegan', 'Vegetarian', 'Pescatarian'}):
        accepted = {'Vegan'} if 'Vegan' in diets else {'Vegan', 'Vegetarian'}
        if diets.isdisjoint({'Vegan', 'Vegetarian'}):
            accepted.add('Seafood')
        if category not in accepted and any(base_name(name) not in SIMPLE for name in names):
            checks.append('Verify prepared ingredients for dietary restrictions.')
    return {'status': 'needs_review' if checks else 'safe',
            'reasons': checks, 'ingredients': ingredients}


def validate_recipe(row, people):
    """Public raw-record validator, using the same path as live recommendations."""
    try:
        recipe = normalize_recipe(row)
    except ValueError as exc:
        return {'status': 'invalid', 'reasons': [str(exc)], 'ingredients': []}
    return _validate_normalized(recipe, people)


def _score_normalized(recipe, people):
    reasons, scores = score_recipe(people, [name.split() for name in recipe['names']])
    coverage = sum(bool(reason['matched']) for reason in reasons) / len(people) if people else 0.0
    return {'happiness': household_happiness(scores, coverage), 'roommate_scores': reasons,
            'scores': scores, 'coverage': coverage}


def evaluate_happiness(row, people):
    """Direct scoring helper, using the single canonical formula."""
    return _score_normalized(normalize_recipe(row), people)


def evaluate_candidate(row, people):
    """The active evaluator: normalize, screen, then score a retrieved candidate."""
    try:
        recipe = normalize_recipe(row)
    except ValueError as exc:
        return {'status': 'invalid', 'reasons': [str(exc)], 'recipe': None}
    validation = _validate_normalized(recipe, people)
    if validation['status'] == 'unsafe':
        return dict(validation, recipe=None)
    score = _score_normalized(recipe, people)
    card = {name: recipe[name] for name in (
        'id', 'title', 'category', 'area', 'photo', 'ingredients', 'instructions'
    )}
    card.update(happiness=score['happiness'], reasons=score['roommate_scores'],
                roommate_scores=score['roommate_scores'], review_notes=validation['reasons'],
                verification_status=validation['status'], prior_rating=None, url='https://www.themealdb.com/meal/' + recipe['id'])
    return dict(validation, recipe=card, scores=score['scores'], coverage=score['coverage'])


def choose_recipe(request, get=None, max_attempts=None, max_results=12):
    """Compatibility endpoint: delegate retrieval/ranking to the shared pipeline.

    With the same limits, /evaluate and /recommend return the same recipes and
    fit scores. The legacy singular recipe field always excludes review items.
    """
    # Imported only when called, so the agent can import evaluate_candidate.
    from recipe_agent import fetch, recommend
    result = recommend(request, get=fetch if get is None else get,
                       max_attempts=max_attempts, max_results=max_results)
    result['recipe'] = result['recipes'][0] if result['recipes'] else None
    if result['status'] == 'no_match':
        result['status'] = 'no_verified_recipe'
    return result
