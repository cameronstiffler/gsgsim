# ui/rich_ui.py
from __future__ import annotations
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
except Exception as e:  # guard: if rich missing, this module should not be imported
    raise

from gsg_sim import GameState, Player, Rank, can_target_card, use_ability

class RichUI:
    def __init__(self) -> None:
        self.console = Console()

    def render_board(self, gs: GameState) -> None:
        lay = Layout()
        lay.split_row(Layout(name="p1"), Layout(name="p2"))
        lay["p1"].update(self._player_panel(gs.p1, "P1"))
        lay["p2"].update(self._player_panel(gs.p2, "P2"))
        self.console.print(lay)

    def _player_panel(self, p: Player, label: str) -> Panel:
        t = Table(title=f"Board {label}: {p.name}")
        t.add_column("#", justify="right", style="cyan")
        t.add_column("Name", style="bold")
        t.add_column("Rank")
        t.add_column("Wind")
        t.add_column("Statuses")
        if not p.board:
            t.add_row("-", "(empty)", "-", "-", "-")
        else:
            for i, c in enumerate(p.board):
                sts = ",".join(sorted((c.statuses or {}).keys())) or "-"
                t.add_row(str(i), c.name, c.rank.name, str(c.wind), sts)
        return Panel(t, border_style="magenta")

    def render_hand(self, p: Player, label: str) -> None:
        t = Table(title=f"{label} hand ({len(p.hand)})")
        t.add_column("#", justify="right", style="cyan")
        t.add_column("Name"); t.add_column("Rank")
        if not p.hand:
            t.add_row("-", "(empty)", "-")
        else:
            for i, c in enumerate(p.hand):
                t.add_row(str(i), c.name, c.rank.name)
        self.console.print(t)

    def info(self, msg: str) -> None: self.console.print(f"[green]{msg}[/green]")
    def error(self, msg: str) -> None: self.console.print(f"[red]{msg}[/red]")

    # same command handlers as CLI, but echo with Rich
    def _deploy_from_hand(self, gs: GameState, player: Player, hand_idx: int) -> bool:
        if not (0 <= hand_idx < len(player.hand)): self.error("Invalid hand index."); return False
        card = player.hand[hand_idx]
        if card.rank != Rank.SL and not any(c.rank == Rank.SL for c in player.board):
            self.error("Must deploy Squad Leader first."); return False
        player.board.append(card); player.hand.pop(hand_idx)
        self.info(f"Deployed: {card.name}"); return True

    def _use_ability(self, gs: GameState, player: Player, src_idx: int, a_idx: int, tgt_idx: int | None) -> bool:
        enemy = gs.p2 if player is gs.p1 else gs.p1
        if not (0 <= src_idx < len(player.board)): self.error("Invalid source index."); return False
        src = player.board[src_idx]
        try: ability = src.abilities[a_idx]
        except Exception: self.error("Invalid ability index."); return False
        target = None
        if tgt_idx is not None:
            if not (0 <= tgt_idx < len(enemy.board)): self.error("Invalid target index."); return False
            target = enemy.board[tgt_idx]
            if not can_target_card(gs, src, target, player, enemy, ability):
                self.error("Illegal target."); return False
        ok = use_ability(gs, player, src_idx, a_idx, tgt_idx if target is not None else None)
        self.info("Ability resolved." if ok else "Ability failed.")
        return ok

    def run_loop(self, gs: GameState) -> None:
        self.info("[bold]Rich UI[/bold] ready. Type 'help', 'quit' to exit.")
        while True:
            try:
                line = self.console.input("[bold cyan]> [/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                break
            if not line: continue
            parts = line.split(); cmd = parts[0].lower()
            if cmd in ("quit", "exit"): break
            if cmd == "help":
                self.console.print(
                    "[yellow]Commands[/yellow]: show | hand p1|p2 | deploy p1|p2 HAND_IDX | use p1|p2 SRC_IDX ABIL_IDX [TGT_IDX] | end | quit"
                ); continue
            if cmd == "show": self.render_board(gs); continue
            if cmd == "hand" and len(parts) >= 2:
                who = gs.p1 if parts[1].lower() == "p1" else gs.p2
                self.render_hand(who, "P1" if who is gs.p1 else "P2"); continue
            if cmd == "deploy" and len(parts) >= 3:
                who = gs.p1 if parts[1].lower() == "p1" else gs.p2
                try: idx = int(parts[2])
                except ValueError: self.error("HAND_IDX must be integer."); continue
                self._deploy_from_hand(gs, who, idx); continue
            if cmd == "use" and len(parts) >= 4:
                who = gs.p1 if parts[1].lower() == "p1" else gs.p2
                try:
                    sidx = int(parts[2]); aidx = int(parts[3])
                    tidx = int(parts[4]) if len(parts) >= 5 else None
                except ValueError: self.error("Indexes must be integers."); continue
                self._use_ability(gs, who, sidx, aidx, tidx); continue
            if cmd == "end":
                self.info("Turn end placeholder."); continue
            self.error("Unknown command. Type 'help'.")