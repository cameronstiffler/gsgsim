from __future__ import annotations
from typing import List, Optional, Tuple, Callable
from .models import Card, Player
from .rules import destroy_if_needed

Chooser = Callable[[List[Tuple[int, Card, int]], int], Optional[List[Tuple[int, int]]]]

def _eligible_with_caps(owner: Player) -> List[Tuple[int, Card, int]]:
    out: List[Tuple[int, Card, int]] = []
    for idx, c in enumerate(owner.board):
        if getattr(c, "new_this_turn", False):
            setattr(c, "_why_ineligible", "new this turn")
            continue
        cap = max(0, 4 - getattr(c, "wind", 0))
        out.append((idx, c, cap))
    return out

def _auto_plan(eligible: List[Tuple[int, Card, int]], total_cost: int) -> Optional[List[Tuple[int, int]]]:
    if sum(cap for _, _, cap in eligible) < total_cost:
        return None
    plan: List[Tuple[int, int]] = []
    caps = [cap for _, _, cap in eligible]
    i = 0; remaining = total_cost; n = len(eligible)
    while remaining > 0:
        if caps[i] > 0:
            idx = eligible[i][0]
            plan.append((idx, 1))
            caps[i] -= 1
            remaining -= 1
        i = (i + 1) % n
    return plan

def _validate_plan(eligible: List[Tuple[int, Card, int]], total_cost: int, plan: List[Tuple[int, int]]) -> bool:
    totals = {}
    for idx, amt in plan:
        if amt <= 0: return False
        totals[idx] = totals.get(idx, 0) + amt
    if sum(totals.values()) != total_cost: return False
    caps = {idx: cap for idx, _, cap in eligible}
    for idx, amt in totals.items():
        if idx not in caps: return False
        if amt > caps[idx]: return False
    return True

def distribute_wind(owner: Player, total_cost: int, *, auto: bool = True, chooser: Optional[Chooser] = None, allow_cancel: bool = False) -> Optional[bool]:
    if total_cost <= 0: return True
    eligible = _eligible_with_caps(owner)
    if not eligible:
        # explain why
        reasons = []
        for c in owner.board:
            if getattr(c, "new_this_turn", False):
                reasons.append(f"{getattr(c, 'name', 'Goon')}: new this turn")
        msg = "No eligible goons to pay wind."
        if reasons:
            msg += " (" + "; ".join(reasons) + ")"
        print(msg)
        return False
    if sum(cap for _, _, cap in eligible) < total_cost: return False
    if chooser is not None:
        plan = chooser(eligible, total_cost)
        if plan is None: return False
    else:
        plan = _auto_plan(eligible, total_cost)
        if plan is None: return False
    if not _validate_plan(eligible, total_cost, plan): return False
    idx_to_card = {i: c for i, c, _ in eligible}
    for idx, amt in plan:
        card = idx_to_card[idx]
        card.wind = getattr(card, "wind", 0) + amt
    for c in list(owner.board):
        destroy_if_needed(owner, c)
    return True
