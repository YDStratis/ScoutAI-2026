# Scout.AI Coach Agent

A tactical assistant for national-team coaches preparing for the 2026 World Cup,
built with **Google ADK + Gemini + MongoDB Atlas**. It evaluates a starting XI,
detects weak links, scores player-vs-player matchups against a specific opponent,
recommends substitutions, optimizes the formation, and persists every
recommendation, memory and audit log to MongoDB.

It runs on **real BALLDONTLIE World Cup data** imported into MongoDB Atlas
(database `scoutai`) by the repo-root importer `07_fetch_balldontlie_no_matches.py`.
The agent lives entirely under `agent/` and never modifies the importer.

## What the agent does

1. **Roster / player lookup** — reads real squads and identities from MongoDB.
2. **Lineup evaluation** — builds a best-XI for a formation and flags weak links
   (recent avg rating < 5.8, form < 55, role fit < 60, matchup < 45).
3. **Matchup analysis** — infers positional duels from the formation (our RW vs
   their LB, our LB vs their RW, ST vs CBs, midfield battle…) and scores each
   0–100: `attribute_advantage*0.40 + form_advantage*0.25 + role_fit_advantage*0.20 + tactical_context*0.15`
   (risk: 0–44 high, 45–59 medium, 60–74 manageable, 75–100 advantage).
4. **Formation optimization** — compares 4-3-3 / 4-2-3-1 (and others):
   `form_avg*0.30 + role_fit_avg*0.20 + matchup_avg*0.30 + tactical_balance*0.10 + availability*0.10`.
5. **Replacement recommendation** — ranks roster alternatives by form, role fit
   and the direct matchup, and reports the matchup-score improvement.
6. **Persistence & memory** — recommendations, matchup reports, memories, task
   plans and run audit logs in MongoDB.

## How BALLDONTLIE data is used

| Signal | Source | Notes |
| --- | --- | --- |
| Player identity, team, position | `bdl_rosters`, `bdl_players`, `players` | Position is coarse: **G/D/M/F**. |
| Team name ↔ id | `teams`, `bdl_teams` | Roster docs store numeric `team_id`. |
| Recent form (rating, xG, xA, goals, minutes) | `bdl_player_match_stats` | Joined by `player_id` = roster `player.id`. The **only** real performance signal. |
| Real historical formations | `bdl_match_lineups` | Reference for valid formation strings. |

### Raw `bdl_*` vs normalized collections

- **Raw `bdl_*`** are verbatim API documents (source of truth, read-only),
  carrying a `_source` provenance block and `_import_key`.
- **Normalized** `players` / `teams` are flattened convenience copies the
  importer derives from the raw collections. Tools prefer raw `bdl_rosters` for
  rosters (it links players↔team↔season) and fall back to normalized `players`.

### Verified vs derived data (anti-hallucination)

Rosters only carry coarse **G/D/M/F** positions and no tactical attributes
(speed/dribbling/defending are absent). So the agent **separates**:

- **Verified**: player identities, rosters, and per-match stats.
- **Derived** (clearly flagged): granular slots (RW/LB/CB/ST…) inferred from
  G/D/M/F, provisional best-XI lineups, and all heuristic scores. Tool outputs
  carry `provisional`, `exact_fit`, `missing_data`, `low_confidence` and
  `limitations` so nothing derived is presented as confirmed fact.

Every score is computed by **deterministic Python**, never the LLM. Tools return
`{"error": ...}` or partial results with `missing_data` rather than guessing, and
every result carries a `source` block (collections / ids) for citation.

## MongoDB collections (db `scoutai`)

| Collection | Role |
| --- | --- |
| `bdl_players`, `bdl_rosters`, `bdl_teams` | Raw squad/identity data (read) |
| `bdl_player_match_stats` | Raw per-match performance (read) |
| `bdl_match_lineups`, `bdl_team_match_stats`, `bdl_match_team_form` | Raw match detail (read) |
| `players`, `teams` | Normalized convenience copies (read) |
| `lineups` | Saved lineups; else provisional ones are generated on the fly (agent) |
| `player_attributes` | Optional derived tactical attributes (agent, currently empty) |
| `matchup_reports` | Saved matchup evidence (agent write) |
| `lineup_recommendations` | Saved recommendations (agent write) |
| `coach_agent_memory` | Long-horizon memories (agent write) |
| `coach_task_plans` | Multi-step task plans (agent write) |
| `coach_agent_runs` | Run audit log (agent write) |

## Memory design

`coach_agent_memory` is searched (regex over content/tags, filtered by
team/opponent) before recommending and cited by id; useful findings are written
back with `write_coach_memory`. `coach_task_plans` + `update_task_step` support
long-horizon work that resumes across sessions; `coach_agent_runs` audit-logs
each run. Memory is treated as prior reasoning, not verified truth.

## MCP design

`coach_agent/mcp_tools.py` optionally builds a Google ADK `McpToolset` running
the official MongoDB MCP server **read-only**
(`npx -y mongodb-mcp-server@latest --readOnly`). It is **off by default**
(`ENABLE_MONGODB_MCP=false`) and degrades gracefully: if the flag is off, or
Node/npx / the ADK MCP classes are missing, it logs a warning and returns
`None` — the PyMongo tools remain the reliable path and all writes go through
them. `agent/mcp.example.json` is a config template for external MCP clients.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env   # then fill in GOOGLE_API_KEY + MONGODB_URI
```

Environment variables (see `.env.example`): `GOOGLE_API_KEY`, `MONGODB_URI`,
`SCOUT_DB_NAME` (default `scoutai`), `GEMINI_MODEL` (default `gemini-2.0-flash`),
`ENABLE_MONGODB_MCP` (default `false`).

## Run

```powershell
# Backend smoke test (auto-discovers real teams from MongoDB)
python agent/smoke_test_coach_agent.py

# Verify the ADK agent imports
python -c "from agent.coach_agent.agent import root_agent; print(root_agent.name)"

# Chat with the agent in the ADK web UI
cd agent
adk web --no-reload   # open http://localhost:8000 and pick "coach_agent"
```

## Known limitations

- Roster positions are coarse **G/D/M/F**; all granular slots and the
  attacking/defending duels built on them are **derived**, not confirmed.
- Tactical attributes (speed/dribbling/defending) are **not in the data**, so
  matchup `attribute_advantage` is derived from match stats or reported missing.
- `bdl_player_match_stats` covers only a subset of players; players without
  stats return no form (`form_available: false`) instead of an invented number.
- Lineups are **provisional best-XIs** unless a real one is saved in `lineups`.
- "Recent" form orders matches by `match_id` (no per-match dates in the data).
