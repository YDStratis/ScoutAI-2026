"""
STEP 2: Δημιουργία Atlas Search + Vector Search indexes
ΣΗΜΑΝΤΙΚΟ: Τρέξε αυτό ΜΕΤΑ το 01_ingest_data.py

Τρέξε: python 02_create_atlas_indexes.py
"""

import os
import time
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI   = os.getenv("MONGODB_URI")
DB_NAME       = os.getenv("DB_NAME", "scoutai")

# Atlas Admin API — βρες τα από το Atlas UI: Project Settings > Access Manager > API Keys
ATLAS_PUBLIC_KEY  = os.getenv("ATLAS_PUBLIC_KEY")
ATLAS_PRIVATE_KEY = os.getenv("ATLAS_PRIVATE_KEY")
ATLAS_PROJECT_ID  = os.getenv("ATLAS_PROJECT_ID")
ATLAS_CLUSTER_NAME = os.getenv("ATLAS_CLUSTER_NAME", "scout-cluster")

BASE_URL = f"https://cloud.mongodb.com/api/atlas/v2/groups/{ATLAS_PROJECT_ID}/clusters/{ATLAS_CLUSTER_NAME}/fts/indexes"

def create_index_via_api(index_definition: dict) -> dict:
    """Δημιουργεί Search index μέσω Atlas Admin API"""
    response = requests.post(
        BASE_URL,
        json=index_definition,
        auth=requests.auth.HTTPDigestAuth(ATLAS_PUBLIC_KEY, ATLAS_PRIVATE_KEY),
        headers={"Content-Type": "application/json", "Accept": "application/vnd.atlas.2023-02-01+json"}
    )
    return response.json()

VECTOR_SEARCH_INDEX = {
    "collectionName": "players",
    "database": DB_NAME,
    "name": "vector_index",
    "type": "vectorSearch",
    "definition": {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": 768,
                "similarity": "cosine"
            },
            {
                "type": "filter",
                "path": "group"
            },
            {
                "type": "filter",
                "path": "position"
            },
            {
                "type": "filter",
                "path": "country"
            }
        ]
    }
}

FULL_TEXT_INDEX = {
    "collectionName": "players",
    "database": DB_NAME,
    "name": "player_search",
    "type": "search",
    "definition": {
        "analyzer": "lucene.standard",
        "mappings": {
            "dynamic": False,
            "fields": {
                "name":         {"type": "string", "analyzer": "lucene.standard"},
                "country":      {"type": "string", "analyzer": "lucene.standard"},
                "team":         {"type": "string", "analyzer": "lucene.standard"},
                "position":     {"type": "string", "analyzer": "lucene.standard"},
                "group":        {"type": "string", "analyzer": "lucene.keyword"},
                "profile_text": {"type": "string", "analyzer": "lucene.standard"},
                "stats": {
                    "type": "document",
                    "fields": {
                        "goals":      {"type": "number"},
                        "assists":    {"type": "number"},
                        "speed":      {"type": "number"},
                        "dribbles":   {"type": "number"}
                    }
                }
            }
        }
    }
}

def print_manual_instructions():
    print("""
╔══════════════════════════════════════════════════════════════╗
║        MANUAL ATLAS INDEX CREATION (Χωρίς Admin API)        ║
╚══════════════════════════════════════════════════════════════╝

Αν δεν έχεις Atlas Admin API keys, φτιάξε τα indexes χειροκίνητα:

━━━ VECTOR SEARCH INDEX ━━━
1. Πήγαινε: Atlas UI → Database → scout-cluster → Search Indexes
2. Κλικ "Create Index" → JSON Editor
3. Επίλεξε collection: scoutai.players
4. Επικόλλησε:

{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 768,
      "similarity": "cosine"
    },
    { "type": "filter", "path": "group" },
    { "type": "filter", "path": "position" },
    { "type": "filter", "path": "country" }
  ]
}

5. Index Name: vector_index
6. Κλικ "Create Search Index"

━━━ FULL-TEXT SEARCH INDEX ━━━
1. Κλικ "Create Index" → Visual Editor
2. Επίλεξε collection: scoutai.players
3. Index Name: player_search
4. Κλικ "Next" → Add field mappings:
   - name       → String
   - country    → String
   - team       → String
   - position   → String
   - group      → String
   - profile_text → String
5. Κλικ "Create Search Index"

⏳ Τα indexes χρειάζονται 2-5 λεπτά για build.
   Θα δεις "Active" status όταν είναι έτοιμα.
""")

def test_vector_search(db):
    """Test ότι το vector search λειτουργεί"""
    import google.generativeai as genai
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)

    print("\nTesting Vector Search...")
    query = "fast explosive winger with strong dribbling"
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=query,
        task_type="retrieval_query"
    )
    query_embedding = result["embedding"]

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 20,
                "limit": 3
            }
        },
        {
            "$project": {
                "name": 1, "position": 1, "country": 1, "group": 1,
                "score": {"$meta": "vectorSearchScore"},
                "_id": 0
            }
        }
    ]

    results = list(db["players"].aggregate(pipeline))
    print(f"\nQuery: '{query}'")
    print("Top 3 results:")
    for r in results:
        print(f"  {r['name']} ({r['position']}, {r['country']}, Group {r['group']}) — score: {r['score']:.4f}")
    return results

def test_aggregation(db):
    """Test aggregation pipeline"""
    print("\nTesting Aggregation Pipeline...")
    pipeline = [
        {"$match": {"position": {"$in": ["Forward", "Winger"]}}},
        {"$sort": {"stats.goals": -1}},
        {"$limit": 3},
        {"$project": {"name": 1, "group": 1, "stats.goals": 1, "stats.assists": 1, "_id": 0}}
    ]
    results = list(db["players"].aggregate(pipeline))
    print("Top 3 goal scorers (Forwards/Wingers):")
    for r in results:
        print(f"  {r['name']} — Goals: {r['stats']['goals']}, Assists: {r['stats']['assists']}, Group: {r['group']}")

def main():
    print("=== Scout AI - Atlas Index Creator ===\n")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    print(f"Players in DB: {db['players'].count_documents({})}")

    if ATLAS_PUBLIC_KEY and ATLAS_PRIVATE_KEY and ATLAS_PROJECT_ID:
        print("Atlas Admin API keys found — creating indexes via API...")
        r1 = create_index_via_api(VECTOR_SEARCH_INDEX)
        print(f"Vector Search index: {r1.get('name', r1)}")
        r2 = create_index_via_api(FULL_TEXT_INDEX)
        print(f"Full-Text index: {r2.get('name', r2)}")
        print("\nIndexes submitted. Waiting ~3 minutes for build...")
        time.sleep(30)
    else:
        print("Atlas Admin API keys not found.")
        print_manual_instructions()

    print("\nWaiting 10s before testing (index must be Active)...")
    time.sleep(10)

    try:
        test_vector_search(db)
    except Exception as e:
        print(f"Vector Search test failed (index may still be building): {e}")
        print("Επανάλαβε το test σε 2-3 λεπτά.")

    test_aggregation(db)

    print("\n=== Index setup complete! ===")
    print("Επόμενο βήμα: 03_setup_mcp.py")
    client.close()

if __name__ == "__main__":
    main()
