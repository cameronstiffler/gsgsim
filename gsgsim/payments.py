from __future__ import annotations
from typing import List, Optional, Tuple
from .models import Card, Player
from .rules import destroy_if_needed

def _eligible_pool(cards: List[Card]) -> List[Card]:
    """Goons deployed this turn cannot pay wind."""
    return [c for c in cards if not getattr(c, "new_this_turn", False)]

def _simulate_payment(pool: List[Card], total_cost: int) -> Tuple[bool, List[Tuple[Card, int]]]:
    """
    Try to cover total_cost by stacking wind on the same goon if needed.
    Returns (ok, deltas) with deltas as (card, +wind) pairs.
    """
    if total_cost <= 0:
        return True, []
    pool = sorted(pool, key=lambda c: (getattr(c, "wind", 0), getattr(c, "name", "")))
    remaining = total_cost
    deltas: List[Tuple[Card, int]] = []
    i = 0
    if not pool:
        return False, []
    while remaining > 0:
        c = pool[i]
        deltas.append((c, 1))   # KO, if any, is handled after commit
        remaining -= 1
        i = (i + 1) % len(pool)
        # keep cycling until we meet cost
    return (remaining == 0), deltas

def distribute_wind(owner: Player, total_cost: int, *, auto: bool = True, allow_cancel: bool = False) -> Optional[bool]:
    """Transactional wind payment. Applies nothing unless the full cost can be met."""
    if total_cost <= 0:
        return True
    if not owner.board:
        print("No goons in play to pay wind.")
        return False

    pool = _eligible_pool(owner.board)
    if not pool:
        print("No eligible goons to pay wind (new this turn).");
        return False

    ok, deltas = _simulate_payment(pool, total_cost)
    if not ok:
        return False  # nothing applied on failure

    # Commit
    for c, inc in deltas:
        c.wind = getattr(c, "wind", 0) + inc

    # Process retirements/KO
    for c in list(owner.board):
        destroy_if_needed(owner, c)

    return True
