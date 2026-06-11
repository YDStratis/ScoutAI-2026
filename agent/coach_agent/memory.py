"""MongoDB-backed memory for the Scout.AI Coach Agent.

Independent of ADK's built-in session memory: memories, task plans, run audit
logs and recommendations all live in Atlas so long-horizon coaching work can
resume across sessions.
"""
import re
from datetime import datetime, timezone

from .db import get_db
from .schemas import COL_AGENT_RUNS, COL_MEMORY


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def search_coach_memory(query: str, team_name: str = "", opponent_team: str = "",
                        limit: int = 5) -> dict:
    """Search past coaching memories (decisions, findings, preferences) before recommending.

    Memory is prior decision history, not absolute truth — cite memory ids when used.

    Args:
        query: Free-text query, e.g. "right wing matchup France".
        team_name: Optional filter by our team.
        opponent_team: Optional filter by opponent.
        limit: Max results (default 5).
    """
    db = get_db()
    filters = []
    if team_name:
        filters.append({"team_name": re.compile(re.escape(team_name), re.I)})
    if opponent_team:
        filters.append({"opponent_team": re.compile(re.escape(opponent_team), re.I)})
    words = [w for w in re.split(r"\W+", query or "") if len(w) > 2]
    if words:
        rx = re.compile("|".join(re.escape(w) for w in words), re.I)
        filters.append({"$or": [{"content": rx}, {"tags": rx}, {"memory_type": rx}]})
    q = {"$and": filters} if filters else {}
    docs = list(db[COL_MEMORY].find(q).sort("created_at", -1).limit(limit))
    items = [{"memory_id": str(d["_id"]), "memory_type": d.get("memory_type"),
              "content": d.get("content"), "team_name": d.get("team_name"),
              "opponent_team": d.get("opponent_team"), "tags": d.get("tags", []),
              "created_at": d.get("created_at")} for d in docs]
    return {"count": len(items), "memories": items, "collection": COL_MEMORY}


def write_coach_memory(memory_type: str, content: str, team_name: str = "",
                       opponent_team: str = "", tags: list = None,
                       source: str = "agent") -> dict:
    """Save a coaching memory (decision, tactical finding, coach preference).

    Args:
        memory_type: e.g. "decision", "tactical_finding", "preference", "observation".
        content: The memory text.
        team_name: Our team this relates to (optional).
        opponent_team: Opponent this relates to (optional).
        tags: Optional tags, e.g. ["RW", "matchup"].
        source: Who created it (default "agent").
    """
    db = get_db()
    doc = {"memory_type": memory_type, "content": content, "team_name": team_name,
           "opponent_team": opponent_team, "tags": tags or [], "source": source,
           "created_at": _now()}
    res = db[COL_MEMORY].insert_one(doc)
    return {"saved": True, "memory_id": str(res.inserted_id), "collection": COL_MEMORY}


def save_agent_run(user_goal: str, final_answer: str, tools_used: list,
                   sources_used: list, memory_used: list, limitations: list) -> dict:
    """Audit-log a completed agent run (goal, answer, tools, sources, memory, limitations).

    Args:
        user_goal: What the coach asked for.
        final_answer: The final recommendation text.
        tools_used: Tool names invoked during the run.
        sources_used: Collections/ids the answer is grounded on.
        memory_used: Memory ids consulted.
        limitations: Data gaps or caveats stated in the answer.
    """
    db = get_db()
    doc = {"user_goal": user_goal, "final_answer": final_answer,
           "tools_used": tools_used or [], "sources_used": sources_used or [],
           "memory_used": memory_used or [], "limitations": limitations or [],
           "agent": "scout_ai_coach", "created_at": _now()}
    res = db[COL_AGENT_RUNS].insert_one(doc)
    return {"saved": True, "run_id": str(res.inserted_id), "collection": COL_AGENT_RUNS}
