import dataclasses as _dc
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Tuple
import json
import sys
import os
import re


class Rank(Enum):
    BG = auto()
    SG = auto()
    SL = auto()
    TITAN = auto()


@dataclass
class Status:
    name: str
    expires: Any = None
    tags: set[str] = _dc.field(default_factory=set)


@dataclass
class Effect:
    op: str
    args: Dict[str, Any]


@dataclass
class Ability:
    name: str
    cost: Dict[str, Any]
    effects: List[Effect]
    timing: str = "activated"
    limit_per_turn: Optional[int] = 1


@dataclass
class Card:
    name: str
    rank: Rank
    traits: set[str] = _dc.field(default_factory=set)
    abilities: List[Ability] = _dc.field(default_factory=list)
    wind: int = 0
    new_this_turn: bool = False
    used_this_turn: int = 0
    statuses: Dict[str, Status] = _dc.field(default_factory=dict)


@dataclass
class Player:
    name: str
    board: list["Card"] = _dc.field(default_factory=list)  # was `field`
    hand: list["Card"] = _dc.field(default_factory=list)
    dead_pool: list["Card"] = _dc.field(default_factory=list)
    retired: list["Card"] = _dc.field(default_factory=list)
    gear: int = 0
    meat: int = 0
    power: int = 0


@dataclass
class GameState:
    p1: Player
    p2: Player
    turn_player: Player
    phase: str = "start"


def is_negative_effect(ability: Ability) -> bool:
    for eff in ability.effects:
        op = eff.op.lower()
        if op in ("add_wind", "destroy"):
            return True
        if op == "grant_status":
            status = (eff.args or {}).get("status", "").lower()
            if status in {"shackled", "no_unwind", "blind"}:
                return True
    return False


def can_target_card(
    gs: GameState,
    source: Card,
    target: Card,
    owner: Player,
    enemy: Player,
    ability: Ability,
) -> bool:
    if target.rank == Rank.TITAN:
        return False
    if target.rank == Rank.SL and any(
        c for c in enemy.board if c is not target and c.rank != Rank.SL
    ):
        return False
    if "cover" in target.statuses and owner is not enemy:
        return False
    defender = enemy if target in enemy.board else owner
    node_count = sum(
        1 for c in defender.board if c.name.strip().lower() == "shield array node"
    )
    if node_count >= 2 and is_negative_effect(ability) and owner is not defender:
        return False
    singularity = next(
        (c for c in enemy.board if c.name.strip().lower() == "local singularity"), None
    )
    if singularity and singularity is not target:
        if can_target_card(gs, source, singularity, owner, enemy, ability):
            return False
    return True


def distribute_wind(owner: Player, total: int) -> bool:
    to_pay = total
    for c in owner.board:
        if c.rank == Rank.TITAN or c.new_this_turn or ("shackled" in c.statuses):
            continue
        while to_pay > 0:
            c.wind += 1
            to_pay -= 1
            if to_pay == 0:
                break
    return to_pay == 0


def pay_cost(
    gs: GameState,
    owner: Player,
    ability: Ability,
    pending_destroy: List[Tuple[Player, Card]],
) -> bool:
    wind_cost = int(ability.cost.get("wind", 0))
    gear_cost = int(ability.cost.get("gear", 0))
    meat_cost = int(ability.cost.get("meat", 0))
    power_cost = int(ability.cost.get("power", 0))
    if wind_cost > 0:
        if not distribute_wind(owner, wind_cost):
            return False
        for c in owner.board:
            if c.wind >= 4:
                pending_destroy.append((owner, c))
    if owner.gear < gear_cost or owner.meat < meat_cost or owner.power < power_cost:
        return False
    owner.gear -= gear_cost
    owner.meat -= meat_cost
    owner.power -= power_cost
    return True


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


def post_resolve_cleanup(
    gs: GameState, pending_destroy: List[Tuple[Player, Card]]
) -> None:
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
                apply_wind_with_resist(
                    src_owner, enemy, target, int(args.get("amount", 0))
                )
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


def parse_rank(rank_text: str) -> Rank:
    t = rank_text.strip().lower()
    if t.startswith("basic"):
        return Rank.BG
    if t.startswith("squad goon"):
        return Rank.SG
    if t.startswith("squad leader"):
        return Rank.SL
    if t.startswith("titan"):
        return Rank.TITAN
    return Rank.BG


def build_cards(deck_obj: Dict[str, Any]) -> List[Card]:
    """
    Build Card objects from a deck JSON.
    - Cost parsing is robust: accepts only "<int><w|g|m>" tokens (e.g., 1w, 2g, 3m) and "p".
      Unknown tokens (like "x") are ignored safely.
    - Effect inference kept minimal just so the engine can run.
    """
    cards: List[Card] = []
    for raw in deck_obj.get("goons", []):
        name = raw["name"]
        rank = parse_rank(raw.get("rank", "Basic Goon"))
        traits = set(raw.get("icons", []))
        abilities: List[Ability] = []

        for a in raw.get("abilities", []):
            # ---- robust cost parsing ----
            cost: Dict[str, int] = {}
            for raw_tok in a.get("cost", []):
                tok = str(raw_tok or "").strip().lower()
                if tok == "p":
                    cost["power"] = cost.get("power", 0) + 1
                    continue
                m = re.fullmatch(r"(\d+)\s*([wgm])", tok)
                if not m:
                    # Ignore unknown/free-text tokens like 'x'
                    continue
                n = int(m.group(1))
                kind = m.group(2)
                key = {"w": "wind", "g": "gear", "m": "meat"}[kind]
                cost[key] = cost.get(key, 0) + n

            # ---- minimal effect inference so things run ----
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
            elif (
                "cover" in (raw.get("name") or "").lower()
                or "may not be targeted" in text
            ):
                effects.append(
                    Effect(
                        "grant_status",
                        {"status": "cover", "expires": ("start_of_turn", "owner")},
                    )
                )

            abilities.append(Ability(a.get("name", "ABILITY"), cost, effects))

        cards.append(Card(name=name, rank=rank, traits=traits, abilities=abilities))
    return cards


def main():
    narc = load_deck_json("narc_deck.json")
    pcu = load_deck_json("pcu_deck.json")
    narc_cards = build_cards(narc)
    pcu_cards = build_cards(pcu)
    p1 = Player("NARC", board=[c for c in narc_cards if c.rank == Rank.SL][:1])
    p2 = Player("PCU", board=[c for c in pcu_cards if c.rank == Rank.SL][:1])
    if not p1.board or not p2.board:
        print("Both decks must contain a Squad Leader to start.")
        sys.exit(1)
    print(
        "GSG engine ready. Decks loaded. SLs on field. (Run abilities via your CLI/UI harness.)"
    )


if __name__ == "__main__":
    main()
