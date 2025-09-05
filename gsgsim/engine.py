from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .abilities import use_ability
from .models import GameState, Player
from .payments import distribute_wind
from .rules import cannot_spend_wind

Chooser = Callable[[List[Tuple[int, object, int]], int], Optional[List[Tuple[int, int]]]]


def deploy_from_hand(
    gs: GameState, player: Player, hand_idx: int, chooser: Optional[Chooser] = None
) -> bool:
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
    if not distribute_wind(gs, player, wind_cost, chooser=chooser):
        print("refused: paying wind would require lethal SL payment or no eligible payers")
        # fallback: if only SL can pay, force SL payment of the full wind cost
        try:
            from .payments import manual_pay

            # determine wind cost from the card being deployed
            try:
                cw = int(getattr(card, "deploy_wind", 0) or 0)
            except NameError:
                cw = 0
            sl_idx = None
            for i, c2 in enumerate(getattr(player, "board", [])):
                rnk = getattr(c2, "rank", "")
                if (isinstance(rnk, str) and rnk.upper() == "SL") or (
                    hasattr(rnk, "name") and str(rnk.name).upper() == "SL"
                ):
                    sl_idx = i
                    break
            if (
                sl_idx is not None
                and cw > 0
                and manual_pay(player, cw, [(sl_idx, cw)], allow_lethal_sl=True)
            ):
                print("auto-pay fallback: forced SL payment accepted")
            else:
                return False
        except Exception:
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
    print(
        "ability ok"
        if ok
        else f'ability failed (passive/new/handler/cost): {getattr(card, "name", "<??>")} [{abil_idx}]'
    )
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


# === canonical wind mutation and checks (rules-backed) ===
def add_wind_and_check(gs, card, delta: int) -> int:
    """Mutate wind by delta. KO and retire at >= 4. Return applied delta."""
    old = int(getattr(card, "wind", 0) or 0)
    new = max(0, old + int(delta))
    card.wind = new

    # KO at 4+ wind
    if new >= 4:
        owner = None
        if hasattr(gs, "p1") and card in getattr(gs.p1, "board", []):
            owner = gs.p1
        elif hasattr(gs, "p2") and card in getattr(gs.p2, "board", []):
            owner = gs.p2
        if owner:
            try:
                owner.board.remove(card)
            except ValueError:
                pass
            owner.retired.append(card)
    return new - old


def manual_pay(gs, total: int, targets: list[tuple[str, int]]) -> bool:
    """
    Spend 'total' wind across target board indices (p1|p2,idx).
    Applies KO-at-4 immediately via add_wind_and_check.
    """
    if total <= 0:
        return True

    pool = []
    for side, idx in targets:
        pl = gs.p1 if side == "p1" else gs.p2
        try:
            c = pl.board[idx]
        except Exception:
            continue
        if not cannot_spend_wind(c):
            pool.append(c)

    paid = 0
    # greedy round-robin, 1 wind at a time
    while paid < total and pool:
        progressed, next_pool = False, []
        for c in pool:
            # skip if already retired
            if c not in getattr(gs.p1, "board", []) and c not in getattr(gs.p2, "board", []):
                continue
            add_wind_and_check(gs, c, +1)
            paid += 1
            progressed = True
            if (
                c in getattr(gs.p1, "board", []) or c in getattr(gs.p2, "board", [])
            ) and not cannot_spend_wind(c):
                next_pool.append(c)
            if paid >= total:
                break
        pool = next_pool
        if not progressed:
            break

    return paid >= total


def manual_pay_cli(gs, amount: int, target_spec: str) -> None:
    from .engine import parse_targets

    targets = parse_targets(target_spec, gs)
    ok = manual_pay(gs, amount, targets)
    print("pay ok" if ok else "pay failed (insufficient eligible goons)")
