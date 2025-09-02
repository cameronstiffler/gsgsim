from __future__ import annotations
from typing import Optional, Callable, List, Tuple
from .models import GameState, Player
from .payments import distribute_wind
from .abilities import use_ability

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
        # payments module prints an error line already
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


def use_ability_cli(gs: GameState, src_idx: int, abil_idx: int) -> None:
    """CLI-friendly wrapper: try to execute ability; print a crisp status."""
    try:
        card = gs.turn_player.board[src_idx]
    except Exception:
        print("ability failed")
        return
    ok = use_ability(gs, card, abil_idx)
    if ok:
        print("ability ok")
    else:
        name = getattr(card, "name", "<?>")
        print(f"ability not implemented: {name} [{abil_idx}]")


def select_ui(name: str):
    """Lazy import to avoid engine<->UI circular imports."""
    if name and name.lower() == "rich":
        from .ui.rich_ui import RichUI
        return RichUI()
    from .ui.terminal import TerminalUI
    return TerminalUI()
