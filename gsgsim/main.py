# === IMPORT SENTRY ===
from __future__ import annotations

import argparse
import os
import random

from .engine import select_ui, start_of_turn
from .loader import build_cards, find_squad_leader, load_deck_json
from .models import GameState, Player


def main():
    # CLI

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ui", choices=["cli", "rich"], default=os.environ.get("GSG_UI", "cli"))
    parser.add_argument("--first", choices=["random", "p1", "p2"], default=os.environ.get("GSG_FIRST", "random"))
    parser.add_argument("--ai", choices=["none", "p1", "p2", "both"], default=os.environ.get("GSG_AI", "none"))
    parser.add_argument("--auto", action="store_true", default=False)
    parser.add_argument("--seed", type=int, default=os.environ.get("GSG_SEED", None))
    args, _ = parser.parse_known_args()

    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    # Load decks
    narc = load_deck_json("narc_deck.json")
    pcu = load_deck_json("pcu_deck.json")
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
    ui.run_loop(gs, ai_p1=ai_p1, ai_p2=ai_p2, auto=auto)


if __name__ == "__main__":
    main()
