"""Dish interpretations are reviewable proposals, never inferred restrictions."""
import copy
import json
import unittest
from config import GeminiConfig
from preference_agent import AIError, parse_preferences

CONFIG = GeminiConfig(api_key='fake-test-key')


class DishSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.output = {
            'roommates':[{'name':'Mike','diet':'Any','preferences':[], 'avoid':[], 'allergies':[]}],
            'questions':[], 'unsupported_requests':[],
            'dish_suggestions':[{'name':'Mike','dish':'cheeseburger',
                                 'ingredients':['beef','cheese','bread'], 'strength':2}],
        }

    def parse(self):
        envelope = {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(self.output)}]}}]}
        return parse_preferences({'text':'Mike loves cheeseburgers.'}, lambda *_:envelope, CONFIG)

    def test_core_dish_ingredients_are_applied_automatically(self):
        result = self.parse()
        self.assertEqual(result['roommates'][0]['preferences'], [{'ingredient':value,'strength':2} for value in ('beef','cheese','bread')])
        self.assertEqual(result['dish_suggestions'][0]['ingredients'], ['beef','cheese','bread'])
        self.assertFalse(result['requires_confirmation'])

    def test_dish_proposals_never_change_exclusions_or_allergies(self):
        before = copy.deepcopy(self.output['roommates'][0])
        person = self.parse()['roommates'][0]
        self.assertEqual(person['allergies'], before['allergies'])
        self.assertEqual(person['avoid'], before['avoid'])

    def test_explicit_preferences_are_preserved(self):
        self.output['roommates'][0]['preferences'] = [{'ingredient':'rice','strength':1}]
        self.assertEqual(self.parse()['roommates'][0]['preferences'][0], {'ingredient':'rice','strength':1})

    def test_explicit_ingredient_strength_wins_over_inference(self):
        self.output['roommates'][0]['preferences'] = [{'ingredient':'cheese','strength':0}]
        result = self.parse()
        self.assertEqual(result['roommates'][0]['preferences'][0], {'ingredient':'cheese','strength':0})
        self.assertNotIn('cheese', result['dish_suggestions'][0]['applied_ingredients'])

    def test_inferred_preferences_stay_within_the_profile_limit(self):
        self.output['roommates'][0]['preferences'] = [{'ingredient':f'food {i}','strength':1} for i in range(19)]
        result = self.parse()
        self.assertEqual(len(result['roommates'][0]['preferences']),20)
        self.assertEqual(result['status'],'needs_clarification')
        self.assertTrue(result['questions'])

    def test_multiple_dishes_do_not_duplicate_shared_ingredients(self):
        self.output['dish_suggestions'].append({'name':'Mike','dish':'pizza','ingredients':['cheese','bread','tomato'],'strength':1})
        prefs = self.parse()['roommates'][0]['preferences']
        self.assertEqual(len(prefs),4)
        self.assertEqual(next(item['strength'] for item in prefs if item['ingredient']=='cheese'),2)

    def test_suggestion_ingredients_are_normalized_and_deduplicated(self):
        self.output['dish_suggestions'][0]['ingredients'] = ['Tomatoes','tomato','Aubergine','eggplants']
        self.assertEqual(self.parse()['dish_suggestions'][0]['ingredients'], ['tomato','eggplant'])

    def test_unknown_roommate_is_rejected_instead_of_guessed(self):
        self.output['dish_suggestions'][0]['name'] = 'Someone else'
        with self.assertRaises(AIError):
            self.parse()

    def test_duplicate_dish_cards_are_removed(self):
        self.output['dish_suggestions'] *= 2
        self.assertEqual(len(self.parse()['dish_suggestions']), 1)

    def test_known_allergy_conflict_is_removed_from_proposals(self):
        self.output['roommates'][0]['allergies'] = ['milk']
        result = self.parse()['dish_suggestions'][0]
        self.assertEqual(result['ingredients'], ['beef','bread'])
        self.assertEqual(result['excluded_ingredients'], ['cheese'])

    def test_generic_exclusion_is_respected(self):
        self.output['roommates'][0]['avoid'] = ['dairy']
        self.assertNotIn('cheese', self.parse()['dish_suggestions'][0]['ingredients'])

    def test_vegetarian_conflict_is_removed(self):
        self.output['roommates'][0]['diet'] = 'Vegetarian'
        result = self.parse()['dish_suggestions'][0]
        self.assertNotIn('beef', result['ingredients'])
        self.assertIn('beef', result['excluded_ingredients'])

    def test_mediterranean_is_not_applied_as_a_whole_meal_test_to_each_ingredient(self):
        self.output['roommates'][0]['diet'] = 'Mediterranean'
        self.output['dish_suggestions'][0]['ingredients'] = ['rice','tomato','beef']
        result = self.parse()['dish_suggestions'][0]
        self.assertEqual(result['ingredients'], ['rice','tomato'])
        self.assertEqual(result['excluded_ingredients'], ['beef'])

    def test_invalid_strength_is_rejected(self):
        self.output['dish_suggestions'][0]['strength'] = True
        with self.assertRaises(AIError):
            self.parse()

    def test_inferred_allergy_field_is_rejected(self):
        self.output['dish_suggestions'][0]['allergies'] = ['milk']
        with self.assertRaises(AIError):
            self.parse()

    def test_ingredient_limit_is_enforced(self):
        self.output['dish_suggestions'][0]['ingredients'] = ['rice']*9
        with self.assertRaises(AIError):
            self.parse()

    def test_empty_normalized_ingredient_is_rejected(self):
        self.output['dish_suggestions'][0]['ingredients'] = ['!!!']
        with self.assertRaises(AIError):
            self.parse()


if __name__ == '__main__':
    unittest.main()
