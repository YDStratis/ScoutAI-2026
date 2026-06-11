"""Seed synthetic demo data for the Scout.AI Coach Agent.

Idempotent: every document uses a demo_* string _id and replace_one(upsert=True),
so real collections are never overwritten. All docs carry "is_synthetic": true.
Player names are fictional on purpose — we never invent stats for real people.

Demo scenario (Greece vs France, 2026 World Cup prep):
- Greece's starting RW (Stelios Vardas) is in poor form (avg rating 5.1,
  speed 75) and faces France's elite LB (speed 92, defending 84).
- Substitute RW (Ilias Fountas, speed 88, rating 7.1) is the data-driven fix.
- Defensive mismatch too: Greece's LB (speed 72) faces France's RW (speed 93).
- Two candidate formations seeded: 4-3-3 and 4-2-3-1.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coach_agent.db import get_db, ping_mongo
from coach_agent.schemas import (
    COL_LINEUPS, COL_MATCH_STATS, COL_MEMORY, COL_OPPONENT_PROFILES,
    COL_PLAYERS, COL_TEAMS,
)

MATCH_DATES = ["2026-06-01", "2026-05-25", "2026-05-18", "2026-05-11", "2026-05-04"]


def player(slug, name, team, position, stats, ratings, goals, assists,
           xg, xa, minutes, alt_positions=None, availability="available"):
    return {
        "_id": f"demo_player_{slug}",
        "name": name, "team": team, "country": team, "position": position,
        "alt_positions": alt_positions or [], "stats": stats,
        "availability": availability, "is_synthetic": True,
        "_matches": list(zip(MATCH_DATES, ratings, goals, assists, xg, xa, minutes)),
    }


def flat(rating, n=5):
    return [round(rating + d, 1) for d in (-0.1, 0.2, -0.2, 0.1, 0.0)][:n]


Z5 = [0] * 5
GREECE = [
    player("vlachos", "Petros Vlachos", "Greece", "GK",
           {"speed": 55, "defending": 75, "physicality": 80, "work_rate": 70, "role_fit": 84},
           flat(6.8), Z5, Z5, Z5, Z5, [90] * 5),
    # Our LB: slow — exposed against France's fast RW (defensive mismatch)
    player("laskaris", "Dimitris Laskaris", "Greece", "LB",
           {"speed": 72, "acceleration": 70, "dribbling": 68, "defending": 79,
            "physicality": 78, "work_rate": 80, "role_fit": 82},
           [6.3, 6.0, 6.2, 5.9, 6.1], Z5, [0, 1, 0, 0, 0],
           [0.02] * 5, [0.08] * 5, [90] * 5),
    player("mavros", "Stefanos Mavros", "Greece", "CB",
           {"speed": 78, "defending": 85, "physicality": 86, "work_rate": 75, "role_fit": 86},
           flat(7.0), Z5, Z5, [0.03] * 5, [0.02] * 5, [90] * 5),
    player("doukas", "Kostas Doukas", "Greece", "CB",
           {"speed": 74, "defending": 83, "physicality": 84, "work_rate": 74, "role_fit": 84},
           flat(6.7), Z5, Z5, [0.03] * 5, [0.02] * 5, [90] * 5),
    player("galanis", "Nikos Galanis", "Greece", "RB",
           {"speed": 81, "acceleration": 82, "dribbling": 72, "defending": 80,
            "physicality": 79, "work_rate": 84, "role_fit": 83},
           flat(6.6), Z5, [0, 0, 1, 0, 0], [0.03] * 5, [0.10] * 5, [90] * 5),
    player("manolas_a", "Aris Manolas", "Greece", "DM",
           {"speed": 70, "defending": 82, "physicality": 83, "dribbling": 70,
            "work_rate": 86, "role_fit": 85}, flat(6.9), Z5, Z5,
           [0.04] * 5, [0.06] * 5, [90] * 5, alt_positions=["CM"]),
    player("rallis", "Vasilis Rallis", "Greece", "DM",
           {"speed": 73, "defending": 80, "physicality": 80, "dribbling": 72,
            "work_rate": 84, "role_fit": 82}, flat(6.6), Z5, Z5,
           [0.04] * 5, [0.05] * 5, [75] * 5, alt_positions=["CM"]),
    player("petridis", "Yannis Petridis", "Greece", "CM",
           {"speed": 76, "dribbling": 79, "defending": 72, "physicality": 75,
            "work_rate": 82, "role_fit": 84}, flat(6.8),
           [0, 0, 1, 0, 0], [0, 1, 0, 0, 0], [0.12] * 5, [0.15] * 5, [90] * 5,
           alt_positions=["CAM", "DM"]),
    player("economou", "Thanos Economou", "Greece", "CM",
           {"speed": 75, "dribbling": 80, "defending": 68, "physicality": 72,
            "work_rate": 78, "role_fit": 82}, flat(6.5),
           Z5, [0, 0, 0, 1, 0], [0.10] * 5, [0.14] * 5, [85] * 5,
           alt_positions=["CAM"]),
    player("zafiris", "Lefteris Zafiris", "Greece", "CAM",
           {"speed": 78, "dribbling": 84, "defending": 55, "physicality": 68,
            "work_rate": 74, "role_fit": 85, "finishing": 76}, flat(7.0),
           [1, 0, 0, 1, 0], [0, 1, 1, 0, 0], [0.25] * 5, [0.28] * 5, [80] * 5,
           alt_positions=["CM", "RW"]),
    player("antoniou", "Markos Antoniou", "Greece", "LW",
           {"speed": 87, "acceleration": 88, "dribbling": 84, "defending": 45,
            "physicality": 70, "work_rate": 76, "role_fit": 85, "finishing": 77},
           flat(7.1), [1, 0, 1, 0, 0], [0, 1, 0, 0, 1],
           [0.35] * 5, [0.25] * 5, [88] * 5),
    player("bakas", "Christos Bakas", "Greece", "ST",
           {"speed": 80, "dribbling": 76, "defending": 40, "physicality": 84,
            "work_rate": 78, "role_fit": 86, "finishing": 82}, flat(6.9),
           [1, 1, 0, 1, 0], [0, 0, 1, 0, 0], [0.55] * 5, [0.12] * 5, [90] * 5),
    # The weak link: starting RW in poor form, slow vs France's LB
    player("vardas", "Stelios Vardas", "Greece", "RW",
           {"speed": 75, "acceleration": 76, "dribbling": 78, "defending": 42,
            "physicality": 68, "work_rate": 65, "role_fit": 80, "finishing": 70},
           [5.3, 4.9, 5.0, 5.4, 4.9], Z5, Z5,
           [0.05] * 5, [0.03] * 5, [90] * 5),
    # The data-driven replacement
    player("fountas", "Ilias Fountas", "Greece", "RW",
           {"speed": 88, "acceleration": 90, "dribbling": 86, "defending": 48,
            "physicality": 72, "work_rate": 81, "role_fit": 84, "finishing": 78},
           [7.0, 7.3, 6.9, 7.2, 7.1], [1, 0, 1, 0, 0], [0, 1, 0, 1, 0],
           [0.40] * 5, [0.30] * 5, [72] * 5, alt_positions=["LW", "ST"]),
    player("sideris", "Alexis Sideris", "Greece", "ST",
           {"speed": 83, "dribbling": 78, "defending": 38, "physicality": 80,
            "work_rate": 75, "role_fit": 82, "finishing": 79}, flat(6.4),
           [0, 1, 0, 0, 0], Z5, [0.45] * 5, [0.10] * 5, [60] * 5,
           alt_positions=["RW"]),
    player("kappas", "Loukas Kappas", "Greece", "LB",
           {"speed": 84, "acceleration": 85, "dribbling": 74, "defending": 74,
            "physicality": 74, "work_rate": 85, "role_fit": 78}, flat(6.4),
           Z5, [0, 0, 1, 0, 0], [0.02] * 5, [0.10] * 5, [55] * 5,
           alt_positions=["LWB", "LW"]),
]

FRANCE = [
    player("marchand", "Hugo Marchand", "France", "GK",
           {"speed": 58, "defending": 80, "physicality": 84, "work_rate": 72, "role_fit": 88},
           flat(7.2), Z5, Z5, Z5, Z5, [90] * 5),
    # Elite LB — the bad matchup for our weak RW
    player("verdier", "Lucas Verdier", "France", "LB",
           {"speed": 92, "acceleration": 91, "dribbling": 80, "defending": 84,
            "physicality": 82, "work_rate": 88, "role_fit": 88},
           [7.5, 7.3, 7.6, 7.4, 7.2], Z5, [0, 1, 0, 0, 0],
           [0.03] * 5, [0.12] * 5, [90] * 5),
    player("roche", "Antoine Roche", "France", "CB",
           {"speed": 80, "defending": 87, "physicality": 88, "work_rate": 78, "role_fit": 89},
           flat(7.3), Z5, Z5, [0.04] * 5, [0.02] * 5, [90] * 5),
    player("mercier", "Julien Mercier", "France", "CB",
           {"speed": 77, "defending": 85, "physicality": 86, "work_rate": 76, "role_fit": 87},
           flat(7.1), Z5, Z5, [0.04] * 5, [0.02] * 5, [90] * 5),
    player("lambert", "Theo Lambert", "France", "RB",
           {"speed": 85, "acceleration": 84, "dribbling": 78, "defending": 80,
            "physicality": 79, "work_rate": 85, "role_fit": 85}, flat(7.0),
           Z5, [0, 1, 0, 0, 0], [0.03] * 5, [0.12] * 5, [90] * 5),
    player("belaid", "Karim Belaid", "France", "DM",
           {"speed": 74, "defending": 84, "physicality": 85, "dribbling": 76,
            "work_rate": 87, "role_fit": 87}, flat(7.1), Z5, Z5,
           [0.05] * 5, [0.08] * 5, [90] * 5),
    player("renaud", "Paul Renaud", "France", "CM",
           {"speed": 78, "dribbling": 82, "defending": 74, "physicality": 78,
            "work_rate": 84, "role_fit": 86}, flat(7.0),
           [0, 1, 0, 0, 0], [0, 0, 1, 0, 0], [0.15] * 5, [0.18] * 5, [90] * 5),
    player("caron", "Mathis Caron", "France", "CAM",
           {"speed": 80, "dribbling": 86, "defending": 58, "physicality": 72,
            "work_rate": 78, "role_fit": 87, "finishing": 80}, flat(7.2),
           [1, 0, 1, 0, 0], [0, 1, 0, 1, 0], [0.30] * 5, [0.32] * 5, [88] * 5,
           alt_positions=["CM"]),
    player("dumont", "Adrien Dumont", "France", "LW",
           {"speed": 90, "acceleration": 89, "dribbling": 87, "defending": 42,
            "physicality": 74, "work_rate": 74, "role_fit": 87, "finishing": 80},
           flat(7.3), [1, 0, 1, 1, 0], [0, 1, 0, 0, 0],
           [0.45] * 5, [0.25] * 5, [90] * 5),
    # Fast RW — exposes our slow LB (defensive mismatch for Greece)
    player("kessler", "Yanis Kessler", "France", "RW",
           {"speed": 93, "acceleration": 94, "dribbling": 89, "defending": 40,
            "physicality": 76, "work_rate": 76, "role_fit": 88, "finishing": 82},
           [7.8, 7.4, 7.6, 7.5, 7.7], [1, 1, 0, 1, 0], [1, 0, 1, 0, 0],
           [0.55] * 5, [0.35] * 5, [90] * 5),
    player("garnier", "Olivier Garnier", "France", "ST",
           {"speed": 84, "dribbling": 80, "defending": 38, "physicality": 86,
            "work_rate": 80, "role_fit": 88, "finishing": 86}, flat(7.2),
           [1, 1, 1, 0, 1], [0, 0, 1, 0, 0], [0.65] * 5, [0.15] * 5, [90] * 5),
]

LINEUPS = [
    {"_id": "demo_lineup_greece_433", "team_name": "Greece", "formation": "4-3-3",
     "is_default": True, "is_synthetic": True, "updated_at": "2026-06-08",
     "players": [
         {"position": "GK", "player_name": "Petros Vlachos"},
         {"position": "LB", "player_name": "Dimitris Laskaris"},
         {"position": "CB", "player_name": "Stefanos Mavros"},
         {"position": "CB", "player_name": "Kostas Doukas"},
         {"position": "RB", "player_name": "Nikos Galanis"},
         {"position": "DM", "player_name": "Aris Manolas"},
         {"position": "CM", "player_name": "Yannis Petridis"},
         {"position": "CM", "player_name": "Thanos Economou"},
         {"position": "LW", "player_name": "Markos Antoniou"},
         {"position": "ST", "player_name": "Christos Bakas"},
         {"position": "RW", "player_name": "Stelios Vardas"},
     ]},
    {"_id": "demo_lineup_greece_4231", "team_name": "Greece", "formation": "4-2-3-1",
     "is_default": False, "is_synthetic": True, "updated_at": "2026-06-08",
     "players": [
         {"position": "GK", "player_name": "Petros Vlachos"},
         {"position": "LB", "player_name": "Dimitris Laskaris"},
         {"position": "CB", "player_name": "Stefanos Mavros"},
         {"position": "CB", "player_name": "Kostas Doukas"},
         {"position": "RB", "player_name": "Nikos Galanis"},
         {"position": "DM", "player_name": "Aris Manolas"},
         {"position": "DM", "player_name": "Vasilis Rallis"},
         {"position": "CAM", "player_name": "Lefteris Zafiris"},
         {"position": "LW", "player_name": "Markos Antoniou"},
         {"position": "RW", "player_name": "Stelios Vardas"},
         {"position": "ST", "player_name": "Christos Bakas"},
     ]},
    {"_id": "demo_lineup_france_433", "team_name": "France", "formation": "4-3-3",
     "is_default": True, "is_synthetic": True, "updated_at": "2026-06-08",
     "players": [
         {"position": "GK", "player_name": "Hugo Marchand"},
         {"position": "LB", "player_name": "Lucas Verdier"},
         {"position": "CB", "player_name": "Antoine Roche"},
         {"position": "CB", "player_name": "Julien Mercier"},
         {"position": "RB", "player_name": "Theo Lambert"},
         {"position": "DM", "player_name": "Karim Belaid"},
         {"position": "CM", "player_name": "Paul Renaud"},
         {"position": "CAM", "player_name": "Mathis Caron"},
         {"position": "LW", "player_name": "Adrien Dumont"},
         {"position": "ST", "player_name": "Olivier Garnier"},
         {"position": "RW", "player_name": "Yanis Kessler"},
     ]},
]

OPPONENT_PROFILES = [
    {"_id": "demo_opp_profile_france", "team_name": "France", "is_synthetic": True,
     "style": "high pressing, wing-focused attack with fast transitions",
     "press_intensity": "high",
     "strengths": ["elite fullback pace", "wing overloads", "physical CB pairing"],
     "weaknesses": ["space behind fullbacks on quick counters",
                    "DM slow to cover wide rotations"],
     "notes": "Synthetic demo profile for the hackathon scenario."},
    {"_id": "demo_opp_profile_greece", "team_name": "Greece", "is_synthetic": True,
     "style": "compact possession build-up",
     "press_intensity": "medium",
     "strengths": ["organized low block", "left-wing pace"],
     "weaknesses": ["right-wing form", "left back pace against fast wingers"],
     "notes": "Synthetic demo profile for the hackathon scenario."},
]

MEMORIES = [
    {"_id": "demo_memory_1", "memory_type": "tactical_finding", "is_synthetic": True,
     "content": "March 2026 friendly: the 4-2-3-1 double pivot contained a "
                "high-pressing opponent well; build-up went through the DMs.",
     "team_name": "Greece", "opponent_team": "", "tags": ["4-2-3-1", "press"],
     "source": "coach", "created_at": "2026-03-28T18:00:00+00:00"},
    {"_id": "demo_memory_2", "memory_type": "preference", "is_synthetic": True,
     "content": "Coach prefers possession build-up and dislikes long-ball setups; "
                "wide attackers must track back against fast fullbacks.",
     "team_name": "Greece", "opponent_team": "", "tags": ["style", "possession"],
     "source": "coach", "created_at": "2026-04-10T09:00:00+00:00"},
]

TEAMS = [
    {"_id": "demo_team_greece", "name": "Greece", "country": "Greece",
     "confederation": "UEFA", "coach": "Demo Coach", "style": "compact possession",
     "is_synthetic": True},
    {"_id": "demo_team_france", "name": "France", "country": "France",
     "confederation": "UEFA", "coach": "Demo Coach (Opp)",
     "style": "high press, wing attack", "is_synthetic": True},
]


def main() -> int:
    ping = ping_mongo()
    if not ping["ok"]:
        print(f"FAIL: cannot reach MongoDB Atlas: {ping['error']}")
        return 1
    db = get_db()
    print(f"Connected to db '{ping['db']}'. Seeding demo data (demo_* ids only)...")

    n_players = n_matches = 0
    for p in GREECE + FRANCE:
        matches = p.pop("_matches")
        db[COL_PLAYERS].replace_one({"_id": p["_id"]}, p, upsert=True)
        n_players += 1
        for i, (date, rating, goals, assists, xg, xa, minutes) in enumerate(matches):
            doc = {"_id": f"{p['_id']}_match_{i}", "player_name": p["name"],
                   "team": p["team"], "match_date": date, "opponent": "Demo Opponent",
                   "rating": rating, "goals": goals, "assists": assists,
                   "xg": xg, "xa": xa, "minutes": minutes, "is_synthetic": True}
            db[COL_MATCH_STATS].replace_one({"_id": doc["_id"]}, doc, upsert=True)
            n_matches += 1

    for doc in LINEUPS:
        db[COL_LINEUPS].replace_one({"_id": doc["_id"]}, doc, upsert=True)
    for doc in OPPONENT_PROFILES:
        db[COL_OPPONENT_PROFILES].replace_one({"_id": doc["_id"]}, doc, upsert=True)
    for doc in MEMORIES:
        db[COL_MEMORY].replace_one({"_id": doc["_id"]}, doc, upsert=True)
    for doc in TEAMS:
        # Don't shadow a real team document with the same name.
        if not db[COL_TEAMS].find_one({"name": doc["name"], "is_synthetic": {"$ne": True}}):
            db[COL_TEAMS].replace_one({"_id": doc["_id"]}, doc, upsert=True)

    db[COL_MATCH_STATS].create_index("player_name")
    db[COL_MEMORY].create_index([("created_at", -1)])

    print(f"Seeded: {n_players} players, {n_matches} match stats, "
          f"{len(LINEUPS)} lineups, {len(OPPONENT_PROFILES)} opponent profiles, "
          f"{len(MEMORIES)} memories.")
    print("Demo scenario ready: Greece vs France, weak RW = Stelios Vardas, "
          "fix = Ilias Fountas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
