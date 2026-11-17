import unittest
from unittest.mock import patch
import pandas as pd

from brains.learning import learned_weights


class AsOfLearningTests(unittest.TestCase):
    def _history(self):
        rows = []
        for i in range(12):
            rows.append({"base_date": f"2026-01-{i+1:02d}", "agent": "technical",
                         "prob_up": .8, "went_up": 0, "correct": 0, "brier": .64,
                         "regime": "下行趋势"})
        # Future rows remain present, but their outcomes must never affect Jan 13.
        for i in range(12):
            rows.append({"base_date": f"2026-02-{i+1:02d}", "agent": "technical",
                         "prob_up": .8, "went_up": 1, "correct": 1, "brier": .04,
                         "regime": "下行趋势"})
        return pd.DataFrame(rows)

    @patch("brains.learning.similarity_weight_adjustments", return_value={})
    @patch("brains.learning.event_weight_adjustments", return_value={})
    @patch("brains.learning.build_postmortem", return_value={"agents": {}})
    @patch("brains.learning.load_scored")
    def test_future_outcomes_do_not_change_past_weight(self, load, *_):
        history = self._history()
        load.return_value = history
        weights_original = learned_weights(["technical"], "下行趋势", as_of_date="2026-01-13")
        altered = history.copy()
        future = altered.base_date >= "2026-01-13"
        altered.loc[future, "correct"] = 0
        altered.loc[future, "brier"] = .99
        altered.loc[future, "went_up"] = 0
        load.return_value = altered
        weights_future_changed = learned_weights(["technical"], "下行趋势", as_of_date="2026-01-13")
        self.assertEqual(weights_original, weights_future_changed)

    @patch("brains.learning.similarity_weight_adjustments", return_value={})
    @patch("brains.learning.event_weight_adjustments", return_value={})
    @patch("brains.learning.build_postmortem", return_value={"agents": {}})
    @patch("brains.learning.load_scored")
    def test_regime_history_changes_weight_after_minimum_samples(self, load, *_):
        rows = self._history().copy()
        extra = []
        for i in range(12):
            extra.append({"base_date": f"2026-01-{i+1:02d}", "agent": "technical",
                          "prob_up": .8, "went_up": 1, "correct": 1, "brier": .04,
                          "regime": "震荡"})
        load.return_value = pd.concat([rows, pd.DataFrame(extra)], ignore_index=True)
        down = learned_weights(["technical"], "下行趋势", as_of_date="2026-01-13")
        sideways = learned_weights(["technical"], "震荡", as_of_date="2026-01-13")
        self.assertNotEqual(down["technical"], sideways["technical"])

    @patch("brains.learning.evaluate_walk_forward", return_value={
        "evaluation_dates": 25, "improvement_brier": -0.001
    })
    @patch("brains.learning.similarity_weight_adjustments", return_value={})
    @patch("brains.learning.event_weight_adjustments", return_value={})
    @patch("brains.learning.build_postmortem", return_value={"agents": {}})
    @patch("brains.learning.load_scored")
    def test_live_learning_stays_neutral_without_oos_improvement(self, load, *_):
        rows = self._history().query("base_date < '2026-01-13'").copy()
        load.return_value = rows
        weights = learned_weights(["technical"], "下行趋势", as_of_date="2026-01-13")
        self.assertEqual(weights["technical"], 1.0)


if __name__ == "__main__":
    unittest.main()
