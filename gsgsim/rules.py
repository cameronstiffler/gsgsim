# === IMPORT SENTRY ===
from __future__ import annotations

from .models import Card, Player


def apply_wind_with_resist(
    attacker_owner: Player, defender_owner: Player, target: Card, amount: int
) -> int:
    # minimal placeholder consistent with your previous code
    if amount <= 0:
        return 0
    is_enemy = attacker_owner is not defender_owner
    has_resist = bool(target.statuses.get("resist")) if isinstance(target.statuses, dict) else False
    reduction = 1 if (is_enemy and has_resist) else 0
    actual = max(0, amount - reduction)
    target.wind += actual
    return actual


def destroy_if_needed(owner: Player, card: Card) -> None:
    # put your threshold/KO rules here if you already have them; safe no-op otherwise
    pass


def can_target_card(src: Card, tgt: Card) -> bool:
    # extend with Cover, immunity, etc. For now allow all.
    return True
