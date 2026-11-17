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
        # These future perfect results must not leak into a January 13 forecast.
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
        weights_with_future_rows = learned_weights(
            ["technical"], "下行趋势", as_of_date="2026-01-13"
        )
        load.return_value = history[history.base_date < "2026-01-13"]
        weights_without_future_rows = learned_weights(
            ["technical"], "下行趋势", as_of_date="2026-01-13"
        )
        self.assertEqual(weights_with_future_rows, weights_without_future_rows)

    @patch("brains.learning.similarity_weight_adjustments", return_value={})
    @patch("brains.learning.event_weight_adjustments", return_value={})
    @patch("brains.learning.build_postmortem", return_value={"agents": {}})
    @patch("brains.learning.load_scored")
    def test_regime_history_changes_weight_only_after_minimum_samples(self, load, *_):
        rows = self._history().query("base_date < '2026-01-13'").copy()
        load.return_value = rows
        down = learned_weights(["technical"], "下行趋势", as_of_date="2026-01-13")
        sideways = learned_weights(["technical"], "震荡", as_of_date="2026-01-13")
        self.assertEqual(down["technical"], sideways["technical"])


if __name__ == "__main__":
    unittest.main()
