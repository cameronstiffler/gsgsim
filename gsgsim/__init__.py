# === IMPORT SENTRY (do not move/duplicate) ===
from __future__ import annotations

from .engine import (
    deploy_from_hand,
    end_of_turn,
    select_ui,
    start_of_turn,
    use_ability_cli,
)
from .loader import build_cards, find_squad_leader, load_deck_json, parse_rank

# Convenient entrypoint
from .main import main
from .models import Ability, Card, GameState, Player, Rank, Status
from .payments import distribute_wind
from .rules import apply_wind_with_resist, destroy_if_needed

__all__ = [
    "Rank",
    "Ability",
    "Status",
    "Card",
    "Player",
    "GameState",
    "load_deck_json",
    "build_cards",
    "find_squad_leader",
    "parse_rank",
    "distribute_wind",
    "apply_wind_with_resist",
    "destroy_if_needed",
    "deploy_from_hand",
    "use_ability_cli",
    "start_of_turn",
    "end_of_turn",
    "select_ui",
    "main",
]
