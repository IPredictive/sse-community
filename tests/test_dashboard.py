import unittest

from brains.dashboard import build_brain_dashboard, _risk_snapshot


class NineBrainDashboardTests(unittest.TestCase):
    def test_a9_and_traditional_scores_are_rendered_separately(self):
        report = {
            "brains": {"flow": {"samples": 10, "accuracy": .6, "brier": .2, "recent20_accuracy": .6}},
            "a9_specialists": {"technical": {"samples": 0, "global": None}},
            "a9_chief": {"samples": 0, "accuracy": 0},
            "regime_breakdown": {},
            "risk_review": None,
        }
        live = {"A9_technical": {"prob_up": .61}, "technical": {"prob_up": .52},
                "A9_SUPER_CHIEF": {"prob_up": .58}}
        markup = build_brain_dashboard(report, live, "2026-11-17", "下行趋势")
        self.assertIn("九脑实战评分与风险中心", markup)
        self.assertIn("技术脑", markup)
        self.assertIn("传统 AI 与 A9 独立成绩对照", markup)
        self.assertIn("样本不足", markup)
        self.assertIn("61.0%", markup)
        self.assertIn("52.0%", markup)

    def test_live_probability_spread_triggers_at_35_percent(self):
        snapshot = _risk_snapshot({
            "A9_technical": {"prob_up": .9},
            "A9_quant": {"prob_up": .5},
            "A9_macro": {"prob_up": .2},
        })
        self.assertTrue(snapshot["triggered"])
        self.assertEqual(snapshot["dissent"], 1)

    def test_no_risk_snapshot_without_two_predictions(self):
        self.assertIsNone(_risk_snapshot({"A9_technical": {"prob_up": .8}}))

    def test_insufficient_samples_do_not_trigger_anomaly_status(self):
        from brains.dashboard import _status
        self.assertEqual(_status({"samples": 4, "accuracy": .1, "brier": .9})[0], "样本不足")


if __name__ == "__main__":
    unittest.main()
