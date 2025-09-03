from __future__ import annotations

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


def cost_str(card):
    return f"{getattr(card, 'deploy_wind', 0)}⟲ {getattr(card, 'deploy_gear', 0)}⛭ {getattr(card, 'deploy_meat', 0)}⚈"


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
        c.print(f"Turn {gs.turn_number} | Player: {'P1' if gs.turn_player is gs.p1 else 'P2'}")

        def board_table(title: str, player) -> Table:
            t = Table(title=title)
            t.add_column("#", justify="right", style="cyan")
            t.add_column("Name")
            t.add_column("Rank")
            t.add_column("Wind", justify="right")
            t.add_column("Abilities")
            for i, card in enumerate(getattr(player, "board", [])):
                abil = getattr(card, "abilities", [])
                # allow abilities to be strings or objects with .name
                names = []
                for idx, a in enumerate(abil or []):
                    n = getattr(a, "name", a)
                    names.append(f"{idx}:{n}")
                abil_txt = ", ".join(names) if names else "-"
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

        def hand_table(title: str, player) -> Table:
            t = Table(title=f"{title} hand ({len(player.hand)})")
            t.add_column("#", justify="right", style="cyan")
            t.add_column("Name")
            t.add_column("Cost")
            for i, card in enumerate(player.hand):
                cost = cost_str(card)
                t.add_row(str(i), getattr(card, "name", "?"), cost)
            return t

        if gs.turn_player is gs.p1:
            c.print(hand_table("P1", gs.p1))
        else:
            c.print(hand_table("P2", gs.p2))

    def run_loop(self, gs: GameState):
        from ..engine import end_of_turn, use_ability_cli

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

            parts = line.split()

            # ability use: u SRC ABIL [TARGETSPEC]
            if len(parts) >= 3 and parts[0] == "u" and parts[1].isdigit() and parts[2].isdigit():
                src = int(parts[1])
                abil = int(parts[2])
                spec = parts[3] if len(parts) >= 4 else None
                use_ability_cli(gs, src, abil, spec)
                continue

            # manual wind payment: pay AMOUNT p1|p2:idx[xN][,idx[xM] ...] [force]
            if parts and parts[0] == "pay" and len(parts) >= 3 and parts[1].isdigit():
                amount = int(parts[1])
                spec = " ".join(parts[2:])
                from ..engine import pay_cli

                pay_cli(gs, amount, spec)
                continue

            # minimal AI helper
            if parts and parts[0] == "ai":
                from ..ai import ai_take_turn

                ai_take_turn(gs)
                continue

            self.console.print("commands: help | quit(q) | end(e) | dN | ddN | " "u <src> <abil> [p1|p2:idx[,idx]|all] | " "pay <amount> p1|p2:idxxN[,idxxM] [force] | ai")
