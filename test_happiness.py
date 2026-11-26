import unittest
from fractions import Fraction

from happiness import (
    household_happiness, household_score, ranking_key, score_recipe,
)


def person(name, likes):
    return {"name": name, "likes": likes, "diet": "Any"}


class HappinessTests(unittest.TestCase):
    def test_strength_changes_preference_weight(self):
        strong = person("A", [])
        normal = person("B", [])
        strong["preferences"] = [{"ingredient": "rice", "strength": 2},
                                 {"ingredient": "tomato", "strength": 1}]
        normal["preferences"] = [{"ingredient": "rice", "strength": 1},
                                 {"ingredient": "tomato", "strength": 1}]
        _, strong_score = score_recipe([strong], [["rice"]])
        _, normal_score = score_recipe([normal], [["rice"]])
        self.assertGreater(strong_score[0], normal_score[0])

    def test_matching_neutral_preference_adds_modest_score(self):
        roommate = person("A", [])
        roommate["preferences"] = [{"ingredient": "rice", "strength": 0}]
        reasons, scores = score_recipe([roommate], [["rice"]])
        self.assertEqual(reasons[0]["happiness"], 65)
        self.assertAlmostEqual(scores[0], 0.65)

    def test_unmatched_neutral_preference_is_not_scored(self):
        roommate = person("A", [])
        roommate["preferences"] = [{"ingredient": "rice", "strength": 0}]
        reasons, scores = score_recipe([roommate], [["beans"]])
        self.assertIsNone(reasons[0]["happiness"])
        self.assertEqual(scores, [])

    def test_matching_positive_preferences_increases_happiness(self):
        roommate = person("A", ["rice", "tomato"])
        reasons, scores = score_recipe([roommate], [["rice"], ["tomato"]])
        self.assertEqual(reasons[0]["happiness"], 78)
        self.assertEqual(household_happiness(scores), 80)

    def test_roommate_without_likes_is_not_personally_scored(self):
        people = [person("A", ["rice"]), person("B", [])]
        reasons, scores = score_recipe(people, [["rice"]])
        self.assertIsNone(reasons[1]["happiness"])
        self.assertAlmostEqual(scores[0], 0.7)
        self.assertEqual(scores[1], 0.7)
        self.assertEqual(household_happiness(scores, coverage=0.5), 70)

    def test_all_roommates_without_preferences_have_no_score(self):
        reasons, scores = score_recipe([person("A", []), person("B", [])], [["rice"]])
        self.assertEqual([reason["happiness"] for reason in reasons], [None, None])
        self.assertEqual(scores, [])
        self.assertIsNone(household_happiness(scores))

    def test_roommate_with_no_recipe_matches_lowers_household_score(self):
        matched = person("A", ["rice"])
        unmatched = person("B", ["tomato", "onion"])
        reasons, scores = score_recipe([matched, unmatched], [["rice"]])
        self.assertEqual(reasons[0]["happiness"], 70)
        self.assertIsNone(reasons[1]["happiness"])
        self.assertAlmostEqual(scores[0], 0.7)
        self.assertEqual(scores[1], 0.7)

    def test_full_preference_coverage_ranks_before_partial_coverage(self):
        full = ranking_key([0.5, 0.5], "Neutral matches", "1", coverage=1.0)
        partial = ranking_key([0.9, 0.5], "One strong match", "2", coverage=0.5)
        self.assertLess(full, partial)

    def test_ranking_blends_minimum_and_average(self):
        fair = [0.85, 0.85]
        uneven = [0.8, 1.0]
        self.assertGreater(household_score(fair), household_score(uneven))
        self.assertLess(ranking_key(fair, "Fair", "1"), ranking_key(uneven, "Uneven", "2"))

        # Equal blended scores use the least-satisfied roommate as the tiebreaker.
        better_minimum = [Fraction(4, 5), Fraction(4, 5)]
        lower_minimum = [Fraction(79, 100), Fraction(841, 1000)]
        self.assertAlmostEqual(household_score(better_minimum), household_score(lower_minimum))
        self.assertLess(ranking_key(better_minimum, "B", "1"),
                        ranking_key(lower_minimum, "A", "2"))


if __name__ == "__main__":
    unittest.main()
