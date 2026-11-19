"""Household happiness scores and fair recipe ranking."""
from diet_rules import (
    key as ingredient_key,
    GROUPS,
    ALIASES
)

MIN_WEIGHT = 0.6


def matches(term, ingredients):
    """Match preferences using ingredient names and known food families."""

    preference = ingredient_key(term)

    # Get the food family for this preference
    family = ALIASES.get(preference)

    # Build a set of acceptable ingredient names
    acceptable = {preference}

    if family and family in GROUPS:
        acceptable.update(GROUPS[family])

    for ingredient in ingredients:
        name = " ".join(ingredient)

        # Exact or phrase-based matching
        for item in acceptable:
            words = item.split()
            tokens = name.split()

            for i in range(len(tokens) - len(words) + 1):
                if tokens[i:i + len(words)] == words:
                    return True

    return False


def person_score(matched_preferences, preferences):
    """Score positive taste matches from 0% to 100%, with no match at 0%."""
    positive_total = sum(item["strength"] for item in preferences if item["strength"] > 0)
    if not positive_total:
        return 0.0
    matched_positive = sum(item["strength"] for item in matched_preferences if item["strength"] > 0)
    matched_negative = sum(abs(item["strength"]) for item in matched_preferences if item["strength"] < 0)
    return max(0.0, min(1.0, (matched_positive - matched_negative) / positive_total))


def score_recipe(people, ingredients):
    """Return per-roommate reasons and scores that count toward the household."""
    reasons, scores = [], []
    for person in people:
        preferences = person.get("preferences", [
            {"ingredient": term, "strength": 1} for term in person.get("likes", [])
        ])
        matched = [item for item in preferences
                   if item["strength"] and matches(item["ingredient"], ingredients)]
        hits = [item["ingredient"] for item in matched]
        active = [item for item in preferences if item["strength"]]
        score = person_score(matched, active)
        if any(item["strength"] > 0 for item in active):
            scores.append(score)
        reasons.append({
            "name": person["name"],
            "matched": hits,
            "total": len(active),
            "happiness": round(score * 100),
            "diet": person["diet"],
        })
    return reasons, scores or [0.0]


def household_score(scores):
    """Blend the lowest roommate score with the household mean."""
    minimum = min(scores)
    mean = sum(scores) / len(scores)
    return MIN_WEIGHT * minimum + (1 - MIN_WEIGHT) * mean


def household_happiness(scores):
    """Return the rounded blended household happiness percentage."""
    return round(household_score(scores) * 100)


def ranking_key(scores, title, meal_id):
    """Rank by blended household happiness, then minimum, then title and ID."""
    return (-household_score(scores), -min(scores), title.casefold(), meal_id)


# The Agent 1 household recommendation formula is separate from the legacy
# helpers above, which remain in use by Agent 2.
MAX_RECOMMENDATION_HAPPINESS = 0.9
RECOMMENDATION_BASELINE = 0.62
RECOMMENDATION_POINTS = {0: 0.03, 1: 0.08, 2: 0.1}
RECOMMENDATION_MAX_BONUS = 0.28
PREFERENCE_COUNT_SCALE_START = 3
PREFERENCE_COUNT_SCALE_STEP = 0.02
RECOMMENDATION_MIN_WEIGHT = 0.6
RECOMMENDATION_SHARED_BONUS = 0.02
UNMATCHED_HOUSEHOLD_BASELINE = 0.7


def score_recipe_for_recommendations(people, ingredients):
    """Return personal reasons and household scores, including neutral unknowns."""
    reasons, personal_scores = [], []
    any_match = False
    for person in people:
        preferences = person.get("preferences", [
            {"ingredient": term, "strength": 1} for term in person.get("likes", [])
        ])
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


def household_score_for_recommendations(scores, coverage=1.0):
    """Blend the lowest participating score with the household mean and shared fit."""
    if not scores:
        return 0.0
    minimum = min(scores)
    mean = sum(scores) / len(scores)
    base = RECOMMENDATION_MIN_WEIGHT * minimum + (1 - RECOMMENDATION_MIN_WEIGHT) * mean
    bonus = (RECOMMENDATION_SHARED_BONUS * minimum
             if coverage >= 1.0 and minimum > 0 else 0.0)
    return min(MAX_RECOMMENDATION_HAPPINESS, base + bonus)


def household_happiness_for_recommendations(scores, coverage=1.0):
    """Return the Agent 1 household percentage, or None when no score applies."""
    if not scores:
        return None
    return round(household_score_for_recommendations(scores, coverage) * 100)


def ranking_key_for_recommendations(scores, title, meal_id, coverage=1.0):
    """Rank by preference coverage first, then household fit and stable ties."""
    return (-coverage,
            -household_score_for_recommendations(scores, coverage),
            -min(scores, default=0.0), title.casefold(), meal_id)
