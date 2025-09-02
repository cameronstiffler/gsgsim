import types


def mk_player(name, board):
    p = types.SimpleNamespace(name=name, board=list(board), hand=[])
    return p


def mk_card(name, rank="BG", wind=0, new_this_turn=False):
    c = types.SimpleNamespace(name=name, rank=rank, wind=wind, new_this_turn=new_this_turn)
    return c


def test_prefers_non_sl_then_safe_sl():
    # Arrange: SL at wind 2 (safe capacity 1), plus a BG with 2 capacity
    from gsgsim.payments import distribute_wind

    sl = mk_card("Lokar Simmons", rank="SL", wind=2)
    bg = mk_card("Shield Array Node", rank="BG", wind=1)  # cap = 3
    p = mk_player("P1", [sl, bg])

    # Act: cost 2 should take 2 from BG first; SL untouched (stays at 2)
    ok = distribute_wind(p, 2)
    assert ok
    assert sl.wind == 2
    assert bg.wind == 3  # took 2


def test_uses_safe_sl_when_needed():
    from gsgsim.payments import distribute_wind

    sl = mk_card("Lokar Simmons", rank="SL", wind=2)  # safe +1
    bg = mk_card("Target Marker Probe", rank="BG", wind=3)  # cap +1
    p = mk_player("P1", [sl, bg])

    # Need 2: should take 1 from BG (to 4) and 1 safe from SL (to 3)
    ok = distribute_wind(p, 2)
    assert ok
    assert sl.wind == 3
    assert bg.wind == 4  # might be destroyed by your rules after payment (engine may clean that up)


def test_refuses_lethal_only_sl():
    from gsgsim.payments import distribute_wind

    sl = mk_card("Lokar Simmons", rank="SL", wind=3)  # lethal if we take 1
    p = mk_player("P1", [sl])

    # Need 1: only way is lethal SL -> should refuse in auto mode
    ok = distribute_wind(p, 1)
    assert not ok
