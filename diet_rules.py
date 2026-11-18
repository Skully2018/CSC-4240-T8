"""Ingredient screening rules. Unknown ingredient compositions stay out of strict searches."""
import re
import unicodedata


# Whole-word culinary equivalents, including common translations and provider spellings.
EQUIVALENTS = {
    "eggplant": "aubergine|brinjal|berenjena|melanzana|melanzane|patlican|egg plant|baingan",
    "zucchini": "courgette|calabacin|zucchina|zucchine",
    "chickpea": "garbanzo|garbanzo bean|chana",
    "spring onion": "scallion|green onion",
    "coriander": "cilantro",
    "chilli": "chili",
    "tomato": "tomatoe",
    "bell pepper": "capsicum",
}
ALIASED_WORDS = {v:k for k, vs in EQUIVALENTS.items() for v in vs.split("|")}
ALIAS_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in
                           sorted(ALIASED_WORDS, key=len, reverse=True)) + r")\b")


def key(value):
    value = unicodedata.normalize("NFKD", value.casefold().replace("ı","i"))
    value = "".join(c for c in value if not unicodedata.combining(c))
    exceptions = {"tomatoes": "tomato", "potatoes": "potato", "anchovies": "anchovy",
                  "leaves": "leaf", "walnuts": "walnut", "molasses": "molasses", "couscous": "couscous"}
    text = " ".join(exceptions.get(w, w[:-1] if len(w) > 3 and w.endswith("s")
                                   and not w.endswith(("us", "ss")) else w)
                    for w in re.findall(r"[^\W_]+", value))


    return ALIAS_PATTERN.sub(lambda m: ALIASED_WORDS[m.group()], text)


def vocabulary(names):
    return {key(x) for x in names.split("|")}


GROUPS = {name: vocabulary(names) for name, names in {
    "milk": "milk|dairy|cream|butter|ghee|cheese|cheddar|mozzarella|feta|parmesan|parmigiano reggiano|yogurt|yoghurt|whey|casein|buttermilk|ricotta|mascarpone|halloumi|pecorino|crème fraîche",
    "egg": "egg|egg white|egg yolk|mayonnaise|mayo|albumen|meringue",
    "peanut": "peanut|groundnut|arachis|peanut oil|peanut butter",
    "tree nut": "tree nut|almond|walnut|cashew|hazelnut|pecan|pistachio|macadamia|brazil nut|pine nut|marzipan|praline",
    "soy": "soy|soya|soybean|soya bean|tofu|tempeh|edamame|miso|soy sauce",
    "sesame": "sesame|sesame seed|sesame oil|tahini|tahina|benne",
    "fish": "fish|salmon|tuna|cod|anchovy|sardine|haddock|hake|trout|tilapia|mackerel|sea bass|halibut|bonito|fish sauce",
    "shellfish": "shellfish|crustacean|mollusc|mollusk|shrimp|prawn|lobster|crab|crayfish|crawfish|scallop|clam|oyster|mussel|squid|calamari|octopus",
    "wheat": "wheat|flour|bread|breadcrumbs|breadcrumb|panko|pasta|penne|spaghetti|macaroni|linguine|tagliatelle|lasagne|lasagna|fusilli|couscous|bulgur|semolina|spelt|farro|seitan|orzo|tortilla|noodle",
}.items()}
GROUPS["gluten"] = GROUPS["wheat"] | vocabulary("barley|rye|triticale|malt|beer|ale|stout|oats|oatmeal|soy sauce")
ALIASES = {term: name for name, names in GROUPS.items() if name != "gluten" for term in names}
ALIASES.update({"gluten": "gluten", "nut": "nuts", "nuts": "nuts", "seafood": "seafood"})
GROUPS["nuts"] = GROUPS["peanut"] | GROUPS["tree nut"]
GROUPS["seafood"] = GROUPS["fish"] | GROUPS["shellfish"]

VEGETABLES = vocabulary("tomato|onion|red onion|spring onion|garlic|carrot|celery|broccoli|spinach|kale|courgette|zucchini|aubergine|eggplant|cucumber|lettuce|cabbage|bell pepper|red pepper|green pepper|yellow pepper|beetroot|cauliflower|fennel|asparagus|mushroom")
LEGUMES = vocabulary("chickpea|lentil|red lentil|green lentil|black bean|kidney bean|cannellini bean|butter bean|pea|green bean")
GRAINS = vocabulary("brown rice|quinoa|wild rice|bulgur|farro|whole wheat pasta")
MEAT = vocabulary("beef|pork|lamb|chicken|turkey|duck|veal|mutton|goat meat|rabbit|bacon|ham|pancetta|prosciutto|chorizo|sausage|salami|pepperoni|lard|suet|gelatin|gelatine|oxtail|venison|brisket|steak|mince|black pudding")
SIMPLE = VEGETABLES | LEGUMES | GRAINS | MEAT | vocabulary(
    "salt|sea salt|pepper|black pepper|white pepper|water|sugar|brown sugar|honey|olive oil|extra virgin olive oil|sunflower oil|rapeseed oil|lemon|lime|lemon juice|lime juice|orange|apple|banana|avocado|potato|sweet potato|rice|white rice|basmati rice|jasmine rice|corn|sweetcorn|parsley|mint|basil|oregano|cumin|coriander|cilantro|turmeric|paprika|thyme|rosemary|ginger|chilli|chili|cinnamon|bay leaf|olive")
# Only single-source items can pass composition screening. Sauces, breads,
# pasta and other prepared foods can have extra ingredients beyond their name.
SIMPLE |= vocabulary("milk|cream|butter|egg|egg white|egg yolk|peanut|almond|walnut|cashew|hazelnut|pecan|pistachio|pine nut|soybean|sesame seed|sesame oil|wheat|barley|rye|oats")
SIMPLE |= (GROUPS["fish"] | GROUPS["shellfish"]) - {"fish sauce"}
# Support named simple foods as custom exclusions. Keep established family
# rules (e.g. almond -> tree nuts) in preference to a narrower literal rule.
for ingredient in SIMPLE:
    if ingredient not in ALIASES:
        ALIASES[ingredient] = ingredient
        GROUPS.setdefault(ingredient, {ingredient})
for synonyms in ("aubergine|eggplant", "courgette|zucchini", "coriander|cilantro", "chilli|chili"):
    family = vocabulary(synonyms)
    for name in family:
        GROUPS[name] = family
GF_SIMPLE = SIMPLE | vocabulary(
    "corn flour|rice flour|potato flour|chickpea flour|almond flour|buckwheat|cornmeal|cornstarch|potato starch|polenta|millet|tapioca|"
    "vegetable oil|oil|plum tomato|cherry tomato|garlic clove|spring onion|red chilli|saffron|chilli powder|cinnamon stick|"
    "coconut|fig|pumpkin|lime zest|lemon zest|anchovy|paella rice|peppercorn|red wine vinegar|white wine vinegar|rice vinegar|"
    "chicken breast|chicken thigh|beef mince|lamb mince|pork loin|salted butter|unsalted butter|green chilli|tomato puree|basil leaf")
# Cured or processed meats require a product-label check.
GF_SIMPLE -= vocabulary("sausage|ham|bacon|chorizo|salami|pepperoni|black pudding|pancetta|prosciutto")
GF_QUALIFIED = re.compile(r"\b(?:gluten free (?:pasta|bread|flour|oat|noodle|soy sauce|penne|spaghetti)|"
                          r"(?:rice|corn|potato|chickpea|almond|buckwheat) flour|rice noodle)\b")
GF_BLOCK = GROUPS["gluten"] | vocabulary("wheat flour|kamut|einkorn|emmer|udon|bulghur|puff pastry|filo pastry|matzo|lager")
PLANT_ALTERNATIVES = re.compile(r"\b(?:coconut (?:milk|cream|butter)|(?:almond|oat|soy|rice) milk|"
                                r"(?:peanut|almond|cashew) butter|butter bean|cream of tartar)\b")


PREP = re.compile(r"^(?:fresh|dried|chopped|sliced|ground|peeled|frozen|crushed|grated|diced|whole|cooked|skinless|boneless) ")
DIETS = ("Any", "Vegetarian", "Vegan", "Mediterranean", "Pescatarian", "Gluten Free")


def base_name(name):
    while PREP.match(name):
        name = PREP.sub("", name, count=1)
    return name


def mentions(text, terms):
    padded = " " + text + " "
    return any(" " + term + " " in padded for term in terms)


def screen(people, names, category, recipe_text):
    diets = {p["diet"] for p in people}
    # Reject explicit conflicts even when other ingredients need manual review.
    for person in people:
        for allergen in person["allergies"]:
            term = key(allergen)
            family = ALIASES.get(term)
            if mentions(recipe_text, GROUPS.get(family, set()) | {term}):
                return False
    if "Gluten Free" in diets and mentions(GF_QUALIFIED.sub(" gfitem ", recipe_text), GF_BLOCK):
        return False
    plant_text = PLANT_ALTERNATIVES.sub(" plantitem ", recipe_text)
    if diets.intersection({"Vegan", "Vegetarian", "Pescatarian"}):
        if category in ("Beef", "Chicken", "Lamb", "Pork", "Goat") or mentions(plant_text, MEAT):
            return False
    if diets.intersection({"Vegan", "Vegetarian"}) and (
            category == "Seafood" or mentions(plant_text, GROUPS["seafood"] | {"rennet"})):
        return False
    if "Vegan" in diets and mentions(plant_text, GROUPS["milk"] | GROUPS["egg"] | {"honey"}):
        return False
    if "Mediterranean" in diets:
        markers = (VEGETABLES, LEGUMES, GRAINS, vocabulary("olive oil|olive"),
                   GROUPS["fish"] | GROUPS["shellfish"], GROUPS["tree nut"])
        groups = [any(mentions(n, group) for n in names) for group in markers]
        if sum(groups) < 2 or not any(groups[:3]) or mentions(recipe_text, MEAT - {"chicken", "turkey"}):
            return False
    return True
