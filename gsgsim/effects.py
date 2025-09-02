from __future__ import annotations

from typing import Any, Iterable, Mapping


def _to_targets(targets: Any) -> list:
    if targets is None:
        return []
    if isinstance(targets, (list, tuple, set)):
        return list(targets)
    return [targets]


def op_mark(gs: Any, source: Any, targets: Iterable[Any], spec: Mapping[str, Any]) -> bool:
    """Mark each target with .marked = True. If no targets provided, mark source."""
    ts = list(targets) or [source]
    for t in ts:
        setattr(t, "marked", True)
    return True


_OPS = {
    "mark": op_mark,
}


def run_effect(gs: Any, source: Any, targets: Iterable[Any], spec: Mapping[str, Any]) -> bool:
    """Run a single effect spec: {"op": "mark", ...}"""
    if not isinstance(spec, Mapping):
        return False
    op = str(spec.get("op", "")).lower()
    fn = _OPS.get(op)
    if not fn:
        # unknown op -> refuse (safe default)
        return False
    return bool(fn(gs, source, targets, spec))


def run_effects(gs: Any, source: Any, targets: Iterable[Any] | None, effects: Iterable[Mapping[str, Any]]) -> bool:
    """Run a sequence of effects; all must succeed."""
    ts = _to_targets(targets)
    ok = True
    for spec in effects or []:
        ok = run_effect(gs, source, ts, spec) and ok
    return ok
