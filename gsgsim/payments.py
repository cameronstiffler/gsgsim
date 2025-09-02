from __future__ import annotations
from typing import List, Optional, Tuple
from .models import Card, Player
from .rules import destroy_if_needed

def _eligible_pool(cards: List[Card]) -> List[Card]:
    """Goons deployed this turn cannot pay wind."""
    return [c for c in cards if not getattr(c, "new_this_turn", False)]

def _simulate_payment(pool: List[Card], total_cost: int) -> Tuple[bool, List[Tuple[Card, int]]]:
    """
    Try to cover total_cost by distributing wind across pool without exceeding
    4 total wind on any single goon. Hitting exactly 4 is allowed (will KO on commit).
    Returns (ok, deltas) where deltas = [(card, +wind), ...].
    """
    if total_cost <= 0:
        return True, []

    # Sort by current wind then name for stable, “even” distribution
    pool = sorted(pool, key=lambda c: (getattr(c, "wind", 0), getattr(c, "name", "")))

    # Calculate per-goon capacity to contribute this transaction
    # Capacity = max extra wind until KO threshold (4 - current)
    capacities = {c: max(0, 4 - getattr(c, "wind", 0)) for c in pool}
    total_capacity = sum(capacities.values())
    if total_capacity < total_cost:
        # Not enough legal wind to pay; fail with no side effects
        return False, []

    remaining = total_cost
    deltas: List[Tuple[Card, int]] = []

    # Round-robin add 1 wind while respecting capacities
    i = 0
    cir = list(pool)
    while remaining > 0:
        c = cir[i]
        if capacities[c] > 0:
            deltas.append((c, 1))
            capacities[c] -= 1
            remaining -= 1
        # advance pointer
        i = (i + 1) % len(cir)

        # (Optional) micro-optimization: if everyone is at 0 capacity, we'd have
        # returned earlier due to total_capacity check.

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
