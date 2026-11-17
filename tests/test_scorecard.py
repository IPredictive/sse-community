import unittest
import pandas as pd

from brains.scorecard import build_scorecard


class BrainScorecardTests(unittest.TestCase):
    def _rows(self):
        rows = []
        outcomes = [1, 0, 1, 0, 1, 1, 0]
        for i, outcome in enumerate(outcomes):
            rows.append({"base_date": f"2026-01-{i+1:02d}", "agent": "technical",
                         "prob_up": 0.8 if outcome else 0.2, "went_up": outcome,
                         "correct": 1, "brier": 0.04})
            rows.append({"base_date": f"2026-01-{i+1:02d}", "agent": "quant",
                         "prob_up": 0.2 if outcome else 0.8, "went_up": outcome,
                         "correct": 0, "brier": 0.64})
        return pd.DataFrame(rows)

    def test_ranking_rewards_lower_brier(self):
        report = build_scorecard(self._rows())
        self.assertEqual(report["ranking"][0]["brain"], "technical")
        self.assertEqual(report["ranking"][1]["brain"], "quant")

    def test_disagreement_uses_same_matured_dates(self):
        report = build_scorecard(self._rows())
        pair = report["disagreements"][0]
        self.assertEqual(pair["samples"], 7)
        self.assertEqual(pair["a_only_correct"] + pair["b_only_correct"], 7)

    def test_insufficient_sample_is_not_ranked(self):
        rows = self._rows().iloc[:4]
        report = build_scorecard(rows)
        self.assertEqual(report["ranking"], [])

    def test_calibrated_duplicate_is_excluded(self):
        rows = self._rows()
        extra = rows[rows.agent == "technical"].copy()
        extra["agent"] = "CHIEF_ANALYST_CALIBRATED"
        report = build_scorecard(pd.concat([rows, extra], ignore_index=True))
        self.assertNotIn("CHIEF_ANALYST_CALIBRATED", report["brains"])


if __name__ == "__main__":
    unittest.main()
