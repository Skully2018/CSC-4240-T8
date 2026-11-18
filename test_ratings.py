import unittest

from recipe_agent import recommend


def meal(meal_id, title):
    return {
        "idMeal": str(meal_id),
        "strMeal": title,
        "strInstructions": "Cook and serve.",
        "strIngredient1": "rice",
        "strCategory": "Side",
    }


class RatingRankingTests(unittest.TestCase):
    def test_prior_household_rating_changes_order_slightly(self):
        data = {
            "household_id": "home-1",
            "roommates": [{"name": "A", "likes": ["rice"]}],
            "ratings": [{"household_id": "home-1", "meal_id": "2", "score": 5,
                         "timestamp": "2026-01-01T00:00:00Z"}],
        }
        rows = [meal(1, "A Recipe"), meal(2, "Z Recipe")]
        result = recommend(data, lambda *_: rows)
        self.assertEqual(result["recipes"][0]["id"], "2")
        self.assertEqual(result["recipes"][0]["prior_rating"], 5)

    def test_ratings_from_another_household_are_ignored(self):
        data = {
            "household_id": "home-1",
            "roommates": [{"name": "A", "likes": ["rice"]}],
            "ratings": [{"household_id": "home-2", "meal_id": "2", "score": 5}],
        }
        result = recommend(data, lambda *_: [meal(1, "A Recipe"), meal(2, "Z Recipe")])
        self.assertEqual(result["recipes"][0]["id"], "1")
        self.assertIsNone(result["recipes"][1]["prior_rating"])

    def test_results_keep_unrated_exploration_recipes(self):
        rows = [meal(i, f"Meal {i:02}") for i in range(1, 16)]
        data = {
            "household_id": "home-1",
            "roommates": [{"name": "A", "likes": ["rice"]}],
            "ratings": [{"household_id": "home-1", "meal_id": str(i), "score": 5}
                        for i in range(1, 13)],
        }
        result = recommend(data, lambda *_: rows)
        self.assertEqual(len(result["recipes"]), 12)
        self.assertGreaterEqual(sum(r["prior_rating"] is None for r in result["recipes"]), 3)

    def test_recipes_with_zero_taste_fit_are_not_presented_as_matches(self):
        data = {"roommates": [{"name": "A", "likes": ["mushrooms"]}]}
        result = recommend(data, lambda *_: [meal(1, "Plain Rice")])
        self.assertEqual(result["recipes"], [])
        self.assertEqual(result["status"], "no_match")
        self.assertIn("positive taste preferences", result["message"])

    def test_high_household_rating_can_retain_a_known_favorite(self):
        data = {
            "household_id": "home-1",
            "roommates": [{"name": "A", "likes": ["mushrooms"]}],
            "ratings": [{"household_id": "home-1", "meal_id": "1", "score": 5}],
        }
        result = recommend(data, lambda *_: [meal(1, "Previously Enjoyed Rice")])
        self.assertEqual([r["id"] for r in result["recipes"]], ["1"])


if __name__ == "__main__":
    unittest.main()
