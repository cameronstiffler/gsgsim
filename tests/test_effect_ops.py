import types


def mk_player(board):
    return types.SimpleNamespace(board=list(board), hand=[])


def mk_card(name):
    return types.SimpleNamespace(name=name)


def test_shield_and_damage_absorb():
    from gsgsim.effects import run_effects

    gs = types.SimpleNamespace(turn_player=None)
    a = mk_card("A")
    b = mk_card("B")
    ok = run_effects(gs, a, [a, b], [{"op": "shield", "n": 2}])
    assert ok and getattr(a, "shield", 0) == 2 and getattr(b, "shield", 0) == 2
    ok = run_effects(gs, a, [a, b], [{"op": "damage", "n": 1}])
    assert ok and getattr(a, "shield", 0) == 1 and getattr(b, "shield", 0) == 1
    ok = run_effects(gs, a, [a, b], [{"op": "damage", "n": 3}])
    # 1 shield absorbed, 2 damage applied
    assert getattr(a, "shield", 0) == 0 and getattr(b, "shield", 0) == 0
    assert getattr(a, "damage", 0) == 2 and getattr(b, "damage", 0) == 2


def test_draw_calls_engine_draw():
    from gsgsim.effects import run_effects

    drawn = {"n": 0}

    def draw(player, n):
        drawn["n"] += n

    p1 = mk_player([])
    gs = types.SimpleNamespace(turn_player=p1, draw=draw)
    ok = run_effects(gs, mk_card("S"), None, [{"op": "draw", "n": 2}])
    assert ok and drawn["n"] == 2
