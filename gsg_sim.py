from __future__ import annotations
from typing import Callable
import argparse
import json
import os
import random
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Deque, Dict, List, Optional, TextIO, Tuple
from rich.console import Console
from rich.table import Table


class TerminalUI:
    def render(self, gs):
        print("\033[2J\033[H", end="")
        p1, p2 = gs.p1, gs.p2

        def row(c, i):
            abil = ", ".join(f"{j}:{a.name}" for j, a in enumerate(getattr(c, "abilities", [])))
            rank = getattr(c, "rank", "?")
            wind = getattr(c, "wind", 0)
            # Shorten line to <=100 chars
            # Shorten line to <=100 chars
            return f"[{i:>2}] {c.name:<20} {rank} | wind={wind} | {abil}"[:100]

        print(f"Board P1 ({p1.name})")
        for i, c in enumerate(p1.board):
            print(row(c, i))
        print(f"\nBoard P2 ({p2.name})")
        for i, c in enumerate(p2.board):
            print(row(c, i))
        human = gs.turn_player
        print(f"\n{human.name} hand ({len(human.hand)}):")
        for i, c in enumerate(human.hand):
            name = c.name
            rank = getattr(c, "rank", "?")
            line = f"  {i:>2}: {name} [{rank}]"
            # Truncate to 100 chars, but preserve info
            if len(line) > 100:
                print(f"{i:>2}: {name[:60]}... [{rank}]")
            else:
                print(line)

    def run_loop(self, gs):
        HELP = (
            "commands: help | quit(q) | end(e) | deploy(d) <hand_idx> | "
            "use(u) <src_idx> <abil_idx> [tgt_idx]"
        )
        print(HELP)
        while True:
            self.render(gs)
            line = input("> ").strip()
            if not line:
                continue
            cmd, *rest = line.lower().split()
            if cmd in {"quit", "q", "exit"}:
                break
            if cmd in {"help", "?"}:
                print(HELP)
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


class RichUI(TerminalUI):
    def __init__(self):
        if Console is None or Table is None:
            raise RuntimeError("Rich is not available")
        self.console = Console()

    def render(self, gs):
        self.console.clear()

        def board_table(title, p):
            t = Table(title=title, expand=True, pad_edge=False, show_edge=True)
            t.add_column("#", justify="right")
            t.add_column("Name")
            t.add_column("Rank")
            t.add_column("Wind", justify="right")
            t.add_column("Abilities")
            for i, c in enumerate(p.board):
                abil = (
                    ", ".join(f"{j}:{a.name}" for j, a in enumerate(getattr(c, "abilities", [])))
                    or "-"
                )
                t.add_row(
                    str(i), c.name, str(getattr(c, "rank", "?")), str(getattr(c, "wind", 0)), abil
                )
            return t

        self.console.print(board_table(f"Board P1: {gs.p1.name}", gs.p1))
        self.console.print(board_table(f"Board P2: {gs.p2.name}", gs.p2))
        h = Table(
            title=f"{gs.turn_player.name} hand ({len(gs.turn_player.hand)})",
            expand=True,
            pad_edge=False,
            show_edge=True,
        )
        h.add_column("#", justify="right")
        h.add_column("Name")
        h.add_column("Rank")
        for i, c in enumerate(gs.turn_player.hand):
            h.add_row(str(i), c.name, str(getattr(c, "rank", "?")))
        self.console.print(h)

    def run_loop(self, gs):
        self.console.print("Type 'help' for commands. 'quit' to exit.")
        while True:
            self.render(gs)
            line = self.console.input("> ").strip()
            if not line:
                continue
            cmd, *rest = line.lower().split()
            if cmd in {"quit", "q", "exit"}:
                break
            if cmd in {"help", "?"}:
                self.console.print(
                    "commands: help | quit(q) | end(e) | deploy(d) <hand_idx> | use(u) <src_idx> "
                    "<abil_idx> [tgt_idx]"
                )
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


@dataclass
class Status:
    name: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Effect:
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)


class Rank(Enum):
    SL = auto()
    SG = auto()
    BG = auto()
    TITAN = auto()
    TN = TITAN  # alias


@dataclass
class Ability:
    name: str
    cost: Dict[str, int] = field(default_factory=dict)
    effects: List[Effect] = field(default_factory=list)
    passive: bool = False
    idx: int = 0


@dataclass
class Card:
    name: str
    rank: Rank
    faction: str
    traits: set[str] = field(default_factory=set)
    abilities: List[Ability] = field(default_factory=list)
    deploy_wind: int = 0
    deploy_gear: int = 0
    deploy_meat: int = 0
    wind: int = 0
    stars: int = 0
    image_url_mini: str = ""
    image_url_full: str = ""
    statuses: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Player:
    name: str
    board: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    deck: List[Card] = field(default_factory=list)
    retired: List[Card] = field(default_factory=list)
    gear: int = 0
    meat: int = 0
    power: int = 0


# ============================== Utilities: deck & turn ==============================
def record(msg):
    print(msg)


def can_target_card(card, ability):
    return True


def pay_cost(player, cost):
    return True


def is_mechanical(card):
    return "mechanical" in getattr(card, "traits", [])


def is_biological(card):
    return "biological" in getattr(card, "traits", [])


def _print_hand(player, label=None):
    print(f"{label or player.name} hand: {[c.name for c in player.hand]}")


def _print_board(player, label=None):
    print(f"{label or player.name} board: {[c.name for c in player.board]}")


def _use_ability_cli(gs, player, sidx, aidx, tidx=None):
    print(f"Use ability: {player.name} src={sidx} abil={aidx} tgt={tidx}")


def ai_take_turn(gs, player):
    print(f"AI {player.name} turn")


def _is_ai(ai_mode, who_is_p1):
    return False


def _select_ui(kind: str):
    if kind == "rich" and Console is not None:
        return RichUI()
    return TerminalUI()


# --- GameState dataclass ---
@dataclass
class GameState:
    p1: "Player"
    p2: "Player"
    turn_player: "Player"
    phase: str = "start"
    turn_number: int = 1


# --- shuffle_deck helper ---
def shuffle_deck(gs: GameState, player: "Player"):
    random.shuffle(player.deck)


def _opponent_of(gs: "GameState", p: "Player") -> "Player":
    return gs.p2 if p is gs.p1 else gs.p1


def start_of_turn(gs: "GameState") -> None:
    """Start-of-turn upkeep for the active player.
    - Draw 1 card.
    - Reset per-turn ability usage counters on their board.
    - Expire simple start-of-turn statuses if you track them.
    - Set phase to 'main'.
    """


# --- Engine stubs for UI integration ---
def draw(gs, player, n=1):
    """Draw up to n cards from player's deck into hand. Returns actual drawn count."""
    drawn = 0
    for _ in range(max(0, int(n))):
        if not player.deck:
            break
        player.hand.append(player.deck.pop())
        drawn += 1
    return drawn


def deploy_from_hand(gs, player, hand_idx):
    # Minimal stub: move card from hand to board if index valid
    if 0 <= hand_idx < len(player.hand):
        card = player.hand.pop(hand_idx)
        player.board.append(card)
        return True
    return False


def use_ability_cli(gs, player, src_idx, abil_idx, tgt_idx=None):
    # Minimal stub: print action and return True
    print(f"{player.name} uses ability {abil_idx} of card {src_idx} targeting {tgt_idx}")
    return True


def end_of_turn(gs):
    # Minimal stub: rotate turn player and increment turn number
    gs.turn_number += 1
    gs.turn_player = gs.p2 if gs.turn_player is gs.p1 else gs.p1
    gs.phase = "start"
    draw(gs, gs.turn_player, 1)


# --- Engine stubs for UI integration ---


def _is_sl_rank(val) -> bool:
    if isinstance(val, Rank):
        return val == Rank.SL
    if isinstance(val, str):
        return val.strip().lower() in {"sl", "squad leader", "squadleader", "leader"}
    return False


def find_squad_leader(cards: List[Card]) -> Optional[Card]:
    for c in cards:
        if _is_sl_rank(getattr(c, "rank", None)):
            if not isinstance(c.rank, Rank):
                c.rank = Rank.SL
            return c
    for c in cards:
        nm = (getattr(c, "name", "") or "").lower()
        if nm in {"lokar simmons", "grim"} or "leader" in nm:
            c.rank = Rank.SL
            return c
    return None


# ============================== Globals & IO ==============================


@dataclass
class _CommandSource:
    queue: Deque[str] = field(default_factory=deque)
    default_on_interrupt: Optional[str] = None


_CMD_SOURCE: Optional[_CommandSource] = None
console = None  # Removed rich Console; use print instead
_LOG: Optional[TextIO] = None  # debug transcript if --log is provided

AI_NARC: bool = False
AI_PCU: bool = False

# Structured game log (persists to file)
GAME_LOG: List[str] = []
TURN_BUFFER: List[str] = []
LAST_TURN_SUMMARY: Optional[Dict[str, object]] = None
_GLOG: Optional[TextIO] = None
GAMELOG_PATH: Optional[str] = None

HELP_TEXT = """\
Commands:
  deploy HAND_IDX                - deploy card from hand index
  use SRC_IDX ABIL_IDX [TGT_IDX] - use ability
  end                            - end turn
  quit                           - exit
  help                           - show this help
"""


# ============================== Deck I/O ==============================

_WORD_NUMS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _infer_wind_from_text(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"(\d+)\s*wind", text, flags=re.I)
    if m:
        return int(m.group(1))
    word_nums_pattern = "\\b(" + "|".join(_WORD_NUMS.keys()) + ")\\b\\s*wind"
    m = re.search(word_nums_pattern, text, flags=re.I)
    if m:
        return _WORD_NUMS[m.group(1).lower()]
    return 0


def _infer_remove_from_text(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"remove\s+(\d+)\s*wind", text, flags=re.I)
    if m:
        return int(m.group(1))
    word_nums_pattern = "remove\\s+(" + "|".join(_WORD_NUMS.keys()) + ")\\s*wind"
    m = re.search(word_nums_pattern, text, flags=re.I)
    if m:
        return _WORD_NUMS[m.group(1).lower()]
    if re.search(r"\bremove\b.*\bwind\b", text, flags=re.I):
        return 1
    return 0


def _infer_draw_from_text(text: str) -> int:
    if not text:
        return 0
    t = text.lower()
    m = re.search(r"draw\s+(a|an|\d+)\s*card", t)
    if m:
        grp = m.group(1)
        return 1 if grp in {"a", "an"} else int(grp)
    m = re.search(r"draw\s+(" + "|".join(_WORD_NUMS) + r")\s*cards?", t)
    if m:
        return _WORD_NUMS[m.group(1)]
    return 0


def _here(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def parse_cost(tokens: List[str]) -> Tuple[int, int, int, int]:
    w = g = m = p = 0
    for tok in tokens or []:
        tok = str(tok).strip().lower()
        num = ""
        suf = ""
        for ch in tok:
            if ch.isdigit():
                num += ch
            else:
                suf += ch
        n = int(num) if num else 1
        if suf == "w":
            w += n
        elif suf == "g":
            g += n
        elif suf == "m":
            m += n
        elif suf == "p":
            p += n
    return w, g, m, p


def load_deck(path: str) -> List[Card]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    deck: List[Card] = []
    for item in data.get("goons", []):
        try:
            dups = int(item.get("duplicates", 1))
        except Exception:
            dups = 1
        dw, dg, dm, dp = parse_cost(item.get("deploy_cost", []))
        abilities: List[Ability] = []
        for idx, ab in enumerate(item.get("abilities", [])):
            aw, ag, am, ap = parse_cost(ab.get("cost", []))
            text = ab.get("text", "")
            max_uses = None
            if isinstance(ab.get("max_uses_per_turn", None), int):
                max_uses = int(ab.get("max_uses_per_turn"))
            abilities.append(
                Ability(
                    idx=idx,
                    name=ab.get("name", "Ability"),
                    wind_cost=aw,
                    gear_cost=ag,
                    meat_cost=am,
                    power_cost=ap,
                    text=text,
                    passive=(ap > 0 and aw == 0 and ag == 0 and am == 0),
                    inflicts_wind=int(ab.get("inflicts_wind", _infer_wind_from_text(text))),
                    removes_wind=int(ab.get("removes_wind", _infer_remove_from_text(text))),
                    friendly_only=bool(ab.get("friendly_only", _infer_remove_from_text(text) > 0)),
                    draw_cards=int(ab.get("draw_cards", _infer_draw_from_text(text))),
                    max_uses_per_turn=max_uses,
                )
            )
        icons = {s.strip().lower() for s in item.get("icons", []) if isinstance(s, str)}
        has_resist = bool(item.get("has_resist", "resist" in icons))
        no_unwind = bool(item.get("no_unwind", "no_unwind" in icons))
        # detect burn-on-destroy from notes or explicit flag
        burns = bool(item.get("burns_on_destroy", False))
        for note in item.get("notes", []) or []:
            if isinstance(note, str) and "burn" in note.lower():
                burns = True
                break
        reqs = str(item.get("requirements", "") or "")
        for _ in range(max(1, dups)):
            deck.append(
                Card(
                    name=item.get("name", "Unnamed"),
                    faction=item.get("faction", ""),
                    wind=int(item.get("wind", 0) or 0),
                    stars=int(item.get("stars", 0) or 0),
                    deploy_wind=dw,
                    deploy_gear=dg,
                    deploy_meat=dm,
                    deploy_power=dp,
                    abilities=[Ability(**vars(a)) for a in abilities],
                    image_url_mini=item.get("image_url_mini", ""),
                    image_url_full=item.get("image_url_full", ""),
                    rank=str(item.get("rank", "")),
                    no_unwind=no_unwind,
                    is_bio=bool(item.get("is_bio", False)),
                    is_mech=bool(item.get("is_mech", False)),
                    is_titan=bool(item.get("is_titan", False)),
                    has_resist=has_resist,
                    burns_on_destroy=burns,
                    requirements=reqs,
                )
            )
    return deck


# ============================== Uniques, Starters, Badges ==============================

_UNIQUE_NAME_HINTS = ["lokar", "lokar simmons", "grim"]


def _name_matches(card_name: str, patterns: List[str]) -> bool:
    n = (card_name or "").strip().lower()
    return any(p in n for p in (s.strip().lower() for s in patterns if s))


def is_squad_leader(c: Card) -> bool:
    return c.stars > 0 or _name_matches(c.name, _UNIQUE_NAME_HINTS)


def is_squad_goon(c: Card) -> bool:
    r = (c.rank or "").lower()
    return (("squad goon" in r) or ("squad" in r)) and not is_squad_leader(c) and not c.is_titan


def card_badges(c: Card) -> str:
    parts: List[str] = []
    if c.is_titan:
        parts.append("Ω")
    elif is_squad_leader(c):
        parts.append("★")
    elif is_squad_goon(c):
        parts.append("♦")
    if getattr(c, "has_resist", False):
        parts.append("✋")
    if getattr(c, "no_unwind", False):
        parts.append("🚫")
    return (" " + " ".join(parts)) if parts else ""


def _name_with_badges(c: Card) -> str:
    return f"{c.name}{card_badges(c)}"


def is_unique(c: Card) -> bool:
    return is_squad_leader(c) or c.is_titan


def conflicts_with_unique(g: GameState, c: Card) -> bool:
    if not is_unique(c):
        return False
    key = (c.name or "").strip().lower()
    for side in (g.narc_player, g.pcu_player):
        for x in side.field:
            if is_unique(x) and (x.name or "").strip().lower() == key:
                return True
    return False


def _pull_named_starter(
    primary: List[Card], secondary: List[Card], patterns: List[str]
) -> tuple[Optional[Card], List[Card], List[Card]]:
    for i, c in enumerate(primary):
        if _name_matches(c.name, patterns):
            return primary.pop(i), primary, secondary
    for i, c in enumerate(secondary):
        if _name_matches(c.name, patterns):
            return secondary.pop(i), primary, secondary
    return None, primary, secondary


# ---------- NEW: Leader Protection Helpers ----------
def _has_leader_protectors(owner: Player) -> bool:
    """True if owner controls any non-leader, non-titan goon (guards the leader)."""
    return any((not is_squad_leader(c)) and (not c.is_titan) for c in owner.field)


def _is_leader_protected(owner: Player, target: Card) -> bool:
    """True if target is a protected leader on owner's side."""
    return is_squad_leader(target) and _has_leader_protectors(owner)


# ============================== Payment & Effects ==============================


def destroy_if_needed(owner: Player, c: Card) -> None:
    # If Vex is destroyed, also destroy Nives
    if (c.name or "").strip().lower() == "vex":
        for goon in list(owner.field):
            if (goon.name or "").strip().lower() == "nives":
                owner.field.remove(goon)
                owner.dead_pool.append(goon)
                print("Nives destroyed because Vex was destroyed.")
                print(f"[destroy] {owner.name}:Nives (linked to Vex)")
                print(f"{owner.name}'s Nives destroyed (linked to Vex)")
    if c.wind >= 4:
        # If Krax is destroyed, also destroy Dragoon
        if (c.name or "").strip().lower() == "krax":
            for goon in list(owner.field):
                if (goon.name or "").strip().lower() == "dragoon":
                    owner.field.remove(goon)
                    owner.dead_pool.append(goon)
                    print("Dragoon destroyed because Krax was destroyed.")
                    print(f"[destroy] {owner.name}:Dragoon (linked to Krax)")
                    print(f"{owner.name}'s Dragoon destroyed (linked to Krax)")
        if c in owner.field:
            owner.field.remove(c)
        # Meatjacker returns to owner's hand when destroyed
        if (c.name or "").strip().lower() == "meatjacker":
            owner.hand.append(c)
            print(f"{c.name} destroyed and returns to hand!")
            print(f"[destroy] {owner.name}:{c.name} -> Hand (Meatjacker rule)")
            print(f"{owner.name}'s {c.name} destroyed and returns to hand")
        elif c.is_titan:
            print(f"{c.name} (Titan) destroyed and burned!")
            print(f"[destroy] {owner.name}:{c.name} (burn)")
            print(f"{owner.name}'s {c.name} destroyed")
        else:
            owner.dead_pool.append(c)
            print(f"{c.name} destroyed → Dead Pool")
            print(f"[destroy] {owner.name}:{c.name} -> Dead Pool")
            print(f"{owner.name}'s {c.name} destroyed")
        if is_squad_leader(c):
            loser = owner.name
            winner = "PCU" if loser == "NARC" else "NARC"
            print(f"GAME OVER — {loser}'s Squad Leader ({c.name}) was destroyed. {winner} wins!")
            print(f"[gameover] leader destroyed: loser={loser}, card={c.name}, winner={winner}")
            if _GLOG:
                _GLOG.write("=== game end ===\n")
                _GLOG.flush()
                _GLOG.close()
            print(f"Full game log saved to: {GAMELOG_PATH}")
            if _LOG:
                _LOG.flush()
                _LOG.close()
            raise SystemExit(0)


def _apply_wind_safely(targets: List[Card], total: int) -> int:
    paid = 0
    pool = sorted([c for c in targets if not c.new_this_turn], key=lambda c: (c.wind, c.name))
    while paid < total and pool:
        pool.sort(key=lambda c: (c.wind, c.name))
        c = next((x for x in pool if x.wind < 3), None)
        if c is None:
            break
        c.wind += 1
        paid += 1
    return paid


# --- Flake8/black-clean distribute_wind ---
def distribute_wind(
    owner: "Player",
    total: int,
    *,
    auto: bool = False,
    allow_cancel: bool = False,
) -> Optional[bool]:
    """
    Pay 'total' wind by incrementing wind on the owner's board goons.
    Returns:
        True  -> fully paid
        False -> could not pay
        None  -> user canceled (only if allow_cancel=True and you implement a prompt)
    """
    if total <= 0:
        return True
    if not owner.board:
        print("No goons in play to pay wind.")
        return False

    before = {id(c): (c, c.wind) for c in owner.board}

    if auto:
        paid = _apply_wind_safely(owner.board, total)
        for _, (card, w0) in before.items():
            if card.wind > w0:
                for step in range(w0 + 1, card.wind + 1):
                    print(f"{owner.name} pays 1 wind with {card.name} (now {step})")
        for c in list(owner.board):
            destroy_if_needed(owner, c)
        return paid >= total

    paid = _apply_wind_safely(owner.board, total)
    for _, (card, w0) in before.items():
        if card.wind > w0:
            for step in range(w0 + 1, card.wind + 1):
                print(f"{owner.name} pays 1 wind with {card.name} (now {step})")
    for c in list(owner.board):
        destroy_if_needed(owner, c)
    return paid >= total


def apply_wind_with_resist(
    attacker_owner: Player, defender_owner: Player, target: Card, amount: int
) -> int:
    if amount <= 0:
        return 0
    is_enemy = attacker_owner is not defender_owner
    has_resist = "resist" in target.statuses or False
    reduction = 1 if (is_enemy and has_resist) else 0
    actual = max(0, amount - reduction)
    if target.name.strip().lower() == "krax":
        dragoon = next(
            (c for c in defender_owner.board if c.name.strip().lower() == "dragoon"),
            None,
        )
        if dragoon:
            redirected = min(actual, actual)
            dragoon.wind += redirected
            actual -= redirected
    target.wind += actual
    return actual


def post_resolve_cleanup(gs: GameState, pending_destroy: List[Tuple[Player, Card]]) -> None:
    seen = set()
    queue: List[Tuple[Player, Card]] = []
    for owner, c in pending_destroy:
        if id(c) not in seen:
            seen.add(id(c))
            queue.append((owner, c))
    for owner, c in queue:
        if c in owner.board and c.wind >= 4:
            owner.board.remove(c)
            if c.rank == Rank.TITAN:
                owner.retired.append(c)
            elif c.name.strip().lower() == "meatjacker":
                owner.hand.append(c)
            else:
                owner.dead_pool.append(c)


class EffectStack:
    def __init__(self):
        self._q: List[Effect] = []

    def push(self, eff: Effect):
        self._q.append(eff)

    def resolve(self, ctx: Dict[str, Any]):
        while self._q:
            eff = self._q.pop(0)
            op = eff.op.lower()
            args = eff.args or {}
            g: GameState = ctx["game"]
            src_owner: Player = ctx["player"]
            enemy = g.p2 if src_owner is g.p1 else g.p2
            target = ctx.get("target")
            pending = ctx["pending_destroy"]
            if op == "add_wind" and target is not None:
                apply_wind_with_resist(src_owner, enemy, target, int(args.get("amount", 0)))
                if target.wind >= 4:
                    pending.append((enemy, target))
            elif op == "destroy" and target is not None:
                target.wind = 4
                pending.append((enemy, target))
            elif op == "grant_status" and target is not None:
                status_name = args.get("status", "cover").lower()
                expires = args.get("expires")
                target.statuses[status_name] = {"expires": expires}
            # extend with more ops as needed


effect_stack = EffectStack()


def use_ability(g, p, c_idx, a_idx, t_idx=None):
    try:
        card = p.board[c_idx]
    except Exception:
        print("Invalid source index.")
        return False
    try:
        ability = card.abilities[a_idx]
    except Exception:
        print("Invalid ability index.")
        return False
    enemy = g.p2 if p is g.p1 else g.p1
    limit = getattr(ability, "limit_per_turn", 1)
    used = getattr(card, "used_this_turn", 0)
    if limit is not None and used >= limit:
        print(f"{card.name} has already used {ability.name} this turn.")
        return False
    target = None
    if t_idx is not None:
        if 0 <= t_idx < len(enemy.board):
            target = enemy.board[t_idx]
        else:
            print("Invalid target index.")
            return False
        if not can_target_card(g, card, target, p, enemy, ability):
            print("Illegal target.")
            return False
    pending_destroy: List[Tuple[Player, Card]] = []
    if not pay_cost(g, p, ability, pending_destroy):
        print("Could not pay cost.")
        return False
    for eff in getattr(ability, "effects", []):
        effect_stack.push(eff)
    context = {
        "game": g,
        "player": p,
        "source": card,
        "ability": ability,
        "target": target,
        "pending_destroy": pending_destroy,
    }
    effect_stack.resolve(context)
    card.used_this_turn = used + 1
    post_resolve_cleanup(g, pending_destroy)
    return True


def load_deck_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        print(f"Deck file not found: {path}")
        sys.exit(1)
    with open(path, "r") as f:
        try:
            return json.load(f)
        except Exception as e:
            print(f"Failed to parse {path}: {e}")
            sys.exit(1)


def parse_rank(raw: str) -> Rank:
    s = (raw or "").strip().lower()
    if s in {"sl", "squad leader", "squadleader", "leader"}:
        return Rank.SL
    if s in {"sg", "standard goon", "squad goon", "goon"}:
        return Rank.SG
    if s in {"bg", "basic goon", "boss goon", "basic"}:
        return Rank.BG
    if s in {"titan", "tn"}:
        return Rank.TITAN
    return Rank.BG


def build_cards(deck_obj: Dict[str, Any], faction: str) -> List[Card]:
    """
    Build Card objects from a deck JSON for a given faction.
    - Accepts only tokens like "<int><w|g|m>" (e.g., 1w, 2g, 3m) and "p" (passive).
    - Unknown tokens are ignored safely.
    """
    cards: List[Card] = []

    for raw in deck_obj.get("goons", []):
        name = raw["name"]
        rank = parse_rank(raw.get("rank", "Basic Goon"))
        deploy_cost: Dict[str, int] = {}
        for tok in raw.get("deploy_cost", []):
            t = str(tok or "").strip().lower()
            m = re.fullmatch(r"(\d+)\s*([wgm])", t)
            if not m:
                continue
            n = int(m.group(1))
            key = {"w": "wind", "g": "gear", "m": "meat"}[m.group(2)]
            deploy_cost[key] = deploy_cost.get(key, 0) + n
        abilities: List[Ability] = []
        for a in raw.get("abilities", []):
            cost: Dict[str, int] = {}
            passive = False
            for tok in a.get("cost", []):
                t = str(tok or "").strip().lower()
                if t == "p":
                    passive = True
                    continue
                m = re.fullmatch(r"(\d+)\s*([wgm])", t)
                if not m:
                    continue
                n = int(m.group(1))
                key = {"w": "wind", "g": "gear", "m": "meat"}[m.group(2)]
                cost[key] = cost.get(key, 0) + n
            text = (a.get("text") or "").lower()
            effects: List[Effect] = []
            if "destroy" in text:
                effects.append(Effect("destroy", {}))
            elif "remove 1 wind" in text:
                effects.append(Effect("add_wind", {"amount": -1}))
            elif "add 2 wind" in text:
                effects.append(Effect("add_wind", {"amount": 2}))
            elif "add 1 wind" in text:
                effects.append(Effect("add_wind", {"amount": 1}))
            elif "may not be targeted" in text or "cover" in (raw.get("name") or "").lower():
                effects.append(
                    Effect(
                        "grant_status",
                        {"status": "cover", "expires": ("start_of_turn", "owner")},
                    )
                )
            abilities.append(Ability(a.get("name", "ABILITY"), cost, effects, passive=passive))
        cards.append(
            Card(
                name=name,
                rank=rank,
                faction=faction,
                abilities=abilities,
                deploy_wind=deploy_cost.get("wind", 0),
                deploy_gear=deploy_cost.get("gear", 0),
                deploy_meat=deploy_cost.get("meat", 0),
            )
        )

    return cards


# --- Deploy cost payment API ---
def can_pay_deploy_cost(gs: GameState, player: Player, card: Card) -> bool:
    dc = card.deploy_cost or {}
    need_w = int(dc.get("wind", 0) or 0)
    need_g = int(dc.get("gear", 0) or 0)
    need_m = int(dc.get("meat", 0) or 0)

    if need_w > 0 and len(player.board) == 0:
        return False
    mech = sum(1 for c in gs.shared_dead if is_mechanical(c))
    bio = sum(1 for c in gs.shared_dead if is_biological(c))
    return mech >= need_g and bio >= need_m


def pay_deploy_cost(
    gs: GameState,
    player: Player,
    card: Card,
    wind_splits: list[tuple[int, int]],
    burn_mech_idxs: list[int],
    burn_bio_idxs: list[int],
) -> bool:
    dc = card.deploy_cost or {}
    need_w = int(dc.get("wind", 0) or 0)
    need_g = int(dc.get("gear", 0) or 0)
    need_m = int(dc.get("meat", 0) or 0)

    if len(burn_mech_idxs) != need_g or len(burn_bio_idxs) != need_m:
        return False
    shared = gs.shared_dead
    try:
        sel_mech = [shared[i] for i in burn_mech_idxs]
        sel_bio = [shared[i] for i in burn_bio_idxs]
    except Exception:
        return False
    if not all(is_mechanical(c) for c in sel_mech):
        return False
    if not all(is_biological(c) for c in sel_bio):
        return False

    total_w = sum(int(a) for _, a in wind_splits)
    if total_w != need_w:
        return False
    if any(i < 0 or i >= len(player.board) or a <= 0 for i, a in wind_splits):
        return False

    # Burn shared dead selections → retired (distinct, descending index removal)
    for idx in sorted(set(burn_mech_idxs + burn_bio_idxs), reverse=True):
        burned = shared.pop(idx)
        player.retired.append(burned)

    # Apply wind to payers (deferred death for deploy)
    for i, a in wind_splits:
        src = player.board[i]
        apply_wind_with_resist(player, player, src, a)

    return True


WindSelector = Callable[[GameState, Player, "Card", dict], list[tuple[int, int]]]
BurnSelector = Callable[[GameState, Player, "Card", dict], tuple[list[int], list[int]]]


def deploy_with_cost(
    gs: GameState,
    player: Player,
    hand_idx: int,
    pick_wind: WindSelector,
    pick_burn: BurnSelector,
) -> bool:
    if hand_idx < 0 or hand_idx >= len(player.hand):
        return False
    card = player.hand[hand_idx]
    dc = card.deploy_cost or {}

    if not can_pay_deploy_cost(gs, player, card):
        return False

    need_w = int(dc.get("wind", 0) or 0)
    need_g = int(dc.get("gear", 0) or 0)
    need_m = int(dc.get("meat", 0) or 0)

    wind_splits: list[tuple[int, int]] = []
    mech_idx: list[int] = []
    bio_idx: list[int] = []

    if need_w > 0:
        wind_splits = pick_wind(gs, player, card, dc)
        if not wind_splits:
            return False

    if need_g or need_m:
        mech_idx, bio_idx = pick_burn(gs, player, card, dc)
        if mech_idx is None or bio_idx is None:
            return False

    if not pay_deploy_cost(gs, player, card, wind_splits, mech_idx, bio_idx):
        return False

    player.board.append(card)
    player.hand.pop(hand_idx)
    post_resolve_cleanup(gs, [])
    return True


def main():
    # Load decks from local files in current folder
    narc = load_deck_json("narc_deck.json")
    pcu = load_deck_json("pcu_deck.json")

    narc_cards = build_cards(narc, faction="NARC")
    pcu_cards = build_cards(pcu, faction="PCU")

    # --- Robust SL detection ---
    p1_sl = find_squad_leader(narc_cards)
    p2_sl = find_squad_leader(pcu_cards)
    if not p1_sl or not p2_sl:

        def _sl_debug(deck_name: str, deck_cards: list["Card"]) -> None:
            out = []
            for c in deck_cards:
                r = getattr(c, "rank", None)
                rtxt = r.name if hasattr(r, "name") else (str(r) if r is not None else "")
                out.append(f"{getattr(c, 'name', '?')}[{rtxt}]")
            print(f"[{deck_name}] no SL found. Cards: {', '.join(out)}")

        if not p1_sl:
            _sl_debug("NARC", narc_cards)
        if not p2_sl:
            _sl_debug("PCU", pcu_cards)
        raise SystemExit("Both decks must contain a Squad Leader to start.")

    # Start SLs on board, exclude from deck
    p1_deck = [c for c in narc_cards if c is not p1_sl]
    p2_deck = [c for c in pcu_cards if c is not p2_sl]
    p1 = Player("NARC", board=[p1_sl], hand=[], deck=p1_deck, retired=[])
    p2 = Player("PCU", board=[p2_sl], hand=[], deck=p2_deck, retired=[])

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ui", choices=["cli", "rich"], default=os.environ.get("GSG_UI", "cli"))
    parser.add_argument(
        "--first",
        choices=["random", "p1", "p2"],
        default=os.environ.get("GSG_FIRST", "random"),
    )
    parser.add_argument(
        "--ai",
        choices=["none", "p1", "p2", "both"],
        default=os.environ.get("GSG_AI", "none"),
    )
    # Coerce env seed properly (argparse won't cast default)
    env_seed = os.environ.get("GSG_SEED")
    default_seed = int(env_seed) if env_seed and env_seed.isdigit() else None
    parser.add_argument("--seed", type=int, default=default_seed)

    args, _ = parser.parse_known_args()

    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    gs = GameState(p1=p1, p2=p2, turn_player=p1, phase="start", turn_number=1)
    gs.rng = rng

    shuffle_deck(gs, p1)
    shuffle_deck(gs, p2)
    draw(gs, p1, 6)
    draw(gs, p2, 6)

    first = args.first if args.first != "random" else rng.choice(["p1", "p2"])
    gs.turn_player = p1 if first == "p1" else p2
    gs.turn_number = 1
    start_of_turn(gs)  # current player draws 1 at start

    ui = _select_ui("rich" if args.ui == "rich" else "cli")
    if hasattr(ui, "configure_runtime"):
        ui.configure_runtime(ai=args.ai)

    print("GSG engine ready. Decks loaded. SLs on board. (Type 'help' to see commands.)")
    ui.run_loop(gs)


if __name__ == "__main__":
    main()
