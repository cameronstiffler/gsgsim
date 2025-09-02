from __future__ import annotations
from typing import List, Optional, Tuple
from .models import Card, Player
from .rules import destroy_if_needed

def _eligible_pool(cards: List[Card]) -> List[Card]:
    """Goons deployed this turn cannot pay wind."""
    return [c for c in cards if not getattr(c, "new_this_turn", False)]

def _simulate_payment(pool: List[Card], total_cost: int) -> Tuple[bool, List[Tuple[Card, int]]]:
    """
    Distribute wind without exceeding 4 total wind on any single goon.
    Hitting exactly 4 is allowed (KO handled on commit).
    Returns (ok, deltas) where deltas = [(card, +wind), ...].
    """
    if total_cost <= 0:
        return True, []

    # Stable order: lowest wind first
    pool = sorted(pool, key=lambda c: (getattr(c, "wind", 0), getattr(c, "name", "")))

    # Parallel array of capacities (max we can add before hitting 4)
    capacities = [max(0, 4 - getattr(c, "wind", 0)) for c in pool]
    if sum(capacities) < total_cost:
        return False, []

    deltas: List[Tuple[Card, int]] = []
    remaining = total_cost
    i = 0
    n = len(pool)

    # Round-robin add 1 wind at a time, respecting capacities
    while remaining > 0:
        if capacities[i] > 0:
            deltas.append((pool[i], 1))
            capacities[i] -= 1
            remaining -= 1
        i = (i + 1) % n

    return True, deltas

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
