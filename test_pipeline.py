"""Regressions for the shared evaluator, ingredient matching, and provider data."""
import copy
import unittest
from unittest.mock import patch
import happiness
from household import household
from happiness import matches, score_recipe
from recipe_agent import ProviderError, recommend
from recipe_evaluator import choose_recipe, evaluate_candidate, evaluate_happiness, validate_recipe


def meal(meal_id=1, ingredients=('rice',), title='Dinner'):
    row = {'idMeal': str(meal_id), 'strMeal': title, 'strInstructions': 'Cook and serve.',
           'strCategory': 'Vegetarian'}
    row.update({f'strIngredient{i}': name for i, name in enumerate(ingredients, 1)})
    return row


class SharedPipelineTests(unittest.TestCase):
    def test_both_entry_points_share_recipes_scores_ratings_and_reviews(self):
        rows = [meal(1), meal(2, ('rice', 'mystery sauce')), meal(3, ('rice', 'peanut'))]
        data = {'household_id':'home', 'roommates':[{'name':'A','likes':['rice'],'allergies':['peanut']}],
                'ratings':[{'household_id':'home','meal_id':'1','score':5}]}
        first = recommend(data, lambda *_:rows)
        second = choose_recipe(data, lambda *_:rows)
        for field in ('recipes', 'review_recipes', 'rejected', 'attempts', 'excluded_by_rules'):
            self.assertEqual(first[field], second[field])
        self.assertEqual(first['recipes'][0]['happiness'], 71)
        self.assertEqual(second['recipe'], first['recipes'][0])
        self.assertEqual([r['id'] for r in second['review_recipes']], ['2'])

    def test_normal_recommendations_really_call_the_evaluator(self):
        with patch('recipe_agent.evaluate_candidate', wraps=evaluate_candidate) as evaluator:
            recommend({'roommates':[{'name':'A','likes':['rice']}]}, lambda *_:[meal()])
        evaluator.assert_called_once()

    def test_direct_evaluator_score_matches_returned_score(self):
        data = {'roommates':[{'name':'A','likes':['rice','spinach']}]}
        result = recommend(data, lambda *_:[meal()])
        score = evaluate_happiness(meal(), household(data))
        self.assertEqual(result['recipes'][0]['happiness'], score['happiness'])
        self.assertEqual(result['recipes'][0]['reasons'], score['roommate_scores'])
        self.assertEqual(score['happiness'], 71)

    def test_compatibility_score_names_are_aliases_not_other_formulas(self):
        for name in ('score_recipe','household_score','household_happiness','ranking_key'):
            self.assertIs(getattr(happiness, name), getattr(happiness, name + '_for_recommendations'))

    def test_same_limits_produce_same_candidates_and_order(self):
        rows = [meal(i, title=f'Dinner {i}') for i in range(1, 10)]
        data = {'roommates':[{'name':'A','likes':['rice']}]}
        a = recommend(data, lambda *_:rows, max_attempts=4, max_results=2)
        b = choose_recipe(data, lambda *_:rows, max_attempts=4, max_results=2)
        self.assertEqual(a['recipes'], b['recipes'])
        self.assertEqual(a['attempts'], 4)
        self.assertEqual(len(a['recipes']), 2)

    def test_review_only_never_becomes_the_legacy_selected_recipe(self):
        data = {'roommates':[{'name':'A','allergies':['milk']}]}
        result = choose_recipe(data, lambda *_:[meal(1, ('rice','mystery sauce'))])
        self.assertIsNone(result['recipe'])
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(len(result['review_recipes']), 1)

    def test_invalid_limits_are_rejected_by_both_routes(self):
        data = {'roommates':[{'name':'A'}]}
        for function in (recommend, choose_recipe):
            for options in ({'max_attempts':True}, {'max_attempts':0}, {'max_results':False}, {'max_results':0}):
                with self.subTest(function=function.__name__, options=options):
                    with self.assertRaises(ValueError):
                        function(data, lambda *_:[], **options)


class PreferenceMatchingTests(unittest.TestCase):
    def test_specific_likes_do_not_expand_to_allergen_families(self):
        for term, ingredient in [('salmon','cod'), ('cheddar','butter'), ('shrimp','octopus'), ('almond','walnut')]:
            with self.subTest(term=term):
                self.assertFalse(matches(term, [[ingredient]]))

    def test_categories_and_real_synonyms_still_match(self):
        for term, ingredient in [('fish','salmon'), ('dairy','butter'), ('cheese','cheddar'),
                                 ('nuts','walnut'), ('shrimp','prawns'), ('aubergine','eggplant')]:
            with self.subTest(term=term):
                self.assertTrue(matches(term, [ingredient.split()]))

    def test_generic_exclusions_reject_their_members_in_both_routes(self):
        for excluded, ingredient in [('fish','salmon'), ('dairy','butter'), ('nuts','peanut'), ('cheese','cheddar')]:
            data = {'roommates':[{'name':'A','avoid':[excluded]}]}
            for function in (recommend, choose_recipe):
                result = function(data, lambda *_:[meal(1, (ingredient,))])
                self.assertEqual(result['recipes'], [], (excluded, function.__name__))
                self.assertEqual(result['excluded_by_rules'], 1)

    def test_specific_exclusion_does_not_ban_unrelated_family_members(self):
        result = recommend({'roommates':[{'name':'A','avoid':['salmon']}]}, lambda *_:[meal(1, ('cod',))])
        self.assertEqual(len(result['recipes']), 1)

    def test_allergy_screening_remains_conservative(self):
        people = household({'roommates':[{'name':'A','allergies':['fish']}]})
        self.assertEqual(validate_recipe(meal(1, ('cod',)), people)['status'], 'unsafe')

    def test_synonym_duplicates_use_one_canonical_ingredient_and_max_strength(self):
        prefs = [{'ingredient':'aubergine','strength':0}, {'ingredient':'eggplants','strength':2},
                 {'ingredient':'Eggplant','strength':1}]
        data = {'roommates':[{'name':'A','preferences':prefs}]}
        self.assertEqual(household(data)[0]['preferences'], [{'ingredient':'eggplant','strength':2}])
        self.assertEqual(household({'roommates':[{'name':'A','preferences':list(reversed(prefs))}]})[0]['preferences'],
                         [{'ingredient':'eggplant','strength':2}])

    def test_repeated_preferences_cannot_inflate_scores(self):
        outputs = []
        for count in (1, 2, 4):
            data = {'roommates':[{'name':'A','preferences':[{'ingredient':'rice','strength':1}]*count}]}
            result = recommend(data, lambda *_:[meal()])
            outputs.append((result['recipes'][0]['happiness'], result['recipes'][0]['reasons']))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        self.assertEqual(outputs[0][0], 71)

    def test_direct_scoring_helper_also_deduplicates(self):
        people = [{'name':'A','diet':'Any','preferences':[{'ingredient':'rice','strength':1}]*4}]
        reasons, _ = score_recipe(people, [['rice']])
        self.assertEqual(reasons[0]['happiness'], 70)
        self.assertEqual(reasons[0]['total'], 1)


class ProviderRecordTests(unittest.TestCase):
    def test_malformed_records_are_skipped_without_crashing_or_losing_valid_meals(self):
        invalid = []
        for field, value in [('strMeal',7), ('strInstructions',7), ('strIngredient1',7),
                             ('strMeasure1',7), ('strCategory',[]), ('strArea',{}), ('strMealThumb',False)]:
            row = meal(len(invalid)+1)
            row[field] = value
            invalid.append(row)
        rows = [None, [], {'idMeal':True}, *invalid, meal(100)]
        data = {'roommates':[{'name':'A','likes':['rice']}]}
        for function in (recommend, choose_recipe):
            result = function(data, lambda *_:rows)
            self.assertEqual([r['id'] for r in result['recipes']], ['100'])
            self.assertGreaterEqual(result['invalid_records'], len(invalid))
            self.assertEqual(result['excluded_by_rules'], 0)

    def test_invalid_only_records_return_a_controlled_empty_result(self):
        result = recommend({'roommates':[{'name':'A'}]}, lambda *_:[dict(meal(), strInstructions=None)])
        self.assertEqual(result['status'], 'no_match')
        self.assertEqual(result['recipes'], [])
        self.assertIn('invalid', result['message'])

    def test_bad_outer_provider_shape_is_a_provider_error(self):
        with self.assertRaises(ProviderError):
            recommend({'roommates':[{'name':'A'}]}, lambda *_:{'unexpected':'object'})

    def test_null_optional_fields_and_blank_ingredient_slots_are_supported(self):
        row = dict(meal(), strMeasure1=None, strIngredient2='', strArea=None, strMealThumb=None)
        result = recommend({'roommates':[{'name':'A'}]}, lambda *_:[row])
        self.assertEqual(len(result['recipes']), 1)
        self.assertEqual(result['recipes'][0]['ingredients'], [{'name':'rice','measure':''}])

    def test_evaluator_does_not_mutate_provider_records(self):
        row = meal()
        original = copy.deepcopy(row)
        evaluate_candidate(row, household({'roommates':[{'name':'A'}]}))
        self.assertEqual(row, original)


if __name__ == '__main__':
    unittest.main()
