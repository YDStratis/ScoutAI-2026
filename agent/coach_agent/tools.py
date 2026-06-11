"""Deterministic coaching tools for the Scout.AI Coach Agent.

These tools read REAL BALLDONTLIE World Cup 2026 data from MongoDB Atlas and
compute every score in Python (never the LLM). They are written defensively
because imported API documents have varied shapes.

Data realities this layer adapts to (verified against the `scoutai` database):
  * Roster/player positions are coarse single letters: G, D, M, F. Granular
    slots (GK, LB, CB, RB, DM, CM, CAM, RW, ST, LW ...) are DERIVED here for
    tactical analysis and are clearly labelled as derived, not verified data.
  * Rosters (`bdl_rosters`) are just player<->team<->season links; their stat
    fields are empty. The only real performance signal is `bdl_player_match_stats`
    (rating, expected_goals, expected_assists, tackles, dribbles, ...), joined to
    a player by `player_id` == roster `player.id`.
  * Team names are resolved from numeric `team_id` via `teams` / `bdl_teams`.

Anti-hallucination contract: tools return `{"error": ...}` or partial results
with a `missing_data` / `limitations` list and a `source` block (collections +
ids). They never invent stats. Derived tactical attributes are flagged derived.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId

from .db import get_db
from .schemas import (
    COL_BDL_PLAYER_MATCH_STATS,
    COL_BDL_ROSTERS,
    COL_BDL_TEAMS,
    COL_LINEUPS,
    COL_MATCHUP_REPORTS,
    COL_PLAYER_ATTRIBUTES,
    COL_PLAYERS,
    COL_RECOMMENDATIONS,
    COL_TASK_PLANS,
    COL_TEAMS,
)

DEFAULT_SEASON = 2026

# ---- Formation templates: granular slots derived from coarse G/D/M/F buckets ----
FORMATIONS: Dict[str, List[str]] = {
    "4-3-3": ["GK", "RB", "CB", "CB", "LB", "DM", "CM", "CM", "RW", "ST", "LW"],
    "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "DM", "DM", "RW", "CAM", "LW", "ST"],
    "4-4-2": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"],
    "3-5-2": ["GK", "CB", "CB", "CB", "RWB", "CM", "CM", "CM", "LWB", "ST", "ST"],
}
DEFAULT_FORMATIONS = ["4-3-3", "4-2-3-1"]

# Slot -> coarse position bucket it should be filled from.
_SLOT_BUCKET = {
    "GK": "G",
    "RB": "D", "LB": "D", "CB": "D", "RWB": "D", "LWB": "D",
    "DM": "M", "CM": "M", "CAM": "M", "RM": "M", "LM": "M",
    "RW": "F", "LW": "F", "ST": "F", "CF": "F",
}
# Slot -> line for matchup pairing.
_SLOT_LINE = {
    "GK": "GK",
    "RB": "DEF", "LB": "DEF", "CB": "DEF", "RWB": "DEF", "LWB": "DEF",
    "DM": "MID", "CM": "MID", "CAM": "MID", "RM": "MID", "LM": "MID",
    "RW": "ATT", "LW": "ATT", "ST": "ATT", "CF": "ATT",
}
# Slot -> pitch zone. Mirror left<->right when two teams face each other.
_SLOT_ZONE = {
    "RB": "right", "RWB": "right", "RM": "right", "RW": "right",
    "LB": "left", "LWB": "left", "LM": "left", "LW": "left",
    "GK": "center", "CB": "center", "DM": "center", "CM": "center",
    "CAM": "center", "ST": "center", "CF": "center",
}
_MIRROR = {"left": "right", "right": "left", "center": "center"}

# Weak-link thresholds.
WEAK_RATING = 5.8
WEAK_FORM = 55.0
WEAK_ROLE_FIT = 60.0
WEAK_MATCHUP = 45.0

# In-process caches (data is static during a tool run).
_FORM_CACHE: Dict[Any, Optional[dict]] = {}
_TEAM_NAME_CACHE: Dict[int, Optional[str]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _avg(values: List[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _clean_doc(doc: Optional[dict]) -> Optional[dict]:
    """Strip Mongo/internal fields and stringify _id so a doc is JSON-friendly."""
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k in ("embedding", "profile_text_full", "_source", "_import_key"):
            continue
        if k == "_id":
            out["_id"] = str(v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- #
# Field accessors (tolerate raw vs normalized vs nested shapes)               #
# --------------------------------------------------------------------------- #
def _player_name_from_doc(doc: dict) -> Optional[str]:
    if not doc:
        return None
    if doc.get("name"):
        return doc["name"]
    player = doc.get("player")
    if isinstance(player, dict):
        return player.get("name") or player.get("short_name")
    return doc.get("short_name")


def _player_id_from_doc(doc: dict) -> Optional[int]:
    if not doc:
        return None
    player = doc.get("player")
    if isinstance(player, dict) and player.get("id") is not None:
        return player.get("id")
    return doc.get("player_id") or doc.get("id") or doc.get("raw_player_id")


def _position_from_doc(doc: dict) -> Optional[str]:
    """Coarse bucket letter G/D/M/F (upper-cased first letter)."""
    if not doc:
        return None
    pos = doc.get("position")
    if not pos:
        player = doc.get("player")
        if isinstance(player, dict):
            pos = player.get("position")
    if not pos:
        return None
    letter = str(pos).strip().upper()[:1]
    return letter if letter in ("G", "D", "M", "F") else None


def _season_from_doc(doc: dict) -> Optional[int]:
    if not doc:
        return None
    season = doc.get("season")
    if isinstance(season, dict):
        return season.get("year")
    return doc.get("season_year")


def _team_id_from_doc(doc: dict) -> Optional[int]:
    return doc.get("team_id") if doc else None


# --------------------------------------------------------------------------- #
# Team name <-> id resolution                                                 #
# --------------------------------------------------------------------------- #
def _team_name_for(team_id: Optional[int]) -> Optional[str]:
    if team_id is None:
        return None
    if team_id in _TEAM_NAME_CACHE:
        return _TEAM_NAME_CACHE[team_id]
    db = get_db()
    doc = db[COL_TEAMS].find_one({"team_id": team_id}) or db[COL_BDL_TEAMS].find_one({"id": team_id})
    name = doc.get("name") if doc else None
    _TEAM_NAME_CACHE[team_id] = name
    return name


def _team_id_for(team_name: str) -> Optional[int]:
    if not team_name:
        return None
    db = get_db()
    rx = re.compile(f"^{re.escape(team_name.strip())}$", re.I)
    doc = db[COL_TEAMS].find_one({"name": rx})
    if doc and doc.get("team_id") is not None:
        return doc["team_id"]
    doc = db[COL_BDL_TEAMS].find_one({"name": rx})
    if doc and doc.get("id") is not None:
        return doc["id"]
    rx2 = re.compile(re.escape(team_name.strip()), re.I)  # fuzzy contains fallback
    doc = db[COL_TEAMS].find_one({"name": rx2}) or db[COL_BDL_TEAMS].find_one({"name": rx2})
    if doc:
        return doc.get("team_id") if doc.get("team_id") is not None else doc.get("id")
    return None


# --------------------------------------------------------------------------- #
# Roster & player lookup                                                       #
# --------------------------------------------------------------------------- #
def _roster_player_entry(doc: dict) -> dict:
    """Normalize a bdl_rosters / players doc into a compact roster entry."""
    return {
        "player_id": _player_id_from_doc(doc),
        "name": _player_name_from_doc(doc),
        "position_bucket": _position_from_doc(doc),
        "team_id": _team_id_from_doc(doc),
        "season_year": _season_from_doc(doc),
    }


def _find_team_roster(team_name: str, season_year: int = DEFAULT_SEASON) -> List[dict]:
    """Roster entries for a team. Prefers bdl_rosters (links players to teams)."""
    db = get_db()
    team_id = _team_id_for(team_name)
    if team_id is None:
        return []
    cur = db[COL_BDL_ROSTERS].find({"team_id": team_id, "season.year": season_year})
    entries = [_roster_player_entry(d) for d in cur]
    if not entries:  # season fallback: any season
        entries = [_roster_player_entry(d) for d in db[COL_BDL_ROSTERS].find({"team_id": team_id})]
    if not entries:  # last resort: normalized players
        entries = [_roster_player_entry(d) for d in db[COL_PLAYERS].find({"team_id": team_id})]
    return [e for e in entries if e.get("player_id") is not None and e.get("name")]


def _find_player_candidates(player_name: str, team_name: str = "") -> List[dict]:
    """Find raw player/roster docs matching a name (optionally within a team)."""
    db = get_db()
    rx = re.compile(re.escape(player_name.strip()), re.I)
    q: Dict[str, Any] = {"$or": [{"name": rx}, {"short_name": rx}, {"player.name": rx},
                                 {"player.short_name": rx}]}
    if team_name:
        team_id = _team_id_for(team_name)
        if team_id is not None:
            q = {"$and": [q, {"team_id": team_id}]}
    out: List[dict] = list(db[COL_BDL_ROSTERS].find(q).limit(10))
    out.extend(db[COL_PLAYERS].find(q).limit(10))
    return out


# --------------------------------------------------------------------------- #
# Match stats & form                                                           #
# --------------------------------------------------------------------------- #
def _get_latest_player_stats(player_id: Optional[int] = None, player_name: str = "",
                             team_name: str = "", last_n: int = 5) -> List[dict]:
    """Most recent per-match stat rows for a player (proxy recency: match_id desc)."""
    db = get_db()
    if player_id is None and player_name:
        cands = _find_player_candidates(player_name, team_name)
        player_id = next((_player_id_from_doc(c) for c in cands
                          if _player_id_from_doc(c) is not None), None)
    if player_id is None:
        return []
    rows = list(db[COL_BDL_PLAYER_MATCH_STATS].find({"player_id": player_id}))
    rows.sort(key=lambda r: r.get("match_id") or 0, reverse=True)
    return rows[: max(1, last_n)]


def _stat(row: dict, *keys: str) -> float:
    for k in keys:
        v = row.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _compute_form(player_id: Optional[int], position_bucket: Optional[str],
                  last_n: int = 5) -> Optional[dict]:
    """Deterministic form score (0-100) from bdl_player_match_stats, or None if no data."""
    if player_id is None:
        return None
    cache_key = (player_id, last_n)
    if cache_key in _FORM_CACHE:
        return _FORM_CACHE[cache_key]
    rows = _get_latest_player_stats(player_id=player_id, last_n=last_n)
    if not rows:
        _FORM_CACHE[cache_key] = None
        return None

    n = len(rows)
    ratings = [r.get("rating") for r in rows if isinstance(r.get("rating"), (int, float))]
    avg_rating = _avg(ratings)
    goals = sum(_stat(r, "goals") for r in rows)
    xg = sum(_stat(r, "expected_goals") for r in rows)
    assists = sum(_stat(r, "assists") for r in rows)
    xa = sum(_stat(r, "expected_assists") for r in rows)
    avg_minutes = sum(_stat(r, "minutes_played") for r in rows) / n

    rating_comp = _clamp((avg_rating or 0) * 10.0)
    minutes_comp = _clamp(avg_minutes / 90.0 * 100.0)

    trend = 50.0  # recent-half vs older-half avg rating (50 = flat)
    if len(ratings) >= 2:
        half = max(1, len(ratings) // 2)
        recent = _avg(ratings[:half]) or 0
        older = _avg(ratings[half:]) or recent
        trend = _clamp(50.0 + (recent - older) * 25.0)

    if position_bucket == "G":
        form = 0.65 * rating_comp + 0.15 * minutes_comp + 0.20 * trend
    else:
        goal_comp = _clamp(((goals + xg) / n) * 50.0)
        assist_comp = _clamp(((assists + xa) / n) * 60.0)
        form = (0.40 * rating_comp + 0.20 * goal_comp + 0.15 * assist_comp
                + 0.10 * minutes_comp + 0.15 * trend)

    result = {
        "form_score": round(form, 1),
        "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
        "goals_xg_per_match": round((goals + xg) / n, 2),
        "assists_xa_per_match": round((assists + xa) / n, 2),
        "avg_minutes": round(avg_minutes, 1),
        "trend": round(trend, 1),
        "matches_used": n,
    }
    _FORM_CACHE[cache_key] = result
    return result


# --------------------------------------------------------------------------- #
# Derived tactical attributes & role fit                                       #
# --------------------------------------------------------------------------- #
def _get_player_attributes(player_name: str, team_name: str = "") -> dict:
    """Read synthetic/derived attributes from player_attributes if present (else {})."""
    db = get_db()
    if COL_PLAYER_ATTRIBUTES not in db.list_collection_names():
        return {}
    rx = re.compile(f"^{re.escape(player_name.strip())}$", re.I)
    q: Dict[str, Any] = {"$or": [{"name": rx}, {"player_name": rx}]}
    if team_name:
        tid = _team_id_for(team_name)
        if tid is not None:
            q = {"$and": [q, {"team_id": tid}]}
    return _clean_doc(db[COL_PLAYER_ATTRIBUTES].find_one(q)) or {}


def _role_fit(position_bucket: Optional[str], slot: str) -> float:
    """Derived 0-100 fit of a coarse-bucket player into a granular formation slot."""
    needed = _SLOT_BUCKET.get(slot)
    if not needed or not position_bucket:
        return 50.0
    if position_bucket == needed:
        return 85.0
    if (position_bucket, needed) in {("D", "M"), ("M", "D"), ("M", "F"), ("F", "M")}:
        return 62.0
    if position_bucket == "G" or needed == "G":
        return 20.0
    return 40.0  # D<->F


def _offensive_rate(rows: List[dict]) -> Optional[float]:
    if not rows:
        return None
    n = len(rows)
    return sum(_stat(r, "expected_goals") + 0.5 * _stat(r, "goals")
               + 0.3 * _stat(r, "key_passes") + 0.4 * _stat(r, "dribbles_completed")
               + 0.3 * _stat(r, "shots_on_target") for r in rows) / n


def _defensive_rate(rows: List[dict]) -> Optional[float]:
    if not rows:
        return None
    n = len(rows)
    return sum(_stat(r, "tackles") + _stat(r, "interceptions")
               + 0.7 * _stat(r, "clearances") + 0.5 * _stat(r, "duels_won")
               + 0.4 * _stat(r, "blocked_shots") for r in rows) / n


# --------------------------------------------------------------------------- #
# Lineup building                                                              #
# --------------------------------------------------------------------------- #
def _rank_key(entry: dict) -> tuple:
    form = _compute_form(entry["player_id"], entry.get("position_bucket"))
    return (1 if form else 0, form["form_score"] if form else 0.0, entry.get("name") or "")


def _build_provisional_lineup(team_name: str, formation: str,
                              season_year: int = DEFAULT_SEASON) -> dict:
    """Assign roster players (coarse buckets) into granular formation slots."""
    slots = FORMATIONS.get(formation)
    if not slots:
        return {"error": f"Unknown formation '{formation}'. Supported: {', '.join(FORMATIONS)}."}
    roster = _find_team_roster(team_name, season_year)
    if not roster:
        return {"error": f"No roster found for team '{team_name}' (season {season_year}). "
                         "Try list_known_teams."}

    buckets: Dict[str, List[dict]] = {"G": [], "D": [], "M": [], "F": []}
    for e in roster:
        buckets.get(e.get("position_bucket") or "M", buckets["M"]).append(e)
    for b in buckets.values():
        b.sort(key=_rank_key, reverse=True)

    used_ids: set = set()
    players: List[dict] = []
    borrowed = 0
    for slot in slots:
        need = _SLOT_BUCKET.get(slot, "M")
        pick = next((c for c in buckets.get(need, []) if c["player_id"] not in used_ids), None)
        if pick is None:  # borrow from another line (roster short here)
            borrowed += 1
            for alt in ("G", "D", "M", "F"):
                pick = next((c for c in buckets.get(alt, []) if c["player_id"] not in used_ids), None)
                if pick:
                    break
        if pick is None:
            continue
        used_ids.add(pick["player_id"])
        players.append({
            "position": slot, "player_name": pick["name"], "player_id": pick["player_id"],
            "position_bucket": pick.get("position_bucket"),
            "exact_fit": pick.get("position_bucket") == need,
        })
    return {
        "team_name": team_name, "formation": formation, "players": players,
        "provisional": True, "borrowed_slots": borrowed,
        "note": ("Granular slots (RW/LB/CB...) are DERIVED from coarse G/D/M/F roster "
                 "positions; player identities are real BALLDONTLIE data."),
    }


def _get_lineup(team_name: str, formation: str) -> dict:
    """Saved lineup from `lineups` if present, else a provisional one from the roster."""
    db = get_db()
    rx = re.compile(f"^{re.escape(team_name.strip())}$", re.I)
    q: Dict[str, Any] = {"team_name": rx}
    if formation:
        q["formation"] = formation
    saved = db[COL_LINEUPS].find_one(q)
    if saved and saved.get("players"):
        out = _clean_doc(saved)
        out["provisional"] = False
        out.setdefault("formation", formation)
        out.setdefault("team_name", team_name)
        return out
    return _build_provisional_lineup(team_name, formation or "4-3-3")


# --------------------------------------------------------------------------- #
# Matchup scoring                                                              #
# --------------------------------------------------------------------------- #
def _risk_level(score: float) -> str:
    if score < 45:
        return "high"
    if score < 60:
        return "medium"
    if score < 75:
        return "manageable"
    return "advantage"


def _matchup(attacker_name: str, defender_name: str, attacking_team: str = "",
             defending_team: str = "", zone: str = "") -> dict:
    """Score a duel 0-100 from the attacker's perspective. Honest about missing data."""
    a_cands = _find_player_candidates(attacker_name, attacking_team)
    d_cands = _find_player_candidates(defender_name, defending_team)
    a_id = next((_player_id_from_doc(c) for c in a_cands if _player_id_from_doc(c) is not None), None)
    d_id = next((_player_id_from_doc(c) for c in d_cands if _player_id_from_doc(c) is not None), None)
    a_bucket = next((_position_from_doc(c) for c in a_cands if _position_from_doc(c)), None)
    d_bucket = next((_position_from_doc(c) for c in d_cands if _position_from_doc(c)), None)

    missing: List[str] = []
    reasons: List[str] = []
    a_rows = _get_latest_player_stats(player_id=a_id) if a_id is not None else []
    d_rows = _get_latest_player_stats(player_id=d_id) if d_id is not None else []

    off = _offensive_rate(a_rows)
    deff = _defensive_rate(d_rows)
    if off is None or deff is None:
        attribute_advantage = 50.0
        missing.append("attacker/defender match-stat attributes")
    else:
        att_norm, def_norm = _clamp(off * 35.0), _clamp(deff * 12.0)
        attribute_advantage = _clamp(50.0 + (att_norm - def_norm) / 2.0)
        reasons.append(f"derived attribute edge {att_norm:.0f} vs {def_norm:.0f}")

    a_form = _compute_form(a_id, a_bucket)
    d_form = _compute_form(d_id, d_bucket)
    if a_form and d_form:
        form_advantage = _clamp(50.0 + (a_form["form_score"] - d_form["form_score"]) / 2.0)
        reasons.append(f"form {a_form['form_score']:.0f} vs {d_form['form_score']:.0f}")
    else:
        form_advantage = 50.0
        missing.append("recent form (no match stats for one/both players)")

    role_fit_advantage = 50.0     # neutral: granular roles are derived
    tactical_context = 50.0       # neutral: no pace/style attributes in data

    matchup_score = round(attribute_advantage * 0.40 + form_advantage * 0.25
                          + role_fit_advantage * 0.20 + tactical_context * 0.15, 1)
    risk = _risk_level(matchup_score)
    action = ("Avoid isolating this duel; add cover or change the matchup." if risk == "high"
              else "Monitor this duel; prepare an in-game adjustment." if risk == "medium"
              else "Favorable — can be used to target the opponent here.")
    return {
        "attacker": attacker_name, "defender": defender_name, "zone": zone,
        "matchup_score": matchup_score, "risk_level": risk,
        "components": {"attribute_advantage": round(attribute_advantage, 1),
                       "form_advantage": round(form_advantage, 1),
                       "role_fit_advantage": round(role_fit_advantage, 1),
                       "tactical_context": round(tactical_context, 1)},
        "attacker_form": a_form["form_score"] if a_form else None,
        "defender_form": d_form["form_score"] if d_form else None,
        "reason": "; ".join(reasons) or "limited data; partial score",
        "tactical_action": action, "missing_data": missing,
    }


def _duel_pairs(our_lineup: List[dict], opp_lineup: List[dict]) -> List[dict]:
    """Infer attacker-vs-defender duels by formation line + mirrored zone."""
    def by_line(lineup, line):
        return [s for s in lineup if _SLOT_LINE.get(s["position"]) == line]

    def pick(cands, zone, used):
        for c in cands:
            if c["player_id"] not in used and _SLOT_ZONE.get(c["position"]) == zone:
                return c
        for c in cands:
            if c["player_id"] not in used:
                return c
        return cands[0] if cands else None

    pairs: List[dict] = []
    used: set = set()
    opp_def = by_line(opp_lineup, "DEF")
    for s in by_line(our_lineup, "ATT"):
        opp = pick(opp_def, _MIRROR[_SLOT_ZONE.get(s["position"], "center")], used)
        if opp:
            used.add(opp["player_id"])
            pairs.append({"kind": "attack", "zone": f"{_SLOT_ZONE.get(s['position'])} attack",
                          "our": s, "opp": opp})
    used = set()
    opp_att = by_line(opp_lineup, "ATT")
    for s in by_line(our_lineup, "DEF"):
        opp = pick(opp_att, _MIRROR[_SLOT_ZONE.get(s["position"], "center")], used)
        if opp:
            used.add(opp["player_id"])
            pairs.append({"kind": "defense", "zone": f"{_SLOT_ZONE.get(s['position'])} defense",
                          "our": s, "opp": opp})
    our_mid, opp_mid = by_line(our_lineup, "MID"), by_line(opp_lineup, "MID")
    if our_mid and opp_mid:
        pairs.append({"kind": "midfield", "zone": "central midfield",
                      "our": our_mid[0], "opp": opp_mid[0]})
    return pairs


# --------------------------------------------------------------------------- #
# PUBLIC TOOLS                                                                  #
# --------------------------------------------------------------------------- #
def get_player(player_name: str, team_name: str = "") -> dict:
    """Look up a player's identity, team, position and recent form from MongoDB.

    Searches raw `bdl_rosters` then normalized `players`. Returns only fields
    that exist in the data; never invents stats.

    Args:
        player_name: Full or partial player name (case-insensitive).
        team_name: Optional team to disambiguate (e.g. "Brazil").
    """
    cands = _find_player_candidates(player_name, team_name)
    if not cands:
        return {"error": f"No player matching '{player_name}'"
                         + (f" in team '{team_name}'" if team_name else "") + "."}
    doc = cands[0]
    pid, bucket, team_id = _player_id_from_doc(doc), _position_from_doc(doc), _team_id_from_doc(doc)
    form = _compute_form(pid, bucket)
    return {
        "player": {"player_id": pid, "name": _player_name_from_doc(doc),
                   "position_bucket": bucket, "team_id": team_id,
                   "team_name": _team_name_for(team_id), "season_year": _season_from_doc(doc)},
        "recent_form": form, "form_available": form is not None,
        "source": {"collections": [COL_PLAYERS, COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS],
                   "player_id": pid},
        "limitations": [] if form else ["No match stats for this player; form unavailable."],
    }


def get_team_players(team_name: str, position: str = "", season_year: int = DEFAULT_SEASON) -> dict:
    """List a national team's roster (players linked to the team for a season).

    Prefers `bdl_rosters`. Position filter accepts coarse buckets G/D/M/F.

    Args:
        team_name: Team name, e.g. "Argentina".
        position: Optional coarse position filter (G/D/M/F or word).
        season_year: World Cup season (default 2026).
    """
    roster = _find_team_roster(team_name, season_year)
    if not roster:
        return {"error": f"No roster for team '{team_name}' (season {season_year}). "
                         "Use list_known_teams to see available teams."}
    if position:
        want = position.strip().upper()[:1]
        roster = [r for r in roster if r.get("position_bucket") == want]
    return {"team": team_name, "season_year": season_year, "count": len(roster),
            "players": roster, "source": {"collections": [COL_BDL_ROSTERS, COL_TEAMS]}}


def get_current_lineup(team_name: str, formation: str = "4-3-3") -> dict:
    """Get a team's starting XI for a formation.

    Reads the `lineups` collection if a saved lineup exists; otherwise generates
    a PROVISIONAL best-XI from the roster (granular slots derived from coarse
    positions). Provisional lineups are NOT saved automatically.

    Args:
        team_name: Team name.
        formation: One of 4-3-3, 4-2-3-1, 4-4-2, 3-5-2.
    """
    res = _get_lineup(team_name, formation)
    if "error" in res:
        return res
    return {"lineup": res, "source": {"collections": [COL_LINEUPS, COL_BDL_ROSTERS]}}


def get_opponent_lineup(opponent_team: str, formation: str = "4-3-3") -> dict:
    """Get the opponent's likely starting XI (saved lineup or provisional from roster).

    Args:
        opponent_team: Opponent team name.
        formation: Opponent formation (default 4-3-3).
    """
    res = _get_lineup(opponent_team, formation)
    if "error" in res:
        return res
    return {"lineup": res, "source": {"collections": [COL_LINEUPS, COL_BDL_ROSTERS]}}


def get_player_recent_form(player_name: str, team_name: str = "", last_n: int = 5) -> dict:
    """Compute a player's recent form (0-100) from bdl_player_match_stats.

    Args:
        player_name: Player name.
        team_name: Optional team to disambiguate.
        last_n: How many recent matches to use (default 5).
    """
    cands = _find_player_candidates(player_name, team_name)
    if not cands:
        return {"error": f"No player matching '{player_name}'."}
    pid = next((_player_id_from_doc(c) for c in cands if _player_id_from_doc(c) is not None), None)
    bucket = next((_position_from_doc(c) for c in cands if _position_from_doc(c)), None)
    form = _compute_form(pid, bucket, last_n)
    if not form:
        return {"player": _player_name_from_doc(cands[0]), "player_id": pid,
                "position_bucket": bucket, "form_score": None,
                "limitations": ["No match stats found; form cannot be computed from real data."],
                "source": {"collections": [COL_BDL_PLAYER_MATCH_STATS]}}
    return {"player": _player_name_from_doc(cands[0]), "player_id": pid,
            "position_bucket": bucket, **form,
            "source": {"collections": [COL_BDL_PLAYER_MATCH_STATS]}}


def evaluate_matchup(attacking_player: str, defending_player: str,
                     attacking_team: str = "", defending_team: str = "") -> dict:
    """Score a single attacker-vs-defender duel 0-100 (attacker's perspective).

    Uses derived attribute rates from match stats + recent form. States missing
    data instead of inventing speed/dribbling/defending values.

    Args:
        attacking_player: Attacker name.
        defending_player: Defender name.
        attacking_team: Optional attacker's team.
        defending_team: Optional defender's team.
    """
    res = _matchup(attacking_player, defending_player, attacking_team, defending_team)
    res["source"] = {"collections": [COL_BDL_PLAYER_MATCH_STATS, COL_BDL_ROSTERS]}
    return res


def analyze_matchups(team_name: str, opponent_team: str, formation: str = "4-3-3") -> dict:
    """Map and score every key positional duel between two teams for a formation.

    Builds both lineups (saved or provisional), infers duels by line + mirrored
    zone (our RW vs their LB, our LB vs their RW, ST vs CB, mid vs mid ...), and
    scores each 0-100.

    Args:
        team_name: Our team.
        opponent_team: Opponent team.
        formation: Our formation (default 4-3-3).
    """
    ours = _get_lineup(team_name, formation)
    if "error" in ours:
        return ours
    opp = _get_lineup(opponent_team, formation)
    if "error" in opp:
        return opp

    rows: List[dict] = []
    for pair in _duel_pairs(ours["players"], opp["players"]):
        if pair["kind"] == "defense":
            duel = _matchup(pair["opp"]["player_name"], pair["our"]["player_name"],
                            opponent_team, team_name, zone=pair["zone"])
            our_score = round(100.0 - duel["matchup_score"], 1)
            rows.append({"zone": pair["zone"], "kind": "defense",
                         "our_player": pair["our"]["player_name"],
                         "opponent_player": pair["opp"]["player_name"],
                         "matchup_score": our_score, "risk_level": _risk_level(our_score),
                         "reason": f"opponent attacker duel inverted ({duel['reason']})",
                         "tactical_action": duel["tactical_action"],
                         "components": duel["components"], "missing_data": duel["missing_data"]})
        else:
            duel = _matchup(pair["our"]["player_name"], pair["opp"]["player_name"],
                            team_name, opponent_team, zone=pair["zone"])
            rows.append({"zone": pair["zone"], "kind": pair["kind"],
                         "our_player": pair["our"]["player_name"],
                         "opponent_player": pair["opp"]["player_name"],
                         "matchup_score": duel["matchup_score"], "risk_level": duel["risk_level"],
                         "reason": duel["reason"], "tactical_action": duel["tactical_action"],
                         "components": duel["components"], "missing_data": duel["missing_data"]})

    scored = [r for r in rows if r.get("matchup_score") is not None]
    avg = round(sum(r["matchup_score"] for r in scored) / len(scored), 1) if scored else None
    strongest = max(scored, key=lambda r: r["matchup_score"]) if scored else None
    riskiest = min(scored, key=lambda r: r["matchup_score"]) if scored else None
    any_missing = any(r["missing_data"] for r in rows)
    return {
        "team": team_name, "opponent": opponent_team, "formation": formation,
        "matchups": rows, "matchup_average": avg,
        "strongest_advantage": strongest, "highest_risk": riskiest,
        "recommended_actions": [r["tactical_action"] for r in rows
                                if r["risk_level"] in ("high", "medium")],
        "lineup_provisional": ours.get("provisional", False) or opp.get("provisional", False),
        "limitations": (["Granular positions are derived from coarse G/D/M/F data."]
                        + (["Some duels lack match stats; scores are partial."] if any_missing else [])),
        "source": {"collections": [COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS, COL_LINEUPS]},
    }


def _evaluate_lineup_core(team_name: str, opponent_team: str, formation: str) -> dict:
    ours = _get_lineup(team_name, formation)
    if "error" in ours:
        return ours
    matchups = analyze_matchups(team_name, opponent_team, formation)
    worst_by_player: Dict[str, dict] = {}
    for r in matchups.get("matchups", []):
        p = r["our_player"]
        if p not in worst_by_player or r["matchup_score"] < worst_by_player[p]["matchup_score"]:
            worst_by_player[p] = r

    players_out: List[dict] = []
    form_vals, rolefit_vals = [], []
    for slot in ours["players"]:
        name = slot["player_name"]
        form = _compute_form(slot["player_id"], slot.get("position_bucket"))
        role_fit = _role_fit(slot.get("position_bucket"), slot["position"])
        rolefit_vals.append(role_fit)
        avg_rating = form["avg_rating"] if form else None
        form_score = form["form_score"] if form else None
        if form_score is not None:
            form_vals.append(form_score)
        worst = worst_by_player.get(name)
        flags: List[str] = []
        if avg_rating is not None and avg_rating < WEAK_RATING:
            flags.append(f"recent avg rating {avg_rating} < {WEAK_RATING}")
        if form_score is not None and form_score < WEAK_FORM:
            flags.append(f"form score {form_score} < {WEAK_FORM}")
        if role_fit < WEAK_ROLE_FIT:
            flags.append(f"role fit {role_fit:.0f} < {WEAK_ROLE_FIT:.0f} "
                         f"(plays {slot.get('position_bucket')} in {slot['position']})")
        if worst and worst["matchup_score"] < WEAK_MATCHUP:
            flags.append(f"matchup {worst['matchup_score']} < {WEAK_MATCHUP} "
                         f"vs {worst['opponent_player']} ({worst['zone']})")
        players_out.append({
            "position": slot["position"], "player": name,
            "form_score": form_score, "avg_rating": avg_rating, "role_fit": round(role_fit, 1),
            "worst_matchup": ({"opponent": worst["opponent_player"], "score": worst["matchup_score"],
                               "zone": worst["zone"]} if worst else None),
            "form_available": form is not None, "flags": flags,
        })

    weak = sorted([p for p in players_out if p["flags"]], key=lambda p: len(p["flags"]), reverse=True)
    form_avg = round(sum(form_vals) / len(form_vals), 1) if form_vals else 0.0
    rolefit_avg = round(sum(rolefit_vals) / len(rolefit_vals), 1) if rolefit_vals else 0.0
    lineup_score = round(0.5 * form_avg + 0.3 * (matchups.get("matchup_average") or 50.0)
                         + 0.2 * rolefit_avg, 1)
    return {
        "team": team_name, "opponent": opponent_team, "formation": formation,
        "lineup_score": lineup_score, "players": players_out, "weak_links": weak,
        "form_average": form_avg, "role_fit_average": rolefit_avg,
        "matchup_summary": {"matchup_average": matchups.get("matchup_average"),
                            "strongest_advantage": matchups.get("strongest_advantage"),
                            "highest_risk": matchups.get("highest_risk")},
        "lineup_provisional": ours.get("provisional", False),
        "limitations": matchups.get("limitations", []),
        "source": {"collections": [COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS, COL_LINEUPS]},
    }


def evaluate_lineup(team_name: str, opponent_team: str, formation: str = "4-3-3") -> dict:
    """Evaluate a starting XI vs an opponent and flag weak links.

    Scores each player on form, role fit and worst matchup; flags players below
    thresholds (avg rating < 5.8, form < 55, role fit < 60, matchup < 45).

    Args:
        team_name: Our team.
        opponent_team: Opponent team.
        formation: Our formation (default 4-3-3).
    """
    return _evaluate_lineup_core(team_name, opponent_team, formation)


def recommend_replacement(team_name: str, opponent_team: str, weak_player_name: str,
                          position: str = "") -> dict:
    """Recommend a roster replacement for a weak player, with matchup improvement.

    Ranks same-team roster players (same coarse bucket, not already starting) by
    form + role fit + matchup vs the key opposing player in that zone.

    Args:
        team_name: Our team.
        opponent_team: Opponent team.
        weak_player_name: The player to replace.
        position: Optional formation slot the replacement must fill (e.g. "RW").
    """
    ev = _evaluate_lineup_core(team_name, opponent_team, "4-3-3")
    if "error" in ev:
        return ev
    weak_slot = next((p for p in ev["players"]
                      if weak_player_name.lower() in (p["player"] or "").lower()), None)
    slot = position or (weak_slot["position"] if weak_slot else "")
    if not slot:
        return {"error": f"Could not locate '{weak_player_name}' in the lineup; "
                         "pass an explicit position (e.g. RW)."}
    need_bucket = _SLOT_BUCKET.get(slot, "M")
    starters = {p["player"] for p in ev["players"]}
    opp_player = weak_slot["worst_matchup"]["opponent"] if (weak_slot and weak_slot.get("worst_matchup")) else None
    current_score = weak_slot["worst_matchup"]["score"] if (weak_slot and weak_slot.get("worst_matchup")) else None

    candidates: List[dict] = []
    for e in _find_team_roster(team_name):
        if e["name"] in starters or e.get("position_bucket") != need_bucket:
            continue
        form = _compute_form(e["player_id"], e.get("position_bucket"))
        role_fit = _role_fit(e.get("position_bucket"), slot)
        new_matchup = _matchup(e["name"], opp_player, team_name, opponent_team)["matchup_score"] if opp_player else None
        composite = round(0.5 * (form["form_score"] if form else 0.0) + 0.2 * role_fit
                          + 0.3 * (new_matchup if new_matchup is not None else 50.0), 1)
        candidates.append({"name": e["name"], "position_bucket": e.get("position_bucket"),
                           "form_score": form["form_score"] if form else None,
                           "avg_rating": form["avg_rating"] if form else None,
                           "role_fit": round(role_fit, 1), "matchup_score": new_matchup,
                           "form_available": form is not None, "composite": composite})
    candidates.sort(key=lambda c: (c["form_available"], c["composite"]), reverse=True)
    if not candidates:
        return {"team": team_name, "opponent": opponent_team, "position": slot,
                "weak_player": weak_player_name, "recommended": None, "all_candidates": [],
                "limitations": [f"No alternative {need_bucket}-bucket roster player available."],
                "source": {"collections": [COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS]}}
    best = candidates[0]
    improvement = None
    if current_score is not None and best["matchup_score"] is not None:
        improvement = {"vs_defender": opp_player, "current_matchup_score": current_score,
                       "new_matchup_score": best["matchup_score"],
                       "delta": round(best["matchup_score"] - current_score, 1)}
    return {"team": team_name, "opponent": opponent_team, "position": slot,
            "weak_player": weak_player_name, "recommended": best,
            "all_candidates": candidates[:5], "matchup_improvement": improvement,
            "low_confidence": not best["form_available"],
            "limitations": ([] if best["form_available"]
                            else ["Recommended player has no match stats; low confidence."]),
            "source": {"collections": [COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS]}}


def optimize_formation_with_matchups(team_name: str, opponent_team: str,
                                     candidate_formations: list = None) -> dict:
    """Compare candidate formations against an opponent using matchup + form scores.

    formation_score = form_avg*0.30 + role_fit_avg*0.20 + matchup_avg*0.30
                      + tactical_balance*0.10 + availability_score*0.10

    Args:
        team_name: Our team.
        opponent_team: Opponent team.
        candidate_formations: Formations to compare (default 4-3-3, 4-2-3-1).
    """
    formations = candidate_formations or DEFAULT_FORMATIONS
    ranking: List[dict] = []
    skipped: List[dict] = []
    for f in formations:
        ev = _evaluate_lineup_core(team_name, opponent_team, f)
        if "error" in ev:
            skipped.append({"formation": f, "error": ev["error"]})
            continue
        lineup = _get_lineup(team_name, f)
        n_slots = len(FORMATIONS.get(f, [])) or 11
        exact = sum(1 for p in lineup.get("players", []) if p.get("exact_fit"))
        filled = len(lineup.get("players", []))
        tactical_balance = round(exact / n_slots * 100.0, 1)
        availability_score = round(filled / n_slots * 100.0, 1)
        matchup_avg = ev["matchup_summary"]["matchup_average"] or 50.0
        score = round(ev["form_average"] * 0.30 + ev["role_fit_average"] * 0.20
                      + matchup_avg * 0.30 + tactical_balance * 0.10
                      + availability_score * 0.10, 1)
        ranking.append({"formation": f, "formation_score": score,
                        "components": {"lineup_form_average": ev["form_average"],
                                       "role_fit_average": ev["role_fit_average"],
                                       "matchup_average": matchup_avg,
                                       "tactical_balance": tactical_balance,
                                       "availability_score": availability_score},
                        "highest_risk": ev["matchup_summary"]["highest_risk"],
                        "weak_links": [w["player"] for w in ev["weak_links"]]})
    ranking.sort(key=lambda r: r["formation_score"], reverse=True)
    if not ranking:
        return {"error": "No formation could be evaluated.", "skipped": skipped}
    best = ranking[0]
    return {"team": team_name, "opponent": opponent_team,
            "recommended_formation": best["formation"], "formation_score": best["formation_score"],
            "ranking": ranking, "skipped": skipped,
            "rationale": (f"{best['formation']} maximizes the weighted blend of form, role fit, "
                          "matchup average, balance and availability."),
            "limitations": ["Provisional lineups; granular positions derived from coarse data."],
            "source": {"collections": [COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS, COL_LINEUPS]}}


def recommend_formation(team_name: str, opponent_team: str, preferred_style: str = "") -> dict:
    """Recommend the best formation vs an opponent (wrapper over the optimizer).

    Args:
        team_name: Our team.
        opponent_team: Opponent team.
        preferred_style: Optional style hint (advisory only).
    """
    res = optimize_formation_with_matchups(team_name, opponent_team)
    if preferred_style:
        res["note"] = f"Preferred style '{preferred_style}' noted; ranking is matchup-driven."
    return res


def compare_players(player_a: str, player_b: str, role: str = "") -> dict:
    """Compare two players by recent form (and role fit if a slot is given).

    Args:
        player_a: First player.
        player_b: Second player.
        role: Optional formation slot for role-fit comparison (e.g. "ST").
    """
    def side(name):
        cands = _find_player_candidates(name)
        pid = next((_player_id_from_doc(c) for c in cands if _player_id_from_doc(c) is not None), None)
        bucket = next((_position_from_doc(c) for c in cands if _position_from_doc(c)), None)
        form = _compute_form(pid, bucket)
        return {"name": _player_name_from_doc(cands[0]) if cands else name, "player_id": pid,
                "position_bucket": bucket, "form_score": form["form_score"] if form else None,
                "avg_rating": form["avg_rating"] if form else None,
                "role_fit": _role_fit(bucket, role) if role else None,
                "form_available": form is not None}, form
    a, fa = side(player_a)
    b, fb = side(player_b)
    comp_a = (a["form_score"] or 0) + (a["role_fit"] or 0) * 0.3
    comp_b = (b["form_score"] or 0) + (b["role_fit"] or 0) * 0.3
    verdict = a["name"] if comp_a >= comp_b else b["name"]
    note = (f"{verdict} rates higher on available data." if fa and fb
            else "Comparison limited: one or both players lack match stats.")
    return {"role": role, "player_a": a, "player_b": b, "verdict": verdict, "note": note,
            "source": {"collections": [COL_BDL_PLAYER_MATCH_STATS, COL_BDL_ROSTERS]}}


def list_known_teams() -> dict:
    """List national teams available in the database (for valid tool inputs)."""
    db = get_db()
    names = {d["name"] for d in db[COL_TEAMS].find({}, {"name": 1}) if d.get("name")}
    if not names:
        names = {d["name"] for d in db[COL_BDL_TEAMS].find({}, {"name": 1}) if d.get("name")}
    return {"teams": sorted(names), "count": len(names),
            "source": {"collections": [COL_TEAMS, COL_BDL_TEAMS]}}


def save_lineup_recommendation(team_name: str, opponent_team: str, recommendation: dict) -> dict:
    """Persist a final recommendation to `lineup_recommendations` (+ matchup_reports).

    Args:
        team_name: Our team.
        opponent_team: Opponent team.
        recommendation: The recommendation payload (decision, formation, evidence).
    """
    db = get_db()
    doc = {"team_name": team_name, "opponent_team": opponent_team,
           "recommendation": recommendation, "created_at": _now(), "agent": "scout_ai_coach",
           "sources_used": recommendation.get("sources_used")
           or [COL_BDL_ROSTERS, COL_BDL_PLAYER_MATCH_STATS],
           "confidence": recommendation.get("confidence", "medium"),
           "limitations": recommendation.get("limitations",
                                             ["Provisional lineups; derived positions."])}
    res = db[COL_RECOMMENDATIONS].insert_one(doc)
    out = {"saved": True, "recommendation_id": str(res.inserted_id), "collection": COL_RECOMMENDATIONS}
    matchups = recommendation.get("matchup_evidence") or recommendation.get("matchups")
    if matchups:
        rep = db[COL_MATCHUP_REPORTS].insert_one({"team_name": team_name, "opponent_team": opponent_team,
                                                  "matchups": matchups, "created_at": _now(),
                                                  "recommendation_id": str(res.inserted_id)})
        out["matchup_report_id"] = str(rep.inserted_id)
        out["matchup_reports_collection"] = COL_MATCHUP_REPORTS
    return out


def create_task_plan(goal: str, team_name: str = "", opponent_team: str = "") -> dict:
    """Create a multi-step coaching task plan in `coach_task_plans`.

    Args:
        goal: The coaching objective.
        team_name: Our team (optional).
        opponent_team: Opponent (optional).
    """
    db = get_db()
    steps = [{"name": s, "status": "pending", "notes": ""} for s in
             ["search_memory", "load_lineups", "evaluate_lineup", "analyze_matchups",
              "optimize_formation", "recommend_replacement", "save_recommendation"]]
    res = db[COL_TASK_PLANS].insert_one({"goal": goal, "team_name": team_name,
                                         "opponent_team": opponent_team, "steps": steps,
                                         "status": "active", "created_at": _now()})
    return {"plan_id": str(res.inserted_id), "steps": [s["name"] for s in steps],
            "collection": COL_TASK_PLANS}


def update_task_step(plan_id: str, step_name: str, status: str, notes: str = "") -> dict:
    """Update one step's status in a coaching task plan.

    Args:
        plan_id: The plan id from create_task_plan.
        step_name: Step to update.
        status: New status (pending/in_progress/done/blocked).
        notes: Optional notes.
    """
    db = get_db()
    try:
        oid = ObjectId(plan_id)
    except (InvalidId, TypeError):
        return {"error": f"Invalid plan_id '{plan_id}'."}
    res = db[COL_TASK_PLANS].update_one(
        {"_id": oid, "steps.name": step_name},
        {"$set": {"steps.$.status": status, "steps.$.notes": notes, "updated_at": _now()}})
    if res.matched_count == 0:
        return {"error": f"No plan/step match for plan_id={plan_id}, step={step_name}."}
    return {"updated": True, "plan_id": plan_id, "step": step_name, "status": status}
