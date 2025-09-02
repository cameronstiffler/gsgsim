from __future__ import annotations
from typing import Optional
from .models import GameState, Player
from .payments import distribute_wind

def deploy_from_hand(gs: GameState, player: Player, hand_idx: int) -> bool:
    if hand_idx < 0 or hand_idx >= len(player.hand):
        print("invalid hand index")
        return False
    card = player.hand[hand_idx]
    wind_cost = getattr(card, "deploy_wind", 0)
    gear_cost = getattr(card, "deploy_gear", 0)
    meat_cost = getattr(card, "deploy_meat", 0)

    # Pay wind
    if wind_cost > 0:
        if not distribute_wind(player, total_cost=wind_cost, auto=True):
            print("could not pay wind")
            return False

    # (Optional) Gear/Meat not implemented yet
    if gear_cost or meat_cost:
        print("gear/meat payment not implemented yet")
        return False

    player.hand.pop(hand_idx)
    player.board.append(card)
    card.new_this_turn = True
    return True

def use_ability_cli(gs: GameState, player: Player, src_idx: int, abil_idx: int, tgt_idx: Optional[int]) -> bool:
    # Placeholder: wire real abilities here
    print("ability not implemented in this build")
    return False

def start_of_turn(gs: GameState) -> None:
    p = gs.turn_player
    # draw 1
    if p.deck:
        p.hand.append(p.deck.pop())
    # clear summoning sickness
    for c in p.board:
        c.new_this_turn = False

def end_of_turn(gs: GameState) -> None:
    gs.turn_player = gs.p2 if gs.turn_player is gs.p1 else gs.p1
    gs.turn_number += 1
    start_of_turn(gs)

def select_ui(name: str):
    """Lazy import to avoid engine<->UI circular imports."""
    if name and name.lower() == "rich":
        from .ui.rich_ui import RichUI
        return RichUI()
    from .ui.terminal import TerminalUI
    return TerminalUI()
