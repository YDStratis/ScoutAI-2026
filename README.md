# Scout AI — MongoDB Setup

## Quick Start (2 hours total)

### Prerequisites
```bash
python -m pip install -r requirements.txt
npm install -g @mongodb-js/mongodb-mcp-server
```

### .env setup
Copy `.env.example` to `.env` and fill in:
```
MONGODB_URI=mongodb+srv://scoutadmin:PASSWORD@scout-cluster.xxxxx.mongodb.net/
GOOGLE_API_KEY=your_google_api_key
DB_NAME=scoutai
# Optional for API-based index creation:
ATLAS_PUBLIC_KEY=...
ATLAS_PRIVATE_KEY=...
ATLAS_PROJECT_ID=...
ATLAS_CLUSTER_NAME=scout-cluster
```

### Step-by-step
```bash
python 01_ingest_data.py       # ~15 min (embeddings)
python 02_create_atlas_indexes.py  # ~5 min + 3 min build
python 03_setup_mcp.py         # verify + MCP config
python 04_test_queries.py      # test all 4 patterns
```

## Collections
| Collection | Purpose |
|---|---|
| `players` | 30+ WC2026 players with 768-dim embeddings |
| `teams` | 14 national teams with group/style data |
| `sessions` | Persistent agent memory per user session |

## Atlas Indexes
| Index | Type | Purpose |
|---|---|---|
| `vector_index` | Vector Search | Semantic player similarity |
| `player_search` | Full-Text | Name/country/position lookup |
| Standard | B-Tree | Stats filters, sorting |

## MCP Config
The file `mcp_configs/mcp_config.json` is ready to use.
Give it to the agent team for Gemini CLI integration.
