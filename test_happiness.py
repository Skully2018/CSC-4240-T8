import unittest
from fractions import Fraction

from happiness import household_happiness, household_score, ranking_key, score_recipe


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

    def test_soft_dislike_lowers_score_but_does_not_exclude(self):
        roommate = person("A", [])
        roommate["preferences"] = [{"ingredient": "olives", "strength": -2}]
        reasons, scores = score_recipe([roommate], [["olive"]])
        self.assertEqual(reasons[0]["matched"], ["olives"])
        self.assertEqual(scores[0], 0.0)

    def test_dislike_only_roommate_does_not_drag_positive_household_score(self):
        likes = person("A", ["rice"])
        dislikes = person("B", [])
        dislikes["preferences"] = [{"ingredient": "olives", "strength": -2}]
        reasons, scores = score_recipe([likes, dislikes], [["rice"]])
        self.assertEqual(reasons[1]["happiness"], 0)
        self.assertEqual(len(scores), 1)
        self.assertEqual(household_happiness(scores), 100)

    def test_neutral_preference_does_not_affect_score(self):
        roommate = person("A", [])
        roommate["preferences"] = [{"ingredient": "rice", "strength": 0}]
        reasons, scores = score_recipe([roommate], [["rice"]])
        self.assertEqual(reasons[0]["happiness"], 0)
        self.assertEqual(scores, [0.0])

    def test_matching_positive_preferences_increases_happiness(self):
        roommate = person("A", ["rice", "tomato"])
        reasons, scores = score_recipe([roommate], [["rice"], ["tomato"]])
        self.assertEqual(reasons[0]["happiness"], 100)
        self.assertEqual(household_happiness(scores), 100)

    def test_no_likes_score_zero_and_are_excluded_when_others_have_preferences(self):
        people = [person("A", ["rice"]), person("B", [])]
        reasons, scores = score_recipe(people, [["rice"]])
        self.assertEqual(reasons[1]["happiness"], 0)
        self.assertEqual(len(scores), 1)
        self.assertEqual(household_happiness(scores), 100)

    def test_all_no_likes_fall_back_to_zero_score(self):
        reasons, scores = score_recipe([person("A", []), person("B", [])], [["rice"]])
        self.assertEqual([reason["happiness"] for reason in reasons], [0, 0])
        self.assertEqual(scores, [0.0])
        self.assertEqual(household_happiness(scores), 0)

    def test_ranking_blends_minimum_and_average(self):
        fair = [0.85, 0.85]
        uneven = [0.8, 1.0]
        self.assertGreater(household_score(fair), household_score(uneven))
        self.assertLess(ranking_key(fair, "Fair", "1"), ranking_key(uneven, "Uneven", "2"))

        # Equal blended scores use the least-satisfied roommate as the tiebreaker.
        better_minimum = [Fraction(4, 5), Fraction(4, 5)]
        lower_minimum = [Fraction(79, 100), Fraction(84, 100)]
        self.assertEqual(household_score(better_minimum), household_score(lower_minimum))
        self.assertLess(ranking_key(better_minimum, "B", "1"),
                        ranking_key(lower_minimum, "A", "2"))


if __name__ == "__main__":
    unittest.main()
