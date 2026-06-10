"""
STEP 1: Ingest World Cup 2026 data into MongoDB Atlas
"""

import os
import time
from pymongo import MongoClient
from dotenv import load_dotenv
from players_data import WORLD_CUP_2026_PLAYERS, WORLD_CUP_2026_TEAMS
import google.generativeai as genai

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DB_NAME = os.getenv("DB_NAME", "scoutai")

genai.configure(api_key=GOOGLE_API_KEY)

def get_embedding(text: str) -> list:
    """Δημιουργεί embedding με Google gemini-embedding-exp-03-07"""
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
    )
    return result["embedding"]

def build_player_profile_text(player: dict) -> str:
    stats = player["stats"]
    form_str = " ".join(player["form"])
    return (
        f"{player['name']} is a {player['age']}-year-old {player['position']} "
        f"from {player['country']} playing for {player['team']} in Group {player['group']}. "
        f"Speed: {stats['speed']}, Goals: {stats['goals']}, Assists: {stats['assists']}, "
        f"Dribbles per game: {stats['dribbles']}, Pass accuracy: {stats['passes_accuracy']}. "
        f"Recent form: {form_str}. "
        f"{player['profile_text']}"
    )

def ingest_players(db):
    collection = db["players"]
    collection.drop()
    print(f"Ingesting {len(WORLD_CUP_2026_PLAYERS)} players...")

    for i, player in enumerate(WORLD_CUP_2026_PLAYERS):
        profile_text = build_player_profile_text(player)
        print(f"  [{i+1}/{len(WORLD_CUP_2026_PLAYERS)}] Embedding: {player['name']}...")

        embedding = get_embedding(profile_text)

        doc = {
            **player,
            "profile_text_full": profile_text,
            "embedding": embedding,
            "created_at": time.time()
        }

        collection.insert_one(doc)
        time.sleep(0.5)

    print(f"Players ingested: {collection.count_documents({})}")

def ingest_teams(db):
    collection = db["teams"]
    collection.drop()
    print(f"\nIngesting {len(WORLD_CUP_2026_TEAMS)} teams...")
    collection.insert_many(WORLD_CUP_2026_TEAMS)
    print(f"Teams ingested: {collection.count_documents({})}")

def ingest_sessions(db):
    collection = db["sessions"]
    collection.drop()
    collection.create_index("session_id", unique=True)
    collection.create_index("updated_at")
    print("\nSessions collection ready")

def create_standard_indexes(db):
    print("\nCreating standard indexes...")
    db["players"].create_index([("group", 1)])
    db["players"].create_index([("position", 1)])
    db["players"].create_index([("country", 1)])
    db["players"].create_index([("stats.speed", -1)])
    db["players"].create_index([("stats.goals", -1)])
    db["players"].create_index([("stats.assists", -1)])
    db["teams"].create_index([("group", 1)])
    print("Standard indexes created")

def main():
    print("=== Scout AI - MongoDB Data Ingestion ===\n")

    # Test embedding first
    print("Testing Google API...")
    test = get_embedding("test player fast striker")
    print(f"Embedding works! Dimensions: {len(test)}")

    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    print(f"Connected to: {DB_NAME}")

    ingest_players(db)
    ingest_teams(db)
    ingest_sessions(db)
    create_standard_indexes(db)

    print("\n=== DONE! ===")
    print("Επόμενο βήμα: τρέξε 02_create_atlas_indexes.py")
    client.close()

if __name__ == "__main__":
    main()