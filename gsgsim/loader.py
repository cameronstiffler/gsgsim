# === IMPORT SENTRY ===
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .models import Ability, Card, Rank


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


def build_cards(deck_obj: Dict[str, Any], *, faction: Optional[str] = None) -> List[Card]:
    cards: List[Card] = []
    for raw in deck_obj.get("goons", []):
        name = raw["name"]
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
            abilities.append(Ability(a.get("name", "ABILITY"), cost, [], passive=passive))

        cards.append(
            Card(
                name=name,
                rank=rank,
                faction=faction,
                traits=traits,
                abilities=abilities,
                deploy_wind=dw,
                deploy_gear=dg,
                deploy_meat=dm,
            )
        )
    return cards


def find_squad_leader(cards: List[Card]) -> Optional[Card]:
    for c in cards:
        if c.rank == Rank.SL:
            return c
    return None


# === Back-compat: normalize icons array to explicit booleans ===
def _normalize_card_flags(d: dict, default_faction: str | None = None) -> dict:
    """
    Accepts either old 'icons' list or explicit boolean fields.
    Explicit booleans take precedence if present.
    - icons: ["narc","pcu","biological","mechanical","resist","no_unwind"]
    - new:   faction: "NARC"|"PCU", biological: bool, mechanical: bool, resist: bool, no_unwind: bool
    """
    icons = set((d.get("icons") or []))
    icons = {str(x).strip().lower() for x in icons}

    # faction: explicit wins; else from icons; else default_faction
    if "faction" not in d or not d["faction"]:
        if "narc" in icons:
            d["faction"] = "NARC"
        elif "pcu" in icons:
            d["faction"] = "PCU"
        elif default_faction:
            d["faction"] = default_faction

    # boolean flags: explicit wins; else from icons; else False
    def _set_bool(key: str, icon_name: str):
        if key not in d:
            d[key] = icon_name in icons

    _set_bool("biological", "biological")
    _set_bool("mechanical", "mechanical")
    _set_bool("resist", "resist")
    _set_bool("no_unwind", "no_unwind")

    return d
