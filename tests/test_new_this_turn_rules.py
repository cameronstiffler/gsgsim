import types


def mk_player(name, board):
    return types.SimpleNamespace(name=name, board=list(board), hand=[])


def mk_card(name, rank="BG", wind=0, new_this_turn=False, abilities=None):
    return types.SimpleNamespace(
        name=name, rank=rank, wind=wind, new_this_turn=new_this_turn, abilities=abilities or []
    )


def test_new_this_turn_cannot_pay_wind_when_only_option():
    from gsgsim.payments import distribute_wind

    fresh = mk_card("Fresh BG", rank="BG", wind=0, new_this_turn=True)
    p = mk_player("P1", [fresh])
    # Need 1 wind, but only payer is new_this_turn -> should refuse
    assert distribute_wind(p, 1) is False
    assert fresh.wind == 0


def test_new_this_turn_is_ignored_if_older_payer_available():
    from gsgsim.payments import distribute_wind

    fresh = mk_card("Fresh BG", rank="BG", wind=0, new_this_turn=True)
    old = mk_card("Old BG", rank="BG", wind=0, new_this_turn=False)
    p = mk_player("P1", [fresh, old])
    assert distribute_wind(p, 1) is True
    assert fresh.wind == 0
    assert old.wind == 1


def test_new_this_turn_cannot_use_active_ability():
    # Uses abilities layer (active) — must be blocked if new_this_turn
    from types import SimpleNamespace as NS

    from gsgsim.abilities import use_ability

    gs = NS()  # minimal dummy GameState for registry
    fresh = mk_card("Target Marker Probe", rank="BG", new_this_turn=True, abilities=["MARK TARGET"])
    # Even if ability exists, because card is new_this_turn, active use must fail.
    ok = use_ability(gs, fresh, 0)
    assert ok is False


def test_old_card_can_use_active_ability():
    from types import SimpleNamespace as NS

    from gsgsim.abilities import use_ability

    gs = NS()
    old = mk_card("Target Marker Probe", rank="BG", new_this_turn=False, abilities=["MARK TARGET"])
    ok = use_ability(gs, old, 0)
    assert ok is True
