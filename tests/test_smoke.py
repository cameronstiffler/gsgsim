# tests/test_smoke.py
import types

def test_import_and_compile():
    import gsg_sim  # noqa: F401

def test_player_constructor_accepts_board_kwarg():
    from gsg_sim import Player
    p = Player("X", board=[], hand=[], deck=[], retired=[])
    assert p.name == "X" and p.board == []

def test_distribute_wind_signature_and_call():
    from gsg_sim import Player, Card, distribute_wind
    a = Card(name="A", rank=None, abilities=[], wind=0)
    p = Player("P", board=[a], hand=[], deck=[], retired=[])
    assert distribute_wind(p, 0) is True