from __future__ import annotations

import os

from rich.console import Console
from rich.table import Table

from ..models import Card, GameState

try:
    from .. import engine_rule_shim
except Exception:
    engine_rule_shim = None


def rank_icon(card: Card) -> str:
    r = getattr(card, "rank", None)
    if isinstance(r, str):
        return "⭐" if r.upper() == "SL" else "BG"
    if hasattr(r, "name"):
        return "⭐" if str(r.name).upper() == "SL" else str(r.name)
    return "?"


def cost_str(card) -> str:
    return f"{getattr(card, 'deploy_wind', 0)}⟲ {getattr(card, 'deploy_gear', 0)}⛭ {getattr(card, 'deploy_meat', 0)}⚈"


def _parse_d_cmd(tok: str):
    """Accepts 'd 3', 'd3', 'dd 2', 'dd2' and returns ('d'|'dd', index) or (None, None)."""
    t = (tok or "").strip()
    if t.startswith("dd") and t[2:].isdigit():
        return ("dd", int(t[2:]))
    if t.startswith("d") and len(t) > 1 and t[1:].isdigit():
        return ("d", int(t[1:]))
    return (None, None)


class RichUI:
    def __init__(self) -> None:
        self.console = Console()

    def _print_ai_banner(self) -> None:
        self.console.print(
            """[bold]Tip:[/bold] Type [bold]ai[/bold] to have the [bold]current player[/bold] act once.
Use [bold]ai p1[/bold] or [bold]ai p2[/bold] to target a side.
Deploy with [bold]dN[/bold] or [bold]d N[/bold]; end turn with [bold]e[/bold] or [bold]end[/bold]."""
        )

    def _check_game_over(self, gs: GameState) -> bool:
        if engine_rule_shim and hasattr(engine_rule_shim, "check_sl_loss"):
            loser = engine_rule_shim.check_sl_loss(gs)
            if loser is not None:
                winner = "P1" if loser == "P2" else "P2"
                self.console.print(f"[bold]Game over! Winner: {winner}[/bold]")
                return True
        return False

    def render(self, gs: GameState) -> None:
        c = self.console
        c.print(f"Turn {gs.turn_number} | Player: {'P1' if gs.turn_player is gs.p1 else 'P2'}")

        def board_table(title: str, player) -> Table:
            t = Table(title=title)
            t.add_column("#", justify="right", style="cyan")
            t.add_column("Name")
            t.add_column("Wind", justify="right")
            t.add_column("Abilities")
            for i, card in enumerate(getattr(player, "board", [])):
                abil = getattr(card, "abilities", []) or []
                names = []
                for idx, a in enumerate(abil):
                    n = getattr(a, "name", a)
                    names.append(f"{idx}:{n}")
                abil_txt = ", ".join(names) if names else "-"
                fstr = _resolve_faction(player, card)
                name_txt = _name_with_icons(card, fstr)
                t.add_row(
                    str(i),
                    name_txt,
                    str(getattr(card, "wind", 0)),
                    abil_txt,
                )
            return t

        c.print(board_table("Board P1", gs.p1))
        c.print(board_table("Board P2", gs.p2))

        def hand_table(title: str, player) -> Table:
            t = Table(title=f"{title} hand ({len(player.hand)})")
            t.add_column("#", justify="right", style="cyan")
            t.add_column("Name")
            t.add_column("Cost")
            for i, card in enumerate(player.hand):
                t.add_row(str(i), _name_with_icons(card, getattr(player, "faction", None)), cost_str(card))
            return t

        if gs.turn_player is gs.p1:
            c.print(hand_table("P1", gs.p1))
        else:
            c.print(hand_table("P2", gs.p2))

    def run_loop(self, gs: GameState, ai_p1: bool = False, ai_p2: bool = False, auto: bool = False):
        # Local imports so tests/monkeypatch can override engine pieces
        from ..engine import end_of_turn, use_ability_cli

        # Merge environment flags if explicit args not set
        if not (ai_p1 or ai_p2):
            env_ai = (os.environ.get("GSG_AI") or "").strip().lower()
            if env_ai == "both":
                ai_p1 = ai_p2 = True
            elif env_ai == "p1":
                ai_p1 = True
            elif env_ai == "p2":
                ai_p2 = True
        if not auto:
            auto = bool(os.environ.get("GSG_AUTO"))

        # One-time banners
        control = "P1+P2" if (ai_p1 and ai_p2) else ("P1" if ai_p1 else ("P2" if ai_p2 else "none"))
        if control != "none":
            self.console.print(f"[bold]AI control:[/bold] {control}  (auto={'on' if auto else 'off'})")
        self._print_ai_banner()

        while True:
            if self._check_game_over(gs):
                break

            self.render(gs)

            # If auto mode or the current side is AI-controlled, let the AI act and continue without a prompt
            do_ai = auto or (ai_p1 and gs.turn_player is gs.p1) or (ai_p2 and gs.turn_player is gs.p2)
            if do_ai:
                try:
                    from ..ai import ai_take_turn

                    prev_player = gs.turn_player
                    ai_take_turn(gs)
                    # If AI didn't advance the turn, do it here to avoid tight loops
                    if gs.turn_player is prev_player:
                        end_of_turn(gs)
                except Exception as e:
                    self.console.print(f"[red]AI error:[/red] {e}")
                continue

            # Human input branch
            try:
                line = self.console.input("> ").strip()
            except Exception:
                break

            if line in ("quit", "q"):
                break
            if line in ("end", "e"):
                end_of_turn(gs)
                continue

            parts = line.split()

            # deploy: d N | dN  and  dd N | ddN (deploy then end turn)
            if parts and (parts[0] == "d" or parts[0] == "dd" or parts[0].startswith("d")):
                kind, idx = _parse_d_cmd(parts[0])
                if kind is None and len(parts) >= 2 and parts[1].isdigit():
                    if parts[0] in ("d", "dd"):
                        kind = parts[0]
                        idx = int(parts[1])
                if kind and isinstance(idx, int):
                    try:
                        from ..engine import deploy_from_hand

                        if deploy_from_hand(gs, gs.turn_player, idx):
                            if kind == "dd":
                                end_of_turn(gs)
                        else:
                            self.console.print("deploy failed")
                    except Exception as e:
                        self.console.print(f"deploy error: {e}")
                    continue

            # ability use: u SRC ABIL [TARGETSPEC]
            if len(parts) >= 3 and parts[0] == "u" and parts[1].isdigit() and parts[2].isdigit():
                src = int(parts[1])
                abil = int(parts[2])
                spec = parts[3] if len(parts) >= 4 else None
                try:
                    use_ability_cli(gs, src, abil, spec)
                except Exception as e:
                    self.console.print(f"use error: {e}")
                continue

            # manual wind payment: pay AMOUNT p1|p2:idx[xN][,idx[xM] ...] [force]
            if parts and parts[0] == "pay" and len(parts) >= 3 and parts[1].isdigit():
                amount = int(parts[1])
                spec = " ".join(parts[2:])
                try:
                    from ..engine import pay_cli

                    pay_cli(gs, amount, spec)
                except Exception as e:
                    self.console.print(f"pay error: {e}")
                continue

            self.console.print(
                "commands: help | quit(q) | end(e) | dN|d N | ddN|dd N | " "u <src> <abil> [targets] | pay <amount> p1|p2:idxxN[,idxxM] | ai [p1|p2]  " "(start flags: --ai p1|p2|both, --auto)"
            )


# ==== icon helpers (final override) ====
def _safe_str(x):
    try:
        return str(x)
    except Exception:
        return ""


def _icons_has(card, name: str) -> bool:
    try:
        lst = getattr(card, "icons", None)
        if not lst:
            return False
        return name.lower() in {str(x).strip().lower() for x in lst}
    except Exception:
        return False


def _is_true(card, *names):
    for n in names:
        if hasattr(card, n):
            v = getattr(card, n)
            if isinstance(v, str):
                if v.strip().lower() in ("1", "true", "yes", "y", "on"):
                    return True
            if v:
                return True
    return False


def _rank_icon_for_name(card):
    r = getattr(card, "rank", None)
    tag = None
    if isinstance(r, str):
        tag = r.upper()
    elif hasattr(r, "name"):
        tag = _safe_str(getattr(r, "name", "")).upper()
    if tag == "SL":
        return "⭐"
    if tag == "SG":
        return "🔶"
    if tag == "T":
        return "Ω"
    return ""  # BG => no icon


def _bio_mech_icon(card):
    out = []
    if _is_true(card, "biological", "is_bio", "bio") or _icons_has(card, "biological"):
        out.append("🥩")
    if _is_true(card, "mechanical", "is_mech", "mech") or _icons_has(card, "mechanical"):
        out.append("⚙️")
    return "".join(out)


def _resist_icon(card):
    return "✋" if _is_true(card, "resist", "has_resist") or _icons_has(card, "resist") else ""


def _no_unwind_icon(card):
    return "🚫" if _is_true(card, "no_unwind") or _icons_has(card, "no_unwind") else ""


def _resolve_faction(player, card):
    # prefer player.faction → player.name → card.faction → icons
    for obj, attr in ((player, "faction"), (player, "name"), (card, "faction")):
        try:
            v = getattr(obj, attr, None)
            if v:
                return _safe_str(v).upper()
        except Exception:
            pass
    if _icons_has(card, "narc"):
        return "NARC"
    if _icons_has(card, "pcu"):
        return "PCU"
    return ""


def _faction_icon_from_str(f):
    f = (f or "").upper()
    if f == "NARC":
        return "🚨"
    if f == "PCU":
        return "🌀"
    return ""


def _locked_icon(card):
    # "just deployed and cannot act this turn"
    if _is_true(card, "just_deployed"):
        return "🔒"
    if getattr(card, "turns_in_play", None) == 0:
        return "🔒"
    return ""


def _name_with_icons(card, faction_str):
    # NAME + [rank][resist][no_unwind][bio|mech][faction][locked] — no spaces
    name = _safe_str(getattr(card, "name", "?"))
    pieces = [
        _rank_icon_for_name(card),
        _faction_icon_from_str(faction_str),
        _bio_mech_icon(card),
        _resist_icon(card),
        _no_unwind_icon(card),
        _locked_icon(card),
    ]
    return f"{name}{''.join(p for p in pieces if p)}"


# ==== end helpers (final override) ====
