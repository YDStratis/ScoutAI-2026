"""Google ADK root agent for Scout.AI Coach.

If google-adk is not installed, root_agent is None (deterministic tools and the
Streamlit app still work); importing this module never crashes.
"""
import os
import sys

from . import memory, tools
from .mcp_tools import get_mongodb_mcp_toolset
from .prompts import SYSTEM_INSTRUCTION

DETERMINISTIC_TOOLS = [
    tools.get_player,
    tools.get_team_players,
    tools.get_current_lineup,
    tools.get_opponent_lineup,
    tools.get_player_recent_form,
    tools.compare_players,
    tools.evaluate_matchup,
    tools.analyze_matchups,
    tools.evaluate_lineup,
    tools.recommend_replacement,
    tools.recommend_formation,
    tools.optimize_formation_with_matchups,
    tools.save_lineup_recommendation,
    tools.create_task_plan,
    tools.update_task_step,
    tools.list_known_teams,
    memory.search_coach_memory,
    memory.write_coach_memory,
    memory.save_agent_run,
]


def _build_root_agent():
    try:
        try:
            from google.adk.agents import Agent as _Agent
        except ImportError:
            from google.adk.agents import LlmAgent as _Agent
    except ImportError as e:
        print(f"[agent] google-adk not available ({e}); root_agent is None. "
              "Run: pip install google-adk", file=sys.stderr)
        return None

    agent_tools = list(DETERMINISTIC_TOOLS)
    mcp_toolset = get_mongodb_mcp_toolset()
    if mcp_toolset is not None:
        agent_tools.append(mcp_toolset)

    return _Agent(
        name="scout_ai_coach",
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        description=(
            "Tactical assistant for national-team coaches: evaluates the starting XI, "
            "detects weak links, analyzes player-vs-player matchups, and optimizes the "
            "formation against a specific opponent using MongoDB-grounded data."
        ),
        instruction=SYSTEM_INSTRUCTION,
        tools=agent_tools,
    )


root_agent = _build_root_agent()
