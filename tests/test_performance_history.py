import unittest
import pandas as pd

from brains.performance import build_performance_history
from brains.performance_dashboard import build_performance_dashboard


class BrainPerformanceHistoryTests(unittest.TestCase):
    def _frame(self):
        rows = []
        for i, outcome in enumerate([1, 0, 1]):
            date = f"2026-11-{i+1:02d}"
            for agent, prob in (
                ("A9_SUPER_CHIEF", .7 if outcome else .3),
                ("CHIEF_ANALYST", .6 if outcome else .4),
                ("A9_technical", .65 if outcome else .35),
                ("technical", .55 if outcome else .45),
            ):
                rows.append({
                    "base_date": date, "agent": agent, "prob_up": prob,
                    "went_up": outcome, "correct": 1, "brier": (prob-outcome)**2,
                    "regime": "下行趋势",
                })
        return pd.DataFrame(rows)

    def test_daily_records_are_separated_and_have_rolling_metrics(self):
        report = build_performance_history(self._frame())
        a9 = [x for x in report["records"] if x["agent"] == "A9_technical"]
        legacy = [x for x in report["records"] if x["agent"] == "technical"]
        self.assertEqual(len(a9), 3)
        self.assertEqual(len(legacy), 3)
        self.assertEqual(a9[-1]["regime"], "下行趋势")
        self.assertIn("rolling20_brier", a9[-1])
        self.assertEqual(a9[-1]["family"], "A9")
        self.assertEqual(legacy[-1]["family"], "traditional")

    def test_a9_traditional_comparison_uses_same_matured_dates_and_gate(self):
        report = build_performance_history(self._frame())
        pair = report["paired_comparison"]
        self.assertEqual(pair["paired_dates"], 3)
        self.assertEqual(pair["status"], "collecting")
        self.assertEqual(pair["minimum_paired_dates"], 60)
        self.assertEqual(pair["regimes"]["下行趋势"]["evidence_status"], "insufficient_evidence")

    def test_risk_history_prefers_a9_when_available(self):
        predictions = pd.DataFrame([
            {"base_date": "2026-11-03", "agent": "A9_technical", "prob_up": .9},
            {"base_date": "2026-11-03", "agent": "A9_quant", "prob_up": .2},
            {"base_date": "2026-11-03", "agent": "technical", "prob_up": .5},
            {"base_date": "2026-11-03", "agent": "flow", "prob_up": .5},
        ])
        report = build_performance_history(self._frame(), predictions)
        risk = report["risk_history"][0]
        self.assertEqual(risk["family"], "A9")
        self.assertTrue(risk["triggered"])

    def test_dashboard_renders_daily_curves_and_comparison_gate(self):
        report = build_performance_history(self._frame())
        markup = build_performance_dashboard(report)
        self.assertIn("九脑每日表现曲线与风险时间轴", markup)
        self.assertIn("A9 与传统 AI", markup)
        self.assertIn("3/30", markup)


if __name__ == "__main__":
    unittest.main()
