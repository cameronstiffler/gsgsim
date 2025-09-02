from __future__ import annotations
import re
from typing import List, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from ..models import GameState, Card, Rank

try:
    from .. import engine_rule_shim
except Exception:
    engine_rule_shim = None

def rank_icon(card: Card) -> str:
    r = getattr(card, "rank", None)
    if r == Rank.SL: return " ⭐"
    if r == Rank.SG: return " 🔶"
    if r == Rank.TITAN or r == getattr(Rank, "TN", None): return " 💪"
    return ""

def prop_icons(card: Card) -> str:
    props = getattr(card, "properties", {}) or {}
    statuses = getattr(card, "statuses", {}) or {}
    out = []
    if props.get("resist") or "resist" in statuses:
        out.append(" ✋")
    if props.get("no_unwind") or "no_unwind" in statuses:
        out.append(" 🚫")
    return "".join(out)

def cost_text(card: Card) -> Text:
    w = int(getattr(card, "deploy_wind", 0) or 0)
    g = int(getattr(card, "deploy_gear", 0) or 0)
    m = int(getattr(card, "deploy_meat", 0) or 0)
    t = Text()
    t.append(str(w), style="white"); t.append("⟲", style="cyan"); t.append(" ")
    t.append(str(g), style="white"); t.append("⛭", style="bright_black"); t.append(" ")
    t.append(str(m), style="white"); t.append("⚈", style="red")
    return t

def ability_lines(card: Card) -> List[Text]:
    out = []
    for j, a in enumerate(getattr(card, "abilities", []) or []):
        line = Text(f"{j}: ")
        nm = getattr(a, "name", None) or "ABILITY"
        line.append(nm)
        w = int(getattr(a, "wind_cost", 0) or 0)
        g = int(getattr(a, "gear_cost", 0) or 0)
        m = int(getattr(a, "meat_cost", 0) or 0)
        if any((w,g,m)):
            line.append("  ")
            line.append(str(w), style="white"); line.append("⟲", style="cyan"); line.append(" ")
            line.append(str(g), style="white"); line.append("⛭", style="bright_black"); line.append(" ")
            line.append(str(m), style="white"); line.append("⚈", style="red")
        desc = getattr(a, "text", None) or getattr(a, "description", None)
        if desc:
            line.append("  — "); line.append(desc)
        out.append(line)
    if not out:
        out.append(Text("-"))
    return out

def name_with_icons(card: Card) -> Text:
    t = Text(card.name)
    t.append(rank_icon(card))
    t.append(prop_icons(card))
    if getattr(card, "new_this_turn", False) or getattr(card, "new_in_hand", False):
        t.append(" ✨", style=Style(color="yellow"))
    return t

class RichUI:
    def __init__(self):
        self.console = Console()

    def _check_game_over(self, gs: GameState) -> bool:
        if engine_rule_shim:
            winner = engine_rule_shim.check_sl_loss(gs)
            if winner:
                self.console.print(f"[bold red]Game over! Winner: {winner}[/bold red]")
                return True
        return False

    def render(self, gs: GameState):
        def board_table(title, p):
            t = Table(title=title)
            t.add_column("#", justify="right")
            t.add_column("Name")
            t.add_column("Wind", justify="right")
            t.add_column("Abilities")
            for i, c in enumerate(p.board):
                abil_text = Text("\n").join(ability_lines(c))
                t.add_row(str(i), name_with_icons(c), str(getattr(c,"wind",0)), abil_text)
            return t

        self.console.print(board_table(f"Board {gs.p1.name}", gs.p1))
        self.console.print(board_table(f"Board {gs.p2.name}", gs.p2))
        h = Table(title=f"{gs.turn_player.name} hand ({len(gs.turn_player.hand)})")
        h.add_column("#", justify="right"); h.add_column("Name"); h.add_column("Cost")
        for i,c in enumerate(gs.turn_player.hand):
            h.add_row(str(i), name_with_icons(c), cost_text(c))
        self.console.print(h)

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli
        while True:
            if self._check_game_over(gs): break
            self.render(gs)
            try: line = self.console.input("> ").strip()
            except: break
            if line in ("quit","q"): break
            if line in ("end","e"): end_of_turn(gs); continue
            m = re.fullmatch(r"d(\d+)", line)
            if m: deploy_from_hand(gs, gs.turn_player, int(m.group(1))); continue
            m = re.fullmatch(r"dd(\d+)", line)
            if m: deploy_from_hand(gs, gs.turn_player, int(m.group(1))); continue
