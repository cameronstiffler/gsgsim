from __future__ import annotations
import re
from typing import List, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from ..models import GameState, Card, Rank

# Try to activate flag shim (✨ for freshly drawn/deployed)
try:
    from .. import engine_flagshim  # noqa: F401
except Exception:
    pass

def rank_icon(card: Card) -> str:
    r = getattr(card, "rank", None)
    if r == Rank.SL: return " ⭐"
    if r == Rank.SG: return " 🔶"
    if r == Rank.TITAN or r == getattr(Rank, "TN", None): return " 💪"
    return ""

def prop_icons(card: Card) -> str:
    # Prefer properties; gracefully fall back to attrs/statuses so no JSON edit is required
    props = getattr(card, "properties", {}) or {}
    statuses = getattr(card, "statuses", {}) or {}
    resist = props.get("resist")
    if resist is None:
        resist = bool(getattr(card, "resist", False)) or ("resist" in statuses)
    no_unwind = props.get("no_unwind")
    if no_unwind is None:
        no_unwind = bool(getattr(card, "no_unwind", False)) or ("no_unwind" in statuses)
    out = []
    if resist: out.append(" ✋")
    if no_unwind: out.append(" 🚫")
    return "".join(out)

def cost_text(card: Card) -> Text:
    w = int(getattr(card, "deploy_wind", 0) or 0)
    g = int(getattr(card, "deploy_gear", 0) or 0)
    m = int(getattr(card, "deploy_meat", 0) or 0)
    t = Text()
    # white numbers; colored icons
    t.append(str(w), style="white"); t.append("⟲", style="cyan"); t.append(" ")
    t.append(str(g), style="white"); t.append("⛭", style="bright_black"); t.append(" ")
    t.append(str(m), style="white"); t.append("⚈", style="red")
    return t

def name_with_icons(card: Card) -> Text:
    t = Text(card.name)
    # rank + properties
    for piece in (rank_icon(card), prop_icons(card)):
        if piece:
            t.append(piece)
    # ✨ for freshly deployed or freshly drawn
    if getattr(card, "new_this_turn", False) or getattr(card, "new_in_hand", False):
        t.append(" ✨", style=Style(color="yellow"))
    return t

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
                rank_val = getattr(c, "rank", None)
                rank_str = rank_val.name if hasattr(rank_val, "name") else (str(rank_val) if rank_val is not None else "?")
                t.add_row(str(i), name_with_icons(c), rank_str, str(getattr(c, "wind", 0)), abil)
            return t

        p1, p2 = gs.p1, gs.p2
        self.console.print(f"[bold]P1 {p1.name}[/bold]: board={len(p1.board)} hand={len(p1.hand)}"
                           f"   |   [bold]P2 {p2.name}[/bold]: board={len(p2.board)} hand={len(p2.hand)}")
        self.console.print(board_table(f"Board P1: {p1.name}", p1))
        self.console.print(board_table(f"Board P2: {p2.name}", p2))

        h = Table(title=f"{gs.turn_player.name} hand ({len(gs.turn_player.hand)})",
                  expand=False, pad_edge=False, padding=(0, 1), show_edge=True)
        h.add_column("#", justify="right", no_wrap=True)
        h.add_column("Name", no_wrap=True)
        h.add_column("Cost", no_wrap=True)
        for i, c in enumerate(gs.turn_player.hand):
            h.add_row(str(i), name_with_icons(c), cost_text(c))
        self.console.print(h)

    def _chooser(self, gs: GameState):
        def chooser(eligible: List[Tuple[int, object, int]], total_cost: int) -> Optional[List[Tuple[int, int]]]:
            table = Table(title=f"Choose payers (cost {total_cost})", expand=False)
            table.add_column("Idx", justify="right"); table.add_column("Name"); table.add_column("Wind"); table.add_column("Cap")
            for idx, card, cap in eligible:
                table.add_row(str(idx), card.name, str(getattr(card, "wind", 0)), str(cap))
            self.console.print(table)
            self.console.print("Enter allocations like: 0:2,1:1,0:1 (default amt=1) or empty to cancel.")
            try:
                line = self.console.input("pay> ").strip()
            except (KeyboardInterrupt, EOFError):
                return None
            if not line: return None
            plan: List[Tuple[int, int]] = []
            try:
                parts = [p.strip() for p in line.split(',') if p.strip()]
                for tok in parts:
                    if ':' in tok:
                        i_s, a_s = tok.split(':', 1); idx = int(i_s); amt = int(a_s)
                    else:
                        idx = int(tok); amt = 1
                    plan.append((idx, amt))
            except Exception:
                self.console.print("[red]Bad input[/red]"); return None
            return plan
        return chooser

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli
        self.console.print("[bold]Type 'help' for commands. 'quit' to exit.[/bold]")
        try:
            while True:
                self.render(gs)
                try:
                    line = self.console.input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    self.console.print("\nExiting game."); break
                if not line: continue

                # Shorthand: dN = manual, ddN = auto (also spaced forms)
                m = re.fullmatch(r"d(\d+)", line.lower())
                if m:
                    idx = int(m.group(1))
                    ok = deploy_from_hand(gs, gs.turn_player, idx, chooser=self._chooser(gs))
                    if not ok: self.console.print("[red]deploy failed (manual)[/red]")
                    continue
                m = re.fullmatch(r"dd(\d+)", line.lower())
                if m:
                    idx = int(m.group(1))
                    ok = deploy_from_hand(gs, gs.turn_player, idx)
                    if not ok: self.console.print("[red]deploy failed[/red]")
                    continue
                parts = line.lower().split()
                if len(parts) == 2 and parts[0] == "dd" and parts[1].isdigit():
                    idx = int(parts[1]); ok = deploy_from_hand(gs, gs.turn_player, idx)
                    if not ok: self.console.print("[red]deploy failed[/red]"); continue
                if len(parts) == 2 and parts[0] == "d" and parts[1].isdigit():
                    idx = int(parts[1]); ok = deploy_from_hand(gs, gs.turn_player, idx, chooser=self._chooser(gs))
                    if not ok: self.console.print("[red]deploy failed (manual)[/red]"); continue

                cmd, *rest = parts
                if cmd in {"quit", "q", "exit"}: break
                if cmd in {"help", "?"}:
                    self.console.print("commands: help | quit(q) | end(e) | deploy(d) <i> | deploym(dm) <i> | use(u) <src> <abil> [tgt] | dN (manual) | ddN (auto)")
                    continue
                if cmd in {"end", "e"}: end_of_turn(gs); continue
                if cmd in {"deploy", "d"}:
                    if not rest: self.console.print("usage: deploy <hand_idx>"); continue
                    try: i = int(rest[0])
                    except ValueError: self.console.print("hand_idx must be int"); continue
                    ok = deploy_from_hand(gs, gs.turn_player, i, chooser=self._chooser(gs))
                    if not ok: self.console.print("[red]deploy failed (manual)[/red]")
                    continue
                if cmd in {"deploym", "dm"}:
                    if not rest: self.console.print("usage: deploym <hand_idx>"); continue
                    try: i = int(rest[0])
                    except ValueError: self.console.print("hand_idx must be int"); continue
                    ok = deploy_from_hand(gs, gs.turn_player, i, chooser=self._chooser(gs))
                    if not ok: self.console.print("[red]deploy failed (manual)[/red]")
                    continue
                if cmd in {"use", "u"}:
                    if len(rest) < 2: self.console.print("usage: use <src_idx> <abil_idx> [tgt_idx]"); continue
                    try:
                        s = int(rest[0]); a = int(rest[1]); t = int(rest[2]) if len(rest) > 2 else None
                    except ValueError:
                        self.console.print("indices must be ints"); continue
                    ok = use_ability_cli(gs, gs.turn_player, s, a, t)
                    if not ok: self.console.print("[red]ability failed[/red]")
                    continue
                self.console.print("unknown cmd; type help")
        except KeyboardInterrupt:
            self.console.print("\nExiting game.")
