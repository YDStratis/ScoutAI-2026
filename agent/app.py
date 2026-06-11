"""Scout.AI Coach Agent — minimal Streamlit demo.

Runs the deterministic tool pipeline (evaluate lineup -> matchups -> formation
optimization -> replacement -> save) and optionally asks Gemini for a
coach-facing narrative grounded ONLY in the tool outputs.

Run from repo root:  streamlit run agent/app.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from coach_agent import memory, tools
from coach_agent.db import ping_mongo

EXAMPLE_PROMPTS = [
    "Evaluate my starting XI against the opponent and find the missing player key.",
    "My RW looks weak. Should I replace him?",
    "Check if my wide attackers match up well against the opponent fullbacks.",
    "Recommend the best 4-3-3 lineup.",
    "Compare 4-3-3 and 4-2-3-1 using matchup scores.",
]

st.set_page_config(page_title="Scout.AI Coach Agent", page_icon="⚽", layout="wide")
st.title("Scout.AI Coach Agent")
st.caption("Formation + matchup optimizer for national-team coaches — grounded in MongoDB Atlas.")

with st.sidebar:
    st.header("Match setup")
    team = st.text_input("Your team", "Greece")
    opponent = st.text_input("Opponent", "France")
    formation = st.selectbox("Current formation", ["4-3-3", "4-2-3-1", "3-5-2"])
    goal = st.text_area("Coaching goal / concern", EXAMPLE_PROMPTS[0])
    st.caption("Examples:")
    for p in EXAMPLE_PROMPTS:
        st.caption(f"- {p}")
    run = st.button("Analyze", type="primary")

ping = ping_mongo()
if not ping["ok"]:
    st.error(f"MongoDB Atlas unreachable: {ping['error']}")
    st.stop()
st.caption(f"Connected to MongoDB db `{ping['db']}`")


def matchup_df(matchups: list) -> pd.DataFrame:
    rows = [{"Zone": d.get("zone"), "Our Player": d.get("our_player"),
             "Opponent Player": d.get("opponent_player"),
             "Score": d.get("matchup_score"), "Risk": d.get("risk_level"),
             "Tactical Note": d.get("suggested_action") or d.get("reason")}
            for d in matchups if "matchup_score" in d]
    return pd.DataFrame(rows)


if run:
    mem = memory.search_coach_memory(goal, team_name=team, opponent_team=opponent)
    evaluation = tools.evaluate_lineup(team, opponent, formation)
    matchups = tools.analyze_matchups(team, opponent, formation)
    optimization = tools.optimize_formation_with_matchups(team, opponent)

    for name, res in (("Lineup evaluation", evaluation), ("Matchup analysis", matchups),
                      ("Formation optimization", optimization)):
        if "error" in res:
            st.error(f"{name}: {res['error']}")
            st.info("Tip: run `python agent/seed_coach_demo_data.py` to load the demo scenario.")
            st.stop()

    # ---- Lineup evaluation / weak links ----
    st.header("Lineup Evaluation")
    weak_links = evaluation["weak_links"]
    if weak_links:
        worst = weak_links[0]
        st.error(f"Weak link detected: **{worst['player']}** ({worst['position']}) — "
                 + "; ".join(worst["flags"]))
    else:
        st.success("No weak links flagged in the current XI.")
    st.dataframe(pd.DataFrame([{ "Position": p["position"], "Player": p["player"],
                                 "Form": p["form_score"], "Avg rating": p["avg_rating"],
                                 "Role fit": p["role_fit"],
                                 "Flags": "; ".join(p["flags"]) or "—"}
                               for p in evaluation["players"]]),
                 use_container_width=True, hide_index=True)

    # ---- Matchup analysis (first-class section) ----
    st.header("Matchup Analysis")
    st.dataframe(matchup_df(matchups["matchups"]), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    adv, risk = matchups["strongest_advantage"], matchups["highest_risk"]
    c1.success(f"**Biggest advantage** — {adv['zone']}: {adv['our_player']} vs "
               f"{adv['opponent_player']} (score {adv['matchup_score']}). {adv['reason']}")
    c2.error(f"**Biggest risk** — {risk['zone']}: {risk['our_player']} vs "
             f"{risk['opponent_player']} (score {risk['matchup_score']}). {risk['reason']}")

    # ---- Formation comparison ----
    st.header("Formation Optimization")
    st.dataframe(pd.DataFrame([{ "Formation": r["formation"], "Score": r["formation_score"],
                                 **{k.replace("_", " ").title(): v
                                    for k, v in r["components"].items()},
                                 "Highest risk zone": r["highest_risk"].get("zone")}
                               for r in optimization["ranking"]]),
                 use_container_width=True, hide_index=True)
    st.info(f"Recommended formation: **{optimization['recommended_formation']}** "
            f"(score {optimization['formation_score']})")

    # ---- Replacement for the worst weak link ----
    replacement = None
    if weak_links and weak_links[0].get("player"):
        replacement = tools.recommend_replacement(team, opponent,
                                                  weak_links[0]["player"],
                                                  weak_links[0]["position"])
        st.header("Recommended Replacement")
        if "error" in replacement:
            st.warning(replacement["error"])
        else:
            best = replacement["recommended"]
            line = (f"Replace **{replacement['weak_player']}** with **{best['name']}** "
                    f"(form {best['form_score']}, role fit {best['role_fit']}, "
                    f"matchup {best['matchup_score']}).")
            imp = replacement.get("matchup_improvement")
            if imp:
                line += (f" Matchup vs {imp['vs_defender']} improves from "
                         f"**{imp['current_matchup_score']}** to "
                         f"**{imp['new_matchup_score']}** ({imp['delta']:+}).")
            st.success(line)
            st.dataframe(pd.DataFrame(replacement["all_candidates"]),
                         use_container_width=True, hide_index=True)

    # ---- Memory used ----
    if mem["count"]:
        with st.expander(f"Memory used ({mem['count']} items from {mem['collection']})"):
            for m in mem["memories"]:
                st.markdown(f"- `{m['memory_id']}` [{m['memory_type']}] {m['content']}")

    # ---- Save recommendation ----
    payload = {
        "goal": goal, "current_formation": formation,
        "recommended_formation": optimization["recommended_formation"],
        "formation_ranking": optimization["ranking"],
        "weak_links": weak_links,
        "replacement": (replacement if replacement and "error" not in replacement else None),
        "matchup_evidence": {"matchup_average": matchups["matchup_average"],
                             "strongest_advantage": adv, "highest_risk": risk,
                             "matchups": matchups["matchups"]},
        "memory_used": [m["memory_id"] for m in mem["memories"]],
        "limitations": ["Demo data is synthetic (is_synthetic=true).",
                        "Scores are deterministic heuristics on available fields."],
    }
    saved = tools.save_lineup_recommendation(team, opponent, payload)
    st.success(f"Recommendation saved to `{saved['collection']}` — "
               f"id `{saved['recommendation_id']}`")

    # ---- Optional Gemini narrative (grounded in tool outputs only) ----
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        with st.spinner("Asking Gemini for the coach briefing..."):
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                grounding = json.dumps({"goal": goal, "evaluation_weak_links": weak_links,
                                        "matchups": matchups, "optimization": {
                                            "recommended": optimization["recommended_formation"],
                                            "ranking": optimization["ranking"]},
                                        "replacement": replacement,
                                        "memory": mem["memories"]}, default=str)[:24000]
                resp = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                    contents=(
                        "You are Scout.AI Coach Agent. Using ONLY this tool data (do not "
                        "invent stats), write a concise coach briefing with sections: "
                        "Executive decision, Recommended formation, Weak player, Evidence, "
                        "Biggest advantage, Biggest risk, Recommended replacement, "
                        "Tactical adjustment, Confidence, Limitations.\n\nTOOL DATA:\n"
                        + grounding),
                )
                st.header("Coach Briefing (Gemini)")
                st.markdown(resp.text)
                memory.save_agent_run(goal, resp.text,
                                      ["evaluate_lineup", "analyze_matchups",
                                       "optimize_formation_with_matchups",
                                       "recommend_replacement"],
                                      [saved["recommendation_id"]],
                                      [m["memory_id"] for m in mem["memories"]],
                                      payload["limitations"])
            except Exception as e:  # noqa: BLE001
                st.warning(f"Gemini narrative skipped: {e}")
    else:
        st.caption("Set GOOGLE_API_KEY in .env to get a Gemini-written coach briefing.")
