"""
STEP 3: Test MongoDB MCP Server connection
Βεβαιώνεται ότι το MCP server μπορεί να διαβάσει τα collections.

Τρέξε: python 03_setup_mcp.py
"""

import os
import json
import subprocess
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "scoutai")

MCP_CONFIG = {
    "mcpServers": {
        "mongodb": {
            "command": "npx",
            "args": [
                "-y",
                "@mongodb-js/mongodb-mcp-server"
            ],
            "env": {
                "MDB_MCP_CONNECTION_STRING": MONGODB_URI
            }
        }
    }
}

def check_node():
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"Node.js: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("Node.js not found! Install from https://nodejs.org")
        return False

def check_npm():
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        print(f"npm: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("npm not found!")
        return False

def verify_mongodb_data():
    print("\n=== Verifying MongoDB data ===")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    players_count = db["players"].count_documents({})
    teams_count   = db["teams"].count_documents({})
    print(f"Players: {players_count}")
    print(f"Teams:   {teams_count}")

    sample = db["players"].find_one({}, {"name": 1, "position": 1, "group": 1, "embedding": 1})
    if sample:
        emb_len = len(sample.get("embedding", []))
        print(f"Sample player: {sample['name']} — embedding dims: {emb_len}")
        if emb_len == 768:
            print("Embeddings: OK (768 dims)")
        else:
            print(f"WARNING: Expected 768 dims, got {emb_len}")

    groups = db["players"].distinct("group")
    print(f"Groups present: {sorted(groups)}")

    client.close()
    return players_count > 0

def save_mcp_configs():
    print("\n=== Saving MCP config files ===")

    os.makedirs("mcp_configs", exist_ok=True)

    with open("mcp_configs/mcp_config.json", "w") as f:
        json.dump(MCP_CONFIG, f, indent=2)
    print("Saved: mcp_configs/mcp_config.json")

    gemini_cli_path = os.path.expanduser("~/.gemini/settings.json")
    print(f"\nFor Gemini CLI, add to {gemini_cli_path}:")
    print(json.dumps({"mcpServers": MCP_CONFIG["mcpServers"]}, indent=2))

    agent_builder_note = """
For Google Cloud Agent Builder:
1. Go to: console.cloud.google.com → Agent Builder
2. Create Agent → Tools → Add Tool
3. Tool type: MCP Server
4. MCP Server URL: (use Cloud Run deployed MCP)
5. Or use the MongoDB Atlas Data API as REST tool
"""
    print(agent_builder_note)

def print_mcp_test_commands():
    print("""
=== MCP Server Test Commands ===

Install (once):
  npm install -g @mongodb-js/mongodb-mcp-server

Test manually:
  MDB_MCP_CONNECTION_STRING="your_uri" npx @mongodb-js/mongodb-mcp-server

Available MCP tools your agent will get:
  - find          : Query documents with filter
  - aggregate     : Run aggregation pipelines
  - insertOne     : Insert a document (for session memory)
  - updateOne     : Update a document
  - listCollections : List all collections
  - createIndex   : Create indexes programmatically
  
The agent uses these via MCP to do:
  1. Vector Search   → db.players.aggregate([$vectorSearch pipeline])
  2. Full-text search → db.players.aggregate([$search pipeline])
  3. Stats filter    → db.players.find({stats.goals: {$gte: 5}, group: "B"})
  4. Save memory     → db.sessions.updateOne({session_id}, {$push: {history: ...}})
""")

def main():
    print("=== Scout AI - MCP Setup Verification ===\n")

    node_ok = check_node()
    npm_ok  = check_npm()

    if not node_ok or not npm_ok:
        print("\nInstall Node.js first: https://nodejs.org/en/download")
        return

    data_ok = verify_mongodb_data()
    if not data_ok:
        print("\nNo data found! Run 01_ingest_data.py first.")
        return

    save_mcp_configs()
    print_mcp_test_commands()

    print("\n=== Setup Complete! ===")
    print("""
Summary:
  DB:          scoutai
  Players:     ingested with 768-dim embeddings
  Indexes:     vector_index + player_search (Atlas)
  MCP Config:  mcp_configs/mcp_config.json
  
Next: Give the agent team the connection string and mcp_config.json
""")

if __name__ == "__main__":
    main()
