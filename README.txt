
GSGSIM PATCHES – 2025-09-02

Files included (replace these into your repo at the same paths):

- gsgsim/abilities.py        (NEW) – registry + minimal handlers
- gsgsim/payments.py         (REPLACE) – auto-plan avoids lethal SL; manual via chooser still allowed
- gsgsim/engine.py           (REPLACE) – deploy + start/end turn + use_ability_cli hook
- gsgsim/ui/rich_ui.py       (REPLACE) – game-over guard + "u <src> <abil>" command

Notes:
- Auto deploy will refuse to sacrifice an SL to pay wind. You'll see "could not pay wind".
  Use your existing manual allocation path (if present in your UI) to intentionally sacrifice.
- The ability handlers are placeholders—effects are no-ops except flipping simple flags.
  The point is to remove the "ability not implemented" dead-end and give you a clear place to add logic.

