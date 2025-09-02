# === IMPORT SENTRY ===
from __future__ import annotations

from ..models import GameState
from . import rich_ui  # not used here; avoid circular import by local import in select_ui if needed


class TerminalUI:
    HELP = (
        "commands: help | quit(q) | end(e) | "
        "deploy(d) <hand_idx> | use(u) <src_idx> <abil_idx> [tgt_idx]"
    )

    def render(self, gs: GameState):
        print("\033[2J\033[H", end="")
        p1, p2 = gs.p1, gs.p2

        def row(c, i):
            abil = (
                ", ".join(f"{j}:{a.name}" for j, a in enumerate(getattr(c, "abilities", []))) or "-"
            )
            rank = getattr(c, "rank", "?")
            wind = getattr(c, "wind", 0)
            return f"[{i:>2}] {c.name:<20} {rank} | wind={wind} | {abil}"

        print(
            f"P1 {p1.name}: board={len(p1.board)} hand={len(p1.hand)}    |    P2 {p2.name}: board={len(p2.board)} hand={len(p2.hand)}"
        )
        print(f"Board P1 ({p1.name})")
        for i, c in enumerate(p1.board):
            print(row(c, i))
        print(f"\nBoard P2 ({p2.name})")
        for i, c in enumerate(p2.board):
            print(row(c, i))
        human = gs.turn_player
        print(f"\n{human.name} hand ({len(human.hand)}):")
        for i, c in enumerate(human.hand):
            rank = getattr(c, "rank", "?")
            print(f"  {i:>2}: {c.name} [{rank}]")

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli

        print(self.HELP)
        try:
            while True:
                self.render(gs)
                try:
                    line = input("> ").strip()
                except EOFError:
                    print("\nBye.")
                    break
                if not line:
                    continue
                cmd, *rest = line.lower().split()
                if cmd in {"quit", "q", "exit"}:
                    break
                if cmd in {"help", "?"}:
                    print(self.HELP)
                    continue
                if cmd in {"end", "e"}:
                    end_of_turn(gs)
                    continue
                if cmd in {"deploy", "d"}:
                    if not rest:
                        print("usage: deploy <hand_idx>")
                        continue
                    try:
                        i = int(rest[0])
                    except ValueError:
                        print("hand_idx must be int")
                        continue
                    ok = deploy_from_hand(gs, gs.turn_player, i)
                    if not ok:
                        print("deploy failed")
                    continue
                if cmd in {"use", "u"}:
                    if len(rest) < 2:
                        print("usage: use <src_idx> <abil_idx> [tgt_idx]")
                        continue
                    try:
                        s = int(rest[0])
                        a = int(rest[1])
                        t = int(rest[2]) if len(rest) > 2 else None
                    except ValueError:
                        print("indices must be ints")
                        continue
                    ok = use_ability_cli(gs, gs.turn_player, s, a, t)
                    if not ok:
                        print("ability failed")
                    continue
                print("unknown cmd; type help")
        except KeyboardInterrupt:
            print("\nExiting game.")
