"""Lightweight schemas and collection names for the Scout.AI Coach Agent.

These TypedDicts document the document shapes; they are not enforced.
Collection name constants are the single source of truth for tools/memory.
"""
from typing import List, TypedDict

# ---- Normalized collections (written by the BALLDONTLIE importer 07_*.py) ----
COL_PLAYERS = "players"
COL_TEAMS = "teams"

# ---- Raw BALLDONTLIE collections (source of truth, read-only) ----
COL_BDL_PLAYERS = "bdl_players"
COL_BDL_ROSTERS = "bdl_rosters"
COL_BDL_TEAMS = "bdl_teams"
COL_BDL_PLAYER_MATCH_STATS = "bdl_player_match_stats"
COL_BDL_TEAM_MATCH_STATS = "bdl_team_match_stats"
COL_BDL_MATCH_LINEUPS = "bdl_match_lineups"
COL_BDL_MATCH_TEAM_FORM = "bdl_match_team_form"

# ---- Collections (owned/written by the coach agent) ----
COL_LINEUPS = "lineups"
COL_PLAYER_ATTRIBUTES = "player_attributes"
COL_MATCHUP_REPORTS = "matchup_reports"
COL_MATCH_STATS = "player_match_stats"
COL_OPPONENT_PROFILES = "opponent_profiles"
COL_RECOMMENDATIONS = "lineup_recommendations"
COL_MEMORY = "coach_agent_memory"
COL_TASK_PLANS = "coach_task_plans"
COL_AGENT_RUNS = "coach_agent_runs"


class PlayerStats(TypedDict, total=False):
    # Existing ingestion fields
    speed: float
    goals: int
    assists: int
    shots_on_target: float
    dribbles: float
    passes_accuracy: float
    tackles: float
    # Extended fields (synthetic/demo players only; absent on real docs)
    acceleration: float
    dribbling: float
    finishing: float
    defending: float
    physicality: float
    work_rate: float
    role_fit: float


class Player(TypedDict, total=False):
    name: str
    country: str
    team: str
    position: str
    alt_positions: List[str]
    age: int
    stats: PlayerStats
    form: List[str]  # ["W", "D", "L", ...]
    availability: str  # "available" | "injured" | "doubtful"
    is_synthetic: bool


class LineupSlot(TypedDict):
    position: str  # GK, LB, CB, RB, DM, CM, CAM, LW, RW, ST, LWB, RWB
    player_name: str


class Lineup(TypedDict, total=False):
    team_name: str
    formation: str  # "4-3-3", "4-2-3-1", "3-5-2"
    players: List[LineupSlot]
    is_default: bool
    is_synthetic: bool


class MatchStat(TypedDict, total=False):
    player_name: str
    match_date: str  # ISO date
    opponent: str
    rating: float
    goals: int
    assists: int
    xg: float
    xa: float
    minutes: int
    is_synthetic: bool


class OpponentProfile(TypedDict, total=False):
    team_name: str
    style: str
    press_intensity: str  # "low" | "medium" | "high"
    strengths: List[str]
    weaknesses: List[str]
    notes: str
    is_synthetic: bool


class Matchup(TypedDict, total=False):
    zone: str
    our_player: str
    opponent_player: str
    matchup_score: float  # 0-100, our perspective
    risk_level: str  # "high" | "medium" | "favorable"
    reason: str
    suggested_action: str


class Recommendation(TypedDict, total=False):
    team_name: str
    opponent_team: str
    recommendation: dict
    created_at: str


class MemoryItem(TypedDict, total=False):
    memory_type: str
    content: str
    team_name: str
    opponent_team: str
    tags: List[str]
    source: str
    created_at: str


class TaskPlan(TypedDict, total=False):
    goal: str
    team_name: str
    opponent_team: str
    steps: List[dict]  # {name, status, notes}
    status: str
    created_at: str
