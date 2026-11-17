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
                         "correct": 1, "brier": 0.04, "regime": "下行趋势"})
            rows.append({"base_date": f"2026-01-{i+1:02d}", "agent": "quant",
                         "prob_up": 0.2 if outcome else 0.8, "went_up": outcome,
                         "correct": 0, "brier": 0.64, "regime": "下行趋势"})
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

    def test_regime_breakdown_is_reported(self):
        report = build_scorecard(self._rows())
        self.assertIn("technical", report["regime_breakdown"])
        self.assertEqual(
            report["regime_breakdown"]["technical"]["下行趋势"]["evidence_status"],
            "insufficient_evidence",
        )

    def test_calibrated_duplicate_and_ensemble_are_excluded_from_brain_rank(self):
        rows = self._rows()
        extra = rows[rows.agent == "technical"].copy()
        extra["agent"] = "CHIEF_ANALYST_CALIBRATED"
        chief = rows[rows.agent == "technical"].copy()
        chief["agent"] = "CHIEF_ANALYST"
        report = build_scorecard(pd.concat([rows, extra, chief], ignore_index=True))
        self.assertNotIn("CHIEF_ANALYST_CALIBRATED", report["brains"])
        self.assertNotIn("CHIEF_ANALYST", report["brains"])

    def test_a9_specialists_are_separate_and_require_evidence(self):
        rows = self._rows()
        a9 = rows[rows.agent == "technical"].copy()
        a9["agent"] = "A9_technical"
        report = build_scorecard(pd.concat([rows, a9], ignore_index=True))
        self.assertEqual(report["a9_specialists"]["technical"]["samples"], 7)
        self.assertEqual(report["a9_specialists"]["technical"]["evidence_status"], "eligible")
        self.assertEqual(
            report["a9_specialists"]["technical"]["regimes"]["下行趋势"]["evidence_status"],
            "insufficient_evidence",
        )
        self.assertEqual(report["a9_specialists"]["quant"]["evidence_status"], "collecting")

    def test_a9_scorecard_does_not_mix_a9_super_chief(self):
        rows = self._rows()
        a9 = rows[rows.agent == "technical"].copy()
        a9["agent"] = "A9_SUPER_CHIEF"
        report = build_scorecard(pd.concat([rows, a9], ignore_index=True))
        self.assertEqual(report["a9_specialists"]["technical"]["samples"], 0)

    def test_high_probability_spread_triggers_risk_review(self):
        rows = self._rows().iloc[:2].copy()
        rows["prob_up"] = [0.9, 0.2]
        report = build_scorecard(rows)
        self.assertTrue(report["risk_review"]["triggered"])
        self.assertEqual(report["risk_review"]["status"], "high_disagreement_review")

    def test_calibrated_duplicate_is_excluded(self):
        rows = self._rows()
        extra = rows[rows.agent == "technical"].copy()
        extra["agent"] = "CHIEF_ANALYST_CALIBRATED"
        report = build_scorecard(pd.concat([rows, extra], ignore_index=True))
        self.assertNotIn("CHIEF_ANALYST_CALIBRATED", report["brains"])


if __name__ == "__main__":
    unittest.main()
