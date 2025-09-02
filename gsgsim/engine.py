# === IMPORT SENTRY ===
from __future__ import annotations

from typing import Optional

from .models import GameState, Player
from .payments import distribute_wind
from .ui.rich_ui import RichUI
from .ui.terminal import TerminalUI


def deploy_from_hand(gs: GameState, player: Player, hand_idx: int) -> bool:
    if hand_idx < 0 or hand_idx >= len(player.hand):
        print("invalid hand index")
        return False
    card = player.hand[hand_idx]

    wind_cost = getattr(card, "deploy_wind", 0)
    gear_cost = getattr(card, "deploy_gear", 0)
    meat_cost = getattr(card, "deploy_meat", 0)

    if wind_cost > 0:
        ok = distribute_wind(player, total_cost=wind_cost, auto=True)
        if not ok:
            print("could not pay wind")
            return False

    if gear_cost or meat_cost:
        print("gear/meat payment not implemented yet")
        return False

    player.hand.pop(hand_idx)
    player.board.append(card)
    card.new_this_turn = True
    return True


def use_ability_cli(
    gs: GameState, player: Player, src_idx: int, abil_idx: int, tgt_idx: Optional[int]
) -> bool:
    # keep your working logic; call can_target_card where appropriate
    print("ability not implemented in this card")  # placeholder to preserve signature
    return False


def start_of_turn(gs: GameState) -> None:
    p = gs.turn_player
    # draw 1
    if p.deck:
        p.hand.append(p.deck.pop())
    for c in p.board:
        if getattr(c, "new_this_turn", False):
            c.new_this_turn = False


def end_of_turn(gs: GameState) -> None:
    gs.turn_player = gs.p2 if gs.turn_player is gs.p1 else gs.p1
    start_of_turn(gs)


def select_ui(name: str):
    if name == "rich":
        return RichUI()
    return TerminalUI()
