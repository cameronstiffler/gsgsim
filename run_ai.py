#!/usr/bin/env python
from __future__ import annotations
import argparse, sys

def get_init_game():
    # Prefer engine.init_game (library), fall back to gsg_sim.init_game if present
    try:
        from gsgsim.engine import init_game  # type: ignore
        return init_game
    except Exception:
        pass
    try:
        from gsg_sim import init_game  # type: ignore
        return init_game
    except Exception:
        print("Could not locate init_game in gsgsim.engine or gsg_sim.", file=sys.stderr)
        sys.exit(2)

def get_ui(name: str):
    if name == "rich":
        from gsgsim.ui.rich_ui import RichUI
        return RichUI()
    elif name in ("term", "terminal"):
        from gsgsim.ui.terminal import TerminalUI
        return TerminalUI()
    else:
        print(f"Unknown UI '{name}'. Use 'rich' or 'term'.", file=sys.stderr)
        sys.exit(2)

def main(argv=None):
    p = argparse.ArgumentParser(description="GSGSim launcher with optional AI player.")
    p.add_argument("--ui", default="rich", choices=["rich", "term"], help="UI to use")
    p.add_argument("--ai", default=None, choices=["p1", "p2"], help="Make p1 or p2 controlled by AI")
    args = p.parse_args(argv)

    init_game = get_init_game()
    gs = init_game()

    if args.ai:
        target = args.ai.lower()
        if target == "p1":
            gs.p1.controller = "ai"
        else:
            gs.p2.controller = "ai"

    ui = get_ui(args.ui)
    ui.run_loop(gs)

if __name__ == "__main__":
    main()
