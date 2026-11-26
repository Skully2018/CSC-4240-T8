"""One shared preference-fit formula for recipe recommendation and evaluation."""
from diet_rules import key as ingredient_key, food_terms, mentions


def matches(term, ingredients):
    """Match specific ingredients/synonyms; expand only explicit categories."""
    acceptable = food_terms(term)
    return any(mentions(ingredient_key(' '.join(ingredient)), acceptable)
               for ingredient in ingredients)


MAX_RECOMMENDATION_HAPPINESS = 0.9
RECOMMENDATION_BASELINE = 0.62
RECOMMENDATION_POINTS = {0: 0.03, 1: 0.08, 2: 0.1}
RECOMMENDATION_MAX_BONUS = 0.28
PREFERENCE_COUNT_SCALE_START = 3
PREFERENCE_COUNT_SCALE_STEP = 0.02
RECOMMENDATION_MIN_WEIGHT = 0.6
RECOMMENDATION_SHARED_BONUS = 0.02
UNMATCHED_HOUSEHOLD_BASELINE = 0.7


def score_recipe(people, ingredients):
    """Return personal reasons and household scores, including neutral unknowns."""
    reasons, personal_scores = [], []
    any_match = False
    for person in people:
        preferences = person.get("preferences", [
            {"ingredient": term, "strength": 1} for term in person.get("likes", [])
        ])
        unique = {}
        for item in preferences:
            name = ingredient_key(item['ingredient'])
            unique[name] = max(item['strength'], unique.get(name, 0))
        preferences = [{'ingredient': name, 'strength': strength}
                       for name, strength in unique.items()]
        matched = [item for item in preferences
                   if matches(item["ingredient"], ingredients)]
        hits = [item["ingredient"] for item in matched]
        if not preferences or not matched:
            score = None
        else:
            any_match = True
            points = sum(RECOMMENDATION_POINTS[item["strength"]] for item in matched)
            list_scale = 1 + PREFERENCE_COUNT_SCALE_STEP * max(
                0, len(preferences) - PREFERENCE_COUNT_SCALE_START
            )
            bonus = min(RECOMMENDATION_MAX_BONUS, points / list_scale)
            score = min(MAX_RECOMMENDATION_HAPPINESS,
                        RECOMMENDATION_BASELINE + bonus)
        personal_scores.append(score)
        reasons.append({
            "name": person["name"],
            "matched": hits,
            "total": len(preferences),
            "happiness": round(score * 100) if score is not None else None,
            "diet": person["diet"],
        })
    if not any_match:
        return reasons, []
    scores = [score if score is not None else UNMATCHED_HOUSEHOLD_BASELINE
              for score in personal_scores]
    return reasons, scores


def household_score(scores, coverage=1.0):
    """Blend the lowest participating score with the household mean and shared fit."""
    if not scores:
        return 0.0
    minimum = min(scores)
    mean = sum(scores) / len(scores)
    base = RECOMMENDATION_MIN_WEIGHT * minimum + (1 - RECOMMENDATION_MIN_WEIGHT) * mean
    bonus = (RECOMMENDATION_SHARED_BONUS * minimum
             if coverage >= 1.0 and minimum > 0 else 0.0)
    return min(MAX_RECOMMENDATION_HAPPINESS, base + bonus)


def household_happiness(scores, coverage=1.0):
    """Return household fit, or None when no preference score applies."""
    if not scores:
        return None
    return round(household_score(scores, coverage) * 100)


def ranking_key(scores, title, meal_id, coverage=1.0):
    """Rank by preference coverage first, then household fit and stable ties."""
    return (-coverage,
            -household_score(scores, coverage),
            -min(scores, default=0.0), title.casefold(), meal_id)


# Import compatibility for existing team code: aliases to the same functions,
# not alternate formulas or wrappers that calculate a second score.
score_recipe_for_recommendations = score_recipe
household_score_for_recommendations = household_score
household_happiness_for_recommendations = household_happiness
ranking_key_for_recommendations = ranking_key
