import json
from pathlib import Path

STATE_PATH=Path(__file__).parent.parent/"data"/"scenario_state.json"

def persist_scenario(report):
    STATE_PATH.parent.mkdir(exist_ok=True)
    payload=dict(report)
    payload["updated_at"]=__import__("datetime").datetime.utcnow().isoformat()+"Z"
    STATE_PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return payload
