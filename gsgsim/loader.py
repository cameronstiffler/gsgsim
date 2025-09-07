# === IMPORT SENTRY ===
from __future__ import annotations

import json
import re
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from .models import Ability
from .models import Card
from .models import Rank


def load_deck_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_rank(text: str | None) -> Rank:
    map_ = {
        "sl": Rank.SL,
        "squad leader": Rank.SL,
        "sg": Rank.SG,
        "bg": Rank.BG,
        "titan": Rank.TITAN,
        "tn": Rank.TN,
        "basic goon": Rank.BG,  # fallback for your data
    }
    t = (text or "").strip().lower()
    return map_.get(t, Rank.BG)


def build_cards(deck_obj: Dict[str, Any], faction: Optional[str] = None) -> List[Card]:
    cards: List[Card] = []
    for raw in deck_obj.get("goons", []):
        raw = _normalize_card_flags(raw, default_faction=faction)
        goon_name = raw["name"]
        rank = parse_rank(raw.get("rank", "Basic Goon"))
        traits = set(raw.get("icons", []))

        # deploy costs (tokens like "2w", "1g", "3m")
        dw = dg = dm = 0
        for tok in raw.get("deploy_cost", []):
            s = str(tok or "").strip().lower()
            m = re.fullmatch(r"(\d+)\s*([wgm])", s)
            if not m:
                continue
            n = int(m.group(1))
            kind = m.group(2)
            if kind == "w":
                dw += n
            elif kind == "g":
                dg += n
            elif kind == "m":
                dm += n

        abilities: List[Ability] = []
        for a in raw.get("abilities", []):
            cost: Dict[str, int] = {}
            passive = False
            for ctok in a.get("cost", []):
                t = str(ctok or "").strip().lower()
                if t == "p":
                    passive = True
                    continue
                m = re.fullmatch(r"(\d+)\s*([wgm])", t)
                if not m:
                    continue
                n = int(m.group(1))
                k = m.group(2)
                key = {"w": "wind", "g": "gear", "m": "meat"}[k]
                cost[key] = cost.get(key, 0) + n
            # effect inference minimal (keep as-is)
            aname = a.get("name", "ABILITY")
            ab = Ability(aname, cost, [], passive=passive)
            setattr(ab, "text", a.get("text", ""))
            abilities.append(ab)

        card = Card(
            name=goon_name,
            rank=rank,
            faction=faction,
            traits=traits,
            abilities=abilities,
            deploy_wind=dw,
            deploy_gear=dg,
            deploy_meat=dm,
        )
        _apply_card_flags(card, raw)
        cards.append(card)
    return cards


def find_squad_leader(cards: List[Card]) -> Optional[Card]:
    for c in cards:
        if c.rank == Rank.SL:
            return c
    return None


# === Back-compat + normalization for card flags ===
def _normalize_card_flags(d: dict, default_faction: str | None = None) -> dict:
    """
    Supports either explicit booleans or legacy 'icons' list.
    Produces: faction, biological, mechanical, resist, no_unwind on the dict.
    """
    icons = {str(x).strip().lower() for x in (d.get("icons") or [])}

    # faction
    if not d.get("faction"):
        if "narc" in icons:
            d["faction"] = "NARC"
        elif "pcu" in icons:
            d["faction"] = "PCU"
        elif default_faction:
            d["faction"] = default_faction

    def ensure_bool(key: str, token: str):
        if key not in d:
            d[key] = token in icons

    ensure_bool("biological", "biological")
    ensure_bool("mechanical", "mechanical")
    ensure_bool("resist", "resist")
    ensure_bool("no_unwind", "no_unwind")
    return d


def _apply_card_flags(card, data: dict) -> None:
    """
    Ensure the Card instance exposes booleans the UI expects.
    Explicit booleans beat icons. Keep icons on card as fallback.
    """
    icons = {str(x).strip().lower() for x in (data.get("icons") or [])}

    def val(key: str, token: str) -> bool:
        return bool(data.get(key, False) or (token in icons))

    for attr, token in (
        ("biological", "biological"),
        ("mechanical", "mechanical"),
        ("resist", "resist"),
        ("no_unwind", "no_unwind"),
    ):
        try:
            if not getattr(card, attr, False):
                setattr(card, attr, val(attr, token))
        except Exception:
            pass

    # Keep a copy of icons on the card so UI can read it if needed
    try:
        if not getattr(card, "icons", None) and icons:
            card.icons = list(icons)
    except Exception:
        pass
