"""Fetch BALLDONTLIE FIFA World Cup data into MongoDB, excluding the matches endpoint.

This importer intentionally does NOT call /matches and does NOT write bdl_matches.
It fetches all other supported global/cursor endpoints that can be fetched without a
preloaded match list, including all available players and rosters.

Usage examples:
  python 07_fetch_balldontlie_no_matches.py --dry-run
  python 07_fetch_balldontlie_no_matches.py
  python 07_fetch_balldontlie_no_matches.py --seasons 2018 2022 2026 --sleep 0.15
  python 07_fetch_balldontlie_no_matches.py --seasons 2018 2022 2026 --skip-match-detail
  python 07_fetch_balldontlie_no_matches.py --refresh

Environment variables:
  BALLDONTLIE_API_KEY
  MONGODB_URI
  DB_NAME or SCOUT_DB_NAME

Notes:
  - Trial GOAT keys are limited to 5 req/min. Use --sleep 13.
  - Paid GOAT is 600 req/min. Use --sleep 0.15 or higher.
  - Players and rosters use cursor pagination until meta.next_cursor is empty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, OperationFailure

BASE_URL = "https://api.balldontlie.io/fifa/worldcup/v1"
PROVIDER = "balldontlie"
SPORT = "fifa_worldcup"

# Endpoints that accept seasons[] directly.
SEASON_ENDPOINTS = [
    {
        "label": "teams",
        "endpoint": "teams",
        "collection": "bdl_teams",
        "key_fields": ["id"],
    },
    {
        "label": "stadiums",
        "endpoint": "stadiums",
        "collection": "bdl_stadiums",
        "key_fields": ["id"],
    },
    {
        "label": "group standings",
        "endpoint": "group_standings",
        "collection": "bdl_group_standings",
        "key_fields": ["season.year", "team.id", "group.id"],
    },
    {
        "label": "players",
        "endpoint": "players",
        "collection": "bdl_players",
        "key_fields": ["id"],
    },
    {
        "label": "rosters",
        "endpoint": "rosters",
        "collection": "bdl_rosters",
        "key_fields": ["season.year", "team_id", "player.id"],
    },
    {
        "label": "odds",
        "endpoint": "odds",
        "collection": "bdl_odds",
        "key_fields": ["id"],
    },
    {
        "label": "futures odds",
        "endpoint": "odds/futures",
        "collection": "bdl_odds_futures",
        "key_fields": ["id"],
    },
]

# Endpoints that do not require fetching /matches first. Docs list match_ids[] as optional.
# These can be heavy. Use --skip-match-detail to avoid them.
MATCH_DETAIL_ENDPOINTS = [
    {
        "label": "match lineups",
        "endpoint": "match_lineups",
        "collection": "bdl_match_lineups",
        "key_fields": ["match_id", "team_id", "player.id"],
    },
    {
        "label": "match events",
        "endpoint": "match_events",
        "collection": "bdl_match_events",
        "key_fields": ["id"],
    },
    {
        "label": "player match stats",
        "endpoint": "player_match_stats",
        "collection": "bdl_player_match_stats",
        "key_fields": ["match_id", "player_id", "team_id"],
    },
    {
        "label": "team match stats",
        "endpoint": "team_match_stats",
        "collection": "bdl_team_match_stats",
        "key_fields": ["match_id", "team_id"],
    },
    {
        "label": "match shots",
        "endpoint": "match_shots",
        "collection": "bdl_match_shots",
        "key_fields": ["id"],
    },
    {
        "label": "match momentum",
        "endpoint": "match_momentum",
        "collection": "bdl_match_momentum",
        "key_fields": ["match_id", "minute"],
    },
    {
        "label": "match best players",
        "endpoint": "match_best_players",
        "collection": "bdl_match_best_players",
        "key_fields": ["match_id", "player_id", "team_id", "side_rank"],
    },
    {
        "label": "match average positions",
        "endpoint": "match_avg_positions",
        "collection": "bdl_match_avg_positions",
        "key_fields": ["match_id", "player_id", "team_id"],
    },
    {
        "label": "match team form",
        "endpoint": "match_team_form",
        "collection": "bdl_match_team_form",
        "key_fields": ["match_id", "team_id"],
    },
]

BDL_COLLECTIONS = [item["collection"] for item in SEASON_ENDPOINTS + MATCH_DETAIL_ENDPOINTS]
BDL_COLLECTIONS += ["bdl_import_runs"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_config() -> Dict[str, str]:
    load_dotenv()
    api_key = os.getenv("BALLDONTLIE_API_KEY", "").strip()
    mongo_uri = os.getenv("MONGODB_URI", "").strip()
    db_name = os.getenv("DB_NAME") or os.getenv("SCOUT_DB_NAME") or "scout_ai"

    missing = []
    if not api_key:
        missing.append("BALLDONTLIE_API_KEY")
    if not mongo_uri:
        missing.append("MONGODB_URI")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return {"api_key": api_key, "mongo_uri": mongo_uri, "db_name": db_name}


def get_db(config: Dict[str, str]):
    client = MongoClient(config["mongo_uri"])
    client.admin.command("ping")
    return client[config["db_name"]]


def seasons_params(seasons: Sequence[int]) -> List[Tuple[str, int]]:
    return [("seasons[]", int(season)) for season in seasons]


def params_for_metadata(params: Sequence[Tuple[str, Any]]) -> List[Dict[str, Any]]:
    return [{"key": key, "value": value} for key, value in params]


def _retry_after_seconds(headers: Any, default: int) -> int:
    """Seconds to wait before retrying, from Retry-After or X-RateLimit-Reset."""
    retry_after = headers.get("Retry-After")
    if retry_after:
        try:
            return max(1, int(float(retry_after)))
        except (TypeError, ValueError):
            pass
    reset = headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset")
    if reset:
        try:
            wait = int(reset) - int(time.time())
            if wait > 0:
                return min(wait + 1, 90)
        except (TypeError, ValueError):
            pass
    return default


def _respect_rate_budget(headers: Any) -> None:
    """Proactively pause when the per-minute request budget is exhausted.

    Trial keys are limited to 5 req/min. Honoring x-ratelimit-remaining prevents
    the NEXT request from 429ing, so cursor pagination runs to completion instead
    of being truncated partway through.
    """
    remaining = headers.get("x-ratelimit-remaining") or headers.get("X-RateLimit-Remaining")
    if remaining is None:
        return
    try:
        remaining = int(remaining)
    except (TypeError, ValueError):
        return
    if remaining > 0:
        return
    wait = _retry_after_seconds(headers, default=13)
    print(f"  rate budget exhausted; sleeping {wait}s until the window resets")
    time.sleep(wait)


def request_json(
    endpoint: str,
    params: List[Tuple[str, Any]],
    api_key: str,
    sleep_seconds: float,
    max_retries: int = 4,
    max_rate_limit_waits: int = 120,
) -> Dict[str, Any]:
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    headers = {"Authorization": api_key}
    attempt = 0
    rate_limit_waits = 0

    while True:
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        try:
            response = requests.get(url, headers=headers, params=params, timeout=45)
        except requests.RequestException as exc:
            if attempt >= max_retries:
                raise RuntimeError(f"Network failure after retries: {endpoint}: {exc}") from exc
            delay = min(2 ** attempt, 20)
            print(f"WARN: network error on {endpoint}; retrying in {delay}s: {exc}")
            time.sleep(delay)
            attempt += 1
            continue

        if response.status_code == 200:
            # Pause if this response says we've used up the per-minute budget, so
            # the next paginated call does not get rate limited.
            _respect_rate_budget(response.headers)
            return response.json()

        if response.status_code == 401:
            raise RuntimeError(
                "Unauthorized or account tier missing for this endpoint. "
                "Check BALLDONTLIE_API_KEY and GOAT access."
            )

        if response.status_code == 429:
            # Rate limiting is transient, not fatal: keep waiting until the window
            # resets so pagination is never silently truncated. Trial keys (5/min)
            # rely on this to fetch the full player/roster set.
            rate_limit_waits += 1
            if rate_limit_waits > max_rate_limit_waits:
                raise RuntimeError(
                    f"Still rate limited after {max_rate_limit_waits} waits: {endpoint}"
                )
            delay = _retry_after_seconds(response.headers, default=13)
            print(
                f"WARN: 429 rate limited on {endpoint}; waiting {delay}s "
                f"(wait {rate_limit_waits}/{max_rate_limit_waits})"
            )
            time.sleep(delay)
            continue

        if response.status_code in (500, 503):
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Server error after retries: {endpoint}: {response.status_code}: {response.text[:300]}"
                )
            delay = min(2 ** attempt, 30)
            print(f"WARN: server error {response.status_code} on {endpoint}; retrying in {delay}s")
            time.sleep(delay)
            attempt += 1
            continue

        raise RuntimeError(
            f"API error {response.status_code} on {endpoint}, params={params}: {response.text[:500]}"
        )


def add_source_metadata(doc: Dict[str, Any], endpoint: str, params: List[Tuple[str, Any]], import_run_id: str) -> Dict[str, Any]:
    result = dict(doc)
    result["_source"] = {
        "provider": PROVIDER,
        "sport": SPORT,
        "endpoint": endpoint,
        "params": params_for_metadata(params),
        "fetched_at": utc_now(),
        "import_run_id": import_run_id,
        "is_raw_api_data": True,
    }
    return result


def get_nested(doc: Dict[str, Any], dotted_key: str) -> Any:
    current: Any = doc
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def make_import_key(endpoint: str, doc: Dict[str, Any], key_fields: List[str]) -> str:
    values = []
    for field in key_fields:
        value = get_nested(doc, field)
        if value is None:
            return f"{endpoint}:{stable_hash(doc)}"
        values.append(f"{field}={value}")
    return f"{endpoint}:" + "|".join(values)


def upsert_docs(collection: Collection, docs: List[Dict[str, Any]], endpoint: str, key_fields: List[str], dry_run: bool) -> Tuple[int, int]:
    if not docs:
        return 0, 0

    operations = []
    for doc in docs:
        doc["_import_key"] = make_import_key(endpoint, doc, key_fields)
        operations.append(UpdateOne({"_import_key": doc["_import_key"]}, {"$set": doc}, upsert=True))

    if dry_run:
        return len(docs), 0

    try:
        result = collection.bulk_write(operations, ordered=False)
    except BulkWriteError as exc:
        raise RuntimeError(f"Bulk write failed for {collection.name}: {exc.details}") from exc

    changed = result.upserted_count + result.modified_count + result.matched_count
    return len(docs), changed


def fetch_paginated(
    endpoint: str,
    base_params: List[Tuple[str, Any]],
    collection: Collection,
    key_fields: List[str],
    api_key: str,
    sleep_seconds: float,
    import_run_id: str,
    dry_run: bool,
) -> Dict[str, Any]:
    cursor: Optional[Any] = None
    total_fetched = 0
    total_written = 0
    pages = 0

    while True:
        params = list(base_params)
        params.append(("per_page", 100))
        if cursor is not None:
            params.append(("cursor", cursor))

        payload = request_json(endpoint, params, api_key, sleep_seconds)
        rows = payload.get("data", []) or []
        meta = payload.get("meta", {}) or {}
        docs = [add_source_metadata(row, endpoint, params, import_run_id) for row in rows]

        fetched, written = upsert_docs(collection, docs, endpoint, key_fields, dry_run)
        total_fetched += fetched
        total_written += written
        pages += 1

        next_cursor = meta.get("next_cursor")
        print(f"{endpoint}: page={pages} fetched={fetched} total={total_fetched} next_cursor={bool(next_cursor)}")

        if not next_cursor:
            break
        cursor = next_cursor

    return {
        "endpoint": endpoint,
        "collection": collection.name,
        "documents_fetched": total_fetched,
        "documents_written": total_written,
        "pages": pages,
        "error": None,
    }


def fetch_endpoint_safe(
    db,
    item: Dict[str, Any],
    base_params: List[Tuple[str, Any]],
    api_key: str,
    sleep_seconds: float,
    import_run_id: str,
    dry_run: bool,
    strict: bool,
) -> Dict[str, Any]:
    label = item["label"]
    endpoint = item["endpoint"]
    collection = db[item["collection"]]
    key_fields = item["key_fields"]
    print(f"Fetching {label}: /{endpoint}")
    try:
        return fetch_paginated(
            endpoint=endpoint,
            base_params=base_params,
            collection=collection,
            key_fields=key_fields,
            api_key=api_key,
            sleep_seconds=sleep_seconds,
            import_run_id=import_run_id,
            dry_run=dry_run,
        )
    except Exception as exc:
        if strict:
            raise
        message = str(exc)
        print(f"WARN: failed endpoint /{endpoint}; continuing. Error: {message}")
        return {
            "endpoint": endpoint,
            "collection": item["collection"],
            "documents_fetched": 0,
            "documents_written": 0,
            "pages": 0,
            "error": message,
        }


def normalize_player_from_master(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    player_id = doc.get("id")
    if player_id is None:
        return None
    normalized = {
        "player_id": player_id,
        "name": doc.get("name"),
        "short_name": doc.get("short_name"),
        "position": doc.get("position"),
        "date_of_birth": doc.get("date_of_birth"),
        "country_code": doc.get("country_code"),
        "country_name": doc.get("country_name"),
        "height_cm": doc.get("height_cm"),
        "jersey_number": doc.get("jersey_number"),
        "source": PROVIDER,
        "source_collection": "bdl_players",
        "raw_player_id": player_id,
        "last_updated": utc_now(),
        "is_synthetic": False,
        "_source": doc.get("_source", {}),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def normalize_player_from_roster(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    player = doc.get("player") or {}
    season = doc.get("season") or {}
    player_id = player.get("id") or doc.get("player_id")
    if player_id is None:
        return None
    normalized = {
        "player_id": player_id,
        "name": player.get("name"),
        "short_name": player.get("short_name"),
        "position": doc.get("position") or player.get("position"),
        "date_of_birth": player.get("date_of_birth"),
        "country_code": player.get("country_code"),
        "country_name": player.get("country_name"),
        "height_cm": player.get("height_cm"),
        "jersey_number": player.get("jersey_number"),
        "team_id": doc.get("team_id"),
        "season_year": season.get("year"),
        "appearances": doc.get("appearances"),
        "starts": doc.get("starts"),
        "minutes_played": doc.get("minutes_played"),
        "goals": doc.get("goals"),
        "assists": doc.get("assists"),
        "yellow_cards": doc.get("yellow_cards"),
        "red_cards": doc.get("red_cards"),
        "avg_rating": doc.get("avg_rating"),
        "source": PROVIDER,
        "source_collection": "bdl_rosters",
        "raw_player_id": player_id,
        "last_updated": utc_now(),
        "is_synthetic": False,
        "_source": doc.get("_source", {}),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def normalize_players(db, dry_run: bool) -> int:
    normalized: Dict[Any, Dict[str, Any]] = {}

    if "bdl_players" in db.list_collection_names():
        for doc in db.bdl_players.find({"_source.provider": PROVIDER}):
            row = normalize_player_from_master(doc)
            if row:
                normalized[row["player_id"]] = row

    if "bdl_rosters" in db.list_collection_names():
        for doc in db.bdl_rosters.find({"_source.provider": PROVIDER}):
            row = normalize_player_from_roster(doc)
            if row:
                existing = normalized.get(row["player_id"], {})
                # Roster values enrich master player records. Do not overwrite master name with None.
                existing.update({key: value for key, value in row.items() if value is not None})
                normalized[row["player_id"]] = existing

    docs = list(normalized.values())
    if not docs:
        return 0

    if dry_run:
        print(f"players normalized dry-run count={len(docs)}")
        return len(docs)

    ops = [UpdateOne({"player_id": doc["player_id"], "source": PROVIDER}, {"$set": doc}, upsert=True) for doc in docs]
    db.players.bulk_write(ops, ordered=False)
    return len(docs)


def normalize_teams(db, dry_run: bool) -> int:
    if "bdl_teams" not in db.list_collection_names():
        return 0
    docs = []
    for doc in db.bdl_teams.find({"_source.provider": PROVIDER}):
        team_id = doc.get("id")
        if team_id is None:
            continue
        docs.append(
            {
                "team_id": team_id,
                "name": doc.get("name"),
                "abbreviation": doc.get("abbreviation"),
                "country_code": doc.get("country_code"),
                "confederation": doc.get("confederation"),
                "source": PROVIDER,
                "source_collection": "bdl_teams",
                "last_updated": utc_now(),
                "is_synthetic": False,
                "_source": doc.get("_source", {}),
            }
        )
    if not docs:
        return 0
    if dry_run:
        print(f"teams normalized dry-run count={len(docs)}")
        return len(docs)
    ops = [UpdateOne({"team_id": doc["team_id"], "source": PROVIDER}, {"$set": doc}, upsert=True) for doc in docs]
    db.teams.bulk_write(ops, ordered=False)
    return len(docs)


def create_indexes(db) -> None:
    for name in BDL_COLLECTIONS:
        if name == "bdl_import_runs":
            continue
        try:
            db[name].create_index("_import_key", unique=True, sparse=True)
            db[name].create_index("_source.provider")
            db[name].create_index("_source.endpoint")
        except OperationFailure as exc:
            print(f"WARN: could not create generic indexes for {name}: {exc}")

    # Specific useful indexes for the coach agent.
    db.bdl_players.create_index("id", sparse=True)
    try:
        db.bdl_players.create_index([("name", "text"), ("short_name", "text")], default_language="english")
    except OperationFailure as exc:
        print(f"WARN: text index for bdl_players skipped: {exc}")

    db.bdl_rosters.create_index([("season.year", 1), ("team_id", 1), ("player.id", 1)])
    db.bdl_rosters.create_index("player.id")
    db.bdl_rosters.create_index("team_id")
    db.bdl_rosters.create_index("season.year")

    db.bdl_player_match_stats.create_index("player_id")
    db.bdl_player_match_stats.create_index("team_id")
    db.bdl_player_match_stats.create_index("match_id")

    db.players.create_index([("player_id", 1), ("source", 1)], unique=True, sparse=True)
    db.players.create_index("team_id")
    db.players.create_index("season_year")
    try:
        db.players.create_index([("name", "text"), ("short_name", "text"), ("position", "text")], default_language="english")
    except OperationFailure as exc:
        print(f"WARN: text index for players skipped: {exc}")

    db.teams.create_index([("team_id", 1), ("source", 1)], unique=True, sparse=True)


def refresh_collections(db, include_match_detail: bool, dry_run: bool) -> None:
    names = [item["collection"] for item in SEASON_ENDPOINTS]
    if include_match_detail:
        names.extend(item["collection"] for item in MATCH_DETAIL_ENDPOINTS)
    names = sorted(set(names))

    print("Refresh mode: deleting BALLDONTLIE-imported docs from no-match collections only.")
    for name in names:
        print(f"refresh: {name}")
        if not dry_run:
            db[name].delete_many({"_source.provider": PROVIDER})

    if not dry_run:
        db.players.delete_many({"source": PROVIDER})
        db.teams.delete_many({"source": PROVIDER})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch BALLDONTLIE FIFA World Cup data except /matches into MongoDB.")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2018, 2022, 2026],
        choices=[2018, 2022, 2026],
        help="World Cup seasons to import. Default: 2018 2022 2026.",
    )
    parser.add_argument(
        "--skip-match-detail",
        action="store_true",
        help="Skip match-level detail endpoints such as lineups, events, player stats, shots, momentum. Still skips /matches.",
    )
    parser.add_argument("--refresh", action="store_true", help="Delete only imported bdl_* docs from this script before import.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count but do not write to MongoDB.")
    parser.add_argument("--strict", action="store_true", help="Fail on first endpoint error instead of continuing.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Sleep seconds between API calls. Use 13 for trial keys.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import_run_id = str(uuid.uuid4())
    include_match_detail = not args.skip_match_detail

    config = load_config()
    db = get_db(config)

    print(f"DB: {config['db_name']}")
    print(f"Import run: {import_run_id}")
    print(f"Seasons: {args.seasons}")
    print("Endpoint intentionally skipped: /matches")
    print("Endpoint intentionally skipped: /odds/player_props because it requires match_id")
    print(f"Include match-detail endpoints without fetching matches: {include_match_detail}")
    print(f"Dry run: {args.dry_run}")

    if args.refresh:
        refresh_collections(db, include_match_detail, args.dry_run)

    summaries: List[Dict[str, Any]] = []
    season_params = seasons_params(args.seasons)

    total_steps = len(SEASON_ENDPOINTS) + (len(MATCH_DETAIL_ENDPOINTS) if include_match_detail else 0)
    step = 1

    for item in SEASON_ENDPOINTS:
        print(f"\n[{step}/{total_steps}] {item['label']}")
        summaries.append(
            fetch_endpoint_safe(
                db=db,
                item=item,
                base_params=season_params,
                api_key=config["api_key"],
                sleep_seconds=args.sleep,
                import_run_id=import_run_id,
                dry_run=args.dry_run,
                strict=args.strict,
            )
        )
        step += 1

    if include_match_detail:
        for item in MATCH_DETAIL_ENDPOINTS:
            print(f"\n[{step}/{total_steps}] {item['label']}")
            summaries.append(
                fetch_endpoint_safe(
                    db=db,
                    item=item,
                    base_params=[],
                    api_key=config["api_key"],
                    sleep_seconds=args.sleep,
                    import_run_id=import_run_id,
                    dry_run=args.dry_run,
                    strict=args.strict,
                )
            )
            step += 1

    print("\nNormalizing teams and players for Scout.AI tools...")
    normalized_teams = normalize_teams(db, args.dry_run)
    normalized_players = normalize_players(db, args.dry_run)

    if not args.dry_run:
        print("Creating indexes...")
        create_indexes(db)
        db.bdl_import_runs.insert_one(
            {
                "import_run_id": import_run_id,
                "type": "no_matches_full_import",
                "provider": PROVIDER,
                "sport": SPORT,
                "seasons": args.seasons,
                "skipped_endpoints": ["matches", "odds/player_props"],
                "included_match_detail_without_match_fetch": include_match_detail,
                "dry_run": args.dry_run,
                "finished_at": utc_now(),
                "summaries": summaries,
                "normalized_teams": normalized_teams,
                "normalized_players": normalized_players,
            }
        )

    print("\nSummary")
    print("collection | endpoint | fetched | written | pages | error")
    for item in summaries:
        error = "yes" if item.get("error") else ""
        print(
            f"{item['collection']} | {item['endpoint']} | {item['documents_fetched']} | "
            f"{item['documents_written']} | {item['pages']} | {error}"
        )
    print(f"teams normalized: {normalized_teams}")
    print(f"players normalized: {normalized_players}")

    if not args.dry_run:
        print("\nMongoDB counts")
        for name in ["bdl_players", "bdl_rosters", "players", "bdl_player_match_stats", "bdl_match_lineups"]:
            if name in db.list_collection_names():
                if name == "players":
                    count = db[name].count_documents({"source": PROVIDER})
                else:
                    count = db[name].count_documents({"_source.provider": PROVIDER})
                print(f"{name}: {count}")

    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
