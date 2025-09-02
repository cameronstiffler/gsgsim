from __future__ import annotations
from typing import Callable, Dict, Tuple
# Minimal, UI-agnostic registry so we can wire abilities one by one.

AbilityFn = Callable[[object, object], bool]  # (GameState, card) -> success

REGISTRY: Dict[Tuple[str, int], AbilityFn] = {}

def registers(name: str, idx: int):
    def deco(fn: AbilityFn):
        REGISTRY[(name.lower(), idx)] = fn
        return fn
    return deco

def use_ability(gs, card, idx: int) -> bool:
    key = (getattr(card, "name", "").lower(), idx)
    fn = REGISTRY.get(key)
    if not fn:
        return False
    return fn(gs, card)


# ---------- Minimal placeholder handlers ----------
@registers("Target Marker Probe", 0)
def _mark_target(gs, card):
    # Placeholder: toggle a "marked" flag so tests/UI can verify
    setattr(card, "marked", True)
    return True

@registers("Hover Shield", 0)
def _cover(gs, card):
    # Placeholder: toggle "covered" for a simple status effect
    setattr(card, "covered", True)
    return True

@registers("Sentry Node", 0)
def _autoburst(gs, card):
    # Placeholder: no-op success (damage resolution not implemented here)
    return True

@registers("Sentry Node", 1)
def _lead_laser(gs, card):
    # Placeholder
    return True

@registers("Sausage Droid", 0)
def _process(gs, card):
    # Placeholder: no-op success
    return True
