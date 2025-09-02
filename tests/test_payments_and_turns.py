from gsgsim.models import Player, GameState, Card, Rank
from gsgsim.engine import deploy_from_hand, start_of_turn, end_of_turn
from gsgsim.rules import destroy_if_needed

def mk_state():
    p1 = Player("A"); p2 = Player("B")
    gs = GameState(p1, p2, p1, "main", 1)
    return gs

def test_transactional_wind_no_partial():
    gs = mk_state()
    payer = Card(name="Grim", rank=Rank.SL)
    expensive = Card(name="BigBoy", rank=Rank.BG); expensive.deploy_wind = 5
    gs.turn_player.board.append(payer)
    gs.turn_player.hand.append(expensive)
    ok = deploy_from_hand(gs, gs.turn_player, 0)  # cannot fully pay 5
    assert not ok
    assert payer.wind == 0  # no partial wind

def test_retire_at_4_wind_during_payment():
    gs = mk_state()
    payer = Card(name="Grim", rank=Rank.SL)
    c = Card(name="Voidling", rank=Rank.BG); c.deploy_wind = 4
    gs.turn_player.board.append(payer)
    gs.turn_player.hand.append(c)
    ok = deploy_from_hand(gs, gs.turn_player, 0)
    assert ok
    assert payer not in gs.turn_player.board  # retired
    assert any(x.name == "Grim" for x in gs.turn_player.retired)

def test_new_this_turn_cannot_pay():
    gs = mk_state()
    p = gs.turn_player
    a = Card(name="Helper", rank=Rank.BG)
    b = Card(name="Costs2", rank=Rank.BG); b.deploy_wind = 2
    p.hand.extend([a, b])
    # deploy a (it will be new_this_turn and can’t pay)
    assert deploy_from_hand(gs, p, 0)
    # try to deploy b — with only a new goon on board, this should fail
    ok = deploy_from_hand(gs, p, 0)
    assert not ok
    # end turn clears new_this_turn; now it should work if you have bodies
    end_of_turn(gs);  # flips to B and draws; start_of_turn runs automatically