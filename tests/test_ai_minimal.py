import types


def mk_card(name, cost=0, abil=None):
    return types.SimpleNamespace(
        name=name, deploy_wind=cost, abilities=abil or [], rank="BG", wind=0
    )


class Ability:
    def __init__(self, name, cost=None, effects=None, passive=False):
        self.name = name
        self.cost = cost or {}
        self.effects = effects or []
        self.passive = passive


def test_ai_deploys_free_then_ends():
    from gsgsim.ai import ai_take_turn

    gs = types.SimpleNamespace(
        turn_player=types.SimpleNamespace(board=[], hand=[mk_card("Freebie", 0)]), p1=None, p2=None
    )

    def end_turn(g):
        setattr(g, "ended", True)

    # monkeypatch engine.end_of_turn via attribute (ai imports in function; we simulate by adding)
    from gsgsim import ai as mod

    mod.end_of_turn = end_turn
    ai_take_turn(gs)
    assert gs.turn_player.board and getattr(gs, "ended", False)


def test_ai_uses_zero_cost_effect():
    from gsgsim.abilities import registers
    from gsgsim.ai import ai_take_turn

    called = {"ok": 0}

    @registers("Tool", 0)
    def _ok(gs, card, targets):
        called["ok"] += 1
        return True

    gs = types.SimpleNamespace(
        turn_player=types.SimpleNamespace(
            board=[mk_card("Tool", 0, [Ability("PING", cost={"wind": 0}, effects=[])])], hand=[]
        ),
        p1=None,
        p2=None,
    )

    def end_turn(g):
        setattr(g, "ended", True)

    from gsgsim import ai as mod

    mod.end_of_turn = end_turn
    ai_take_turn(gs)
    assert called["ok"] == 1 and getattr(gs, "ended", False)
