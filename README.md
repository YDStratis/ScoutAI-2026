# Scout AI 🤖⚽

> AI-powered football coach assistant for FIFA World Cup 2026. Analyzes formations, detects underperforming players, and suggests optimal substitutions based on real match stats and opponent matchups.

**Built with:** Google ADK · Gemini 2.0 Flash · MongoDB Atlas Vector Search · BALLDONTLIE API

---

## What it does

Scout AI acts as an intelligent assistant for national team coaches. Given a team, opponent, and formation, it:

- Evaluates the starting XI and flags weak links based on form, rating, and role fit
- Analyzes player matchups across key zones (e.g. RW vs LB speed comparison)
- Recommends the optimal formation from a ranked comparison
- Suggests the best replacement for underperforming players
- Generates a full coach briefing using Gemini, grounded only in real data

---

## Quick Start

### Prerequisites

```bash
python -m pip install -r requirements.txt
```

### Environment setup

Copy `.env.example` to `.env` and fill in:

```
MONGODB_URI=mongodb+srv://YOUR_USER:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?appName=Cluster0
GOOGLE_API_KEY=your_gemini_api_key
BALLDONTLIE_API_KEY=your_balldontlie_api_key
DB_NAME=scoutai
```

### Data ingestion

```bash
# Fetch all 1,258 World Cup 2026 players from BALLDONTLIE API
python 07_fetch_balldontlie_no_matches.py --seasons 2026

# Ingest sample players with vector embeddings (Gemini)
python 01_ingest_data.py

# Create Atlas Search + Vector Search indexes
python 02_create_atlas_indexes.py
```

### Run the app

```bash
streamlit run agent/app.py
```

Open `http://localhost:8501` in your browser.

---

## MongoDB Collections

| Collection | Source | Purpose |
|---|---|---|
| `wc_teams` | BALLDONTLIE API | All 48 World Cup 2026 teams |
| `wc_players` | BALLDONTLIE API | 1,258 players with height, position, age |
| `wc_rosters` | BALLDONTLIE API | Players per team with goals, assists, avg rating |
| `wc_matches` | BALLDONTLIE API | All 104 matches with formations |
| `wc_standings` | BALLDONTLIE API | Group stage standings |
| `players` | Gemini embeddings | 34 key players with 3072-dim vector embeddings |
| `sessions` | Agent memory | Persistent coach session memory |

## Atlas Indexes

| Index | Type | Purpose |
|---|---|---|
| `vector_index` | Vector Search | Semantic player similarity (3072 dims, cosine) |
| `player_search` | Full-Text Search | Name, country, position lookup |
| Standard | B-Tree | Stats filters, sorting, aggregations |

---

## Project Structure

```
scout-ai-2026/
├── agent/
│   ├── app.py                    # Streamlit UI
│   ├── coach_agent/
│   │   ├── agent.py              # Google ADK agent
│   │   ├── tools.py              # Lineup evaluation, matchup analysis
│   │   ├── db.py                 # MongoDB connection
│   │   ├── memory.py             # Persistent session memory
│   │   ├── prompts.py            # Gemini system prompts
│   │   └── schemas.py            # Data models
│   └── seed_coach_demo_data.py   # Demo data seeder
├── 01_ingest_data.py             # Vector embeddings ingestion
├── 02_create_atlas_indexes.py    # Atlas index creation
├── 05_fetch_balldontlie.py       # Full data fetch (with match stats)
├── 07_fetch_balldontlie_no_matches.py  # Data fetch (no match stats)
├── players_data.py               # Sample player data
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | Google ADK |
| LLM | Gemini 2.0 Flash |
| Database | MongoDB Atlas (M0 Free Tier) |
| Vector Search | MongoDB Atlas Vector Search |
| Embeddings | Google `gemini-embedding-001` (3072 dims) |
| Player data | BALLDONTLIE FIFA World Cup API |
| Frontend | Streamlit |

---

## Hackathon

Built for the **Google Cloud Rapid Agent Hackathon** — MongoDB partner track.

> Powered by MongoDB Atlas 