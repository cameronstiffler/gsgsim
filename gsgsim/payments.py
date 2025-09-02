# === IMPORT SENTRY ===
from __future__ import annotations

from typing import List, Optional

from .models import Card, Player
from .rules import destroy_if_needed  # if not implemented yet, keep try/except around calls


def _apply_wind_safely(targets: List[Card], total_cost: int) -> int:
    pool = sorted(
        [c for c in targets if not getattr(c, "new_this_turn", False)],
        key=lambda c: (getattr(c, "wind", 0), getattr(c, "name", "")),
    )
    paid = 0
    for c in pool:
        if paid >= total_cost:
            break
        c.wind = getattr(c, "wind", 0) + 1
        paid += 1
    return paid


def distribute_wind(
    owner: Player,
    total_cost: int,
    *,
    auto: bool = False,
    allow_cancel: bool = False,
) -> Optional[bool]:
    if total_cost <= 0:
        return True
    if not owner.board:
        print("No goons in play to pay wind.")
        return False

    if auto:
        paid = _apply_wind_safely(owner.board, total_cost)
        for c in list(owner.board):
            try:
                destroy_if_needed(owner, c)  # optional: if your rules define it
            except Exception:
                pass
        return True if paid >= total_cost else False

    # Manual payment not implemented; treat as auto for now
    paid = _apply_wind_safely(owner.board, total_cost)
    for c in list(owner.board):
        try:
            destroy_if_needed(owner, c)
        except Exception:
            pass
    return True if paid >= total_cost else False
