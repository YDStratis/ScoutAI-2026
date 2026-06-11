# Deploying Scout.AI Coach Console

The dashboard is a FastAPI app (`agent/server.py`) that serves a static frontend
(`agent/static/`) and reads real BALLDONTLIE data from **MongoDB Atlas**. It is
hostable on any push-to-deploy PaaS. Configs for **Render** (`render.yaml`) and
**Railway / Heroku-style** (`Procfile`) are included.

Repo root is this `ScoutAI-2026/` folder, so all deploy paths are relative to it.
The production start command is:

```
uvicorn agent.server:app --host 0.0.0.0 --port $PORT
```

---

## 0. One-time prerequisite: open MongoDB Atlas to the host

Your DB currently only allows the IPs in its allowlist. A cloud host's egress IP
is dynamic, so:

1. Atlas → **Network Access** → **Add IP Address** → **Allow access from anywhere**
   (`0.0.0.0/0`).
2. (Tighter option) Use the platform's documented static egress IPs instead.

Without this the deploy boots but `/api/status` reports *MongoDB unreachable*.

---

## Option A — Render (uses `render.yaml`)

1. Push this repo to GitHub (see "First push" below).
2. Render → **New +** → **Blueprint** → select the repo. Render reads
   `render.yaml` and provisions a free web service named `scout-ai`.
3. When prompted (or under **Environment** after the first deploy), set the two
   secret env vars:
   - `MONGODB_URI` — your Atlas connection string (no angle brackets on the password)
   - `GOOGLE_API_KEY` — Gemini key (optional; only enables the ADK badge/agent path)
4. Deploy. Render runs `pip install -r requirements.txt`, then the start command.
   Health check hits `/api/status`. Open the service URL.

The non-secret vars (`SCOUT_DB_NAME`, `GEMINI_MODEL`, `ENABLE_MONGODB_MCP`) are
already baked into `render.yaml`.

---

## Option B — Railway (uses `Procfile`)

1. Push to GitHub.
2. Railway → **New Project** → **Deploy from GitHub repo** → select the repo.
   Nixpacks auto-detects Python, installs `requirements.txt`, and uses the
   `Procfile` web process. `runtime.txt` pins Python 3.11.9.
3. **Variables** tab → add:
   ```
   MONGODB_URI       = <your atlas uri>
   GOOGLE_API_KEY    = <gemini key, optional>
   SCOUT_DB_NAME     = scoutai
   GEMINI_MODEL      = gemini-2.0-flash
   ENABLE_MONGODB_MCP= false
   ```
   Railway injects `$PORT` automatically.
4. Deploy and open the generated domain (Settings → **Generate Domain**).

---

## First push to GitHub (if not already a remote)

```powershell
# from ScoutAI-2026/
git add Procfile render.yaml runtime.txt DEPLOY.md requirements.txt agent
git commit -m "Add FastAPI host configs for Render/Railway"
git remote add origin https://github.com/<you>/<repo>.git   # skip if already set
git push -u origin main
```

`.env` is gitignored — real secrets are never committed. Set them in the host's
dashboard instead.

---

## Verifying a live deploy

- `GET /api/status` → `mongo.ok: true` and a non-empty `covered_teams`.
- `GET /` → the dashboard loads; pick South Korea vs Canada → **Load Tactical
  Analysis** populates the pitch, matchups and briefing.

If `/api/status` shows Mongo unreachable, re-check step 0 and the `MONGODB_URI`.
