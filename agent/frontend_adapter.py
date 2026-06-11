"""Thin UI<->backend adapter for the Scout.AI Streamlit dashboard.

This is a *thin* layer: it calls the existing deterministic coach tools and
memory functions (coach_agent.tools / coach_agent.memory) and shapes their
output for the dashboard. It does NOT duplicate scoring logic and never
invents data — every value returned here comes from a backend tool or is an
explicit, labelled fallback.

Public surface used by app.py:
    get_backend_status()                      -> {"mongo": ..., "adk": ...}
    list_teams()                              -> list[str]
    list_players_for_team(team_name)          -> dict
    load_lineup(team_name, formation)         -> dict (lineup) | {"error": ...}
    run_full_analysis(...)                    -> dict (the whole demo flow)
    build_coach_briefing(analysis)            -> dict (coach-facing sections)
    save_recommendation_from_ui(...)          -> dict (ids written to Mongo)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make `coach_agent` importable whether run as `streamlit run agent/app.py`
# (cwd = repo root) or from inside agent/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from coach_agent import memory, tools          # noqa: E402
from coach_agent.db import get_db, ping_mongo   # noqa: E402
from coach_agent.schemas import (               # noqa: E402
    COL_BDL_PLAYER_MATCH_STATS, COL_BDL_ROSTERS, COL_BDL_TEAMS, COL_TEAMS,
)

SUPPORTED_FORMATIONS = ["4-3-3", "4-2-3-1", "3-5-2", "4-4-2"]


# --------------------------------------------------------------------------- #
# Status / health                                                             #
# --------------------------------------------------------------------------- #
def adk_status() -> Dict[str, Any]:
    """Try to import the ADK root_agent for an 'ADK Agent loaded' badge.

    Never raises — a failed import just means the deterministic tool path is
    used (which is the demo path anyway).
    """
    try:
        from coach_agent.agent import root_agent  # noqa: WPS433 (local import on purpose)
        return {
            "ok": True,
            "name": getattr(root_agent, "name", "scout_ai_coach"),
            "tools": len(getattr(root_agent, "tools", []) or []),
        }
    except Exception as exc:  # noqa: BLE001 - badge must never break the UI
        return {"ok": False, "error": str(exc)}


def get_backend_status() -> Dict[str, Any]:
    """MongoDB Atlas + ADK status for the header badges."""
    return {"mongo": ping_mongo(), "adk": adk_status(), "gemini": bool(os.getenv("GOOGLE_API_KEY"))}


# --------------------------------------------------------------------------- #
# Lookups                                                                      #
# --------------------------------------------------------------------------- #
def list_teams() -> List[str]:
    """National teams available in MongoDB (empty list if DB unreachable)."""
    try:
        res = tools.list_known_teams()
        return res.get("teams", []) or []
    except Exception:  # noqa: BLE001
        return []


def teams_with_match_stats() -> set:
    """Names of teams that have `bdl_player_match_stats` rows for their roster.

    Form scores, ratings, and matchup attribute components only exist for
    these teams (see _compute_form / _matchup in tools.py); other teams fall
    back to neutral defaults (form=None, matchup_score=50). Used to give the
    coach an honest "data coverage" signal instead of an unexplained
    "no weak link" / "limited data" result.
    """
    try:
        db = get_db()
        pids = db[COL_BDL_PLAYER_MATCH_STATS].distinct("player_id")
        if not pids:
            return set()
        team_ids = db[COL_BDL_ROSTERS].distinct("team_id", {"player.id": {"$in": pids}})
        names = set()
        for tid in team_ids:
            doc = db[COL_TEAMS].find_one({"team_id": tid}) or db[COL_BDL_TEAMS].find_one({"id": tid})
            if doc and doc.get("name"):
                names.add(doc["name"])
        return names
    except Exception:  # noqa: BLE001
        return set()


def list_players_for_team(team_name: str) -> Dict[str, Any]:
    """Roster for a team from the backend, or an {'error': ...} dict."""
    try:
        return tools.get_team_players(team_name)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "players": []}


def load_lineup(team_name: str, formation: str) -> Dict[str, Any]:
    """Saved or provisional starting XI for a team/formation."""
    res = tools.get_current_lineup(team_name, formation)
    if "error" in res:
        return res
    return res.get("lineup", res)


# --------------------------------------------------------------------------- #
# Full analysis flow                                                           #
# --------------------------------------------------------------------------- #
def run_full_analysis(team_name: str, opponent_team: str, formation: str,
                      goal: str = "", candidate_formations: Optional[List[str]] = None,
                      ) -> Dict[str, Any]:
    """Run the deterministic pipeline and return everything the UI needs.

    Pipeline: memory search -> our lineup + opponent lineup -> evaluate_lineup
    -> analyze_matchups -> optimize_formation_with_matchups -> recommend_replacement
    for the worst weak link. Each sub-result is returned as-is (including any
    {'error': ...}) so the UI can show honest, per-section messages.
    """
    out: Dict[str, Any] = {
        "ok": False, "team": team_name, "opponent": opponent_team,
        "formation": formation, "goal": goal, "errors": [],
    }
    try:
        out["memory"] = memory.search_coach_memory(
            goal or f"{team_name} vs {opponent_team} {formation}",
            team_name=team_name, opponent_team=opponent_team,
        )
    except Exception as exc:  # noqa: BLE001
        out["memory"] = {"count": 0, "memories": [], "error": str(exc)}

    our = load_lineup(team_name, formation)
    if "error" in our:
        out["errors"].append(f"Our lineup: {our['error']}")
        return out
    out["our_lineup"] = our

    opp = load_lineup(opponent_team, formation)
    out["opponent_lineup"] = opp if "error" not in opp else None
    if "error" in opp:
        out["errors"].append(f"Opponent lineup: {opp['error']}")

    evaluation = tools.evaluate_lineup(team_name, opponent_team, formation)
    if "error" in evaluation:
        out["errors"].append(f"Lineup evaluation: {evaluation['error']}")
        return out
    out["evaluation"] = evaluation

    matchups = tools.analyze_matchups(team_name, opponent_team, formation)
    if "error" in matchups:
        out["errors"].append(f"Matchup analysis: {matchups['error']}")
        return out
    out["matchups"] = matchups

    optimization = tools.optimize_formation_with_matchups(
        team_name, opponent_team, candidate_formations or SUPPORTED_FORMATIONS[:3])
    out["optimization"] = optimization if "error" not in optimization else None
    if "error" in optimization:
        out["errors"].append(f"Formation optimizer: {optimization['error']}")

    # Replacement for the single worst weak link (if any).
    replacement = None
    weak = evaluation.get("weak_links") or []
    if weak and weak[0].get("player"):
        try:
            replacement = tools.recommend_replacement(
                team_name, opponent_team, weak[0]["player"], weak[0].get("position", ""))
        except Exception as exc:  # noqa: BLE001
            replacement = {"error": str(exc)}
    out["replacement"] = replacement

    out["ok"] = True
    return out


# --------------------------------------------------------------------------- #
# Coach-facing briefing (deterministic; Gemini optional in app.py)            #
# --------------------------------------------------------------------------- #
def build_coach_briefing(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Compose the 'Agent Recommendation' panel sections from tool outputs only."""
    ev = analysis.get("evaluation", {}) or {}
    mu = analysis.get("matchups", {}) or {}
    opt = analysis.get("optimization") or {}
    rep = analysis.get("replacement") or {}
    weak = (ev.get("weak_links") or [])
    worst = weak[0] if weak else None
    adv = mu.get("strongest_advantage")
    risk = mu.get("highest_risk")

    rec_formation = opt.get("recommended_formation") or analysis.get("formation")
    sub_line = "No substitution required — no weak link flagged."
    if rep and "error" not in rep and rep.get("recommended"):
        best = rep["recommended"]
        imp = rep.get("matchup_improvement")
        sub_line = (f"Replace {rep.get('weak_player')} with {best.get('name')} "
                    f"(form {best.get('form_score')}, role fit {best.get('role_fit')}).")
        if imp:
            sub_line += (f" Matchup vs {imp.get('vs_defender')} "
                         f"{imp.get('current_matchup_score')} → {imp.get('new_matchup_score')} "
                         f"({imp.get('delta'):+}).")

    decision = (f"Set up in {rec_formation} against {analysis.get('opponent')}. "
                + (f"Address the {worst['position']} weak link. " if worst else "Current XI is sound. ")
                + ("Exploit the flagged advantage zone." if adv else ""))

    return {
        "executive_decision": decision,
        "recommended_formation": rec_formation,
        "weak_link": (f"{worst['player']} ({worst['position']}) — "
                      + "; ".join(worst.get("flags", [])) if worst else "None flagged."),
        "biggest_risk": (f"{risk['zone']}: {risk['our_player']} vs {risk['opponent_player']} "
                         f"(score {risk['matchup_score']}, {risk['risk_level']}). {risk.get('reason','')}"
                         if risk else "No duel scored."),
        "biggest_advantage": (f"{adv['zone']}: {adv['our_player']} vs {adv['opponent_player']} "
                              f"(score {adv['matchup_score']}). {adv.get('reason','')}"
                              if adv else "No duel scored."),
        "recommended_substitution": sub_line,
        "tactical_adjustment": (risk.get("tactical_action") if risk else
                                "Maintain shape; no high-risk duel detected."),
        "data_used": (ev.get("source", {}) or {}).get("collections", []),
        "memory_used": [m["memory_id"] for m in (analysis.get("memory", {}) or {}).get("memories", [])],
        "limitations": ev.get("limitations", []) or mu.get("limitations", []),
    }


# --------------------------------------------------------------------------- #
# Persistence                                                                  #
# --------------------------------------------------------------------------- #
def save_recommendation_from_ui(analysis: Dict[str, Any], briefing: Dict[str, Any],
                                ) -> Dict[str, Any]:
    """Persist a recommendation (+ matchup report) to MongoDB via the backend tool."""
    ev = analysis.get("evaluation", {}) or {}
    mu = analysis.get("matchups", {}) or {}
    opt = analysis.get("optimization") or {}
    payload = {
        "goal": analysis.get("goal"),
        "current_formation": analysis.get("formation"),
        "recommended_formation": briefing.get("recommended_formation"),
        "executive_decision": briefing.get("executive_decision"),
        "formation_ranking": opt.get("ranking", []),
        "weak_links": ev.get("weak_links", []),
        "replacement": (analysis.get("replacement")
                        if analysis.get("replacement") and "error" not in analysis["replacement"]
                        else None),
        "matchup_evidence": {
            "matchup_average": mu.get("matchup_average"),
            "strongest_advantage": mu.get("strongest_advantage"),
            "highest_risk": mu.get("highest_risk"),
            "matchups": mu.get("matchups", []),
        },
        "memory_used": briefing.get("memory_used", []),
        "limitations": briefing.get("limitations", []),
        "confidence": "medium",
        "sources_used": (ev.get("source", {}) or {}).get("collections", []),
    }
    return tools.save_lineup_recommendation(
        analysis.get("team"), analysis.get("opponent"), payload)
