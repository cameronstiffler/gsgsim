from __future__ import annotations

import re

from rich.console import Console
from rich.table import Table

from ..models import Card, GameState

try:
    from .. import engine_rule_shim
except Exception:
    engine_rule_shim = None


def rank_icon(card: Card) -> str:
    r = getattr(card, "rank", None)
    if isinstance(r, str):
        return "⭐" if r.upper() == "SL" else "BG"
    if hasattr(r, "name"):
        return "⭐" if str(r.name).upper() == "SL" else str(r.name)
    return "?"


class RichUI:
    def __init__(self) -> None:
        self.console = Console()

    def _check_game_over(self, gs: GameState) -> bool:
        if engine_rule_shim and hasattr(engine_rule_shim, "check_sl_loss"):
            loser = engine_rule_shim.check_sl_loss(gs)
            if loser is not None:
                winner = "P1" if loser == "P2" else "P2"
                self.console.print(f"[bold]Game over! Winner: {winner}[/bold]")
                return True
        return False

    def render(self, gs: GameState) -> None:
        c = self.console
        # Header
        c.print(f"Turn {gs.turn_number} | Player: {'P1' if gs.turn_player is gs.p1 else 'P2'}")

        # Board view (both sides)
        def board_table(title: str, player) -> Table:
            t = Table(title=title)
            t.add_column("#", justify="right", style="cyan")
            t.add_column("Name")
            t.add_column("Rank")
            t.add_column("Wind", justify="right")
            t.add_column("Abilities")
            for i, card in enumerate(getattr(player, "board", [])):
                abil = getattr(card, "abilities", [])
                abil_txt = ", ".join(f"{idx}:{name}" for idx, name in enumerate(abil)) if abil else "-"
                t.add_row(
                    str(i),
                    getattr(card, "name", "?"),
                    rank_icon(card),
                    str(getattr(card, "wind", 0)),
                    abil_txt,
                )
            return t

        c.print(board_table("Board P1", gs.p1))
        c.print(board_table("Board P2", gs.p2))

        # Hand for current and opponent (like your previous UI)
        def hand_table(title: str, player) -> Table:
            t = Table(title=f"{title} hand ({len(player.hand)})")
            t.add_column("#", justify="right", style="cyan")
            t.add_column("Name")
            t.add_column("Cost")
            for i, card in enumerate(player.hand):
                cost = f"{getattr(card, 'deploy_wind', 0)}⟲ {getattr(card, 'deploy_gear', 0)}⛭ {getattr(card, 'deploy_meat', 0)}⚈"
                t.add_row(str(i), getattr(card, "name", "?"), cost)
            return t

        if gs.turn_player is gs.p1:
            c.print(hand_table("P1", gs.p1))
        else:
            c.print(hand_table("P2", gs.p2))

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli

        while True:
            if self._check_game_over(gs):
                break
            self.render(gs)
            try:
                line = self.console.input("> ").strip()
            except Exception:
                break
            if line in ("quit", "q"):
                break
            if line in ("end", "e"):
                end_of_turn(gs)
                continue
            m = re.fullmatch(r"d(\d+)", line)
            if m:
                deploy_from_hand(gs, gs.turn_player, int(m.group(1)))
                continue
            m = re.fullmatch(r"dd(\d+)", line)
            if m:
                # same as dN for now; engine's auto planner refuses lethal SL payments
                deploy_from_hand(gs, gs.turn_player, int(m.group(1)))
                continue
            m = re.fullmatch(r"u\s+(\d+)\s+(\d+)", line)
            if m:
                src = int(m.group(1))
                abil = int(m.group(2))
                use_ability_cli(gs, src, abil, m.group(3))
                continue

            self.console.print("commands: help | quit(q) | end(e) | dN | ddN | u <src> <abil> [p1|p2:idx[,idx]|all]")
