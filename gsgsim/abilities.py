from __future__ import annotations

from typing import Callable, Dict, Tuple

from .payments import distribute_wind

# Minimal, UI-agnostic registry so we can wire abilities one by one.

AbilityFn = Callable[[object, object], bool]  # (GameState, card) -> success

REGISTRY: Dict[Tuple[str, int], AbilityFn] = {}


def registers(name: str, idx: int):
    def deco(fn: AbilityFn):
        REGISTRY[(name.lower(), idx)] = fn
        return fn

    return deco


def use_ability(gs, card, idx: int, targets: list | None = None) -> bool:
    # Block active abilities on deploy turn
    if getattr(card, "new_this_turn", False):
        return False

    # Ability object (if your engine stores them) or a placeholder; allow strings but treat as active
    abilities = getattr(card, "abilities", [])
    try:
        ability = abilities[idx]
    except Exception:
        return False

    # Find handler before paying any costs
    key = (getattr(card, "name", "").lower(), idx)
    fn = REGISTRY.get(key)
    if not fn:
        return False

    # Passive abilities cannot be actively used
    if getattr(ability, "passive", False):
        return False

    # Determine wind cost
    cost = getattr(ability, "cost", {}) or {}
    wind_cost = int(cost.get("wind", 0) or 0)

    # Only require turn_player if we actually need to pay
    if wind_cost > 0:
        owner = getattr(gs, "turn_player", None)
        if owner is None:
            return False
        # from .payments import distribute_wind

        if not distribute_wind(owner, wind_cost):
            return False

    # Execute handler (targets already parsed by UI)
    return fn(gs, card, targets)


def _mark_target(gs, card):
    # Placeholder: toggle a "marked" flag so tests/UI can verify
    setattr(card, "marked", True)
    return True


@registers("Hover Shield", 0)
def _cover(gs, card, targets):
    # Placeholder: toggle "covered" for a simple status effect
    setattr(card, "covered", True)
    return True


@registers("Sentry Node", 0)
def _autoburst(gs, card, targets):
    # Placeholder: no-op success (damage resolution not implemented here)
    return True


@registers("Sentry Node", 1)
def _lead_laser(gs, card, targets):
    # Placeholder
    return True


@registers("Sausage Droid", 0)
def _process(gs, card, targets):
    # Placeholder: no-op success
    return True


@registers("Lokar Simmons", 0)
def _lokar_resourceful(gs, card, targets):
    # define effect here (e.g., draw a card, mark, buff, etc.)
    return True


@registers("Lokar Simmons", 0)
def _diag_lokar_simmons_0(gs, card, targets):
    # DIAGNOSTIC ONLY: succeed to verify cost/flow; replace with real effect later
    try:
        print("[diag] RESOURCEFUL fired; targets=", [getattr(t, "name", None) for t in (targets or [])])
    except Exception:
        pass
    return True


@registers("Grim", 0)
def _diag_grim_0(gs, card, targets):
    # DIAGNOSTIC ONLY: cost 0, immediate success
    try:
        print("[diag] DEFY NATURE fired; targets=", [getattr(t, "name", None) for t in (targets or [])])
    except Exception:
        pass
    return True
