import unittest
from unittest.mock import patch

import pandas as pd

from brains.calibration import calibrate_probability, walk_forward_backtest


class CalibrationTests(unittest.TestCase):
    def test_target_and_future_dates_are_excluded(self):
        rows = []
        for i in range(30):
            rows.append({
                "base_date": f"2026-01-{i + 1:02d}",
                "agent": "CHIEF_ANALYST",
                "prob_up": 0.60,
                "went_up": 1,
            })
        rows.extend([
            {"base_date": "2026-02-01", "agent": "CHIEF_ANALYST", "prob_up": 0.01, "went_up": 0},
            {"base_date": "2026-02-02", "agent": "CHIEF_ANALYST", "prob_up": 0.99, "went_up": 0},
        ])
        with patch("brains.calibration.load_scored", return_value=pd.DataFrame(rows)):
            calibrated, meta = calibrate_probability(0.60, "2026-02-01")
        self.assertTrue(meta["active"])
        self.assertEqual(meta["samples"], 30)
        self.assertGreater(calibrated, 0.60)

    def test_walk_forward_requires_prior_training_history(self):
        rows = []
        for i in range(35):
            rows.append({
                "base_date": f"2026-01-{i + 1:02d}",
                "agent": "CHIEF_ANALYST",
                "prob_up": 0.65,
                "went_up": 1 if i % 2 else 0,
            })
        report = walk_forward_backtest(pd.DataFrame(rows))
        metrics = report["brains"]["CHIEF_ANALYST"]
        self.assertEqual(metrics["backtested_samples"], 5)
        self.assertIn("raw_brier", metrics)
        self.assertIn("calibrated_brier", metrics)

    def test_insufficient_history_leaves_raw_probability_unchanged(self):
        history = pd.DataFrame([{
            "base_date": "2026-01-01", "prob_up": 0.7, "went_up": 1
        }])
        from brains.calibration import _adjust
        calibrated, meta = _adjust(0.63, history)
        self.assertEqual(calibrated, 0.63)
        self.assertFalse(meta["active"])


if __name__ == "__main__":
    unittest.main()
