import json
from pathlib import Path
from .learning import learning_report
from .postmortem import persist_postmortem
from .event_memory import persist_event_memory
PATH=Path(__file__).parent.parent/"data"/"learning_state.json"

def persist_learning(regime_label,event_label="normal_noise"):
    report=learning_report(regime_label,event_label)
    pm=persist_postmortem()
    events=persist_event_memory()
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps({
        "regime":regime_label,
        "event_label":event_label,
        "report":report,
        "postmortem":pm,
        "event_memory_summary":{
            "sample_count":events.get("sample_count",0),
            "events":events.get("events",{})
        }
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return report
