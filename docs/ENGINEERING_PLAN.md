# GSG Sim – Stability Guardrails

## Invariants (must hold at all times)
- Deploy: `dN` moves hand[N] -> board; sets `just_deployed=True`.
- Start of Turn: clears `just_deployed` for the active player's board.
- Wind Rule: any increase to wind must route through `rules.apply_wind*` and auto-retire at wind >= 4.
- Resist: hostile wind uses `apply_wind_with_resist(..., hostile=True)` (reduces incoming +1).
- No circular imports: payments -> rules; engine -> (payments, rules); UI -> engine.
- No duplicate helpers: a helper is defined once (rules or engine), imported elsewhere.

## Process
1. Small feature branches only.
2. Before commit:
   - `python -m compileall -q gsgsim`
   - `scripts/smoke.sh` passes (deploy, pay, KO).
   - `pre-commit run -a` passes.
3. Before merge:
   - Grep confirms no direct wind writes:
     `grep -RIn -E "wind[\\+\\-]=|setattr\\(.*,'wind'|\\.wind\\s*=" gsgsim`
4. After merge:
   - Tag a restore point: `git tag -a sim-stable-YYYYMMDD-HHMMSS -m "stable"`.

## Module boundaries
- `rules.py`: apply_wind, apply_wind_with_resist, destroy_if_needed, cannot_spend_wind.
- `payments.py`: payment/distribution; imports ONLY from rules.
- `engine.py`: turn flow, deploy wrapper, ability bridges; may import payments and rules.
- `ui/`: never mutates game rules; only calls engine.

## CLI contract
- `dN | d N` deploy
- `u <src> <abil> [targets...]` ability
- `pay <amount> p1|p2:idx[,idx]` manual pay
- `e|end` end turn
- `ai [p1|p2]` one AI action
- `--ai p1|p2|both`, `--auto` startup flags


## Guardrails: Rule imports & symbol drift

- **No unused `rules` imports in engine modules.** If a file imports from `gsgsim.rules`, every imported name must be referenced in that file. The pre-commit hook `check-rules-import-usage` enforces this.
- **No deprecated symbols in repo.** Banned identifiers (e.g., `deploy_cli`) must not appear in the tree. The pre-commit hook `ban-deprecated-symbols` enforces this.
- **Wind writes still forbidden.** CI greps for direct `.wind` mutations; all changes must go through `rules.apply_wind*`.
