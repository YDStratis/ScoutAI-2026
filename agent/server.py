"""Scout.AI — ADK Coach Agent dashboard (FastAPI backend).

This replaces the Streamlit app (`app.py`) with a thin JSON API over the same
deterministic backend. It serves a static single-page frontend (static/) and
exposes the existing `frontend_adapter` functions as endpoints — no scoring
logic lives here and no tactical values are invented: every number comes from a
backend tool, exactly as before.

Run from the agent/ directory (or repo root):
    uvicorn server:app --reload --port 8000
    # then open http://localhost:8000

Endpoints:
    GET  /api/status                      -> backend health + data coverage
    GET  /api/teams                       -> teams + which have match-stat data
    POST /api/analyze                     -> full tactical analysis + briefing
    POST /api/save                        -> persist a recommendation to MongoDB
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import frontend_adapter as fa

app = FastAPI(title="Scout.AI · Coach Console", version="1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Short-lived, in-process cache so "Save" can reuse the analysis the coach is
# looking at without recomputing (single-coach demo; not multi-tenant state).
_ANALYSIS_CACHE: Dict[str, Dict[str, Any]] = {}


# --------------------------------------------------------------------------- #
# Request models                                                              #
# --------------------------------------------------------------------------- #
class AnalyzeRequest(BaseModel):
    team: str
    opponent: str
    formation: str = "4-3-3"
    goal: str = ""
    optimize: bool = False


class SaveRequest(BaseModel):
    analysis_id: str


# --------------------------------------------------------------------------- #
# API                                                                          #
# --------------------------------------------------------------------------- #
@app.get("/api/status")
def status() -> Dict[str, Any]:
    """Backend health (Mongo/ADK) plus the list of fully-covered teams."""
    st = fa.get_backend_status()
    covered = sorted(fa.teams_with_match_stats()) if st["mongo"].get("ok") else []
    return {"status": st, "covered_teams": covered}


@app.get("/api/teams")
def teams() -> Dict[str, Any]:
    """All national teams, flagged by match-stat coverage."""
    names = fa.list_teams()
    covered = fa.teams_with_match_stats()
    return {
        "teams": names,
        "covered": sorted(covered),
        "formations": fa.SUPPORTED_FORMATIONS,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> Dict[str, Any]:
    """Run the deterministic pipeline and return analysis + coach briefing.

    Mirrors the Streamlit `run_full_analysis` -> `build_coach_briefing` flow.
    The full analysis is cached under a returned `analysis_id` so /api/save can
    persist exactly what the coach saw.
    """
    analysis = fa.run_full_analysis(
        req.team, req.opponent, req.formation, goal=req.goal
    )
    briefing = fa.build_coach_briefing(analysis) if analysis.get("ok") else None

    analysis_id = uuid.uuid4().hex
    _ANALYSIS_CACHE[analysis_id] = {"analysis": analysis, "briefing": briefing}
    # Keep the cache from growing unbounded across a long session.
    if len(_ANALYSIS_CACHE) > 64:
        for stale in list(_ANALYSIS_CACHE)[:-32]:
            _ANALYSIS_CACHE.pop(stale, None)

    return {"analysis_id": analysis_id, "analysis": analysis, "briefing": briefing}


@app.post("/api/save")
def save(req: SaveRequest) -> Dict[str, Any]:
    """Persist the cached analysis as a recommendation (+ agent run) to MongoDB."""
    cached = _ANALYSIS_CACHE.get(req.analysis_id)
    if not cached or not cached.get("briefing"):
        raise HTTPException(404, "Analysis not found or not saveable. Re-run analysis.")

    analysis, briefing = cached["analysis"], cached["briefing"]
    try:
        saved = fa.save_recommendation_from_ui(analysis, briefing)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Save failed: {exc}") from exc

    # Best-effort agent-run record (matches app.py behaviour).
    try:
        from coach_agent import memory
        run = memory.save_agent_run(
            analysis.get("goal", ""), briefing["executive_decision"],
            ["evaluate_lineup", "analyze_matchups",
             "optimize_formation_with_matchups", "recommend_replacement"],
            briefing.get("data_used", []), briefing.get("memory_used", []),
            briefing.get("limitations", []))
        saved["run_id"] = run.get("run_id")
    except Exception:  # noqa: BLE001
        pass

    return {"saved": saved}


# --------------------------------------------------------------------------- #
# Static frontend                                                              #
# --------------------------------------------------------------------------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
