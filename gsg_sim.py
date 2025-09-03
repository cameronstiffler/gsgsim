"""Facade for convenient imports and CLI entry (flake8 clean)."""

from gsgsim import (
    Ability,
    Card,
    GameState,
    Player,
    Rank,
    Status,
    apply_wind_with_resist,
    build_cards,
    deploy_from_hand,
    destroy_if_needed,
    distribute_wind,
    end_of_turn,
    find_squad_leader,
    load_deck_json,
    parse_rank,
    select_ui,
    start_of_turn,
    use_ability_cli,
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


def _launch_with_flags():
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", choices=["rich", "cli"], default="rich", help="UI to use")
    parser.add_argument("--ai", choices=["p1", "p2", "both"], help="Set which side(s) are AI controlled")
    parser.add_argument("--ai-p1", action="store_true", help="Make P1 AI controlled (one-shot alias for --ai p1)")
    parser.add_argument("--ai-p2", action="store_true", help="Make P2 AI controlled (one-shot alias for --ai p2)")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run without prompts (AI plays for any AI-controlled side each turn)",
    )
    args, unknown = parser.parse_known_args()

    # Encode AI choice into env vars for the UI to read.
    if args.ai:
        os.environ["GSG_AI"] = args.ai
    else:
        # compute from flags if provided
        if args.ai_p1 and args.ai_p2:
            os.environ["GSG_AI"] = "both"
        elif args.ai_p1:
            os.environ["GSG_AI"] = "p1"
        elif args.ai_p2:
            os.environ["GSG_AI"] = "p2"

    if args.auto:
        os.environ["GSG_AUTO"] = "1"

    # Preserve --ui for downstream (if main/main.py inspects it)
    os.environ["GSG_UI"] = args.ui

    # Now call the existing main()
    from gsgsim import main as _main

    _main()


if __name__ == "__main__":
    _launch_with_flags()
