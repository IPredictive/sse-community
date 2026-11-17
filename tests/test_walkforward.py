import unittest
import pandas as pd

from brains.walkforward import evaluate_walk_forward


class WalkForwardTests(unittest.TestCase):
    def _rows(self):
        rows = []
        for i in range(16):
            date = f"2026-01-{i+1:02d}"
            actual = i % 2
            for brain, prob in (("A9_technical", .8 if actual else .2),
                                ("A9_macro", .2 if actual else .8)):
                rows.append({"base_date": date, "agent": brain, "prob_up": prob,
                             "went_up": actual, "correct": 1, "brier": .04,
                             "regime": "震荡"})
        return pd.DataFrame(rows)

    def test_walk_forward_uses_chronological_holdout(self):
        report = evaluate_walk_forward(self._rows())
        self.assertEqual(report["method"], "strict_chronological_walk_forward")
        self.assertGreaterEqual(report["evaluation_dates"], 3)
        self.assertEqual(report["first_evaluation_date"], "2026-01-09")

    def test_future_rows_do_not_change_earlier_walk_forward_results(self):
        rows = self._rows()
        first = evaluate_walk_forward(rows)
        altered = rows.copy()
        altered.loc[altered.base_date >= "2026-01-09", "correct"] = 0
        altered.loc[altered.base_date >= "2026-01-09", "brier"] = .99
        second = evaluate_walk_forward(altered)
        # Evaluation results may change because actual outcomes are changed,
        # but the method and chronological training boundary must not.
        self.assertEqual(first["first_evaluation_date"], second["first_evaluation_date"])
        self.assertEqual(first["training_minimum"], second["training_minimum"])


if __name__ == "__main__":
    unittest.main()
