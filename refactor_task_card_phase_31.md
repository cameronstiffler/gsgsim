# Refactor Task Card — Audit Fixes (v30)

**Goal:** Apply precise, surgical fixes found in audit of the current `gsg_sim.py`. Do not move the import header beyond the sentry, do not duplicate functions, do not change public APIs or semantics. Keep lines ≤ 100.

---

## A) Import Sentry & Header Hygiene

1. **Add/ensure Import Sentry at the very top** (line 1; nothing above it):
```python
# ===== IMPORTS SENTRY: DO NOT MOVE OR INSERT ANYTHING ABOVE THIS LINE =====
from __future__ import annotations

# Standard library imports
import argparse
import json
import os
import random
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Deque, Dict, List, Optional, TextIO, Tuple, Callable

# Third-party imports
from rich.console import Console
from rich.table import Table

# ===== END IMPORTS SENTRY =====
```
2. **Remove the standalone** `from typing import Callable` line near the top (it’s duplicated) and rely on the `Callable` imported in the sentry block.

---

## B) Eliminate Duplicates / Stubs

1. **Duplicate `Rank` enum**: two definitions exist (around lines ~207 and ~228).  
   - **Keep the first** `class Rank(Enum):` block.
   - **Delete** the second `class Rank(Enum):` block completely.

2. **Stub `distribute_wind` at ~216** (wrong signature `distribute_wind(gs, player, card, wind)`):  
   - **Delete this stub** entirely.
   - Keep the **real** `distribute_wind(owner, total, *, auto=False, allow_cancel=False)` defined later (~790+).

> After these removals, confirm there is exactly **one** `class Rank` and **one** `def distribute_wind` in the file.

---

## C) Consistency: `board` not `field`

Replace lingering uses of `.field` with `.board` and fix GameState player names:

1. **`conflicts_with_unique(g, c)`** (around ~680s):  
   - Replace `(g.narc_player, g.pcu_player)` iteration with `(g.p1, g.p2)`.
   - Replace `for x in side.field:` with `for x in side.board:`.

2. **`_has_leader_protectors(owner)`** (around ~704–708):  
   - Replace `owner.field` with `owner.board`.

3. **`destroy_if_needed(owner, c)`** (around ~735–740):  
   - Replace the membership/removal on `owner.field` with `owner.board`:
     ```python
     if c in owner.board:
         owner.board.remove(c)
     ```

---

## D) Owner selection bug in Effect resolution

In the effect stack `resolve()` (~878–885), the enemy owner is computed incorrectly:
```python
enemy = g.p2 if src_owner is g.p1 else g.p2  # BUG: both branches g.p2
```
**Fix**:
```python
enemy = g.p2 if src_owner is g.p1 else g.p1
```

This ensures effects like `add_wind` and `destroy` attribute the pending destroy to the correct opposing owner.

---

## E) Graceful Quit in both UIs

Wrap the input loop to handle Ctrl-C/EOF without tracebacks.

### TerminalUI.run_loop
```python
def run_loop(self, gs):
    HELP = (
        "commands: help | quit(q) | end(e) | "
        "deploy(d) <hand_idx> | use(u) <src_idx> <abil_idx> [tgt_idx]"
    )
    print(HELP)
    try:
        while True:
            self.render(gs)
            try:
                line = input("> ").strip()
            except EOFError:
                print("\nBye.")
                break
            if not line:
                continue
            # ... existing command dispatch ...
    except KeyboardInterrupt:
        print("\nBye.")
```

### RichUI.run_loop
Mirror the same pattern, replacing `input`/`print` with `self.console.input`/`self.console.print`.

---

## F) Rank display (already mostly fixed)

Where ranks are printed in both UIs, keep:
```python
rank = getattr(c, "rank", "?")
rank_str = rank.name if hasattr(rank, "name") else str(rank)
```
and use `rank_str` in table rows/string renders so output shows `SL/SG/BG` rather than `Rank.SL`.

---

## G) Post-Edit Verification

Run:
```bash
isort gsg_sim.py
autoflake --in-place --remove-all-unused-imports --remove-unused-variables gsg_sim.py
black gsg_sim.py --line-length 100
flake8 gsg_sim.py --max-line-length=100
python -m py_compile gsg_sim.py
python gsg_sim.py --ui rich
```

**Acceptance Criteria:**
- No duplicate `Rank` or `distribute_wind` definitions.
- No `.field` references remain; all use `.board`.
- Effect `enemy` owner chosen correctly (`p2` if `src_owner` is `p1`, else `p1`).
- Ctrl-C/EOF exits cleanly in both UIs.
- `flake8` and `py_compile` pass; simulator runs the smoke test without regressions.
