# Usage: python scripts/wrap_rich_ui_refusal.py
# This injects a clearer message when distribute_wind() returns False during deploy_from_hand().
import re
from pathlib import Path

p = Path("gsgsim/engine.py")
s = p.read_text()

# Look for deploy_from_hand(...) and the check on distribute_wind(...)
pat = r"(if\s+not\s+distribute_wind\([^\)]*\):\s*\n\s*)([^\n]*\n)"
m = re.search(pat, s)
if m:
    before = s
    # After the existing print, add a hint line:
    inject = (
        m.group(1)
        + '        print("refused: paying wind would require lethal SL payment or no eligible payers")\n'
    )
    s = s.replace(m.group(0), inject)
    if s != before:
        p.write_text(s)
        print("OK: engine.py updated with clearer refusal message.")
    else:
        print("No change made (pattern already updated).")
else:
    print("Pattern not found; no change made.")
