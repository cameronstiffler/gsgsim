from __future__ import annotations

from typing import List
from typing import Tuple


def _hand_cost_tuple(card) -> Tuple[int, int, int]:
    w = int(getattr(card, "deploy_wind", 0) or 0)
    g = int(getattr(card, "deploy_gear", 0) or 0)
    m = int(getattr(card, "deploy_meat", 0) or 0)
    return (w, g, m)


def _can_afford_auto(gs, player, idx) -> bool:
    try:
        from .engine import deploy_from_hand

        ok = deploy_from_hand(gs, player, idx, dry_run=True)
        return bool(ok)
    except TypeError:
        from .engine import deploy_from_hand

        ok = deploy_from_hand(gs, player, idx)
        if ok:
            return True
        return False


def take_turn(gs, *, logger=None) -> None:
    from .engine import deploy_from_hand
    from .engine import end_of_turn

    me = gs.turn_player
    playable: List[Tuple[int, tuple]] = []
    for i, c in enumerate(me.hand):
        if _can_afford_auto(gs, me, i):
            playable.append((i, _hand_cost_tuple(c)))
    if playable:
        playable.sort(key=lambda x: x[1])
        idx = playable[0][0]
        try:
            ok = deploy_from_hand(gs, me, idx)
            if logger and not ok:
                logger(f"AI failed to deploy hand[{idx}]")
        except Exception as e:
            if logger:
                logger(f"AI deploy error: {e}")
    end_of_turn(gs)
