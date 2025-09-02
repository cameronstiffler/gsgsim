from __future__ import annotations
from .models import Card, Player

def apply_wind_with_resist(attacker_owner: Player, defender_owner: Player, target: Card, amount: int) -> int:
    if amount <= 0:
        return 0
    is_enemy = attacker_owner is not defender_owner
    has_resist = bool(target.statuses.get("resist")) if isinstance(target.statuses, dict) else False
    reduction = 1 if (is_enemy and has_resist) else 0
    actual = max(0, amount - reduction)
    target.wind = getattr(target, "wind", 0) + actual
    return actual

def destroy_if_needed(owner: Player, card: Card) -> None:
    """
    Retire card when wind >= 4. Remove from board, append to owner's retired pile.
    Idempotent if called multiple times.
    """
    if getattr(card, "wind", 0) >= 4:
        if card in owner.board:
            owner.board.remove(card)
        if card not in owner.retired:
            owner.retired.append(card)

def can_target_card(src: Card, tgt: Card) -> bool:
    # Extend later with Cover/Immunity/etc.
    return True