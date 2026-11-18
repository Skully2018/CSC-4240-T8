import unittest
from recipe_evaluator import choose_recipe, validate_recipe
from recipe_agent import household


def meal(mid, ingredients, instructions='Cook and serve.'):
    row = {'idMeal': str(mid), 'strMeal': 'Meal ' + str(mid),
           'strCategory': 'Side', 'strInstructions': instructions}
    row.update({f'strIngredient{i}': ingredient for i, ingredient in enumerate(ingredients, 1)})
    return row


class AgentTwoTests(unittest.TestCase):
    def test_reject_then_accept_different_recipe(self):
        rows = [meal(1, ['peanuts', 'rice']), meal(2, ['rice', 'tomatoes'])]
        result = choose_recipe({'roommates': [{'name': 'A', 'allergies': ['peanut'],
                                               'likes': ['rice']}]}, lambda *_: rows)
        self.assertEqual(result['recipe']['id'], '2')
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['rejected'][0]['id'], '1')
        self.assertEqual(result['recipe']['happiness'], 100)

    def test_uncertain_food_is_not_accepted(self):
        rows = [meal(1, ['mystery sauce', 'rice']), meal(2, ['rice'])]
        result = choose_recipe({'roommates': [{'name': 'A', 'allergies': ['milk']}]}, lambda *_: rows)
        self.assertEqual(result['rejected'][0]['status'], 'needs_review')
        self.assertEqual(result['recipe']['id'], '2')

    def test_instructions_are_screened(self):
        people = household({'roommates': [{'name': 'A', 'allergies': ['milk']}]})
        self.assertEqual(validate_recipe(meal(1, ['rice'], 'Top with butter.'), people)['status'], 'unsafe')

    def test_limit_and_no_unsafe_fallback(self):
        rows = [meal(1, ['peanut']), meal(2, ['peanut'])]
        result = choose_recipe({'roommates': [{'name': 'A', 'allergies': ['peanut']}]},
                               lambda *_: rows, max_attempts=1)
        self.assertEqual(result['status'], 'no_verified_recipe')
        self.assertIsNone(result['recipe'])
        self.assertEqual(result['attempts'], 1)

    def test_duplicate_ids_are_skipped(self):
        rows = [meal(1, ['peanut']), meal(1, ['rice']), meal(2, ['rice'])]
        result = choose_recipe({'roommates': [{'name': 'A', 'allergies': ['peanut']}]}, lambda *_: rows)
        self.assertEqual(result['recipe']['id'], '2')


if __name__ == '__main__':
    unittest.main()
