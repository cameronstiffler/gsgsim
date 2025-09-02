from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .abilities import use_ability
from .models import GameState, Player
from .payments import distribute_wind

Chooser = Callable[[List[Tuple[int, object, int]], int], Optional[List[Tuple[int, int]]]]


def deploy_from_hand(gs: GameState, player: Player, hand_idx: int, chooser: Optional[Chooser] = None) -> bool:
    if hand_idx < 0 or hand_idx >= len(player.hand):
        print("invalid hand index")
        return False

    card = player.hand[hand_idx]
    wind_cost = getattr(card, "deploy_wind", 0)
    gear_cost = getattr(card, "deploy_gear", 0)
    meat_cost = getattr(card, "deploy_meat", 0)
    if gear_cost or meat_cost:
        # Not implemented in this build
        print("could not pay wind")
        return False

    # Pay wind
    if not distribute_wind(player, wind_cost, chooser=chooser):
        print("refused: paying wind would require lethal SL payment or no eligible payers")
        return False

    # Move card to board
    player.board.append(card)
    player.hand.pop(hand_idx)
    # initialize flags
    if not hasattr(card, "wind"):
        card.wind = 0
    card.new_this_turn = True
    return True


def start_of_turn(gs: GameState) -> None:
    # Clear new_this_turn on the ACTIVE player's board at the start of their turn
    p = gs.turn_player
    for c in getattr(p, "board", []):
        c.new_this_turn = False


def end_of_turn(gs: GameState) -> None:
    # Pass turn and then clear new_this_turn for the next player
    gs.turn_player = gs.p2 if gs.turn_player is gs.p1 else gs.p1
    gs.turn_number += 1
    start_of_turn(gs)


def use_ability_cli(gs, src_idx: int, abil_idx: int, target_spec: str | None = None) -> None:
    try:
        card = gs.turn_player.board[src_idx]
    except Exception:
        print("ability failed")
        return
    targets = parse_targets(target_spec or "", gs)
    ok = use_ability(gs, card, abil_idx, targets)
    print("ability ok" if ok else f'ability failed (passive/new/handler/cost): {getattr(card, "name", "<??>")} [{abil_idx}]')
    return


def select_ui(name: str):
    """Lazy import to avoid engine<->UI circular imports."""
    if name and name.lower() == "rich":
        from .ui.rich_ui import RichUI

        return RichUI()
    from .ui.terminal import TerminalUI

    return TerminalUI()


def parse_targets(spec: str, gs) -> list:
    spec = (spec or "").strip()
    if not spec:
        return []
    side, _, rest = spec.partition(":")
    side = side.lower()
    player = gs.p1 if side in ("p1", "self", "me") else gs.p2
    if rest.lower() == "all":
        return list(getattr(player, "board", []))
    idxs = []
    for tok in rest.split(","):
        tok = tok.strip()
        if tok.isdigit():
            idxs.append(int(tok))
    out = []
    board = list(getattr(player, "board", []))
    for i in idxs:
        if 0 <= i < len(board):
            out.append(board[i])
    return out


def parse_payplan(spec: str):
    """Return (side, plan:list[(idx, amt)], force:bool). 'spec' like 'p1:0x2,3x1 [force]'."""
    spec = (spec or "").strip()
    tokens = spec.split()
    if not tokens:
        return None, [], False
    base = tokens[0]
    force = any(t.lower() == "force" for t in tokens[1:])
    side, _, rest = base.partition(":")
    side = side.lower()
    plan = []
    for part in filter(None, (p.strip() for p in rest.split(","))):
        if "x" in part:
            i, x, a = part.partition("x")
            if i.isdigit() and a.isdigit():
                plan.append((int(i), int(a)))
        else:
            # default 1 if no 'xN'
            if part.isdigit():
                plan.append((int(part), 1))
    return side, plan, force


def pay_cli(gs, amount: int, spec: str) -> None:
    from .payments import manual_pay

    side, plan, force = parse_payplan(spec)
    player = gs.p1 if side in ("p1", "self", "me") else gs.p2
    ok = manual_pay(player, amount, plan, allow_lethal_sl=force)
    print("pay ok" if ok else "pay failed")
