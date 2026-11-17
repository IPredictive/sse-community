from dataclasses import dataclass, field
from typing import Any

@dataclass
class BrainResult:
    name: str
    prob_up: float
    confidence: float
    reason: str
    evidence: list[str] = field(default_factory=list)
    horizon: str = "T+1"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class BrainContext:
    df: Any
    context: dict[str, Any]
    regime: dict[str, Any]
