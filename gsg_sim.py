from typing import Optional
# Restored deploy_card implementation
def deploy_card(p: "Player", hand_idx: int, *, auto: bool = False, g: Optional["GameState"] = None):
    import sys
    test_mode = not sys.stdin.isatty() or "--test" in sys.argv
    try:
        c = p.hand[hand_idx]
    except IndexError:
        if not test_mode:
            return console.print("[red]Bad hand index[/red]")
        return
    # Enforce dead pool resource checks for all cards with meat/gear deploy cost
    if g is not None:
        combined_dead_pool = g.narc_player.dead_pool + g.pcu_player.dead_pool
        meat_available = sum(1 for card in combined_dead_pool if getattr(card, "is_bio", False))
        gear_available = sum(1 for card in combined_dead_pool if getattr(card, "is_mech", False))
        if c.deploy_meat > 0 and meat_available < c.deploy_meat:
            log(f"[deploy-block] Not enough meat in dead pool for {c.name}")
            if not test_mode:
                console.print(f"[red]Cannot deploy {c.name}: requires {c.deploy_meat} meat from dead pool, only {meat_available} available.[/red]")
            return
        if c.deploy_gear > 0 and gear_available < c.deploy_gear:
            log(f"[deploy-block] Not enough gear in dead pool for {c.name}")
            if not test_mode:
                console.print(f"[red]Cannot deploy {c.name}: requires {c.deploy_gear} gear from dead pool, only {gear_available} available.[/red]")
            return
    # Prevent shackled goons from contributing wind to deploy
    if hasattr(c, 'shackled') and c.shackled > 0:
        log(f"[deploy-block] {c.name} is shackled and cannot contribute wind to deploy.")
        if not test_mode:
            console.print(f"[red]{c.name} is shackled and cannot contribute wind to deploy this turn.[/red]")
        return
    # Nives can only be deployed if Vex is in play
    if g is not None and (c.name or '').strip().lower() == 'nives':
        vex_in_play = any((x.name or '').strip().lower() == 'vex' for x in p.field)
        if not vex_in_play:
            log("[deploy-block] Nives requires Vex in play")
            if not test_mode:
                console.print("[red]Cannot deploy Nives: Vex must be in play.[/red]")
            return
    # Dragoon can only be deployed if Krax is in play
    if g is not None and (c.name or '').strip().lower() == 'dragoon':
        krax_in_play = any((x.name or '').strip().lower() == 'krax' for x in p.field)
        if not krax_in_play:
            log("[deploy-block] Dragoon requires Krax in play")
            if not test_mode:
                console.print("[red]Cannot deploy Dragoon: Krax must be in play.[/red]")
            return
    # Pay deploy cost
    if not pay_deploy(p, c, auto=auto, allow_cancel=True):
        return
    # Move card from hand to field
    p.hand.pop(hand_idx)
    p.field.append(c)
    c.new_this_turn = True
    log(f"[deploy] {p.name} deploys {c.name}")
    if not test_mode:
        console.print(f"[green]{p.name} deploys {c.name} to the field.[/green]")
import argparse
import json
import os
import random
import re
import sys
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple, TextIO

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# ============================== Globals & IO ==============================

@dataclass
class _CommandSource:
    queue: Deque[str] = field(default_factory=deque)
    default_on_interrupt: Optional[str] = None

_CMD_SOURCE: Optional[_CommandSource] = None
console = Console()
_LOG: Optional[TextIO] = None  # debug transcript if --log is provided

AI_NARC: bool = False
AI_PCU: bool = False

# Structured game log (persists to file)
GAME_LOG: List[str] = []
TURN_BUFFER: List[str] = []
LAST_TURN_SUMMARY: Optional[Dict[str, object]] = None
_GLOG: Optional[TextIO] = None
GAMELOG_PATH: Optional[str] = None

# ============================== Models ==============================

@dataclass
class Ability:
    idx: int
    name: str
    wind_cost: int = 0
    gear_cost: int = 0
    meat_cost: int = 0
    power_cost: int = 0
    text: str = ""
    passive: bool = False
    inflicts_wind: int = 0          # optional: amount of wind inflicted to target (AI uses this)
    removes_wind: int = 0           # amount of wind removed from friendly target (healing)
    friendly_only: bool = False     # heal/support targets allies only
    draw_cards: int = 0             # targetless draw amount
    max_uses_per_turn: Optional[int] = None
    uses_this_turn: int = 0

@dataclass
class Card:
    name: str
    faction: str
    wind: int = 0
    stars: int = 0
    deploy_wind: int = 0
    deploy_gear: int = 0
    deploy_meat: int = 0
    deploy_power: int = 0
    abilities: List[Ability] = field(default_factory=list)
    image_url_mini: str = ""
    image_url_full: str = ""
    rank: str = ""
    new_this_turn: bool = False
    used_this_turn: bool = False
    no_unwind: bool = False
    is_bio: bool = False
    is_mech: bool = False
    is_titan: bool = False
    has_resist: bool = False  # ✋ badge
    burns_on_destroy: bool = False
    requirements: str = ""
    shackled: int = 0  # turns remaining shackled

@dataclass
class Player:
    name: str
    deck: List[Card]
    hand: List[Card]
    field: List[Card]
    dead_pool: List[Card] = field(default_factory=list)
    # resource pools for non-wind costs
    gear: int = 0
    meat: int = 0
    power: int = 0

@dataclass
class GameState:
    narc_player: Player
    pcu_player: Player
    active_faction: str = "NARC"

# ============================== Deck I/O ==============================

_WORD_NUMS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}

def _infer_wind_from_text(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"(\d+)\s*wind", text, flags=re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(" + "|".join(_WORD_NUMS) + r")\b\s*wind", text, flags=re.I)
    if m:
        return _WORD_NUMS[m.group(1).lower()]
    return 0

def _infer_remove_from_text(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"remove\s+(\d+)\s*wind", text, flags=re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"remove\s+(" + "|".join(_WORD_NUMS) + r")\s*wind", text, flags=re.I)
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
def _pull_named_starter(primary: List[Card], secondary: List[Card], patterns: List[str]) -> tuple[Optional[Card], List[Card], List[Card]]:
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
    if (c.name or '').strip().lower() == 'vex':
        for goon in list(owner.field):
            if (goon.name or '').strip().lower() == 'nives':
                owner.field.remove(goon)
                owner.dead_pool.append(goon)
                console.print(f"[red]Nives destroyed because Vex was destroyed.[/red]")
                log(f"[destroy] {owner.name}:Nives (linked to Vex)")
                record(f"{owner.name}'s Nives destroyed (linked to Vex)")
    if c.wind >= 4:
        # If Krax is destroyed, also destroy Dragoon
        if (c.name or '').strip().lower() == 'krax':
            for goon in list(owner.field):
                if (goon.name or '').strip().lower() == 'dragoon':
                    owner.field.remove(goon)
                    owner.dead_pool.append(goon)
                    console.print(f"[red]Dragoon destroyed because Krax was destroyed.[/red]")
                    log(f"[destroy] {owner.name}:Dragoon (linked to Krax)")
                    record(f"{owner.name}'s Dragoon destroyed (linked to Krax)")
        if c in owner.field:
            owner.field.remove(c)
        # Meatjacker returns to owner's hand when destroyed
        if (c.name or '').strip().lower() == 'meatjacker':
            owner.hand.append(c)
            console.print(f"[yellow]{c.name} destroyed and returns to hand![/yellow]")
            log(f"[destroy] {owner.name}:{c.name} -> Hand (Meatjacker rule)")
            record(f"{owner.name}'s {c.name} destroyed and returns to hand")
        elif c.is_titan:
            console.print(f"[red]{c.name} (Titan) destroyed and burned![/red]")
            log(f"[destroy] {owner.name}:{c.name} (burn)")
            record(f"{owner.name}'s {c.name} destroyed")
        else:
            owner.dead_pool.append(c)
            console.print(f"[red]{c.name} destroyed → Dead Pool[/red]")
            log(f"[destroy] {owner.name}:{c.name} -> Dead Pool")
            record(f"{owner.name}'s {c.name} destroyed")
        if is_squad_leader(c):
            loser = owner.name
            winner = "PCU" if loser == "NARC" else "NARC"
            console.print(
                f"[bold red]GAME OVER[/bold red] — {loser}'s Squad Leader ({c.name}) was destroyed. "
                f"[bold green]{winner} wins![/bold green]"
            )
            log(f"[gameover] leader destroyed: loser={loser}, card={c.name}, winner={winner}")
            if _GLOG:
                _GLOG.write("=== game end ===\n")
                _GLOG.flush()
                _GLOG.close()
            console.print(f"[bold]Full game log saved to:[/bold] {GAMELOG_PATH}")
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

def distribute_wind(owner: Player, total: int, *, auto: bool = False, allow_cancel: bool = False) -> Optional[bool]:
    """Returns True if fully paid, False if failed, None if canceled by user (when allow_cancel=True)."""
    if total <= 0:
        return True
    if not owner.field:
        console.print("[red]No goons in play to pay wind.[/red]")
        return False

    before = {id(c): (c, c.wind) for c in owner.field}

    if auto:
        paid = _apply_wind_safely(owner.field, total)
        for cid, (card, w0) in before.items():
            if card.wind > w0:
                for step in range(w0 + 1, card.wind + 1):
                    record(f"{owner.name} pays 1 wind with {card.name} (now {step})")
        for c in list(owner.field):
            destroy_if_needed(owner, c)
        if paid < total:
            console.print("[yellow]AI could not safely pay full wind cost; skipping action.[/yellow]")
            log(f"[ai] wind pay failed: needed {total}, paid {paid}")
            return False
        for c in owner.field:
            log(f"[wind] {owner.name}:{c.name} -> {c.wind}")
        return True

    remaining = total
    while remaining > 0:
        entry = get_next_command(f"Distribute {remaining} wind (e.g., '0 0 1'): enter indexes (space-separated)")
        if allow_cancel and entry.strip() == "":
            return None
        idxs = entry.split()
        try:
            picks = [int(i) for i in idxs]
        except Exception:
            console.print("[red]Invalid indexes.[/red]")
            continue
        applied = 0
        for i in picks:
            if i < 0 or i >= len(owner.field):
                console.print(f"[yellow]Skip invalid idx {i}[/yellow]")
                continue
            target = owner.field[i]
            if target.new_this_turn:
                console.print(f"[yellow]{target.name} is new this turn and cannot pay.[/yellow]")
                continue
            if c.wind >= 4:
                # REACTIVE MUNITIONS: If Dormex Lurker is destroyed, destroy the goon that destroyed it
                if (c.name or '').strip().lower() == 'dormex lurker':
                    # Find last attacker (if tracked)
                    if hasattr(c, 'last_attacker') and c.last_attacker:
                        attacker = c.last_attacker
                        destroy_if_needed(attacker[0], attacker[1])
                        record(f"Dormex Lurker's REACTIVE MUNITIONS destroys {attacker[1].name}!")
                        console.print(f"[red]Dormex Lurker's REACTIVE MUNITIONS destroys {attacker[1].name}![/red]")
                if c in owner.field:
                    owner.field.remove(c)
                if c.is_titan:
                    console.print(f"[red]{c.name} (Titan) destroyed and burned![/red]")
                    log(f"[destroy] {owner.name}:{c.name} (burn)")
                    record(f"{owner.name}'s {c.name} destroyed")
                else:
                    owner.dead_pool.append(c)
                    console.print(f"[red]{c.name} destroyed → Dead Pool[/red]")
                    log(f"[destroy] {owner.name}:{c.name} -> Dead Pool")
                    record(f"{owner.name}'s {c.name} destroyed")
                if is_squad_leader(c):
                    loser = owner.name
                    winner = "PCU" if loser == "NARC" else "NARC"
                    console.print(
                        f"[bold red]GAME OVER[/bold red] — {loser}'s Squad Leader ({c.name}) was destroyed. "
                        f"[bold green]{winner} wins![/bold green]"
                    )
                    log(f"[gameover] leader destroyed: loser={loser}, card={c.name}, winner={winner}")
                    if _GLOG:
                        _GLOG.write("=== game end ===\n")
                        _GLOG.flush()
                        _GLOG.close()
                    console.print(f"[bold]Full game log saved to:[/bold] {GAMELOG_PATH}")
                    if _LOG:
                        _LOG.flush()
                        _LOG.close()
                    raise SystemExit(0)
            # (Removed unreachable Familiar Assist code)

    # Enforce dead pool resource checks for ability costs (meat/gear)
    import sys
    test_mode = not sys.stdin.isatty() or "--test" in sys.argv
    g = None
    try:
        from inspect import currentframe, getouterframes
        stack = getouterframes(currentframe(), 2)
        for frame in stack:
            if "g" in frame.frame.f_locals:
                g = frame.frame.f_locals["g"]
                break
    except Exception:
        pass
    if g is not None:
        combined_dead_pool = g.narc_player.dead_pool + g.pcu_player.dead_pool
        meat_available = sum(1 for card in combined_dead_pool if getattr(card, "is_bio", False))
        gear_available = sum(1 for card in combined_dead_pool if getattr(card, "is_mech", False))


def apply_wind_with_resist(attacker_owner: Player, defender_owner: Player, target: Card, amount: int) -> int:
    """Enemy ability adds wind to target; ✋ reduces by 1."""
    if amount <= 0:
        return 0
    is_enemy = attacker_owner is not defender_owner
    reduction = 1 if (is_enemy and getattr(target, "has_resist", False)) else 0
    actual = max(0, amount - reduction)
    # LOYAL MOUNT: Dragoon can take some or all damage for Krax
    if (target.name or '').strip().lower() == 'krax':
        owner = defender_owner
        dragoon = next((c for c in owner.field if (c.name or '').strip().lower() == 'dragoon'), None)
        if dragoon:
            # Ask how much damage Dragoon should take
            try:
                amt = int(Prompt.ask(f"LOYAL MOUNT: How much wind should Dragoon take for Krax? (0-{actual})", default=str(actual)))
                amt = max(0, min(actual, amt))
            except Exception:
                amt = actual
            if amt > 0:
                for _ in range(amt):
                    dragoon.wind += 1
                record(f"Dragoon takes {amt} wind for Krax (LOYAL MOUNT)")
                console.print(f"[cyan]LOYAL MOUNT: Dragoon takes {amt} wind for Krax.[/cyan]")
                destroy_if_needed(owner, dragoon)
            actual -= amt
    if reduction:
        console.print(f"[cyan]Resist ✋: {target.name} reduces incoming wind by 1 (from {amount} to {actual}).[/cyan]")
    record(f"Wind to {target.name}: +{actual}" + (" (resist -1)" if reduction else ""))
    for _ in range(actual):
        target.wind += 1
        # Track last attacker for REACTIVE MUNITIONS
        if (target.name or '').strip().lower() == 'dormex lurker':
            target.last_attacker = (attacker_owner, attacker_owner.field[0] if attacker_owner.field else None)
    destroy_if_needed(defender_owner, target)
    return actual

# ============================== UI helpers ==============================

def draw_card(p: Player):
    if p.deck:
        card = p.deck.pop()
        p.hand.append(card)
        log(f"[draw] {p.name}:{card.name}")
        # Only reveal card name if human player is drawing
        from inspect import currentframe, getouterframes
        # Check if called from ai_take_turn
        stack = getouterframes(currentframe(), 2)
        called_by_ai = any('ai_take_turn' in f.function for f in stack)
        if called_by_ai:
            record(f"{p.name} drew a card")
        else:
            record(f"{p.name} draws: {card.name}")

def format_cost(w, g, m, p):
    parts = []
    if w:
        parts.append(f"🔄{w}")
    if g:
        parts.append(f"⚙️{g}")
    if m:
        parts.append(f"🥩{m}")
    if p:
        parts.append(f"🅿{p}")
    return " ".join(parts) if parts else "—"

def _ability_line(a: Ability) -> str:
    if a.passive:
        return f"{a.name} [PASSIVE]" + (f" — {a.text}" if a.text else "")
    cost = format_cost(a.wind_cost, a.gear_cost, a.meat_cost, a.power_cost)
    return f"{a.name} [{cost}]" + (f" — {a.text}" if a.text else "")

def _ability_cell_multi(abilities: List[Ability]) -> str:
    if not abilities:
        return "—"
    return "\n".join(f"[{i}] " + _ability_line(a) for i, a in enumerate(abilities))

def _open_card_image(card, prefer_full: bool = True) -> None:
    url = card.image_url_full or card.image_url_mini
    if url:
        webbrowser.open(url)
    else:
        console.print("[yellow]No image URL for that card.[/yellow]")

def _has_image(card) -> bool:
    return bool(card.image_url_full or card.image_url_mini)

def _dead_pool_counts_combined(a: Player, b: Player) -> tuple[int, int]:
    meat = sum(1 for c in a.dead_pool if getattr(c, "is_bio", False)) + sum(1 for c in b.dead_pool if getattr(c, "is_bio", False))
    gear = sum(1 for c in a.dead_pool if getattr(c, "is_mech", False)) + sum(1 for c in b.dead_pool if getattr(c, "is_mech", False))
    return meat, gear

def display_field(p: Player, e: Player):
    # Enemy first
    t1 = Table(title="Enemy Field")
    t1.add_column("Card")
    t1.add_column("Wind")
    t1.add_column("Ability")
    for idx, c in enumerate(e.field):
        tags = []
        if c.new_this_turn:
            tags.append("NEW")
        if c.used_this_turn:
            tags.append("USED")
        icon = " 📷" if _has_image(c) else ""
        prot = " 🛡" if _is_leader_protected(e, c) else ""  # show protection
        t1.add_row(
            f"[{idx}] {_name_with_badges(c)}{icon}{prot}" + (f" {' '.join(tags)}" if tags else ""),
            str(c.wind),
            _ability_cell_multi(c.abilities),
        )
    console.print(t1)

    # Yours
    t2 = Table(title="Your Field")
    t2.add_column("Card")
    t2.add_column("Wind")
    t2.add_column("Ability")
    for idx, c in enumerate(p.field):
        tags = []
        if c.new_this_turn:
            tags.append("NEW")
        if c.used_this_turn:
            tags.append("USED")
        icon = " 📷" if _has_image(c) else ""
        prot = " 🛡" if _is_leader_protected(p, c) else ""  # show protection
        t2.add_row(
            f"[{idx}] {_name_with_badges(c)}{icon}{prot}" + (f" {' '.join(tags)}" if tags else ""),
            str(c.wind),
            _ability_cell_multi(c.abilities),
        )
    console.print(t2)

    # Combined Dead Pool summary
    meat, gear = _dead_pool_counts_combined(p, e)
    console.print(f"Dead Pool (combined): 🥩 {meat}   ⚙️ {gear}")

def display_hand(p: Player):
    t = Table(title="Your Hand")
    t.add_column("#")
    t.add_column("Card")
    t.add_column("Deploy")
    t.add_column("Ability")
    for idx, c in enumerate(p.hand):
        icon = " 📷" if _has_image(c) else ""
        t.add_row(
            str(idx),
            _name_with_badges(c) + icon,
            format_cost(c.deploy_wind, c.deploy_gear, c.deploy_meat, c.deploy_power),
            _ability_cell_multi(c.abilities),
        )
    console.print(t)
    console.print(
        Panel(
            "Commands: d#=deploy, uX.Y>Z=use, v[h|f|e]# =view (full art), s=show, e=end\n"
            "Use the ability index shown in brackets, e.g. u0.1>2\n"
            "Heals target your own field: use friendly indexes (e.g., u0.0>1)\n"
            "Hint: during wind payment, press Enter on an empty line to cancel the deploy.",
            title="Help",
        )
    )

# ============================== Turn flow ==============================

def start_game(opening_hand_size: int = 6, initial_faction: str = "NARC") -> GameState:
    import sys
    test_mode = not sys.stdin.isatty() or "--test" in sys.argv
    try:
        narc_deck = load_deck(_here("narc_deck.json"))
        pcu_deck = load_deck(_here("pcu_deck.json"))
    except Exception as ex:
        print(f"[error] Deck load failed: {ex}", flush=True)
        sys.exit(1)
    if not narc_deck or not pcu_deck:
        print("[error] One or both decks are empty. Exiting.", flush=True)
        sys.exit(1)

    narc_deck = _dedupe_uniques(narc_deck, "NARC")
    pcu_deck = _dedupe_uniques(pcu_deck, "PCU")
    random.shuffle(narc_deck)
    random.shuffle(pcu_deck)

    # Forced starters: Lokar (NARC) and Grim (PCU)
    lokar, narc_deck, pcu_deck = _pull_named_starter(narc_deck, pcu_deck, ["lokar", "lokar simmons"])
    grim, pcu_deck, narc_deck = _pull_named_starter(pcu_deck, narc_deck, ["grim"])

    # Remove all Grim and Lokar from both decks except the starter cards themselves
    def is_lokar(card):
        return _name_matches(card.name, ["lokar", "lokar simmons"])
    def is_grim(card):
        return _name_matches(card.name, ["grim"])
    narc_deck = [c for c in narc_deck if not is_lokar(c) and not is_grim(c)]
    pcu_deck = [c for c in pcu_deck if not is_lokar(c) and not is_grim(c)]

    narc_field: List[Card] = []
    pcu_field: List[Card] = []

    if lokar:
        lokar.wind = 0
        lokar.new_this_turn = False
        narc_field.append(lokar)
        log(f"[starter] NARC:{lokar.name}")
        if not test_mode:
            console.print(f"[green]Starter placed:[/green] {lokar.name} enters play for [bold]NARC[/bold].")
    else:
        log("[starter] Lokar not found")
        if not test_mode:
            console.print("[yellow]Starter note:[/yellow] Lokar not found in either deck.")

    if grim:
        grim.wind = 0
        grim.new_this_turn = False
        pcu_field.append(grim)
        log(f"[starter] PCU:{grim.name}")
        if not test_mode:
            console.print(f"[green]Starter placed:[/green] {grim.name} enters play for [bold]PCU[/bold].")
    else:
        log("[starter] Grim not found")
        if not test_mode:
            console.print("[yellow]Starter note:[/yellow] Grim not found in either deck.")

    narc_hand: List[Card] = []
    pcu_hand: List[Card] = []
    for _ in range(opening_hand_size):
        if narc_deck:
            narc_hand.append(narc_deck.pop())
        if pcu_deck:
            pcu_hand.append(pcu_deck.pop())
    log(f"[hand] NARC:{len(narc_hand)} PCU:{len(pcu_hand)}")

    return GameState(
        Player("NARC", deck=narc_deck, hand=narc_hand, field=narc_field),
        Player("PCU", deck=pcu_deck, hand=pcu_hand, field=pcu_field),
        active_faction=initial_faction,
    )

def _dedupe_uniques(deck, faction):
    # TODO: Implement actual deduplication logic if needed
    return deck

def unwind_phase(p: Player):
    import sys
    test_mode = not sys.stdin.isatty() or "--test" in sys.argv
    for c in p.field:
        if getattr(c, 'shackled', 0) > 0:
            # Skip unwind for shackled goons
            log(f"[shackle] {p.name}:{c.name} does not unwind (shackled)")
            c.shackled -= 1
            continue
        if not c.no_unwind and c.wind > 0:
            c.wind -= 1
            log(f"[unwind] {p.name}:{c.name} -> {c.wind}")
    for c in p.field:
        c.used_this_turn = False
        if c.new_this_turn:
            c.new_this_turn = False
    if not test_mode:
        console.print("\nSTART OF TURN: Unwind applied (-1 wind each).")

# def deploy_card(p: Player, hand_idx: int, *, auto: bool = False, g: Optional[GameState] = None):
def pay_deploy(owner: "Player", c: "Card", *, auto: bool = False, allow_cancel: bool = False) -> Optional[bool]:
    if c.deploy_wind > 0:
        return distribute_wind(owner, c.deploy_wind, auto=auto, allow_cancel=allow_cancel)
    return True

def pay_ability(owner: "Player", ability, card, *, auto: bool = False, allow_cancel: bool = False) -> Optional[bool]:
    import sys
    test_mode = not sys.stdin.isatty() or "--test" in sys.argv
    g = None
    try:
        from inspect import currentframe, getouterframes
        stack = getouterframes(currentframe(), 2)
        for frame in stack:
            if "g" in frame.frame.f_locals:
                g = frame.frame.f_locals["g"]
                break
    except Exception:
        pass
    if g is not None:
        combined_dead_pool = g.narc_player.dead_pool + g.pcu_player.dead_pool
        meat_available = sum(1 for card in combined_dead_pool if getattr(card, "is_bio", False))
        gear_available = sum(1 for card in combined_dead_pool if getattr(card, "is_mech", False))
        if ability.meat_cost > 0 and meat_available < ability.meat_cost:
            log(f"[ability-block] Not enough meat in dead pool for {card.name}.{ability.name}")
            if not test_mode:
                console.print(f"[red]Cannot use ability {ability.name}: requires {ability.meat_cost} meat from dead pool, only {meat_available} available.[/red]")
            return False
        if ability.gear_cost > 0 and gear_available < ability.gear_cost:
            log(f"[ability-block] Not enough gear in dead pool for {card.name}.{ability.name}")
            if not test_mode:
                console.print(f"[red]Cannot use ability {ability.name}: requires {ability.gear_cost} gear from dead pool, only {gear_available} available.[/red]")
            return False
        # Consume resources from dead pool
        for _ in range(ability.meat_cost):
            for i, dead_card in enumerate(combined_dead_pool):
                if getattr(dead_card, "is_bio", False):
                    for player in [g.narc_player, g.pcu_player]:
                        if dead_card in player.dead_pool:
                            player.dead_pool.remove(dead_card)
                            break
                    break
        for _ in range(ability.gear_cost):
            for i, dead_card in enumerate(combined_dead_pool):
                if getattr(dead_card, "is_mech", False):
                    for player in [g.narc_player, g.pcu_player]:
                        if dead_card in player.dead_pool:
                            player.dead_pool.remove(dead_card)
                            break
                    break
    # Default: pay all wind cost from card
    if ability.wind_cost > 0:
        for _ in range(ability.wind_cost):
            card.wind += 1
            record(f"{owner.name} pays 1 wind with {card.name} (now {card.wind})")
            log(f"[wind+] {owner.name}:{card.name} -> {card.wind}")
        destroy_if_needed(owner, card)
    if getattr(ability, "power_cost", 0):
        console.print("[yellow]Note: power cost present — not enforced in this build.[/yellow]")
    return True
    import sys
    test_mode = not sys.stdin.isatty() or "--test" in sys.argv
    g = None
    try:
        from inspect import currentframe, getouterframes
        stack = getouterframes(currentframe(), 2)
        for frame in stack:
            if "g" in frame.frame.f_locals:
                g = frame.frame.f_locals["g"]
                break
    except Exception:
        pass
    if g is not None:
        combined_dead_pool = g.narc_player.dead_pool + g.pcu_player.dead_pool
        meat_available = sum(1 for card in combined_dead_pool if getattr(card, "is_bio", False))
        gear_available = sum(1 for card in combined_dead_pool if getattr(card, "is_mech", False))
        if ability.meat_cost > 0 and meat_available < ability.meat_cost:
            log(f"[ability-block] Not enough meat in dead pool for {card.name}.{ability.name}")
            if not test_mode:
                console.print(f"[red]Cannot use ability {ability.name}: requires {ability.meat_cost} meat from dead pool, only {meat_available} available.[/red]")
            return False
        if ability.gear_cost > 0 and gear_available < ability.gear_cost:
            log(f"[ability-block] Not enough gear in dead pool for {card.name}.{ability.name}")
            if not test_mode:
                console.print(f"[red]Cannot use ability {ability.name}: requires {ability.gear_cost} gear from dead pool, only {gear_available} available.[/red]")
            return False
        # Consume resources from dead pool
        for _ in range(ability.meat_cost):
            for i, dead_card in enumerate(combined_dead_pool):
                if getattr(dead_card, "is_bio", False):
                    for player in [g.narc_player, g.pcu_player]:
                        if dead_card in player.dead_pool:
                            player.dead_pool.remove(dead_card)
                            break
                    break
        for _ in range(ability.gear_cost):
            for i, dead_card in enumerate(combined_dead_pool):
                if getattr(dead_card, "is_mech", False):
                    for player in [g.narc_player, g.pcu_player]:
                        if dead_card in player.dead_pool:
                            player.dead_pool.remove(dead_card)
                            break
                    break
    # Default: pay all wind cost from card
    if ability.wind_cost > 0:
        for _ in range(ability.wind_cost):
            card.wind += 1
            record(f"{owner.name} pays 1 wind with {card.name} (now {card.wind})")
            log(f"[wind+] {owner.name}:{card.name} -> {card.wind}")
        destroy_if_needed(owner, card)
    if getattr(ability, "power_cost", 0):
        console.print("[yellow]Note: power cost present — not enforced in this build.[/yellow]")
    return True
    if c.deploy_wind > 0:
        return distribute_wind(owner, c.deploy_wind, auto=auto, allow_cancel=allow_cancel)
    return True
    if c.deploy_wind > 0:
        return distribute_wind(owner, c.deploy_wind, auto=auto, allow_cancel=allow_cancel)
    return True

    if hasattr(c, 'shackled') and c.shackled > 0:
        log(f"[deploy-block] {c.name} is shackled and cannot contribute wind to deploy.")
        if not test_mode:
            console.print(f"[red]{c.name} is shackled and cannot contribute wind to deploy this turn.[/red]")
        return
    # Nives can only be deployed if Vex is in play
    if g is not None and (c.name or '').strip().lower() == 'nives':
        vex_in_play = any((x.name or '').strip().lower() == 'vex' for x in p.field)
        if not vex_in_play:
            log("[deploy-block] Nives requires Vex in play")
            if not test_mode:
                console.print("[red]Cannot deploy Nives: Vex must be in play.[/red]")
            return

    # Dragoon can only be deployed if Krax is in play
    if g is not None and (c.name or '').strip().lower() == 'dragoon':
        krax_in_play = any((x.name or '').strip().lower() == 'krax' for x in p.field)
        if not krax_in_play:
            log("[deploy-block] Dragoon requires Krax in play")
            if not test_mode:
                console.print("[red]Cannot deploy Dragoon: Krax must be in play.[/red]")
            return

    # Prevent deploying a squad goon with the same name if already in play
    if g is not None:
        # Check both fields for same-named squad goon
        name_key = (c.name or "").strip().lower()
        if is_squad_goon(c):
            for side in (g.narc_player, g.pcu_player):
                for x in side.field:
                    if is_squad_goon(x) and (x.name or "").strip().lower() == name_key:
                        log(f"[deploy-block] squad goon duplicate: {c.name}")
                        if not test_mode:
                            console.print(f"[red]Cannot deploy {c.name}: another squad goon with the same name is already in play.[/red]")
                        return
        if conflicts_with_unique(g, c):
            log(f"[deploy-block] unique duplicate: {c.name}")
            if not test_mode:
                console.print(f"[red]Cannot deploy {c.name}: unique already in play.[/red]")
            return

    result = pay_deploy(p, c, auto=auto, allow_cancel=not auto)
    if result is None:
        import sys
        test_mode = not sys.stdin.isatty() or "--test" in sys.argv
        if not test_mode:
            console.print("Deploy  Canceled")
        record(f"{p.name} canceled deploy of {c.name}")
        log(f"[deploy-cancel] {p.name}:{c.name}")
        return
    if result is False:
        return

    c.wind = 0
    c.new_this_turn = True
    p.hand.pop(hand_idx)
    p.field.append(c)
    console.print(f"[green]Deployed {c.name}[/green]")
    log(f"[deploy] {p.name}:{c.name}")
    record(f"{p.name} deploys {c.name}")

def use_ability(g: GameState, p: Player, c_idx: int, a_idx: int, t_idx: int | None):
    # Dragoon LOYAL MOUNT: redirect wind damage from Krax to Dragoon
    if (c.name or '').strip().lower() == 'dragoon' and a.name.strip().lower() == 'loyal mount':
        krax = next((card for card in p.field if (card.name or '').strip().lower() == 'krax'), None)
        if krax:
            # Prompt for wind to redirect
            wind_to_redirect = krax.wind
            if wind_to_redirect > 0:
                krax.wind -= wind_to_redirect
                c.wind += wind_to_redirect
                record(f"Dragoon takes {wind_to_redirect} wind from Krax via Loyal Mount.")
                console.print(f"[cyan]Dragoon takes {wind_to_redirect} wind from Krax via Loyal Mount.[/cyan]")
                destroy_if_needed(p, c)
        c.used_this_turn = True
        return

    # Primordial Oozer GOOP: enemy goon targeting Oozer does not unwind next turn
    if (c.name or '').strip().lower() == 'primordial oozer' and a.name.strip().lower() == 'goop':
        # Mark enemy goon as no_unwind for next turn
        if t_idx is not None:
            e = g.pcu_player if p is g.narc_player else g.narc_player
            target = e.field[t_idx]
            target.no_unwind = True
            record(f"{target.name} is gooped and will not unwind next turn.")
            console.print(f"[magenta]{target.name} is gooped and will not unwind next turn![/magenta]")
        c.used_this_turn = True
        return

    # Local Singularity DRAW FIRE: friendly goons cannot be targeted by enemy abilities while Singularity is in play
    if (c.name or '').strip().lower() == 'local singularity' and a.name.strip().lower() == 'draw fire':
        # Set a flag on player to prevent targeting
        p.singularity_protect = True
        record(f"{p.name}'s goons are protected by Singularity DRAW FIRE.")
        console.print(f"[cyan]{p.name}'s goons are protected by Singularity DRAW FIRE.[/cyan]")
        c.used_this_turn = True
        return

    # Krax CHAIN REACTION: if Krax destroys a goon with Bash In Skull, may add 2 wind to another target, chaining
    if (c.name or '').strip().lower() == 'krax' and a.name.strip().lower() == 'chain reaction':
        # Only trigger if Bash In Skull destroyed a goon
        destroyed = False
        e = g.pcu_player if p is g.narc_player else g.narc_player
        for card in e.field:
            if card.wind >= 4:
                destroyed = True
                break
        if destroyed:
            # Prompt for chain targets
            while True:
                available = [i for i, card in enumerate(e.field) if card.wind < 4]
                if not available:
                    break
                try:
                    idx = int(Prompt.ask(f"Chain Reaction: Add 2 wind to which enemy goon? (indexes: {available})", default=str(available[0])))
                except Exception:
                    break
                if idx not in available:
                    break
                target = e.field[idx]
                target.wind += 2
                record(f"Krax Chain Reaction: {target.name} takes 2 wind.")
                console.print(f"[red]{target.name} takes 2 wind from Krax Chain Reaction![/red]")
                destroy_if_needed(e, target)
                if target.wind < 4:
                    break
        c.used_this_turn = True
        return
    # Special: Blood Howler Ballistic Barrage
    a = c.abilities[a_idx]
    if (c.name or '').strip().lower() == 'blood howler' and a.name.strip().lower() == 'ballistic barrage':
        if t_idx is None:
            console.print("[red]No target selected for Ballistic Barrage.[/red]")
            return
        # Max spend is 4 - c.wind (cannot exceed 4 wind)
        max_spend = 4 - c.wind
        if max_spend < 1:
            console.print("[red]Blood Howler is already at max wind and cannot pay more.[/red]")
            return
        if hasattr(console, 'input'):
            try:
                wind_to_spend = int(console.input(f"How much wind to spend for Ballistic Barrage? (1-{max_spend}): "))
            except Exception:
                wind_to_spend = max_spend
        else:
            wind_to_spend = max_spend
        wind_to_spend = max(1, min(wind_to_spend, max_spend))
        # Accumulate wind
        c.wind += wind_to_spend
        log(f"[wind+] {p.name}:Blood Howler -> {c.wind}")
        # Deal damage to target enemy goon
        target = g.pcu_player.field[t_idx] if p is g.narc_player else g.narc_player.field[t_idx]
        if hasattr(target, 'damage'):
            target.damage += wind_to_spend
        else:
            target.damage = wind_to_spend
        record(f"{target.name} takes {wind_to_spend} damage from Ballistic Barrage!")
        console.print(f"[red]{target.name} takes {wind_to_spend} damage from Ballistic Barrage![/red]")
        c.used_this_turn = True
        # If wind is now 4, destroy Blood Howler after effect resolves
        if c.wind >= 4:
            record(f"Blood Howler is destroyed after Ballistic Barrage!")
            console.print(f"[red]Blood Howler is destroyed after Ballistic Barrage![/red]")
            destroy_if_needed(p, c)
        return
    try:
        c = p.field[c_idx]
    except IndexError:
        return console.print("[red]Bad card index[/red]")
    if a_idx >= len(c.abilities):
        return console.print("[red]Bad ability index[/red]")
    if c.new_this_turn:
        return console.print("[red]This goon is new this turn and cannot act.[/red]")
    if c.used_this_turn:
        return console.print("[red]This goon already used an ability this turn.[/red]")
    if hasattr(c, 'shackled') and c.shackled > 0:
        return console.print(f"[red]{c.name} is shackled and cannot use abilities this turn.[/red]")
    # Special: Detainment Probe Shackle Beam
    a = c.abilities[a_idx]
    if (c.name or '').strip().lower() == 'detainment probe' and a.name.strip().lower() == 'shackle beam':
        if t_idx is None:
            console.print("[red]No target selected for Shackle Beam.[/red]")
            return
        # Target enemy goon
        target = g.pcu_player.field[t_idx] if p is g.narc_player else g.narc_player.field[t_idx]
        target.shackled = 1  # shackled for next turn
        record(f"{target.name} is shackled by Detainment Probe's Shackle Beam!")
        console.print(f"[magenta]{target.name} is shackled and cannot unwind, use abilities, or pay wind next turn![/magenta]")
        c.used_this_turn = True
        return

    a = c.abilities[a_idx]
    if a.passive:
        console.print("[yellow]This ability is passive and always in effect — cannot be used.[/yellow]")
        return

    # Special: Voidling Rally Ringer ability
    if (c.name or '').strip().lower() == 'voidling' and a.name.strip().lower() == 'rally ringer':
        # Pay 4 wind
        if c.wind < 4:
            console.print("[red]Voidling does not have enough wind to use Rally Ringer (needs 4).[/red]")
            return
        c.wind -= 4
        record(f"{p.name} pays 4 wind with Voidling for Rally Ringer")
        log(f"[wind-] {p.name}:Voidling -> {c.wind}")
        # Destroy Voidling (but ability still resolves)
        destroy_if_needed(p, c)
        # List available cards in deck (no duplicates)
        unique_names = set(card.name for card in p.deck)
        available_cards = []
        for name in unique_names:
            card = next((card for card in p.deck if card.name == name), None)
            if card:
                available_cards.append(card)
        if not available_cards:
            console.print("[yellow]No cards available in deck to rally.[/yellow]")
            return
        console.print("[bold magenta]Rally Ringer: Pick a card from your deck to move to hand:[/bold magenta]")
        for idx, card in enumerate(available_cards):
            console.print(f"[{idx}] {card.name}")
        while True:
            try:
                pick = int(Prompt.ask("Enter the number of the card to move to hand", default="0"))
                if 0 <= pick < len(available_cards):
                    chosen = available_cards[pick]
                    # Remove one instance from deck and add to hand
                    for i, card in enumerate(p.deck):
                        if card.name == chosen.name:
                            p.hand.append(p.deck.pop(i))
                            record(f"{p.name} rallies {chosen.name} to hand via Voidling Rally Ringer")
                            console.print(f"[green]{chosen.name} moved from deck to hand![/green]")
                            break
                    break
                else:
                    console.print("[red]Invalid selection. Try again.[/red]")
            except Exception:
                console.print("[red]Invalid input. Try again.[/red]")
        return
    # ...existing code...

    # Task Mistres DOMINATE ability: force enemy goon to use an ability on target of player's choice
    if (c.name or '').strip().lower() in {'task mistres', 'task mistrex'} and a.name.strip().upper() == 'DOMINATE':
        e = g.pcu_player if p is g.narc_player else g.narc_player
        # Prompt for enemy goon index
        try:
            enemy_idx = int(Prompt.ask("Choose enemy goon to dominate (index from enemy field):", default="0"))
            enemy_goon = e.field[enemy_idx]
        except Exception:
            console.print("[red]Invalid enemy goon index.[/red]")
            return
        # Prompt for ability index
        try:
            ability_idx = int(Prompt.ask(f"Choose ability to use from {enemy_goon.name} (index):", default="0"))
            forced_ability = enemy_goon.abilities[ability_idx]
        except Exception:
            console.print("[red]Invalid ability index.[/red]")
            return
        # Prompt for target (can be any goon in play)
        all_targets = p.field + e.field
        try:
            target_idx = int(Prompt.ask(f"Choose target for {enemy_goon.name}'s {forced_ability.name} (index from all goons in play):", default="0"))
            forced_target = all_targets[target_idx]
        except Exception:
            console.print("[red]Invalid target index.[/red]")
            return
        # Use the ability (simulate as if enemy goon uses it on chosen target)
        record(f"{p.name}: {c.name} uses DOMINATE to force {enemy_goon.name} to use {forced_ability.name} on {forced_target.name}")
        console.print(f"[magenta]{c.name} uses DOMINATE: {enemy_goon.name} uses {forced_ability.name} on {forced_target.name}[/magenta]")
        # Enforce ability cost for dominated goon
        can_pay = pay_ability(e, forced_ability, enemy_goon)
        if not can_pay:
            console.print(f"[red]{enemy_goon.name} cannot pay the cost for {forced_ability.name}. DOMINATE fails.[/red]")
            record(f"{enemy_goon.name} could not pay cost for DOMINATE-forced ability.")
            return
        # Apply effect (wind, heal, etc.)
        if forced_ability.inflicts_wind > 0:
            apply_wind_with_resist(e, g.pcu_player if e is g.narc_player else g.narc_player, forced_target, forced_ability.inflicts_wind)
        elif forced_ability.removes_wind > 0:
            removed = min(forced_ability.removes_wind, forced_target.wind)
            forced_target.wind -= removed
            record(f"{enemy_goon.name} removes {removed} wind from {forced_target.name}")
            console.print(f"[green]{enemy_goon.name} uses {forced_ability.name} on {forced_target.name}[/green] (DOMINATE)")
        enemy_goon.used_this_turn = True
        c.used_this_turn = True
        return

    # Targetless draw
    draw_n = a.draw_cards or _infer_draw_from_text(a.text)
    if draw_n > 0:
        for _ in range(draw_n):
            draw_card(p)
        record(f"{p.name}: {c.name} uses {a.name} — draw {draw_n} card(s)")
        console.print(f"[green]{c.name} uses {a.name}[/green] — draw {draw_n} card(s)")
        c.used_this_turn = True
        return

    # Determine sides
    is_ai_turn = (AI_NARC and p is g.narc_player) or (AI_PCU and p is g.pcu_player)
    e = g.pcu_player if p is g.narc_player else g.narc_player

    # Healing (friendly-only)
    if a.removes_wind > 0:
        if t_idx is None or t_idx < 0 or t_idx >= len(p.field):
            console.print("[red]Bad target index for friendly heal.[/red]")
            return
        target = p.field[t_idx]
        amount = a.removes_wind
        if not is_ai_turn:
            try:
                val = int(Prompt.ask(f"How much WIND to remove from {target.name}? (max {amount})", default=str(amount)))
                amount = max(0, min(amount, val))
            except Exception:
                amount = a.removes_wind
        removed = min(amount, max(0, target.wind))
        if removed > 0:
            target.wind -= removed
            record(f"{p.name} removes {removed} wind from {target.name}")
            console.print(f"[green]{c.name} uses {a.name} on {target.name}[/green] ({a.text or '—'})")
            log(f"[heal] {p.name}:{c.name}.{a.name} -> {target.name} -{removed}")
        else:
            console.print(f"[yellow]{target.name} has no wind to remove.[/yellow]")
        c.used_this_turn = True
        return

    # Offensive path: enemy targeting + resist application
    if t_idx is not None and 0 <= t_idx < len(e.field):
        target = e.field[t_idx]

        # ---------- NEW: Leader protection rule ----------
        if _is_leader_protected(e, target):
            console.print("[red]Cannot target enemy Squad Leader while they control other goons.[/red]")
            return

        # Revolting Disposition passive: add 1 wind to source if targeting a kobold with this passive
        if (getattr(target, 'name', '').strip().lower() == 'kasekobald' and
            any('revolting disposition' in (ab.name or '').strip().lower() and ab.passive for ab in target.abilities)):
            c.wind += 1
            record(f"{c.name} gains 1 wind from Revolting Disposition (targeted Kasekobald)")
            console.print(f"[yellow]{c.name} gains 1 wind from Revolting Disposition![/yellow]")

        record(f"{p.name}: {c.name} uses {a.name} on {target.name}")
        console.print(f"[green]{c.name} uses {a.name} on {target.name}[/green] ({a.text or '—'})")
        inferred = a.inflicts_wind or _infer_wind_from_text(a.text)
        if is_ai_turn:
            incoming = inferred
        else:
            if inferred > 0:
                incoming = inferred
            else:
                resp = Prompt.ask("How much WIND does this ability apply to the target?", default=str(inferred))
                try:
                    incoming = int(resp) if resp.strip() != "" else inferred
                except Exception:
                    incoming = inferred
        apply_wind_with_resist(p, e, target, incoming)
    else:
        record(f"{p.name}: {c.name} uses {a.name}")
        console.print(f"[green]{c.name} uses {a.name}[/green] ({a.text or '—'})")

    c.used_this_turn = True

# ============================== Simple AI ==============================

def _wind_capacity(p: Player) -> int:
    return sum(max(0, 3 - c.wind) for c in p.field if not c.new_this_turn)

def _ai_pick_deploy_index(p: Player, g: GameState) -> Optional[int]:
    cap = _wind_capacity(p)
    candidates: List[Tuple[int, Card]] = []
    for i, c in enumerate(p.hand):
        if c.deploy_wind <= cap:
            if conflicts_with_unique(g, c):
                continue
            candidates.append((i, c))
    if not candidates:
        return None
    candidates.sort(key=lambda ic: (ic[1].deploy_wind, -ic[1].stars, ic[1].name))
    return candidates[0][0]

def _ai_pick_ability_source(p: Player) -> Optional[Tuple[int, Ability]]:
    best: Optional[Tuple[int, Ability]] = None
    for i, c in enumerate(p.field):
        if c.new_this_turn or c.used_this_turn:
            continue
        for a in c.abilities:
            if a.passive:
                continue
            if a.inflicts_wind > 0 or a.removes_wind > 0:
                return i, a
            if best is None:
                best = (i, a)
    return best

def _ai_pick_target_idx(p: Player, e: Player, ability: Optional[Ability] = None) -> Optional[int]:
    if ability and ability.removes_wind > 0:
        candidates = [(i, x.wind) for i, x in enumerate(p.field) if x.wind > 0]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t[1])[0]
    if not e.field:
        return None
    # ---------- NEW: avoid protected leaders ----------
    legal = [i for i, c in enumerate(e.field) if not _is_leader_protected(e, c)]
    pool = legal if legal else list(range(len(e.field)))  # only leader remains → legal
    return min(pool, key=lambda i: e.field[i].wind)

def ai_take_turn(g: GameState):
    p = g.narc_player if g.active_faction == "NARC" else g.pcu_player
    e = g.pcu_player if p is g.narc_player else g.narc_player
    console.print(f"[cyan]AI ({p.name}) is thinking...[/cyan]")
    log(f"[ai] turn for {p.name}")
    record(f"AI({p.name}) begins turn")

    di = _ai_pick_deploy_index(p, g)
    if di is not None:
        console.print(f"[cyan]AI deploys hand[{di}] {p.hand[di].name}[/cyan]")
        deploy_card(p, di, auto=True, g=g)

    # Aggressive AI: focus all damaging abilities on the weakest enemy goon until destroyed
    # Find the enemy goon closest to destruction (highest wind, not protected leader)
    legal_targets = [goon for goon in e.field if not _is_leader_protected(e, goon)]
    if legal_targets:
        # Sort by wind descending (closer to destruction first), then by name
        target = sorted(legal_targets, key=lambda c: (-c.wind, c.name))[0]
        # Find all AI goons with unused damaging abilities
        for ci, c in enumerate(p.field):
            if c.new_this_turn or c.used_this_turn:
                continue
            for a in c.abilities:
                if a.passive or (a.max_uses_per_turn is not None and a.uses_this_turn >= a.max_uses_per_turn):
                    continue
                # Check for required resources in dead pool
                combined_dead_pool = g.narc_player.dead_pool + g.pcu_player.dead_pool
                meat_available = sum(1 for card in combined_dead_pool if getattr(card, "is_bio", False))
                gear_available = sum(1 for card in combined_dead_pool if getattr(card, "is_mech", False))
                if a.meat_cost > 0 and meat_available < a.meat_cost:
                    continue
                if a.gear_cost > 0 and gear_available < a.gear_cost:
                    continue
                # Friendly-only abilities: heal/support
                if a.friendly_only or a.removes_wind > 0:
                    # Find friendly target with wind > 0
                    friendly_targets = [i for i, x in enumerate(p.field) if x.wind > 0]
                    if not friendly_targets:
                        continue
                    target_idx = friendly_targets[0]
                    try:
                        use_ability(g, p, ci, a.idx, target_idx)
                        record(f"AI({p.name}) used {c.name}.{a.name} on {p.field[target_idx].name}")
                    except Exception:
                        log(f"[ai] ability failed on {c.name}")
                    continue
                # Only use abilities that inflict wind or destroy (offensive)
                damage = a.inflicts_wind or _infer_wind_from_text(a.text)
                if damage > 0 or 'destroy' in a.text.lower():
                    # Use ability on the chosen target
                    try:
                        use_ability(g, p, ci, a.idx, e.field.index(target))
                        record(f"AI({p.name}) used {c.name}.{a.name} on {target.name}")
                        # If target is destroyed, break out
                        if target.wind >= 4 or target not in e.field:
                            break
                    except Exception:
                        log(f"[ai] ability failed on {c.name}")
            # Re-evaluate target after each attack
            legal_targets = [goon for goon in e.field if not _is_leader_protected(e, goon)]
            if legal_targets:
                target = sorted(legal_targets, key=lambda c: (-c.wind, c.name))[0]
            else:
                break
    else:
        # Fallback: use any available ability
        src = _ai_pick_ability_source(p)
        if src is not None:
            ci, a = src
            ti = _ai_pick_target_idx(p, e, a)
            try:
                use_ability(g, p, ci, a.idx, ti if ti is not None else None)
                record(f"AI({p.name}) used an ability")
            except Exception:
                log(f"[ai] ability failed on {p.field[ci].name}")

# ============================== Main loop ==============================

def log(msg: str) -> None:
    if _LOG:
        _LOG.write(msg.rstrip() + "\n")
        _LOG.flush()

def record(event: str) -> None:
    msg = event.strip()
    GAME_LOG.append(msg)
    TURN_BUFFER.append(msg)
    if _GLOG:
        _GLOG.write(msg + "\n")
        _GLOG.flush()
    log(f"[ev] {msg}")

def get_next_command(prompt: str, default: Optional[str] = None) -> str:
    global _CMD_SOURCE
    if _CMD_SOURCE is None:
        _CMD_SOURCE = _build_cmd_source()
    if _CMD_SOURCE.queue:
        cmd = _CMD_SOURCE.queue.popleft()
        log(f"[cmd] {cmd}")
        return cmd
    while True:
        try:
            raw = Prompt.ask(prompt, default=default or "")
        except (KeyboardInterrupt, EOFError):
            choice = _CMD_SOURCE.default_on_interrupt
            if choice == "__RETRY__":
                print("\n(ignored; re-prompt)")
                continue
            if choice is None:
                print("\n(exiting)")
                if _LOG:
                    _LOG.close()
                if _GLOG:
                    _GLOG.write("=== game end (interrupt) ===\n")
                    _GLOG.flush()
                    _GLOG.close()
                raise SystemExit(0)
            log(f"[cmd] <interrupt->'{choice or ''}'>")
            return choice or ""
        raw = (raw or "").strip()
        if raw.lower() in {"q", "quit", "exit"}:
            if _LOG:
                _LOG.close()
            if _GLOG:
                _GLOG.write("=== game end (quit) ===\n")
                _GLOG.flush()
                _GLOG.close()
            raise SystemExit(0)
        log(f"[cmd] {raw}")
        return raw

def _build_cmd_source(argv: Optional[List[str]] = None) -> _CommandSource:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--moves", help="Comma-separated commands, e.g. d0,u0.0>0,e")
    parser.add_argument("--moves-file", help="One command per line; '#' for comments.")
    parser.add_argument("--default-on-interrupt", choices=["e", "skip", "exit", "none"], default="exit")
    parser.add_argument("--log", help="Path to transcript/debug file (append).")
    parser.add_argument("--gamelog", help="Path to write the structured game log (txt).")
    parser.add_argument("--ai", choices=["NARC", "PCU", "BOTH"], help="Enable simple AI for a side.")
    try:
        ns, _ = parser.parse_known_args(argv)
    except SystemExit:
        ns = type(
            "NS", (), {"moves": None, "moves_file": None, "default_on_interrupt": "exit", "log": None, "gamelog": None, "ai": None}
        )()

    global _LOG
    if getattr(ns, "log", None):
        try:
            _LOG = open(ns.log, "a", encoding="utf-8")
            log("=== session start ===")
        except Exception as e:
            console.print(f"[yellow]Could not open log file: {e}[/yellow]")

    global _GLOG, GAMELOG_PATH
    GAMELOG_PATH = getattr(ns, "gamelog", None)
    if not GAMELOG_PATH:
        GAMELOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_log.txt")
    try:
        _GLOG = open(GAMELOG_PATH, "a", encoding="utf-8")
        _GLOG.write("=== game start ===\n")
        _GLOG.flush()
    except Exception as e:
        console.print(f"[yellow]Could not open game log file: {e}[/yellow]")

    global AI_NARC, AI_PCU
    AI_NARC = (ns.ai in ("NARC", "BOTH"))
    AI_PCU = (ns.ai in ("PCU", "BOTH"))
    if AI_NARC or AI_PCU:
        sides = " & ".join([s for s, flag in (("NARC", AI_NARC), ("PCU", AI_PCU)) if flag])
        console.print(f"[cyan]AI enabled for: {sides}[/cyan]")
        log(f"[ai] enabled for {sides}")

    q: Deque[str] = deque()
    if getattr(ns, "moves", None):
        for t in ns.moves.split(","):
            if t.strip():
                q.append(t.strip())
    if getattr(ns, "moves_file", None):
        try:
            with open(ns.moves_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        q.append(line)
        except FileNotFoundError:
            print(f"[io] moves file not found: {ns.moves_file}")

    default_map = {"e": "e", "skip": "", "exit": None, "none": "__RETRY__"}
    return _CommandSource(queue=q, default_on_interrupt=default_map.get(ns.default_on_interrupt, None))

def main_loop_rich():
    global LAST_TURN_SUMMARY, _CMD_SOURCE
    # Ensure AI flags are set before any game logic
    if _CMD_SOURCE is None:
        _CMD_SOURCE = _build_cmd_source()

    # Determine which side is human and initial faction after AI flags are set
    if AI_NARC and not AI_PCU:
        human_side = "PCU"
    elif AI_PCU and not AI_NARC:
        human_side = "NARC"
    elif AI_NARC and AI_PCU:
        human_side = None  # Both AI
    else:
        human_side = "NARC"  # Default: human is NARC

    if human_side:
        initial_faction = human_side
        console.print(f"[bold green]You are playing as: {human_side}[/bold green]")
    else:
        initial_faction = "NARC"  # Both AI, default to NARC
        console.print(f"[bold yellow]Both sides are AI. No human turns.[/bold yellow]")

    g = start_game(initial_faction=initial_faction)
    turn = 1

    while True:
        # Assign p/e for current turn
        p = g.narc_player if g.active_faction == "NARC" else g.pcu_player
        e = g.pcu_player if p is g.narc_player else g.narc_player

        # Previous enemy turn summary
        if LAST_TURN_SUMMARY and LAST_TURN_SUMMARY.get("side") != g.active_faction:
            lines: List[str] = list(LAST_TURN_SUMMARY.get("events", []))
            if lines:
                summary = "\n".join(f"• {s}" for s in lines)
                console.print(Panel(summary, title=f"Previous Turn — {LAST_TURN_SUMMARY['side']} (Turn {LAST_TURN_SUMMARY['turn']})"))

        unwind_phase(p)
        draw_card(p)
        console.print(f"\nTURN {turn} — {g.active_faction}")
        log(f"[turn] {turn}:{g.active_faction}")
        display_field(p, e)
        display_hand(p)

        # AI turn
        is_ai_turn = (g.active_faction == "NARC" and AI_NARC) or (g.active_faction == "PCU" and AI_PCU)
        if is_ai_turn:
            ai_take_turn(g)
            display_field(p, e)
            display_hand(p)
            LAST_TURN_SUMMARY = {"side": p.name, "turn": turn, "events": TURN_BUFFER.copy()}
            TURN_BUFFER.clear()
            g.active_faction = "PCU" if g.active_faction == "NARC" else "NARC"
            turn += 1
            continue

        # Human turn only if active_faction matches human_side
        if human_side and g.active_faction == human_side:
            while True:
                cmd = get_next_command("[yellow]Your move[/yellow]")
                if cmd == "":
                    continue
                if cmd in {"e", "end"}:
                    LAST_TURN_SUMMARY = {"side": p.name, "turn": turn, "events": TURN_BUFFER.copy()}
                    TURN_BUFFER.clear()
                    g.active_faction = "PCU" if g.active_faction == "NARC" else "NARC"
                    turn += 1
                    break

                if cmd in {"s", "show"}:
                    display_field(p, e)
                    display_hand(p)
                    continue

                if cmd.startswith("d") and cmd[1:].isdigit():
                    deploy_card(p, int(cmd[1:]), g=g)
                    display_field(p, e)
                    display_hand(p)
                    continue

                if cmd.startswith("v"):
                    try:
                        parts = cmd.split()
                        if len(parts) < 2:
                            console.print("[red]Usage: v[h|f|e]#[/red]")
                        else:
                            token = parts[1]
                            scope = "h"
                            idx_str = token
                            if token and token[0].lower() in {"h", "f", "e"}:
                                scope, idx_str = token[0].lower(), token[1:]
                            idx = int(idx_str)
                            if scope == "h":
                                _open_card_image(p.hand[idx], True)
                            elif scope == "f":
                                _open_card_image(p.field[idx], True)
                            else:
                                _open_card_image(e.field[idx], True)
                    except Exception:
                        console.print("[red]Usage: v[h|f|e]#[/red]")
                    continue

                if cmd.startswith("u"):
                    try:
                        if "." in cmd:
                            body = cmd[1:]
                            if ">" in body:
                                h, t = body.split(".", 1)
                                a_idx, t_idx = t.split(">", 1)
                                use_ability(g, p, int(h), int(a_idx), int(t_idx))
                            else:
                                h, a = body.split(".", 1)
                                use_ability(g, p, int(h), int(a), None)
                        else:
                            parts = cmd.split()
                            if parts[0] == "use" and len(parts) in (3, 5):
                                c_idx = int(parts[1]); a_idx = int(parts[2])
                                t_idx = int(parts[4]) if len(parts) == 5 else None
                                use_ability(g, p, c_idx, a_idx, t_idx)
                            else:
                                console.print("[red]Bad use syntax. Try: u0.0  (no target)  or  u0.0>0[/red]")
                    except Exception:
                        console.print("[red]Bad use syntax. Try: u0.0  (no target)  or  u0.0>0[/red]")
                    display_field(p, e)
                    display_hand(p)
                    continue

                console.print("[red]Unknown[/red]")
        else:
            # If not human turn, just advance to next turn
            g.active_faction = "PCU" if g.active_faction == "NARC" else "NARC"
            turn += 1

# Entry point: start the game loop if run as a script
if __name__ == "__main__":
    main_loop_rich()