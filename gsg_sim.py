"""Facade for convenient imports and CLI entry (flake8 clean)."""

from gsgsim import (
    Ability,
    Card,
    GameState,
    Player,
    Rank,
    Status,
    load_deck_json,
    build_cards,
    find_squad_leader,
    parse_rank,
    distribute_wind,
    apply_wind_with_resist,
    destroy_if_needed,
    deploy_from_hand,
    use_ability_cli,
    start_of_turn,
    end_of_turn,
    select_ui,
)
from gsgsim.main import main

__all__ = [
    "Ability",
    "Card",
    "GameState",
    "Player",
    "Rank",
    "Status",
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

if __name__ == "__main__":
    main()
