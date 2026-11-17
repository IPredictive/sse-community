import json
from pathlib import Path
from .learning import learning_report
PATH=Path(__file__).parent.parent/"data"/"learning_state.json"
def persist_learning(regime_label):
    report=learning_report(regime_label); PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps({"regime":regime_label,"report":report},ensure_ascii=False,indent=2),encoding="utf-8")
    return report
