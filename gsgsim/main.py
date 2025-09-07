# === IMPORT SENTRY ===
from __future__ import annotations

import argparse
import os
import random

from .engine import select_ui
from .engine import start_of_turn
from .loader import build_cards
from .loader import find_squad_leader
from .loader import load_deck_json
from .loader_new import assert_legal_deck
from .loader_new import load_deck
from .models import GameState
from .models import Player


def _choose_decks(args):
    use_strict = bool(getattr(args, "use_strict", False) or os.environ.get("GSG_USE_STRICT"))
    if use_strict:
        return ("pcu_deck_strict.json", "narc_deck_strict.json")
    return ("pcu_deck.json", "narc_deck.json")


def main():
    # CLI

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ui", choices=["cli", "rich"], default=os.environ.get("GSG_UI", "cli"))
    parser.add_argument("--first", choices=["random", "p1", "p2"], default=os.environ.get("GSG_FIRST", "random"))
    parser.add_argument("--ai", choices=["none", "p1", "p2", "both"], default=os.environ.get("GSG_AI", "none"))
    parser.add_argument("--auto", action="store_true", default=False)
    parser.add_argument("--seed", type=int, default=os.environ.get("GSG_SEED", None))
    parser.add_argument("--use-strict", action="store_true", default=False, help="Use strict deck JSON for gameplay (or set GSG_USE_STRICT=1)")
    args, _ = parser.parse_known_args()

    pcu_path, narc_path = _choose_decks(args)

    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    # Validate decks against the strict schema when using strict decks or when GSG_STRICT is set
    try:
        if bool(os.environ.get("GSG_STRICT")) or bool(getattr(args, "use_strict", False)):
            strict_narc = load_deck(narc_path)
            strict_pcu = load_deck(pcu_path)
            if os.environ.get("GSG_STRICT"):
                assert_legal_deck(strict_narc)
                assert_legal_deck(strict_pcu)
    except Exception as _schema_err:
        raise SystemExit(f"Deck schema validation failed: {_schema_err}")

    # Load decks
    narc = load_deck_json(narc_path)
    pcu = load_deck_json(pcu_path)
    narc_cards = build_cards(narc, faction="NARC")
    pcu_cards = build_cards(pcu, faction="PCU")

    p1_sl = find_squad_leader(narc_cards)
    p2_sl = find_squad_leader(pcu_cards)
    if not p1_sl or not p2_sl:
        raise SystemExit("Both decks must contain a Squad Leader to start.")

    # Build players: SL on board; rest in deck
    p1_deck = [c for c in narc_cards if c is not p1_sl]
    p2_deck = [c for c in pcu_cards if c is not p2_sl]
    p1 = Player("NARC", board=[p1_sl], hand=[], deck=p1_deck, retired=[])
    p2 = Player("PCU", board=[p2_sl], hand=[], deck=p2_deck, retired=[])

    gs = GameState(p1=p1, p2=p2, turn_player=p1, phase="start", turn_number=1, rng=rng)

    # draw opening hands: 6 each
    for _ in range(6):
        if p1.deck:
            p1.hand.append(p1.deck.pop())
        if p2.deck:
            p2.hand.append(p2.deck.pop())

    # who goes first
    first = args.first if args.first != "random" else rng.choice(["p1", "p2"])
    gs.turn_player = p1 if first == "p1" else p2
    gs.turn_number = 1
    start_of_turn(gs)

    ui = select_ui(args.ui)
    print("GSG engine ready. Decks loaded. SLs on board. (Type 'help' to see commands.)")

    ai_sel = (args.ai or os.environ.get("GSG_AI") or "").strip().lower()
    ai_p1 = ai_sel in ("p1", "both")
    ai_p2 = ai_sel in ("p2", "both")
    auto = bool(args.auto or os.environ.get("GSG_AUTO"))
    if auto:
        print("Auto mode enabled")

    # Set AI flags on game state so UI can act on them
    gs.p1.is_ai = ai_p1
    gs.p2.is_ai = ai_p2

    # Friendly markers (useful for tests and smoke runs)
    if ai_p1:
        print(f"AI enabled for: {gs.p1.faction.upper()}")
    if ai_p2:
        print(f"AI enabled for: {gs.p2.faction.upper()}")

    ui.run_loop(gs)


if __name__ == "__main__":
    main()
