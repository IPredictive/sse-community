from .types import BrainContext
from .technical_brain import analyze as technical
from .quant_brain import analyze as quant
from .market_brain import analyze as market
from .macro_brain import analyze as macro
from .policy_brain import analyze as policy
from .geopolitical_brain import analyze as geopolitical
from .global_brain import analyze as global_analyst
from .money_brain import analyze as money
from .chief_brain import analyze as chief
from .scenario_engine import run as run_scenarios
from .event_memory import current_event
from .routing import route_brains
from market_regime import classify_market_regime

ANALYZERS = [technical, quant, market, macro, policy, geopolitical, global_analyst, money]

def run_a9_brain(df, context):
    regime = context.get("market_regime") or classify_market_regime(df)
    context["market_regime"] = regime
    try:
        context["event_label"] = current_event(df, context)
    except Exception as exc:
        print(f"[A9-EVENT] classification failed: {exc}")
        context["event_label"] = "normal_noise"
    bc = BrainContext(df, context, regime)
    results = []
    for fn in ANALYZERS:
        try:
            results.append(fn(bc))
        except Exception as exc:
            print(f"[A9] {fn.__name__} failed: {exc}")
    try:
        context["scenario"] = run_scenarios(df, context, results)
    except Exception as exc:
        print(f"[A9-SCENARIO] failed: {exc}")
        context["scenario"] = {"scenario_penalty": 0.0, "stress_adjusted_prob_up": None, "scenarios": []}
    context["routing"] = route_brains(regime, context.get("event_label", "normal_noise"), context.get("scenario", {}))
    regime_for_chief = dict(regime)
    regime_for_chief["_context_scenario"] = context.get("scenario", {})
    regime_for_chief["_event_label"] = context.get("event_label", "normal_noise")
    regime_for_chief["_routing"] = context["routing"]
    regime_for_chief["_as_of_date"] = str(df.date.iloc[-1])[:10]
    chief_result = chief(results, regime_for_chief)
    if chief_result:
        results.append(chief_result)
    return results
