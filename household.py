"""Shared household validation and canonical preference representation."""
from diet_rules import DIETS, key as ingredient_key


def terms(data, field):
    items = data.get(field, [])
    if not isinstance(items, list) or len(items) > 20 or any(
        not isinstance(t, str) or not ingredient_key(t) or len(t) > 80 for t in items
    ):
        raise ValueError(f"Enter up to 20 ingredient names for {field}, each up to 80 characters.")
    return list(dict.fromkeys(ingredient_key(t) for t in items))


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
        by_ingredient = {}
        for item in prefs:
            if not isinstance(item, dict):
                raise ValueError("Each taste preference needs an ingredient and strength.")
            ingredient = item.get("ingredient")
            strength = item.get("strength")
            if (not isinstance(ingredient, str) or not ingredient.strip() or not ingredient_key(ingredient)
                    or len(ingredient) > 80 or isinstance(strength, bool)
                    or not isinstance(strength, int) or strength not in (0, 1, 2)):
                raise ValueError("Taste preferences need an ingredient and a strength from 0 to +2.")
            ingredient = ingredient_key(ingredient)
            # Repetitions and culinary synonyms contribute only once. Keep the
            # strongest stated nonnegative preference, regardless of input order.
            by_ingredient[ingredient] = max(strength, by_ingredient.get(ingredient, 0))
        preferences = [{"ingredient": ingredient, "strength": strength}
                       for ingredient, strength in by_ingredient.items()]
        people.append(dict(name=name, diet=diet, preferences=preferences,
                           likes=[p["ingredient"] for p in preferences if p["strength"] > 0],
                           **{f: terms(row, f) for f in ("avoid", "allergies")}))
    return people

