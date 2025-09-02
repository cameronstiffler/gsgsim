# Monkeypatch draw() and end_of_turn() to set/clear 'new' flags and avoid changing engine.py
from __future__ import annotations

from typing import Any

try:
    from . import engine as _eng
except Exception:
    _eng = None

if _eng is not None:
    _orig_draw = getattr(_eng, "draw", None)
    _orig_eot = getattr(_eng, "end_of_turn", None)

    def _set_new_in_hand(player: Any, before_len: int):
        try:
            after_len = len(player.hand)
            for i in range(before_len, after_len):
                card = player.hand[i]
                setattr(card, "new_in_hand", True)
        except Exception:
            pass

    def draw(player: Any, n: int = 1):
        if _orig_draw is None:
            return None
        before = len(getattr(player, "hand", []))
        res = _orig_draw(player, n)
        _set_new_in_hand(player, before)
        return res

    def _clear_flags(gs: Any):
        try:
            for p in (gs.p1, gs.p2):
                for c in list(getattr(p, "board", [])) + list(getattr(p, "hand", [])):
                    if hasattr(c, "new_this_turn"):
                        c.new_this_turn = False
                    if hasattr(c, "new_in_hand"):
                        c.new_in_hand = False
        except Exception:
            pass

    def end_of_turn(gs: Any):
        if _orig_eot is None:
            return None
        res = _orig_eot(gs)
        _clear_flags(gs)
        return res

    # Apply monkeypatches if originals exist
    if _orig_draw is not None:
        _eng.draw = draw
    if _orig_eot is not None:
        _eng.end_of_turn = end_of_turn
