from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import pandas as pd

@dataclass
class Prediction:
    prob_up: float
    reason: str
    confidence: float = 0.5

class Agent(ABC):
    name: str = "base"

    @abstractmethod
    def predict(self, df: pd.DataFrame, context: dict[str, Any] | None = None) -> Prediction | None:
        ...
