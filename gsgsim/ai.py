from __future__ import annotations


def _get_end_of_turn():
    # Prefer a monkeypatched ai.end_of_turn (used by tests). If missing, return a no-op that just sets a flag.
    try:
        from . import ai as selfmod

        fn = getattr(selfmod, "end_of_turn", None)
        if callable(fn):
            return fn
    except Exception:
        pass

    def _noop(gs):
        setattr(gs, "ended", True)

    return _noop


def ai_take_turn(gs) -> None:
    from .abilities import REGISTRY
    from .abilities import use_ability
    from .payments import distribute_wind

    me = getattr(gs, "turn_player", None)
    if me is None:
        setattr(gs, "ended", True)
        return

    # Deploy first affordable (wind-only) card
    for i, card in enumerate(list(getattr(me, "hand", []))):
        cost = int(getattr(card, "deploy_wind", 0) or 0)
        if cost <= 0 or distribute_wind(me, cost):
            me.board.append(card)
            me.hand.pop(i)
            break

    # Use first zero-cost ability with effects/handler
    for bidx, c in enumerate(getattr(me, "board", [])):
        abilities = getattr(c, "abilities", []) or []
        for aidx, ab in enumerate(abilities):
            cost = int(getattr(ab, "cost", {}).get("wind", 0) or 0)
            if cost == 0:
                key = (getattr(c, "name", "").lower(), aidx)
                effects = getattr(ab, "effects", None) or []
                if effects or key in REGISTRY:
                    if use_ability(gs, c, aidx, None):
                        return _get_end_of_turn()(gs)

    return _get_end_of_turn()(gs)
