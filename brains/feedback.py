import json
from pathlib import Path
from .learning import learning_report
from .postmortem import persist_postmortem
from .event_memory import persist_event_memory
from .similarity_memory import persist_similarity_memory
PATH=Path(__file__).parent.parent/"data"/"learning_state.json"

def persist_learning(regime_label,event_label="normal_noise",as_of_date=None):
    report=learning_report(regime_label,event_label,as_of_date=as_of_date)
    pm=persist_postmortem()
    events=persist_event_memory()
    similar=persist_similarity_memory()
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps({
        "regime":regime_label,
        "event_label":event_label,
        "report":report,
        "postmortem":pm,
        "event_memory_summary":{
            "sample_count":events.get("sample_count",0),
            "events":events.get("events",{})
        },
        "similarity_memory_summary":{
            "as_of":similar.get("as_of"),
            "matched_samples":similar.get("matched_samples",0),
            "nearest_cases":similar.get("nearest_cases",[])
        }
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return report
