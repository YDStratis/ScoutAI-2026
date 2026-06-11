"""
BALLDONTLIE FIFA World Cup exporter/importer for MongoDB Atlas.

Default:
    python 05_fetch_balldontlie.py --season 2026 --core

Full GOAT import:
    python 05_fetch_balldontlie.py --seasons 2018 2022 2026 --full

Dry run:
    python 05_fetch_balldontlie.py --season 2026 --core --dry-run

Required .env:
    BALLDONTLIE_API_KEY=...
    MONGODB_URI=...
    DB_NAME=scoutai              # or SCOUT_DB_NAME=scout_ai
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError

BASE_URL = "https://api.balldontlie.io/fifa/worldcup/v1"
PROVIDER = "balldontlie"
SPORT = "fifa_worldcup"
VALID_SEASONS = {2018, 2022, 2026}

# Endpoint registry.
# paginated=True means cursor pagination with meta.next_cursor.
CORE_ENDPOINTS = [
    {
        "name": "teams",
        "endpoint": "/teams",
        "collection": "bdl_teams",
        "natural_keys": ["id"],
        "seasons": True,
        "paginated": False,
    },
    {
        "name": "stadiums",
        "endpoint": "/stadiums",
        "collection": "bdl_stadiums",
        "natural_keys": ["id"],
        "seasons": True,
        "paginated": False,
    },
    {
        "name": "group_standings",
        "endpoint": "/group_standings",
        "collection": "bdl_group_standings",
        "natural_keys": ["season.year", "team.id", "group.id"],
        "seasons": True,
        "paginated": False,
    },
    {
        "name": "matches",
        "endpoint": "/matches",
        "collection": "bdl_matches",
        "natural_keys": ["id"],
        "seasons": True,
        "paginated": True,
    },
    {
        "name": "players",
        "endpoint": "/players",
        "collection": "bdl_players",
        "natural_keys": ["id"],
        "seasons": True,
        "paginated": True,
    },
    {
        "name": "rosters",
        "endpoint": "/rosters",
        "collection": "bdl_rosters",
        "natural_keys": ["season.year", "team_id", "player.id"],
        "seasons": True,
        "paginated": True,
    },
]

DETAIL_ENDPOINTS = [
    {
        "name": "match_lineups",
        "endpoint": "/match_lineups",
        "collection": "bdl_match_lineups",
        "natural_keys": ["match_id", "team_id", "player.id"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "match_events",
        "endpoint": "/match_events",
        "collection": "bdl_match_events",
        "natural_keys": ["id"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "player_match_stats",
        "endpoint": "/player_match_stats",
        "collection": "bdl_player_match_stats",
        "natural_keys": ["match_id", "player_id", "team_id"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "team_match_stats",
        "endpoint": "/team_match_stats",
        "collection": "bdl_team_match_stats",
        "natural_keys": ["match_id", "team_id"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "match_shots",
        "endpoint": "/match_shots",
        "collection": "bdl_match_shots",
        "natural_keys": ["id"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "match_momentum",
        "endpoint": "/match_momentum",
        "collection": "bdl_match_momentum",
        "natural_keys": ["match_id", "minute"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "match_best_players",
        "endpoint": "/match_best_players",
        "collection": "bdl_match_best_players",
        "natural_keys": ["match_id", "player_id", "team_id", "side_rank"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "match_avg_positions",
        "endpoint": "/match_avg_positions",
        "collection": "bdl_match_avg_positions",
        "natural_keys": ["match_id", "player_id", "team_id"],
        "paginated": True,
        "match_filter": True,
    },
    {
        "name": "match_team_form",
        "endpoint": "/match_team_form",
        "collection": "bdl_match_team_form",
        "natural_keys": ["match_id", "team_id"],
        "paginated": True,
        "match_filter": True,
    },
]

ODDS_ENDPOINTS = [
    {
        "name": "odds",
        "endpoint": "/odds",
        "collection": "bdl_odds",
        "natural_keys": ["id"],
        "seasons": True,
        "paginated": True,
    },
    {
        "name": "odds_futures",
        "endpoint": "/odds/futures",
        "collection": "bdl_odds_futures",
        "natural_keys": ["id"],
        "seasons": True,
        "paginated": False,
    },
]

PLAYER_PROPS_ENDPOINT = {
    "name": "player_props",
    "endpoint": "/odds/player_props",
    "collection": "bdl_player_props",
    "natural_keys": ["id"],
    "paginated": False,
}


@dataclass
class EndpointSummary:
    collection: str
    endpoint: str
    fetched: int = 0
    upserted: int = 0
    modified: int = 0
    pages: int = 0
    errors: List[str] = field(default_factory=list)


class ApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, endpoint: str, params: Dict[str, Any]):
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint
        self.params = params


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def get_nested(doc: Dict[str, Any], dotted: str) -> Any:
    cur: Any = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def build_bdl_key(doc: Dict[str, Any], endpoint: str, natural_keys: List[str]) -> str:
    parts: List[str] = []
    missing = False
    for key in natural_keys:
        value = get_nested(doc, key)
        if value is None:
            missing = True
            break
        parts.append(f"{key}={value}")
    if not missing and parts:
        return f"{endpoint}|" + "|".join(parts)
    return f"{endpoint}|hash={stable_hash(doc)}"


def with_source_metadata(
    doc: Dict[str, Any],
    endpoint: str,
    params: Dict[str, Any],
    import_run_id: str,
    natural_keys: List[str],
) -> Dict[str, Any]:
    clean_doc = dict(doc)
    clean_doc["_bdl_key"] = build_bdl_key(clean_doc, endpoint, natural_keys)
    clean_doc["_source"] = {
        "provider": PROVIDER,
        "sport": SPORT,
        "endpoint": endpoint,
        "params": params,
        "fetched_at": now_utc(),
        "import_run_id": import_run_id,
        "is_raw_api_data": True,
    }
    return clean_doc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export BALLDONTLIE FIFA World Cup data to MongoDB.")
    season_group = parser.add_mutually_exclusive_group()
    season_group.add_argument("--season", type=int, default=2026, help="Single World Cup season. Default: 2026")
    season_group.add_argument("--seasons", type=int, nargs="+", help="One or more seasons: 2018 2022 2026")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--core", action="store_true", help="Fetch teams, stadiums, standings, matches, players, rosters")
    mode.add_argument("--full", action="store_true", help="Fetch core plus match details and odds/player props")
    parser.add_argument("--odds", action="store_true", help="Include odds endpoints with core mode")
    parser.add_argument("--refresh", action="store_true", help="Delete bdl_* collections before import")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only first page where applicable and do not write to MongoDB")
    parser.add_argument("--sleep", type=float, default=0.15, help="Seconds to sleep between requests. Default: 0.15")
    parser.add_argument("--match-chunk-size", type=int, default=50, help="Number of match IDs per detail request chunk")
    return parser.parse_args()


def selected_seasons(args: argparse.Namespace) -> List[int]:
    seasons = args.seasons if args.seasons else [args.season]
    bad = [s for s in seasons if s not in VALID_SEASONS]
    if bad:
        raise SystemExit(f"Invalid season(s): {bad}. Allowed: {sorted(VALID_SEASONS)}")
    return sorted(set(seasons))


def load_env() -> Tuple[str, str, str]:
    load_dotenv()
    api_key = os.getenv("BALLDONTLIE_API_KEY", "").strip()
    mongo_uri = os.getenv("MONGODB_URI", "").strip()
    db_name = (os.getenv("DB_NAME") or os.getenv("SCOUT_DB_NAME") or "scout_ai").strip()

    if not api_key:
        raise SystemExit("BALLDONTLIE_API_KEY is missing from .env")
    if not mongo_uri:
        raise SystemExit("MONGODB_URI is missing from .env")
    if not db_name:
        raise SystemExit("DB_NAME or SCOUT_DB_NAME is empty")
    return api_key, mongo_uri, db_name


def get_db(mongo_uri: str, db_name: str) -> Database:
    client = MongoClient(mongo_uri)
    db = client[db_name]
    db.command("ping")
    return db


def query_params(params: Dict[str, Any]) -> List[Tuple[str, Any]]:
    pairs: List[Tuple[str, Any]] = []
    for key, value in params.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                pairs.append((key, item))
        else:
            pairs.append((key, value))
    return pairs


class BDLClient:
    def __init__(self, api_key: str, sleep_seconds: float = 0.15, max_retries: int = 4):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": api_key})
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        url = f"{BASE_URL}{endpoint}"
        attempt = 0
        delay = self.sleep_seconds

        while True:
            if delay > 0:
                time.sleep(delay)
            try:
                response = self.session.get(url, params=query_params(params), timeout=30)
            except requests.RequestException as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise ApiError(0, f"Network error after retries: {exc}", endpoint, params) from exc
                delay = max(delay * 2, 1.0)
                print(f"  network error; retry {attempt}/{self.max_retries} in {delay:.1f}s")
                continue

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise ApiError(200, f"Invalid JSON response: {response.text[:400]}", endpoint, params) from exc

            body = response.text[:800]
            if response.status_code == 401:
                raise ApiError(401, "Unauthorized or GOAT access missing", endpoint, params)
            if response.status_code == 429:
                attempt += 1
                if attempt > self.max_retries:
                    raise ApiError(429, f"Rate limited after retries: {body}", endpoint, params)
                delay = max(delay * 2, 10.0)
                print(f"  rate limited; retry {attempt}/{self.max_retries} in {delay:.1f}s")
                continue
            if response.status_code in (500, 503):
                attempt += 1
                if attempt > self.max_retries:
                    raise ApiError(response.status_code, f"Server error after retries: {body}", endpoint, params)
                delay = max(delay * 2, 2.0)
                print(f"  server error {response.status_code}; retry {attempt}/{self.max_retries} in {delay:.1f}s")
                continue
            if response.status_code in (400, 404, 406):
                raise ApiError(response.status_code, body, endpoint, params)

            raise ApiError(response.status_code, body, endpoint, params)


def upsert_many(collection: Collection, docs: List[Dict[str, Any]], dry_run: bool = False) -> Tuple[int, int]:
    if not docs:
        return 0, 0
    if dry_run:
        return 0, 0

    operations = [UpdateOne({"_bdl_key": doc["_bdl_key"]}, {"$set": doc}, upsert=True) for doc in docs]
    try:
        result = collection.bulk_write(operations, ordered=False)
        return int(result.upserted_count), int(result.modified_count)
    except BulkWriteError as exc:
        details = exc.details or {}
        write_errors = details.get("writeErrors", [])
        raise RuntimeError(f"Bulk write failed for {collection.name}: {write_errors[:3]}") from exc


def fetch_endpoint(
    client: BDLClient,
    db: Database,
    spec: Dict[str, Any],
    base_params: Dict[str, Any],
    import_run_id: str,
    dry_run: bool = False,
) -> EndpointSummary:
    endpoint = spec["endpoint"]
    collection_name = spec["collection"]
    collection = db[collection_name]
    natural_keys = spec.get("natural_keys", [])
    paginated = bool(spec.get("paginated"))
    summary = EndpointSummary(collection=collection_name, endpoint=endpoint)

    params = dict(base_params)
    if paginated:
        params["per_page"] = 100

    cursor: Optional[int] = None
    while True:
        page_params = dict(params)
        if cursor is not None:
            page_params["cursor"] = cursor
        try:
            payload = client.get(endpoint, page_params)
        except ApiError as exc:
            msg = f"{exc.status_code}: {exc} params={exc.params}"
            summary.errors.append(msg)
            if exc.status_code == 401:
                raise
            print(f"  WARN {endpoint}: {msg}")
            break

        data = payload.get("data") or []
        if isinstance(data, dict):
            data = [data]
        docs = [with_source_metadata(doc, endpoint, page_params, import_run_id, natural_keys) for doc in data]
        upserted, modified = upsert_many(collection, docs, dry_run=dry_run)

        summary.fetched += len(docs)
        summary.upserted += upserted
        summary.modified += modified
        summary.pages += 1
        print(
            f"  {collection_name}: page {summary.pages}, fetched={len(docs)}, "
            f"total={summary.fetched}, upserted={summary.upserted}, modified={summary.modified}"
        )

        if dry_run:
            break
        if not paginated:
            break
        meta = payload.get("meta") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break

    return summary


def chunks(items: List[int], size: int) -> Iterable[List[int]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_season_params(seasons: List[int]) -> Dict[str, Any]:
    return {"seasons[]": seasons}


def refresh_bdl_collections(db: Database) -> None:
    print("Refreshing bdl_* collections only...")
    for name in db.list_collection_names():
        if name.startswith("bdl_"):
            print(f"  dropping {name}")
            db.drop_collection(name)


def match_ids_for_seasons(db: Database, seasons: List[int]) -> List[int]:
    cursor = db["bdl_matches"].find(
        {"season.year": {"$in": seasons}, "id": {"$ne": None}},
        {"_id": 0, "id": 1},
    )
    ids = sorted({int(doc["id"]) for doc in cursor if doc.get("id") is not None})
    return ids


def create_indexes(db: Database) -> None:
    print("Creating MongoDB indexes...")
    index_specs = {
        "bdl_teams": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)]],
        "bdl_stadiums": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)]],
        "bdl_group_standings": [[("_bdl_key", ASCENDING)], [("season.year", ASCENDING), ("team.id", ASCENDING), ("group.id", ASCENDING)]],
        "bdl_matches": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)], [("season.year", ASCENDING)], [("home_team.id", ASCENDING)], [("away_team.id", ASCENDING)]],
        "bdl_players": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)], [("name", ASCENDING)]],
        "bdl_rosters": [[("_bdl_key", ASCENDING)], [("season.year", ASCENDING), ("team_id", ASCENDING), ("player.id", ASCENDING)]],
        "bdl_match_lineups": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)], [("match_id", ASCENDING), ("team_id", ASCENDING), ("player.id", ASCENDING)]],
        "bdl_match_events": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_player_match_stats": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)], [("match_id", ASCENDING), ("player_id", ASCENDING), ("team_id", ASCENDING)]],
        "bdl_team_match_stats": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)], [("match_id", ASCENDING), ("team_id", ASCENDING)]],
        "bdl_match_shots": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_match_momentum": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_match_best_players": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_match_avg_positions": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_match_team_form": [[("_bdl_key", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_odds": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_odds_futures": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)]],
        "bdl_player_props": [[("_bdl_key", ASCENDING)], [("id", ASCENDING)], [("match_id", ASCENDING)]],
        "bdl_import_runs": [[("import_run_id", ASCENDING)], [("started_at", ASCENDING)]],
    }

    for collection_name, specs in index_specs.items():
        col = db[collection_name]
        for spec in specs:
            kwargs: Dict[str, Any] = {}
            if spec == [("_bdl_key", ASCENDING)]:
                kwargs["unique"] = True
            try:
                col.create_index(spec, **kwargs)
            except (DuplicateKeyError, PyMongoError) as exc:
                print(f"  WARN index {collection_name} {spec}: {exc}")
    try:
        db["bdl_players"].create_index([("name", "text"), ("short_name", "text")])
    except PyMongoError as exc:
        print(f"  WARN text index bdl_players: {exc}")


def lookup_team_name(db: Database, team_id: Optional[int]) -> Optional[str]:
    if team_id is None:
        return None
    doc = db["bdl_teams"].find_one({"id": team_id}, {"_id": 0, "name": 1})
    return doc.get("name") if doc else None


def normalize_for_agent(db: Database, seasons: List[int], import_run_id: str, dry_run: bool = False) -> Dict[str, int]:
    print("Normalizing BALLDONTLIE data into agent-friendly collections...")
    counts = {"teams": 0, "players": 0, "lineups": 0, "player_match_stats": 0}
    ts = now_utc()

    if not dry_run:
        # Teams
        team_ops = []
        for doc in db["bdl_teams"].find({}, {"_id": 0}):
            team_doc = {
                "source": PROVIDER,
                "source_collection": "bdl_teams",
                "bdl_team_id": doc.get("id"),
                "team_name": doc.get("name"),
                "name": doc.get("name"),
                "abbreviation": doc.get("abbreviation"),
                "country_code": doc.get("country_code"),
                "confederation": doc.get("confederation"),
                "last_updated": ts,
                "import_run_id": import_run_id,
            }
            team_ops.append(UpdateOne({"source": PROVIDER, "bdl_team_id": doc.get("id")}, {"$set": team_doc}, upsert=True))
        if team_ops:
            db["teams"].bulk_write(team_ops, ordered=False)
        counts["teams"] = len(team_ops)

        # Players from rosters are more useful to the agent because they include team and tournament stats.
        player_ops = []
        roster_query = {"season.year": {"$in": seasons}}
        for doc in db["bdl_rosters"].find(roster_query, {"_id": 0}):
            player = doc.get("player") or {}
            team_id = doc.get("team_id")
            season_year = get_nested(doc, "season.year")
            player_doc = {
                "source": PROVIDER,
                "source_collection": "bdl_rosters",
                "bdl_player_id": player.get("id"),
                "bdl_team_id": team_id,
                "season_year": season_year,
                "player_name": player.get("name"),
                "name": player.get("name"),
                "short_name": player.get("short_name"),
                "team": lookup_team_name(db, team_id),
                "position": doc.get("position") or player.get("position"),
                "date_of_birth": player.get("date_of_birth"),
                "country_code": player.get("country_code"),
                "country_name": player.get("country_name"),
                "height_cm": player.get("height_cm"),
                "jersey_number": player.get("jersey_number"),
                "appearances": doc.get("appearances"),
                "starts": doc.get("starts"),
                "minutes_played": doc.get("minutes_played"),
                "goals": doc.get("goals"),
                "assists": doc.get("assists"),
                "yellow_cards": doc.get("yellow_cards"),
                "red_cards": doc.get("red_cards"),
                "avg_rating": doc.get("avg_rating"),
                "is_synthetic": False,
                "last_updated": ts,
                "import_run_id": import_run_id,
            }
            player_ops.append(
                UpdateOne(
                    {
                        "source": PROVIDER,
                        "bdl_player_id": player.get("id"),
                        "bdl_team_id": team_id,
                        "season_year": season_year,
                    },
                    {"$set": player_doc},
                    upsert=True,
                )
            )
        if player_ops:
            db["players"].bulk_write(player_ops, ordered=False)
        counts["players"] = len(player_ops)

        # Lineups
        lineup_ops = []
        for doc in db["bdl_match_lineups"].find({}, {"_id": 0}):
            player = doc.get("player") or {}
            lineup_doc = {
                "source": PROVIDER,
                "source_collection": "bdl_match_lineups",
                "match_id": doc.get("match_id"),
                "bdl_team_id": doc.get("team_id"),
                "bdl_player_id": player.get("id"),
                "player_name": player.get("name"),
                "team": lookup_team_name(db, doc.get("team_id")),
                "position": doc.get("position") or player.get("position"),
                "formation": doc.get("formation"),
                "is_starter": doc.get("is_starter"),
                "is_substitute": doc.get("is_substitute"),
                "shirt_number": doc.get("shirt_number"),
                "last_updated": ts,
                "import_run_id": import_run_id,
            }
            lineup_ops.append(
                UpdateOne(
                    {
                        "source": PROVIDER,
                        "match_id": doc.get("match_id"),
                        "bdl_team_id": doc.get("team_id"),
                        "bdl_player_id": player.get("id"),
                    },
                    {"$set": lineup_doc},
                    upsert=True,
                )
            )
        if lineup_ops:
            db["lineups"].bulk_write(lineup_ops, ordered=False)
        counts["lineups"] = len(lineup_ops)

        # Player match stats
        stat_ops = []
        for doc in db["bdl_player_match_stats"].find({}, {"_id": 0}):
            stat_doc = dict(doc)
            stat_doc.update(
                {
                    "source": PROVIDER,
                    "source_collection": "bdl_player_match_stats",
                    "last_updated": ts,
                    "import_run_id": import_run_id,
                }
            )
            stat_ops.append(
                UpdateOne(
                    {
                        "source": PROVIDER,
                        "match_id": doc.get("match_id"),
                        "player_id": doc.get("player_id"),
                        "team_id": doc.get("team_id"),
                    },
                    {"$set": stat_doc},
                    upsert=True,
                )
            )
        if stat_ops:
            db["player_match_stats"].bulk_write(stat_ops, ordered=False)
        counts["player_match_stats"] = len(stat_ops)
    else:
        counts["teams"] = db["bdl_teams"].count_documents({})
        counts["players"] = db["bdl_rosters"].count_documents({"season.year": {"$in": seasons}})
        counts["lineups"] = db["bdl_match_lineups"].count_documents({})
        counts["player_match_stats"] = db["bdl_player_match_stats"].count_documents({})

    print(f"  normalized counts: {counts}")
    return counts


def save_import_run(
    db: Database,
    import_run_id: str,
    args: argparse.Namespace,
    seasons: List[int],
    summaries: List[EndpointSummary],
    normalized_counts: Dict[str, int],
    started_at: datetime,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    doc = {
        "import_run_id": import_run_id,
        "provider": PROVIDER,
        "sport": SPORT,
        "seasons": seasons,
        "args": vars(args),
        "started_at": started_at,
        "finished_at": now_utc(),
        "summaries": [summary.__dict__ for summary in summaries],
        "normalized_counts": normalized_counts,
    }
    db["bdl_import_runs"].update_one({"import_run_id": import_run_id}, {"$set": doc}, upsert=True)


def print_summary(summaries: List[EndpointSummary]) -> None:
    print("\n=== BALLDONTLIE IMPORT SUMMARY ===")
    headers = ["collection", "endpoint", "fetched", "upserted", "modified", "pages", "errors"]
    rows = [
        [s.collection, s.endpoint, str(s.fetched), str(s.upserted), str(s.modified), str(s.pages), str(len(s.errors))]
        for s in summaries
    ]
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*row))

    errors = [(s.collection, err) for s in summaries for err in s.errors]
    if errors:
        print("\nErrors/warnings:")
        for collection, err in errors[:25]:
            print(f"  {collection}: {err}")
        if len(errors) > 25:
            print(f"  ... {len(errors) - 25} more")


def run_import(args: argparse.Namespace) -> None:
    seasons = selected_seasons(args)
    if not args.core and not args.full:
        args.core = True

    api_key, mongo_uri, db_name = load_env()
    import_run_id = str(uuid.uuid4())
    started_at = now_utc()

    print("=== Scout.AI BALLDONTLIE FIFA World Cup Import ===")
    print(f"DB: {db_name}")
    print(f"Seasons: {seasons}")
    print(f"Mode: {'full' if args.full else 'core'}")
    print(f"Odds: {args.odds or args.full}")
    print(f"Dry run: {args.dry_run}")
    print(f"Import run: {import_run_id}\n")

    db = get_db(mongo_uri, db_name)
    client = BDLClient(api_key=api_key, sleep_seconds=args.sleep)

    if args.refresh and not args.dry_run:
        refresh_bdl_collections(db)

    summaries: List[EndpointSummary] = []
    season_params = build_season_params(seasons)

    print("[1/5] Fetching core World Cup data...")
    for spec in CORE_ENDPOINTS:
        params = season_params if spec.get("seasons") else {}
        print(f"Fetching {spec['name']} -> {spec['collection']}")
        summary = fetch_endpoint(client, db, spec, params, import_run_id, dry_run=args.dry_run)
        summaries.append(summary)

    if args.full:
        print("\n[2/5] Fetching match-level detail data...")
        match_ids = match_ids_for_seasons(db, seasons)
        if args.dry_run and not match_ids:
            # In dry-run there may be no DB writes. Use already existing match IDs if any; otherwise skip detail.
            print("  Dry-run has no imported match IDs in MongoDB. Detail endpoints skipped unless bdl_matches already exists.")
        print(f"  Match IDs available for detail import: {len(match_ids)}")
        if match_ids:
            for spec in DETAIL_ENDPOINTS:
                combined = EndpointSummary(collection=spec["collection"], endpoint=spec["endpoint"])
                print(f"Fetching {spec['name']} -> {spec['collection']}")
                for batch_num, batch in enumerate(chunks(match_ids, args.match_chunk_size), start=1):
                    print(f"  match batch {batch_num}: {len(batch)} matches")
                    params = {"match_ids[]": batch}
                    summary = fetch_endpoint(client, db, spec, params, import_run_id, dry_run=args.dry_run)
                    combined.fetched += summary.fetched
                    combined.upserted += summary.upserted
                    combined.modified += summary.modified
                    combined.pages += summary.pages
                    combined.errors.extend(summary.errors)
                    if args.dry_run:
                        break
                summaries.append(combined)

    include_odds = args.full or args.odds
    if include_odds:
        print("\n[3/5] Fetching odds data...")
        for spec in ODDS_ENDPOINTS:
            params = season_params if spec.get("seasons") else {}
            print(f"Fetching {spec['name']} -> {spec['collection']}")
            summary = fetch_endpoint(client, db, spec, params, import_run_id, dry_run=args.dry_run)
            summaries.append(summary)

        if args.full:
            print("\n[4/5] Fetching player props per match...")
            match_ids = match_ids_for_seasons(db, seasons)
            combined = EndpointSummary(collection=PLAYER_PROPS_ENDPOINT["collection"], endpoint=PLAYER_PROPS_ENDPOINT["endpoint"])
            if not match_ids:
                print("  No match IDs available for player props.")
            for idx, match_id in enumerate(match_ids, start=1):
                print(f"  player props {idx}/{len(match_ids)} match_id={match_id}")
                params = {"match_id": match_id}
                summary = fetch_endpoint(client, db, PLAYER_PROPS_ENDPOINT, params, import_run_id, dry_run=args.dry_run)
                combined.fetched += summary.fetched
                combined.upserted += summary.upserted
                combined.modified += summary.modified
                combined.pages += summary.pages
                combined.errors.extend(summary.errors)
                if args.dry_run:
                    break
            summaries.append(combined)
    else:
        print("\n[3/5] Odds skipped. Use --odds or --full to include odds endpoints.")

    print("\n[5/5] Indexing and normalizing...")
    normalized_counts: Dict[str, int] = {}
    if not args.dry_run:
        create_indexes(db)
    else:
        print("  dry-run: index creation skipped")
    try:
        normalized_counts = normalize_for_agent(db, seasons, import_run_id, dry_run=args.dry_run)
    except PyMongoError as exc:
        print(f"  WARN normalization failed: {exc}")

    save_import_run(db, import_run_id, args, seasons, summaries, normalized_counts, started_at, args.dry_run)
    print_summary(summaries)
    print("\nDone.")


def main() -> None:
    try:
        args = parse_args()
        run_import(args)
    except ApiError as exc:
        print(f"FATAL API error {exc.status_code} on {exc.endpoint}: {exc}")
        print(f"Params: {exc.params}")
        if exc.status_code == 401:
            print("Unauthorized or GOAT access missing. Check BALLDONTLIE_API_KEY and account tier.")
        sys.exit(1)
    except PyMongoError as exc:
        print(f"FATAL MongoDB error: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
