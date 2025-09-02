from __future__ import annotations
import re
from typing import List, Tuple, Optional
from ..models import GameState, Card, Rank

WHITE = "\033[37m"
CYAN = "\033[36m"
GREY = "\033[90m"
RED = "\033[31m"
YELLOW = "\033[33m"
RST = "\033[0m"

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

def cost_str(card: Card) -> str:
    w = int(getattr(card, "deploy_wind", 0) or 0)
    g = int(getattr(card, "deploy_gear", 0) or 0)
    m = int(getattr(card, "deploy_meat", 0) or 0)
    # white numbers; colored icons
    return f"{WHITE}{w}{RST}{CYAN}⟲{RST} {WHITE}{g}{RST}{GREY}⛭{RST} {WHITE}{m}{RST}{RED}⚈{RST}"

def name_with_icons(card: Card) -> str:
    new_flag = getattr(card, "new_this_turn", False) or getattr(card, "new_in_hand", False)
    new_tag = f"{YELLOW} ✨{RST}" if new_flag else ""
    return f"{card.name}{rank_icon(card)}{prop_icons(card)}{new_tag}"

class TerminalUI:
    HELP = (
        "commands: help | quit(q) | end(e) | "
        "deploy(d) <i> | deploym(dm) <i> | use(u) <src> <abil> [tgt] | dN (manual) | ddN (auto)"
    )

    def render(self, gs: GameState):
        print("\033[2J\033[H", end="")
        p1, p2 = gs.p1, gs.p2

        def row(c, i):
            abil = ", ".join(f"{j}:{a.name}" for j, a in enumerate(getattr(c, "abilities", []))) or "-"
            wind = getattr(c, "wind", 0)
            return f"[{i:>2}] {name_with_icons(c):<24} | wind={wind} | {abil}"

        print(f"P1 {p1.name}: board={len(p1.board)} hand={len(p1.hand)}   |   P2 {p2.name}: board={len(p2.board)} hand={len(p2.hand)}")
        print(f"Board P1 ({p1.name})")
        for i, c in enumerate(p1.board):
            print(row(c, i))
        print(f"\nBoard P2 ({p2.name})")
        for i, c in enumerate(p2.board):
            print(row(c, i))
        human = gs.turn_player
        print(f"\n{human.name} hand ({len(human.hand)}):")
        print("   #  Name                          Cost")
        for i, c in enumerate(human.hand):
            print(f"  {i:>2}  {name_with_icons(c):<28} {cost_str(c)}")

    def _chooser(self, gs: GameState):
        def chooser(eligible: List[Tuple[int, object, int]], total_cost: int) -> Optional[List[Tuple[int, int]]]:
            print("Eligible payers (index:name wind -> capacity):")
            for idx, card, cap in eligible:
                print(f"  {idx}: {card.name} {getattr(card, 'wind', 0)} -> +{cap}")
            print(f"Total cost: {total_cost}")
            print("Enter allocations as comma list: idx[:amt], e.g. '0:2,1:1,0:1'. Default amt=1.")
            line = input("pay> ").strip()
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
                print("bad input"); return None
            return plan
        return chooser

    def run_loop(self, gs: GameState):
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli
        print(self.HELP)
        try:
            while True:
                self.render(gs)
                try:
                    line = input("> ").strip()
                except EOFError:
                    print("\nBye."); break
                if not line: continue

                # Shorthand: dN = manual, ddN = auto (also spaced forms)
                m = re.fullmatch(r"d(\d+)", line.lower())
                if m:
                    idx = int(m.group(1))
                    ok = deploy_from_hand(gs, gs.turn_player, idx, chooser=self._chooser(gs))
                    if not ok: print("deploy failed (manual)")
                    continue
                m = re.fullmatch(r"dd(\d+)", line.lower())
                if m:
                    idx = int(m.group(1))
                    ok = deploy_from_hand(gs, gs.turn_player, idx)
                    if not ok: print("deploy failed")
                    continue
                parts = line.lower().split()
                if len(parts) == 2 and parts[0] == "dd" and parts[1].isdigit():
                    idx = int(parts[1]); ok = deploy_from_hand(gs, gs.turn_player, idx)
                    if not ok: print("deploy failed"); continue
                if len(parts) == 2 and parts[0] == "d" and parts[1].isdigit():
                    idx = int(parts[1]); ok = deploy_from_hand(gs, gs.turn_player, idx, chooser=self._chooser(gs))
                    if not ok: print("deploy failed (manual)"); continue

                cmd, *rest = parts
                if cmd in {"quit", "q", "exit"}: break
                if cmd in {"help", "?"}: print(self.HELP); continue
                if cmd in {"end", "e"}: end_of_turn(gs); continue
                if cmd in {"deploy", "d"}:
                    if not rest: print("usage: deploy <hand_idx>"); continue
                    try: i = int(rest[0])
                    except ValueError: print("hand_idx must be int"); continue
                    ok = deploy_from_hand(gs, gs.turn_player, i, chooser=self._chooser(gs))
                    if not ok: print("deploy failed (manual)"); continue
                if cmd in {"deploym", "dm"}:
                    if not rest: print("usage: deploym <hand_idx>"); continue
                    try: i = int(rest[0])
                    except ValueError: print("hand_idx must be int"); continue
                    ok = deploy_from_hand(gs, gs.turn_player, i, chooser=self._chooser(gs))
                    if not ok: print("deploy failed (manual)")
                    continue
                if cmd in {"use", "u"}:
                    if len(rest) < 2: print("usage: use <src_idx> <abil_idx> [tgt_idx]"); continue
                    try:
                        s = int(rest[0]); a = int(rest[1]); t = int(rest[2]) if len(rest) > 2 else None
                    except ValueError:
                        print("indices must be ints"); continue
                    ok = use_ability_cli(gs, gs.turn_player, s, a, t)
                    if not ok: print("ability failed"); continue
                print("unknown cmd; type help")
        except KeyboardInterrupt:
            print("\nExiting game.")
