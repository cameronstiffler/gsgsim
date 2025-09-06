from __future__ import annotations

import re
from typing import List

from ..models import Card
from ..models import GameState
from ..models import Rank

WHITE = "\033[37m"
CYAN = "\033[36m"
GREY = "\033[90m"
RED = "\033[31m"
YELLOW = "\033[33m"
RST = "\033[0m"

try:
    from .. import engine_rule_shim
except Exception:
    engine_rule_shim = None


def rank_icon(c):
    r = getattr(c, "rank", None)
    return " ⭐" if r == Rank.SL else " 🔶" if r == Rank.SG else " 💪" if r == Rank.TITAN else ""


def prop_icons(c):
    props = getattr(c, "properties", {}) or {}
    out = []
    if props.get("resist"):
        out.append(" ✋")
    if props.get("no_unwind"):
        out.append(" 🚫")
    return "".join(out)


def cost_str(c):
    w = int(getattr(c, "deploy_wind", 0) or 0)
    g = int(getattr(c, "deploy_gear", 0) or 0)
    m = int(getattr(c, "deploy_meat", 0) or 0)
    return f"{WHITE}{w}{RST}{CYAN}⟲{RST} {WHITE}{g}{RST}{GREY}⛭{RST} {WHITE}{m}{RST}{RED}⚈{RST}"


def ability_lines(c: Card) -> List[str]:
    out = []
    for j, a in enumerate(getattr(c, "abilities", []) or []):
        nm = getattr(a, "name", "ABILITY")
        w = int(getattr(a, "wind_cost", 0) or 0)
        g = int(getattr(a, "gear_cost", 0) or 0)
        m = int(getattr(a, "meat_cost", 0) or 0)
        cost = f"{WHITE}{w}{RST}{CYAN}⟲{RST} {WHITE}{g}{RST}{GREY}⛭{RST} {WHITE}{m}{RST}{RED}⚈{RST}" if any((w, g, m)) else ""
        desc = getattr(a, "text", None) or ""
        line = f"{j}: {nm}"
        if cost:
            line += f"  {cost}"
        if desc:
            line += f"  — {desc}"
        out.append(line)
    return out or ["-"]


def name_with_icons(c):
    new_flag = getattr(c, "new_this_turn", False) or getattr(c, "new_in_hand", False)
    return f"{c.name}{rank_icon(c)}{prop_icons(c)}{YELLOW+' ✨'+RST if new_flag else ''}"


class TerminalUI:
    def render(self, gs: GameState):
        print("\033[2J\033[H", end="")
        for label, p in [(f"Board {gs.p1.name}", gs.p1), (f"Board {gs.p2.name}", gs.p2)]:
            print(label)
            for i, c in enumerate(p.board):
                lines = ability_lines(c)
                print(f"[{i}] {name_with_icons(c)} | wind={getattr(c, 'wind', 0)} | {lines[0]}")
                for extra in lines[1:]:
                    print(f"    ↳ {extra}")
        print(f"\n{gs.turn_player.name} hand:")
        for i, c in enumerate(gs.turn_player.hand):
            print(f"[{i}] {name_with_icons(c):<20} {cost_str(c)}")

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand
        from ..engine import end_of_turn

        while True:
            if engine_rule_shim and engine_rule_shim.check_sl_loss(gs):
                break
            self.render(gs)
            try:
                line = input("> ").strip()
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
                deploy_from_hand(gs, gs.turn_player, int(m.group(1)))
                continue
