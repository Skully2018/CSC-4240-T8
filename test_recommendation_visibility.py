"""Best-fit review candidates remain visible without overriding hard conflicts."""
import unittest
from recipe_agent import recommend
from recipe_evaluator import choose_recipe


def meal(mid,ingredients):
    row={'idMeal':str(mid),'strMeal':'Dinner '+str(mid),'strInstructions':'Cook and serve.','strCategory':'Side'}
    row.update({f'strIngredient{i}':value for i,value in enumerate(ingredients,1)})
    return row


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.data={'roommates':[{'name':'Mike','likes':['beef','cheese']},
                                {'name':'Jordan','likes':['mozzarella','potato','carrot'],'allergies':['shellfish']}]}
        self.rows=[meal(1,['carrot']),meal(2,['chicken breasts','beef stock','mozzarella','sour cream','vegetable oil','potato','carrot']),
                   meal(3,['shrimp','potato','carrot'])]

    def test_higher_fit_meal_with_label_notes_is_first_in_main_recommendations(self):
        result=recommend(self.data,lambda *_:self.rows)
        self.assertEqual(result['recommendations'][0]['id'],'2')
        self.assertTrue(result['recommendations'][0]['review_notes'])
        self.assertEqual(result['recommendations'][0]['verification_status'],'needs_review')
        self.assertGreater(result['recommendations'][0]['happiness'],result['recommendations'][1]['happiness'])

    def test_known_allergen_conflict_stays_excluded_from_every_result_list(self):
        result=recommend(self.data,lambda *_:self.rows)
        for field in ('recipes','review_recipes','recommendations'):
            self.assertNotIn('3',[item['id'] for item in result[field]])
        self.assertEqual(result['excluded_by_rules'],1)

    def test_legacy_partition_and_singular_selection_remain_conservative(self):
        result=choose_recipe(self.data,lambda *_:self.rows)
        self.assertEqual([item['id'] for item in result['recipes']],['1'])
        self.assertEqual(result['recipe']['id'],'1')
        self.assertEqual([item['id'] for item in result['review_recipes']],['2'])
        self.assertEqual(result['recommendations'][0]['id'],'2')

    def test_review_only_household_still_has_visible_recommendations(self):
        result=choose_recipe(self.data,lambda *_:[self.rows[1]])
        self.assertIsNone(result['recipe'])
        self.assertEqual(result['recipes'],[])
        self.assertEqual(len(result['recommendations']),1)
        self.assertTrue(result['recommendations'][0]['review_notes'])

    def test_limit_applies_to_combined_main_results_without_duplicates(self):
        result=recommend(self.data,lambda *_:self.rows,max_results=1)
        self.assertEqual([item['id'] for item in result['recommendations']],['2'])


if __name__=='__main__':unittest.main()
