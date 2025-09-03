from __future__ import annotations

from typing import Mapping


def _to_list(x):
    if not x:
        return []
    return list(x) if isinstance(x, (list, tuple, set)) else [x]


def op_mark(gs, source, targets, spec):
    ts = _to_list(targets) or [source]
    for t in ts:
        setattr(t, "marked", True)
    return True


def op_shield(gs, source, targets, spec):
    n = int(spec.get("n", 0) or 0)
    ts = _to_list(targets) or [source]
    for t in ts:
        cur = int(getattr(t, "shield", 0) or 0)
        setattr(t, "shield", cur + n)
    return True


def op_damage(gs, source, targets, spec):
    n = int(spec.get("n", 0) or 0)
    if n <= 0:
        return False
    ts = targets if targets else [source]
    for t in ts:
        d = n
        sh = int(getattr(t, "shield", 0) or 0)
        use = min(sh, d)
        if use:
            setattr(t, "shield", sh - use)
            d -= use
        if d > 0:
            cur = int(getattr(t, "damage", 0) or 0)
            setattr(t, "damage", cur + d)
    return True


def op_draw(gs, source, targets, spec):
    n = int(spec.get("n", 0) or 0)
    if n <= 0:
        return False
    player = getattr(gs, "turn_player", None)
    draw = getattr(gs, "draw", None)
    if callable(draw) and player is not None:
        draw(player, n)
        return True
    return False


_OPS = {
    "mark": op_mark,
    "shield": op_shield,
    "damage": op_damage,
    "draw": op_draw,
}


def run_effect(gs, source, targets, spec):
    if not isinstance(spec, Mapping):
        return False
    fn = _OPS.get(str(spec.get("op", "")).lower())
    return bool(fn and fn(gs, source, _to_list(targets), spec))


def run_effects(gs, source, targets, effects):
    ok = True
    for spec in effects or []:
        ok = run_effect(gs, source, targets, spec) and ok
    return ok
