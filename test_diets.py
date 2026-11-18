import unittest
from recipe_agent import recommend


def meal(names, category="Seafood", directions="Combine and serve."):
    row = {"idMeal": "12", "strMeal": "Dinner", "strInstructions": directions, "strCategory": category}
    row.update({f"strIngredient{i}": n for i, n in enumerate(names, 1)})
    return row


def result(row, diet="Any", allergy=None, second="Any"):
    people = [{"name":"A", "diet":diet}, {"name":"B", "diet":second, "allergies":allergy or []}]
    return recommend({"roommates":people, "query":"Dinner"}, lambda *_: [row])["status"]


class DietScreenTests(unittest.TestCase):
    def test_shared_constraints(self):
        fish = meal(["salmon", "tomatoes", "olive oil"])
        self.assertEqual(result(fish, "Pescatarian", ["peanuts"], "Mediterranean"), "proposed")
        self.assertEqual(result(fish, "Pescatarian", second="Vegan"), "no_match")
        self.assertEqual(result(fish, allergy=["fish"]), "no_match")

    def test_pescatarian_and_mediterranean(self):
        self.assertEqual(result(meal(["prawns", "chicken stock"]), "Pescatarian"), "no_match")
        self.assertEqual(result(meal(["sugar", "water"]), "Mediterranean"), "no_match")
        self.assertEqual(result(meal(["tomatoes", "olive oil", "bacon"]), "Mediterranean"), "no_match")

    def test_gluten_and_composites(self):
        for name in ("barley", "penne", "wheat flour", "soy sauce"):
            with self.subTest(name=name):
                self.assertEqual(result(meal(["rice", name]), "Gluten Free"), "no_match")
        self.assertEqual(result(meal(["rice", "seasoning mix"]), "Gluten Free"), "needs_review")
        self.assertEqual(result(meal(["rice", "salmon"]), "Gluten Free"), "proposed")

    def test_allergens(self):
        for allergy, ingredient in [("dairy","whey"),("sesame","tahini"),("nuts","peanuts"),
                                    ("eggs","egg"),("shellfish","prawns"),("soy","tofu")]:
            self.assertEqual(result(meal(["rice",ingredient]), allergy=[allergy]), "no_match")
        self.assertEqual(result(meal(["rice","mystery sauce"]), allergy=["milk"]), "needs_review")
        self.assertEqual(result(meal(["rice"], directions="Top with butter."), allergy=["milk"]), "no_match")
        self.assertEqual(result(meal(["rice","zucchini"]), allergy=["courgette"]), "no_match")
        self.assertEqual(result(meal(["rice"]), allergy=["unrecognized"]), "needs_review")

    def test_review_lists_preserve_exclusions(self):
        rows = [meal(["rice"]), meal(["rice", "pesto"]), meal(["peanut butter", "pesto"])]
        for i, row in enumerate(rows):
            row["idMeal"] = str(i)
        data = {"query":"Dinner","roommates":[{"name":"A","allergies":["peanut"]}]}
        found = recommend(data, lambda *_: rows)
        self.assertEqual([r["id"] for r in found["recipes"]], ["0"])
        self.assertEqual([r["id"] for r in found["review_recipes"]], ["1"])
        self.assertIn("pesto", found["review_recipes"][0]["review_notes"][0])
        self.assertEqual(result(meal(["sumac"]), allergy=["sumac"]), "no_match")
        self.assertEqual(result(meal(["rice", "pesto"], directions="Add groundnuts."), allergy=["peanuts"]), "no_match")

    def test_screenshot_dislike_all_fields_and_aliases(self):
        for field, word in [("strMeal", "Aubergine & hummus grills"), ("strIngredient2", "Egg Plants"),
                            ("strInstructions", "Roast the brinjals."), ("strMeasure1", "1 berenjena"),
                            ("strIngredient2", "Patlıcan")]:
            row = meal(["rice"])
            row[field] = word
            data = {"roommates": [{"name":"Mike", "avoid":["eggplant"]}]}
            result = recommend(data, lambda *_: [row])
            self.assertEqual((result["recipes"],result["review_recipes"]), ([],[]), (field,word))

    def test_broader_search_and_legacy_form(self):
        def fetch(endpoint, params):
            self.assertEqual(endpoint, "search")
            letter = params["f"]
            first = meal(["wheat"])
            first["idMeal"] = str(ord(letter))
            if letter == "z":
                return [dict(meal(["cherry tomatoes","rice flour"]), idMeal=str(i)) for i in range(5)]
            return [first]
        data = {"roommates":[{"name":"Sam","diet":"Gluten Free"}],"query":"stale","pantry":["unused"]}
        self.assertEqual(len(recommend(data, fetch)["recipes"]), 5)

    def test_qualified_gluten_sources_and_separate_wheat_allergy(self):
        for name in ("corn flour", "gluten-free pasta", "gluten-free oats"):
            self.assertEqual(result(meal(["rice",name]), "Gluten Free"), "proposed")
        self.assertEqual(result(meal(["rice flour","rye"]), "Gluten Free"), "no_match")
        self.assertEqual(result(meal(["gluten-free wheat starch"]), allergy=["wheat"]), "no_match")

if __name__ == "__main__":
    unittest.main()
