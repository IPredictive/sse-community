import unittest

from brains.routing import route_brains


class DynamicRoutingTests(unittest.TestCase):
    def test_uptrend_routes_to_trend_and_structure(self):
        route = route_brains({"label": "上行趋势", "trend20": 0.04}, "normal_noise")
        self.assertGreater(route["multipliers"]["technical"], 1.0)
        self.assertGreater(route["multipliers"]["market_structure"], 1.0)
        self.assertEqual(route["regime"], "上行趋势")

    def test_geopolitical_event_increases_risk_brain(self):
        route = route_brains({"label": "震荡/趋势转换"}, "geopolitical")
        self.assertGreater(route["multipliers"]["geopolitical"], 1.0)

    def test_all_multipliers_are_bounded(self):
        route = route_brains(
            {"label": "高波动风险", "volatility20": 0.5},
            "geopolitical",
            {"downside_stress_avg": 0.9, "scenario_penalty": 0.2},
        )
        for value in route["multipliers"].values():
            self.assertGreaterEqual(value, 0.82)
            self.assertLessEqual(value, 1.22)

    def test_unknown_event_is_neutral(self):
        route = route_brains({"label": "未知"}, "normal_noise")
        self.assertEqual(route["event_label"], "normal_noise")
        self.assertTrue(route["dominant_brains"])


if __name__ == "__main__":
    unittest.main()
