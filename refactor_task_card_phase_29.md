

# Refactor Task Card — Phase 29

## Context
The simulator runs, but smoke test revealed several bugs and polish issues.  
We must fix these **without breaking working functionality**.  
Preserve the **Import Sentry** (all imports at the top, ordered & deduplicated).

---

## Required Fixes

### 1. Enum Rank Display
- Current output shows `Rank.SL`, `Rank.SG`, `Rank.BG`.  
- **Fix**: Adjust `__str__` or `__repr__` in `Rank` enum, or when printing, use `.name` instead of full enum repr.  
  - Example: `str(c.rank.name)` → prints just `SL`, `SG`, `BG`.

---

### 2. Enforce Deploy Costs
- Right now, cards deploy for free.  
- Add a cost check in `deploy_from_hand`:
  - Before placing on board:
    - Check `deploy_wind`, `deploy_gear`, `deploy_meat`.
    - Wind must be distributed via `distribute_wind`.
    - Gear and Meat must be burned from Dead Pool (mechanical/biological as appropriate).
  - If cost cannot be paid → fail deploy gracefully (`print("deploy failed")`).

---

### 3. Starting Hand Draw
- Players currently may be drawing one extra card at the start.  
- Fix logic in `main()`:
  - Both players draw **exactly 6 cards** at setup.
  - At start of turn, **only the active player** draws 1 card.
  - Ensure `start_of_turn(gs)` doesn’t double-draw on the very first turn.

---

### 4. Graceful Quit
- Wrapping `ui.run_loop(gs)`:
  ```python
  try:
      ui.run_loop(gs)
  except (KeyboardInterrupt, EOFError):
      print("\nExiting game.")
      return

	•	Prevents tracebacks when player presses Ctrl-C/D.

⸻

5. UI Polish
	•	Reduce vertical whitespace in Rich UI rendering:
	•	Pass padding=(0,0) and collapse_padding=True when constructing Table.
	•	Remove unnecessary blank print("\n") between sections.
	•	Goal: compact, clean board and hand view with no large empty gaps.

⸻

Additional Safeguards
	•	After implementing, run flake8 and black again.
	•	Verify deploy, use ability, and turn cycle manually (smoke test).
	•	Ensure no duplication of run_loop methods (one in TerminalUI, one in RichUI).

⸻

Reminder for Copilot
	•	Do not relocate working code (keep imports at top, Import Sentry enforced).
	•	Do not strip functionality (all helpers like distribute_wind, apply_wind_with_resist must remain).
	•	Add only the missing fixes above.

⸻
