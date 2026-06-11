"""Smoke test for the Scout.AI Coach Agent (real BALLDONTLIE data in MongoDB).

Run:  python agent/smoke_test_coach_agent.py
Requires: .env with a valid MONGODB_URI pointing at the `scoutai` database that
the BALLDONTLIE importer (07_fetch_balldontlie_no_matches.py) populated.

The test auto-discovers two real teams (preferring teams that have match stats)
instead of assuming any specific country exists.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

RESULTS = []


def check(name, fn):
    try:
        RESULTS.append((name, True, fn() or ""))
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, str(e)))


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _discover_teams(db, tools):
    """Pick two real teams; prefer teams whose players appear in match stats."""
    names = []
    for tid in db.bdl_player_match_stats.distinct("team_id")[:40]:
        name = tools._team_name_for(tid)
        if name:
            names.append(name)
    teams = list(dict.fromkeys(names))  # dedupe, keep order
    if len(teams) < 2:
        teams = tools.list_known_teams()["teams"]
    return teams[0], teams[1]


def main() -> int:
    def t_env():
        from coach_agent import db
        import os
        expect(os.getenv("MONGODB_URI"), "MONGODB_URI not loaded from .env")
        return f"db name = {db.get_db_name()}"
    check("dotenv loads env vars", t_env)

    def t_ping():
        from coach_agent.db import ping_mongo
        r = ping_mongo()
        expect(r["ok"], r.get("error", "ping failed"))
        return f"connected to '{r['db']}'"
    check("MongoDB Atlas ping", t_ping)

    from coach_agent import db as dbmod, memory, tools
    db = dbmod.get_db()

    def t_collections():
        names = db.list_collection_names()
        for c in ("bdl_players", "bdl_rosters", "players", "teams"):
            expect(c in names, f"missing collection {c}")
        return "core BDL + normalized collections present"
    check("relevant collections exist", t_collections)

    def t_counts():
        bp = db.bdl_players.estimated_document_count()
        br = db.bdl_rosters.estimated_document_count()
        pl = db.players.estimated_document_count()
        expect(bp > 0 and br > 0 and pl > 0,
               f"empty: bdl_players={bp} bdl_rosters={br} players={pl}")
        return f"bdl_players={bp}, bdl_rosters={br}, players={pl}"
    check("data counts (bdl_players/bdl_rosters/players)", t_counts)

    def t_agent():
        from coach_agent.agent import root_agent
        if root_agent is None:
            try:
                import google.adk  # noqa: F401
            except ImportError:
                return "google-adk not installed; root_agent=None (acceptable degradation)"
            raise AssertionError("google-adk installed but root_agent is None")
        return f"root_agent '{root_agent.name}' with {len(root_agent.tools)} tools"
    check("root_agent imports", t_agent)

    team_a, team_b = _discover_teams(db, tools)
    print(f"(discovered teams: {team_a} vs {team_b})")

    def t_team():
        r = tools.get_team_players(team_a)
        expect("error" not in r, r.get("error", ""))
        expect(r["count"] >= 11, f"only {r['count']} {team_a} players")
        return f"{team_a}: {r['count']} players"
    check("get_team_players (real team)", t_team)

    sample_player = {"name": None}

    def t_player():
        r = tools.get_team_players(team_a)
        name = None
        for p in r["players"]:  # prefer a player that has match stats
            if db.bdl_player_match_stats.count_documents({"player_id": p["player_id"]}, limit=1):
                name = p["name"]
                break
        name = name or r["players"][0]["name"]
        sample_player["name"] = name
        gp = tools.get_player(name, team_a)
        expect("error" not in gp, gp.get("error", ""))
        expect(gp["player"]["name"], "player has no name")
        return f"get_player('{name}') ok, form_available={gp['form_available']}"
    check("get_player (real player)", t_player)

    def t_lineup():
        r = tools.get_current_lineup(team_a, "4-3-3")
        expect("error" not in r, r.get("error", ""))
        expect(len(r["lineup"]["players"]) == 11, f"lineup not 11: {len(r['lineup']['players'])}")
        return f"{team_a} XI built (provisional={r['lineup'].get('provisional')})"
    check("get_current_lineup (provisional from roster)", t_lineup)

    def t_form():
        r = tools.get_player_recent_form(sample_player["name"] or team_a, team_a)
        expect("error" not in r, r.get("error", ""))
        return (f"form={r.get('form_score')}" if r.get("form_score") is not None
                else "no match stats (reported as limitation, did not crash)")
    check("get_player_recent_form (no crash)", t_form)

    def t_matchups():
        r = tools.analyze_matchups(team_a, team_b, "4-3-3")
        expect("error" not in r, r.get("error", ""))
        expect(len(r["matchups"]) >= 5, f"only {len(r['matchups'])} duels")
        hr = r["highest_risk"]
        return (f"{len(r['matchups'])} duels; avg={r['matchup_average']}; "
                f"highest risk {hr['zone'] if hr else '-'}")
    check("analyze_matchups (structured)", t_matchups)

    def t_eval():
        r = tools.evaluate_lineup(team_a, team_b, "4-3-3")
        expect("error" not in r, r.get("error", ""))
        expect("players" in r and len(r["players"]) == 11, "evaluate_lineup not 11 players")
        return f"lineup_score={r['lineup_score']}; weak_links={len(r['weak_links'])}"
    check("evaluate_lineup (structured)", t_eval)

    def t_optimize():
        r = tools.optimize_formation_with_matchups(team_a, team_b, ["4-3-3", "4-2-3-1"])
        expect("error" not in r, r.get("error", ""))
        expect(len(r["ranking"]) == 2, f"ranked {len(r['ranking'])} formations")
        return (f"best: {r['recommended_formation']} ({r['formation_score']}); "
                + ", ".join(f"{x['formation']}={x['formation_score']}" for x in r["ranking"]))
    check("optimize_formation_with_matchups (structured)", t_optimize)

    def t_replace():
        ev = tools.evaluate_lineup(team_a, team_b, "4-3-3")
        pick = ev["weak_links"][0] if ev.get("weak_links") else ev["players"][0]
        r = tools.recommend_replacement(team_a, team_b, pick["player"], pick["position"])
        expect("error" not in r, r.get("error", ""))
        rec = r.get("recommended")
        return f"replacement -> {rec['name'] if rec else 'none available'}"
    check("recommend_replacement (no crash)", t_replace)

    def t_memory():
        w = memory.write_coach_memory("observation", "smoke-test memory probe",
                                      team_name=team_a, tags=["smoke"])
        expect(w.get("saved"), "memory write failed")
        r = memory.search_coach_memory("smoke", team_name=team_a)
        expect(r["count"] >= 1, "memory search returned nothing")
        return f"wrote {w['memory_id']}, search found {r['count']}"
    check("memory write + search", t_memory)

    def t_save():
        r = tools.save_lineup_recommendation(team_a, team_b,
                                             {"note": "smoke test", "confidence": "low"})
        expect(r.get("saved"), "save failed")
        return f"recommendation id {r['recommendation_id']}"
    check("save_lineup_recommendation", t_save)

    def t_plan():
        r = tools.create_task_plan("Smoke-test plan", team_a, team_b)
        expect("plan_id" in r, r.get("error", "no plan_id"))
        u = tools.update_task_step(r["plan_id"], "evaluate_lineup", "done", "smoke")
        expect(u.get("updated"), u.get("error", "update failed"))
        return f"plan {r['plan_id']} step updated"
    check("task plan create/update", t_plan)

    def t_mcp():
        from coach_agent.mcp_tools import get_mongodb_mcp_toolset
        ts = get_mongodb_mcp_toolset()
        return "MCP toolset built" if ts is not None else "MCP unavailable (graceful skip)"
    check("MCP setup does not crash", t_mcp)

    print("\n" + "=" * 72)
    print("Scout.AI Coach Agent — smoke test (real BALLDONTLIE data)")
    print("=" * 72)
    failed = 0
    for name, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    print("-" * 72)
    print(f"{len(RESULTS) - failed}/{len(RESULTS)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
