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

ANALYZERS=[technical,quant,market,macro,policy,geopolitical,global_analyst,money]

def run_a9_brain(df, context):
    regime=context.get("market_regime",{}) or {}
    bc=BrainContext(df,context,regime); results=[]
    for fn in ANALYZERS:
        try: results.append(fn(bc))
        except Exception as exc: print(f"[A9] {fn.__name__} failed: {exc}")
    c=chief(results,regime)
    if c: results.append(c)
    return results
