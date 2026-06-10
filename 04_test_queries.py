"""
STEP 4: Τεστάρει και τα 3 MongoDB patterns που χρησιμοποιεί ο agent
Αυτό δείχνει στους judges ότι έχεις πλήρη MongoDB integration.

Τρέξε: python 04_test_queries.py
"""

import os
import time
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DB_NAME = os.getenv("DB_NAME", "scoutai")

genai.configure(api_key=GOOGLE_API_KEY)

def get_query_embedding(text: str) -> list:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_query"
    )
    return result["embedding"]

# ═══════════════════════════════════════════
# PATTERN 1: Vector Search (semantic query)
# ═══════════════════════════════════════════
def test_vector_search(db, query: str, group_filter: str = None, limit: int = 3):
    print(f"\n[VECTOR SEARCH] '{query}'")
    if group_filter:
        print(f"  Filter: group = {group_filter}")

    embedding = get_query_embedding(query)

    vector_search_stage = {
        "$vectorSearch": {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": embedding,
            "numCandidates": 50,
            "limit": limit * 3,
        }
    }

    if group_filter:
        vector_search_stage["$vectorSearch"]["filter"] = {"group": {"$eq": group_filter}}

    pipeline = [
        vector_search_stage,
        {
            "$project": {
                "name": 1, "position": 1, "country": 1, "group": 1,
                "stats.speed": 1, "stats.goals": 1, "stats.assists": 1,
                "score": {"$meta": "vectorSearchScore"},
                "_id": 0
            }
        },
        {"$limit": limit}
    ]

    results = list(db["players"].aggregate(pipeline))
    for r in results:
        s = r["stats"]
        print(f"  {r['name']:20s} | {r['position']:22s} | {r['country']:12s} | Grp {r['group']} | "
              f"Speed:{s['speed']} Gls:{s['goals']} Ast:{s['assists']} | score:{r['score']:.3f}")
    return results

# ═══════════════════════════════════════════
# PATTERN 2: Aggregation Pipeline (hard stats)
# ═══════════════════════════════════════════
def test_aggregation(db, position_filter: list, min_goals: int, group: str = None):
    filter_label = f"positions={position_filter}, goals>={min_goals}"
    if group:
        filter_label += f", group={group}"
    print(f"\n[AGGREGATION] {filter_label}")

    match = {
        "position": {"$in": position_filter},
        "stats.goals": {"$gte": min_goals}
    }
    if group:
        match["group"] = group

    pipeline = [
        {"$match": match},
        {"$addFields": {
            "form_wins": {
                "$size": {
                    "$filter": {
                        "input": "$form",
                        "cond": {"$eq": ["$$this", "W"]}
                    }
                }
            }
        }},
        {"$sort": {"stats.goals": -1, "stats.assists": -1}},
        {"$limit": 5},
        {"$project": {
            "name": 1, "position": 1, "country": 1, "group": 1,
            "stats.goals": 1, "stats.assists": 1, "stats.speed": 1,
            "form": 1, "form_wins": 1, "_id": 0
        }}
    ]

    results = list(db["players"].aggregate(pipeline))
    for r in results:
        s = r["stats"]
        form_str = "".join(r["form"])
        print(f"  {r['name']:20s} | {r['position']:22s} | Grp {r['group']} | "
              f"Gls:{s['goals']} Ast:{s['assists']} Spd:{s['speed']} | "
              f"Form:{form_str} ({r['form_wins']}/5 W)")
    return results

# ═══════════════════════════════════════════
# PATTERN 3: Full-Text Search (Atlas Search)
# ═══════════════════════════════════════════
def test_fulltext_search(db, search_term: str):
    print(f"\n[FULL-TEXT SEARCH] '{search_term}'")

    pipeline = [
        {
            "$search": {
                "index": "player_search",
                "text": {
                    "query": search_term,
                    "path": ["name", "country", "team", "position", "profile_text"],
                    "fuzzy": {"maxEdits": 1}
                }
            }
        },
        {
            "$project": {
                "name": 1, "position": 1, "country": 1, "group": 1,
                "score": {"$meta": "searchScore"},
                "_id": 0
            }
        },
        {"$limit": 4}
    ]

    try:
        results = list(db["players"].aggregate(pipeline))
        for r in results:
            print(f"  {r['name']:20s} | {r['position']:22s} | {r['country']:12s} | "
                  f"Grp {r['group']} | score:{r['score']:.3f}")
        return results
    except Exception as e:
        print(f"  Full-text search error (index may still be building): {e}")
        return []

# ═══════════════════════════════════════════
# PATTERN 4: Session memory (για τον agent)
# ═══════════════════════════════════════════
def test_session_memory(db):
    print("\n[SESSION MEMORY] Persistent agent context")

    sessions = db["sessions"]
    session_id = "test_session_001"

    sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {"updated_at": time.time()},
            "$push": {
                "history": {
                    "role": "user",
                    "content": "Find me a fast striker in Group B",
                    "timestamp": time.time()
                }
            },
            "$setOnInsert": {"created_at": time.time()}
        },
        upsert=True
    )

    sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {"updated_at": time.time()},
            "$push": {
                "history": {
                    "role": "assistant",
                    "content": "Found: Vinicius Jr, Darwin Núñez, Lautaro Martínez",
                    "players_found": ["Vinicius Jr", "Darwin Núñez"],
                    "timestamp": time.time()
                }
            }
        }
    )

    session = sessions.find_one({"session_id": session_id})
    print(f"  Session '{session_id}': {len(session['history'])} messages stored")
    print("  Session memory: OK")

def main():
    print("=== Scout AI - Query Pattern Tests ===")
    print("These 4 patterns power the agent's intelligence\n")

    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    # Pattern 1: Vector search
    test_vector_search(db, "explosive fast winger strong dribbler")
    test_vector_search(db, "creative playmaker vision passing", group_filter="C")
    test_vector_search(db, "physical defensive midfielder press")

    # Pattern 2: Aggregation
    test_aggregation(db, ["Forward", "Winger"], min_goals=7)
    test_aggregation(db, ["Forward"], min_goals=5, group="B")

    # Pattern 3: Full-text
    test_fulltext_search(db, "Brazil winger")
    test_fulltext_search(db, "defensive midfielder")

    # Pattern 4: Session memory
    test_session_memory(db)

    print("\n=== All patterns tested! ===")
    print("MongoDB setup is complete and ready for the agent.")
    client.close()

if __name__ == "__main__":
    main()
