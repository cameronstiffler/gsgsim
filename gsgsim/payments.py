from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .models import Card, Player
from .rules import apply_wind

# Chooser: UI-provided callback that gets (eligible, total_cost) and returns a plan [(idx, amt), ...]
Chooser = Callable[[List[Tuple[int, Card, int]], int], Optional[List[Tuple[int, int]]]]


def _eligible_with_caps(player: Player) -> List[Tuple[int, Card, int]]:
    """
    Return list of (board_index, card, cap) that can contribute wind this turn.
    Excludes cards marked new_this_turn. cap is the MAX transferable wind (including lethal);
    the auto planner will restrict itself to 'safe' caps for SLs.
    """
    out: List[Tuple[int, Card, int]] = []
    for idx, c in enumerate(getattr(player, "board", [])):
        if getattr(c, "new_this_turn", False):
            # annotate reason for UIs that render a table
            setattr(c, "_why_ineligible", "new this turn")
            continue
        wind = getattr(c, "wind", 0)
        cap = max(0, 4 - wind)  # hitting 4 kills the card; 0..3 is safe while 4 is lethal
        if cap > 0:
            out.append((idx, c, cap))
    return out


def _auto_plan(
    eligible: List[Tuple[int, Card, int]], total_cost: int
) -> Optional[List[Tuple[int, int]]]:
    """
    Greedy auto plan that:
      1) Prefers non-SL payers first.
      2) For SLs, uses only 'safe' wind (won't push SL to 4) unless unavoidable.
      3) If only lethal SL wind can cover, returns None to force manual confirmation.
    """
    if total_cost <= 0:
        return []

    def is_sl(card: Card) -> bool:
        r = getattr(card, "rank", None)
        # rank might be a string "SL" or an object with .name
        if isinstance(r, str):
            return r.upper() == "SL"
        name = getattr(r, "name", "")
        return str(name).upper() == "SL"

    # Split eligible into non-SL and SL
    non_sl: List[Tuple[int, Card, int]] = []
    sls: List[Tuple[int, Card, int]] = []
    for tup in eligible:
        (i, c, cap) = tup
        (sls if is_sl(c) else non_sl).append(tup)

    plan: List[Tuple[int, int]] = []
    need = total_cost

    # Spend from non-SL first (any cap is fine here)
    for i, c, cap in non_sl:
        if need == 0:
            break
        take = min(cap, need)
        if take > 0:
            plan.append((i, take))
            need -= take

    if need == 0:
        return plan

    # Spend from SLs, but only 'safe' capacity (up to 3 - current wind)
    for i, c, cap in sls:
        if need == 0:
            break
        current = getattr(c, "wind", 0)
        safe_cap = max(0, 3 - current)  # keep SL alive (4 would be lethal)
        take = min(safe_cap, need)
        if take > 0:
            plan.append((i, take))
            need -= take

    if need == 0:
        return plan

    # If we still need wind now, only lethal SL wind remains -> require manual confirmation
    return None


def distribute_wind(gs, player: Player, total_cost: int, chooser: Optional[Chooser] = None) -> bool:
    """
    Apply wind payments on player's board to cover total_cost.
    Returns True if cost fully paid and wind applied, False otherwise.
    - Auto mode (chooser=None): uses _auto_plan and REFUSES lethal SL payments.
    - Manual mode (chooser provided by UI): can return a plan that includes lethal SL payments.
    """
    if total_cost <= 0:
        return True

    eligible = _eligible_with_caps(player)
    have = sum(cap for _, _, cap in eligible)
    if have < total_cost:
        print("could not pay wind")
        return False

    if chooser is not None:
        plan = chooser(eligible, total_cost)
    else:
        plan = _auto_plan(eligible, total_cost)

    if not plan:
        # None or empty plan
        print("could not pay wind")
        return False

    # Apply plan
    for board_idx, amt in plan:
        card = player.board[board_idx]
        apply_wind(gs, card, amt)

    return True


def manual_pay(
    player, total: int, plan: list[tuple[int, int]], allow_lethal_sl: bool = False
) -> bool:
    if total <= 0:
        return False
    if sum(max(0, a) for _, a in plan) != total:
        return False
    board = list(getattr(player, "board", []))
    before = [getattr(c, "wind", 0) for c in board]

    def is_sl(card):
        r = getattr(card, "rank", "")
        return (isinstance(r, str) and r.upper() == "SL") or (
            hasattr(r, "name") and str(r.name).upper() == "SL"
        )

    try:
        for idx, amt in plan:
            if amt <= 0 or not (0 <= idx < len(board)):
                raise RuntimeError("bad plan")
            c = board[idx]
            if is_sl(c) and getattr(c, "wind", 0) + amt > 3 and not allow_lethal_sl:
                raise RuntimeError("lethal")
            setattr(c, "wind", getattr(c, "wind", 0) + amt)
    except Exception:
        for c, w in zip(board, before):
            try:
                setattr(c, "wind", w)
            except Exception:
                pass
        return False
    return True
