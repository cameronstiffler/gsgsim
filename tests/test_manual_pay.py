import types


def mk_player(board):
    return types.SimpleNamespace(board=list(board), hand=[])


def mk_card(name, rank="BG", wind=0):
    return types.SimpleNamespace(name=name, rank=rank, wind=wind)


def test_manual_pay_non_sl_ok():
    from gsgsim.payments import manual_pay

    p = mk_player([mk_card("BG1"), mk_card("BG2")])
    assert manual_pay(p, 2, [(0, 1), (1, 1)], allow_lethal_sl=False) is True
    assert p.board[0].wind == 1 and p.board[1].wind == 1


def test_manual_pay_refuses_lethal_sl_without_force():
    from gsgsim.payments import manual_pay

    p = mk_player([mk_card("Lokar", rank="SL", wind=3)])
    assert manual_pay(p, 1, [(0, 1)], allow_lethal_sl=False) is False
    assert p.board[0].wind == 3


def test_manual_pay_allows_lethal_sl_with_force():
    from gsgsim.payments import manual_pay

    p = mk_player([mk_card("Lokar", rank="SL", wind=3)])
    assert manual_pay(p, 1, [(0, 1)], allow_lethal_sl=True) is True
    assert p.board[0].wind == 4
