from __future__ import annotations


def _retire_card(gs, card) -> None:
    owner = None
    if hasattr(gs, "p1") and card in getattr(gs.p1, "board", []):
        owner = gs.p1
    elif hasattr(gs, "p2") and card in getattr(gs.p2, "board", []):
        owner = gs.p2
    if owner:
        try:
            owner.board.remove(card)
        except ValueError:
            pass
        owner.retired.append(card)


def destroy_if_needed(gs, card) -> bool:
    """
    Ensure a card at 4+ wind is retired. Return True iff card was retired.
    Idempotent; safe to call anytime after wind changes.
    """
    try:
        w = int(getattr(card, "wind", 0) or 0)
    except Exception:
        w = 0
    if w >= 4:
        _retire_card(gs, card)
        return True
    return False


def apply_wind(gs, card, delta: int) -> int:
    """
    Add/remove wind by delta (can be negative). Retire immediately at >= 4 wind.
    Return the applied delta.
    """
    old = int(getattr(card, "wind", 0) or 0)
    new = max(0, old + int(delta))
    card.wind = new
    if new >= 4:
        _retire_card(gs, card)
    return new - old


def cannot_spend_wind(gs, card) -> bool:
    """
    New-deploy lock: cannot spend wind / use abilities this turn.
    `gs` is accepted (may be None) for consistency with callers.
    """
    return bool(getattr(card, "just_deployed", False) or getattr(card, "cannot_spend_wind", False))

def apply_wind_with_resist(gs, card, delta: int, *, hostile: bool = False) -> int:
    """
    Like apply_wind, but if this is hostile wind and the target has resist,
    reduce the incoming positive delta by 1 (to a minimum of 0).
    """
    has_resist = bool(
        getattr(card, "resist", False)
        or getattr(card, "has_resist", False)
        or (
            hasattr(card, "icons")
            and card.icons
            and any(str(x).strip().lower() == "resist" for x in card.icons)
        )
    )
    eff = delta
    if hostile and delta > 0 and has_resist:
        eff = max(0, delta - 1)
    return apply_wind(gs, card, eff)
