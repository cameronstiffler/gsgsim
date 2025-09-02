from __future__ import annotations
from rich.console import Console
from rich.table import Table
from ..models import GameState

class RichUI:
    def __init__(self):
        self.console = Console()

    def render(self, gs: GameState):
        def board_table(title, p):
            t = Table(title=title, expand=False, pad_edge=False, padding=(0, 1), show_edge=True)
            t.add_column("#", justify="right", no_wrap=True)
            t.add_column("Name", no_wrap=True)
            t.add_column("Rank", no_wrap=True)
            t.add_column("Wind", justify="right", no_wrap=True)
            t.add_column("Abilities")
            for i, c in enumerate(p.board):
                abil = ", ".join(f"{j}:{a.name}" for j, a in enumerate(getattr(c, "abilities", []))) or "-"
                rank = getattr(c, "rank", None)
                rank_str = rank.name if hasattr(rank, "name") else (str(rank) if rank is not None else "?")
                t.add_row(str(i), c.name, rank_str, str(getattr(c, "wind", 0)), abil)
            return t

        p1, p2 = gs.p1, gs.p2
        self.console.print(f"[bold]P1 {p1.name}[/bold]: board={len(p1.board)} hand={len(p1.hand)}   |   "
                           f"[bold]P2 {p2.name}[/bold]: board={len(p2.board)} hand={len(p2.hand)}")
        self.console.print(board_table(f"Board P1: {p1.name}", p1))
        self.console.print(board_table(f"Board P2: {p2.name}", p2))

        h = Table(title=f"{gs.turn_player.name} hand ({len(gs.turn_player.hand)})", expand=False,
                  pad_edge=False, padding=(0, 1), show_edge=True)
        h.add_column("#", justify="right", no_wrap=True)
        h.add_column("Name", no_wrap=True)
        h.add_column("Rank", no_wrap=True)
        for i, c in enumerate(gs.turn_player.hand):
            rank = getattr(c, "rank", None)
            rank_str = rank.name if hasattr(rank, "name") else (str(rank) if rank is not None else "?")
            h.add_row(str(i), c.name, rank_str)
        self.console.print(h)

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli
        self.console.print("[bold]Type 'help' for commands. 'quit' to exit.[/bold]")
        try:
            while True:
                self.render(gs)
                line = self.console.input("> ").strip()
                if not line:
                    continue
                parts = line.split()
                cmd, *rest = parts
                cmd = cmd.lower()
                if cmd in {"quit", "q", "exit"}:
                    break
                if cmd in {"help", "?"}:
                    self.console.print("commands: help | quit(q) | end(e) | deploy(d) <hand_idx> | use(u) <src_idx> <abil_idx> [tgt_idx]")
                    continue
                if cmd in {"end", "e"}:
                    end_of_turn(gs)
                    continue
                if cmd in {"deploy", "d"}:
                    if not rest:
                        self.console.print("usage: deploy <hand_idx>")
                        continue
                    try:
                        i = int(rest[0])
                    except ValueError:
                        self.console.print("hand_idx must be int")
                        continue
                    ok = deploy_from_hand(gs, gs.turn_player, i)
                    if not ok:
                        self.console.print("deploy failed")
                    continue
                if cmd in {"use", "u"}:
                    if len(rest) < 2:
                        self.console.print("usage: use <src_idx> <abil_idx> [tgt_idx]")
                        continue
                    try:
                        s = int(rest[0])
                        a = int(rest[1])
                        t = int(rest[2]) if len(rest) > 2 else None
                    except ValueError:
                        self.console.print("indices must be ints")
                        continue
                    ok = use_ability_cli(gs, gs.turn_player, s, a, t)
                    if not ok:
                        self.console.print("ability failed")
                    continue
                self.console.print("unknown cmd; type help")
        except KeyboardInterrupt:
            self.console.print("\nExiting game.")
