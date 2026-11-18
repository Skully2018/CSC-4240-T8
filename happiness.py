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
