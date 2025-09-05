from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ..models import Card, GameState

try:
    from .. import engine_rule_shim
except Exception:
    engine_rule_shim = None


# ---------- icon/name helpers ----------


def _safe_str(x) -> str:
    try:
        return str(x)
    except Exception:
        return "?"


def _is_true(obj, *keys) -> bool:
    for k in keys:
        try:
            v = getattr(obj, k, None)
            if isinstance(v, bool):
                if v:
                    return True
            elif isinstance(v, (int, str)):
                if str(v).strip().lower() in ("1", "true", "yes", "y", "on"):
                    return True
            elif v:
                return True
        except Exception:
            pass
    return False


def _icons_has(card: Card, token: str) -> bool:
    try:
        icons = getattr(card, "icons", None) or []
        return token.lower() in {str(x).strip().lower() for x in icons}
    except Exception:
        return False


def _rank_icon_for_name(card: Card) -> str:
    r = getattr(card, "rank", None)
    tag = None
    if isinstance(r, str):
        tag = r.strip().upper()
    elif hasattr(r, "name"):
        tag = _safe_str(getattr(r, "name", "")).strip().upper()
    if tag == "SL":
        return "⭐"
    if tag == "SG":
        return "🔶"
    if tag == "T":
        return "Ω"
    return ""


def _bio_mech_icon(card: Card) -> str:
    out = []
    if _is_true(card, "biological", "is_bio", "bio") or _icons_has(card, "biological"):
        out.append("🥩")
    if _is_true(card, "mechanical", "is_mech", "mech") or _icons_has(card, "mechanical"):
        out.append("⚙️")
    return "".join(out)


def _resist_icon(card: Card) -> str:
    return "✋" if _is_true(card, "resist", "has_resist") or _icons_has(card, "resist") else ""


def _no_unwind_icon(card: Card) -> str:
    return "🚫" if _is_true(card, "no_unwind") or _icons_has(card, "no_unwind") else ""


def _resolve_faction(player, card) -> str:
    for obj, attr in ((player, "faction"), (player, "name"), (card, "faction")):
        try:
            v = getattr(obj, attr, None)
            if v:
                vu = _safe_str(v).upper()
                if "NARC" in vu:
                    return "NARC"
                if "PCU" in vu:
                    return "PCU"
        except Exception:
            pass
    if _icons_has(card, "narc"):
        return "NARC"
    if _icons_has(card, "pcu"):
        return "PCU"
    return ""


def _faction_icon(f: str) -> str:
    fu = (f or "").upper()
    if fu == "NARC":
        return "🚨"
    if fu == "PCU":
        return "🌀"
    return ""


def _locked_icon(card: Card) -> str:
    if _is_true(card, "just_deployed"):
        return "🔒"
    try:
        if getattr(card, "turns_in_play", None) == 0:
            return "🔒"
    except Exception:
        pass
    return ""


def _name_with_icons(card: Card, faction_str: str) -> str:
    name = _safe_str(getattr(card, "name", "?"))
    pieces = [
        _rank_icon_for_name(card),
        _resist_icon(card),
        _no_unwind_icon(card),
        _bio_mech_icon(card),
        _faction_icon(faction_str),
        _locked_icon(card),
    ]
    return f"{name}{''.join(p for p in pieces if p)}"


def cost_str(card: Card) -> str:
    try:
        w = int(getattr(card, "deploy_wind", 0) or 0)
        g = int(getattr(card, "deploy_gear", 0) or 0)
        m = int(getattr(card, "deploy_meat", 0) or 0)
    except Exception:
        w = g = m = 0
    return f"{w}⟲ {g}⛭ {m}⚈"


# ---------- Rich UI ----------


def _parse_d_cmd(tok: str):
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
                abil = getattr(card, "abilities", [])
                abil_txt = (
                    ", ".join(f"{idx}:{name}" for idx, name in enumerate(abil)) if abil else "-"
                )
                t.add_row(
                    str(i),
                    _name_with_icons(card, _resolve_faction(player, card)),
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
                t.add_row(
                    str(i),
                    _name_with_icons(card, _resolve_faction(player, card)),
                    cost_str(card),
                )
            return t

        if gs.turn_player is gs.p1:
            c.print(hand_table("P1", gs.p1))
        else:
            c.print(hand_table("P2", gs.p2))

    def run_loop(self, gs: GameState, ai_p1: bool = False, ai_p2: bool = False, auto: bool = False):
        from ..ai import ai_take_turn
        from ..engine import deploy_from_hand, end_of_turn, use_ability_cli

        self._print_ai_banner()

        while True:
            if self._check_game_over(gs):
                break

            self.render(gs)

            if auto and (
                (gs.turn_player is gs.p1 and ai_p1) or (gs.turn_player is gs.p2 and ai_p2)
            ):
                prev = gs.turn_player
                ai_take_turn(gs)
                if gs.turn_player is prev:
                    end_of_turn(gs)
                continue

            try:
                line = self.console.input("> ").strip()
            except KeyboardInterrupt:
                break
            except Exception:
                break

            if not line:
                continue

            if line in ("quit", "q", "exit"):
                break

            if line in ("end", "e"):
                end_of_turn(gs)
                continue

            parts = line.split()

            if parts[0] == "ai":
                if len(parts) == 1:
                    prev = gs.turn_player
                    ai_take_turn(gs)
                    if gs.turn_player is prev:
                        end_of_turn(gs)
                else:
                    side = parts[1].lower()
                    side_player = gs.p1 if side in ("p1", "1") else gs.p2
                    original = gs.turn_player
                    gs.turn_player = side_player
                    prev = gs.turn_player
                    ai_take_turn(gs)
                    if gs.turn_player is prev:
                        end_of_turn(gs)
                    gs.turn_player = original
                continue

            # replacing if (parts[0].startswith("d") and parts[0][1:].isdigit()) or (parts[0] == "d" and len(parts) >= 2 and parts[1].isdigit()):
            # replacing continue

            # deploy shortcuts: dN | d N | ddN
            kind, idx = _parse_d_cmd(parts[0]) if parts else (None, None)
            if kind and idx is not None:
                # allow "d N" form
                if parts[0] == "d" and len(parts) >= 2 and parts[1].isdigit():
                    idx = int(parts[1])

                try:
                    ok = deploy_from_hand(gs, gs.turn_player, idx)
                    print("deploy ok" if ok else "deploy failed: cannot pay / illegal")
                except Exception as e:
                    print(f"deploy error: {e}")
                continue

            if len(parts) >= 3 and parts[0] == "u" and parts[1].isdigit() and parts[2].isdigit():
                src = int(parts[1])
                abil = int(parts[2])
                spec = parts[3] if len(parts) >= 4 else None
                use_ability_cli(gs, src, abil, spec)
                continue

            if parts[0] == "pay" and len(parts) >= 3 and parts[1].isdigit():
                amt = int(parts[1])
                spec = parts[2]
                from ..engine import manual_pay_cli

                manual_pay_cli(gs, amt, spec)
                continue

            self.console.print(
                "commands: help | quit(q) | end(e) | dN|d N | ddN|dd N | "
                "u <src> <abil> | pay <amount> p1|p2:idx[,idx] | ai [p1|p2]  "
                "(start flags: --ai p1|p2|both, --auto)  See: gamerules.md"
            )
