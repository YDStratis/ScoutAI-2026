"""Scout.AI — ADK Coach Agent dashboard (Streamlit).

A coach-facing tactical console for World Cup 2026. It reads REAL BALLDONTLIE
data from MongoDB Atlas through the deterministic backend tools
(coach_agent.tools / coach_agent.memory) via frontend_adapter, and never
invents tactical values: missing data is shown as "data unavailable".

Flow: video intro -> control bar (team / opponent / formation) ->
Load Tactical Analysis -> pitch + matchups + formation optimizer +
missing-key panel + agent recommendation -> Save Recommendation (MongoDB).

Run from repo root:  streamlit run agent/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import frontend_adapter as fa
import ui_helpers as ui

st.set_page_config(page_title="Scout.AI · Coach Console", page_icon="⚽", layout="wide")

# Video intro gate removed — the app opens directly on the dashboard.
# To re-enable: `from ui_intro import render_intro` and restore the
# `if not st.session_state.get("entered"): render_intro(); st.stop()` guard.

ui.inject_css()
status = fa.get_backend_status()
ui.render_header(status)

# Hard stop only if Mongo is unreachable — everything downstream needs it.
if not status["mongo"].get("ok"):
    st.error(f"MongoDB Atlas unreachable: {status['mongo'].get('error')}")
    st.info("Set MONGODB_URI in ScoutAI-2026/.env, then reload.")
    st.stop()

teams = fa.list_teams()
if not teams:
    st.warning("No teams found in MongoDB. Run the BALLDONTLIE importer to load "
               "`teams` / `bdl_teams`, then reload.")
    st.stop()


@st.cache_data(ttl=300, show_spinner=False)
def _covered_teams() -> set:
    return fa.teams_with_match_stats()


covered = _covered_teams()


def _default_idx(options, *preferred):
    for p in preferred:
        if p in options:
            return options.index(p)
    return 0


def _label(team_name: str) -> str:
    return f"{team_name} ✓" if team_name in covered else f"{team_name} (no form data)"


# ---- Control bar --------------------------------------------------------- #
c1, c2, c3, c4 = st.columns([1.3, 1.3, 1, 1.4])
with c1:
    # Default to a team with real match-stat coverage so the first load is
    # fully populated (form scores, weak links, matchup detail).
    preferred_team = sorted(covered) or teams
    team = st.selectbox("Your National Team", teams, format_func=_label,
                        index=_default_idx(teams, *preferred_team, "South Korea", "Brazil"))
with c2:
    opp_options = [t for t in teams if t != team] or teams
    preferred_opp = sorted(c for c in covered if c != team) or opp_options
    opponent = st.selectbox("Opponent", opp_options, format_func=_label,
                            index=_default_idx(opp_options, *preferred_opp, "Canada", "France"))
with c3:
    formation = st.selectbox("Formation", ["4-3-3", "4-2-3-1", "3-5-2"])
with c4:
    match_context = st.text_input("Match context / goal",
                                  "Knockout match — find our weak link and the best shape.")

b1, b2, b3, _ = st.columns([1.1, 1.1, 1.1, 1.7])
load = b1.button("⚡ Load Tactical Analysis", type="primary", use_container_width=True)
optimize = b2.button("◎ Optimize Formation", use_container_width=True)
save = b3.button("⬇ Save Recommendation", use_container_width=True)

st.markdown("")

# ---- Run / refresh analysis ---------------------------------------------- #
if load or optimize:
    with st.spinner("Reading MongoDB and scoring matchups…"):
        analysis = fa.run_full_analysis(team, opponent, formation, goal=match_context)
    st.session_state.analysis = analysis
    st.session_state.saved = None  # invalidate previous save
    if optimize and analysis.get("ok"):
        rec = (analysis.get("optimization") or {}).get("recommended_formation")
        if rec:
            st.toast(f"Optimizer recommends {rec}.")

analysis = st.session_state.get("analysis")

if not analysis:
    ui.panel("Getting started",
             "<p style='color:#8aa0c0;margin:0'>Pick your team, the opponent and a "
             "formation, then press <b>Load Tactical Analysis</b>. Scores are computed "
             "in Python from real BALLDONTLIE match data in MongoDB Atlas — never by the "
             "model.</p>")
    st.stop()

# Surface any per-section problems honestly.
for err in analysis.get("errors", []):
    st.warning(err)

if not analysis.get("ok"):
    st.info("Tip: run `python agent/seed_coach_demo_data.py` or the BALLDONTLIE importer "
            "if lineups/match stats are missing.")
    st.stop()

ev = analysis["evaluation"]
mu = analysis["matchups"]
opt = analysis.get("optimization")
briefing = fa.build_coach_briefing(analysis)

# ---- Data-coverage banner -------------------------------------------------
# Form scores, ratings and matchup attribute components only exist for teams
# with bdl_player_match_stats rows. Without them, _compute_form returns None
# and _matchup falls back to a neutral 50, so "no weak link" / "limited data"
# is an honest result of missing source data, not a bug — make that explicit.
missing_sides = [t for t in (team, opponent) if t not in covered]
if missing_sides:
    st.info(
        "📊 **Limited match-stat coverage** for "
        + " and ".join(f"**{m}**" for m in missing_sides)
        + " — recent form, ratings and attribute-based matchup edges fall back "
          "to neutral defaults, so weak-link / missing-key-player detection may "
          "show fewer (or no) results. Teams marked **✓** in the dropdowns have "
          "full `bdl_player_match_stats` coverage (e.g. South Korea vs Canada)."
    )

# ---- Formation optimizer tiles ------------------------------------------- #
if opt and opt.get("ranking"):
    best = opt["ranking"][0]
    comp = best.get("components", {})
    ui.render_tiles([
        ("Recommended Formation", opt.get("recommended_formation"), ""),
        ("Formation Score", best.get("formation_score"), "/100"),
        ("Avg Form", comp.get("lineup_form_average"), ""),
        ("Matchup Avg", comp.get("matchup_average"), ""),
        ("Weak Links", len(best.get("weak_links", [])), ""),
        ("Lineup Score", ev.get("lineup_score"), "/100"),
    ])
    st.markdown("")

# ---- Pitch (ours) + opponent + key panels -------------------------------- #
left, right = st.columns([1.55, 1])

with left:
    st.markdown("#### Starting XI")
    ui.render_pitch(analysis["our_lineup"], eval_players=ev.get("players"))

with right:
    opp_lineup = analysis.get("opponent_lineup")
    st.markdown("#### Opponent")
    if opp_lineup:
        ui.render_pitch(opp_lineup, opponent=True)
        risk = mu.get("highest_risk")
        if risk:
            ui.panel("Key opponent threat",
                     f"<p style='margin:0'><b>{risk['opponent_player']}</b> in "
                     f"{risk['zone']} — {ui.risk_badge(risk['risk_level'])} "
                     f"(duel score {risk['matchup_score']}).</p>")
    else:
        st.info("Opponent lineup data unavailable.")

st.markdown("")

# ---- Missing key player + agent recommendation --------------------------- #
mk, ar = st.columns([1, 1.4])

with mk:
    weak = ev.get("weak_links") or []
    rep = analysis.get("replacement") or {}
    if weak:
        w = weak[0]
        body = (f"<p style='margin:0 0 .4rem 0'><b>{ui._esc(w['player'])}</b> "
                f"({ui._esc(w['position'])})</p>"
                f"<p style='color:#8aa0c0;font-size:.82rem;margin:0 0 .6rem 0'>"
                + "<br>".join("• " + ui._esc(f) for f in w.get("flags", [])) + "</p>")
        if rep and "error" not in rep and rep.get("recommended"):
            r = rep["recommended"]
            imp = rep.get("matchup_improvement")
            body += (f"<p style='margin:.4rem 0 0 0'>Recommended replacement: "
                     f"<b style='color:{ui.ACCENT}'>{ui._esc(r['name'])}</b> "
                     f"(form {ui._esc(r.get('form_score'))}, role fit {ui._esc(r.get('role_fit'))}).</p>")
            if imp:
                body += (f"<p style='color:#8aa0c0;font-size:.82rem;margin:.2rem 0 0 0'>"
                         f"Matchup vs {ui._esc(imp['vs_defender'])}: "
                         f"{ui._esc(imp['current_matchup_score'])} → "
                         f"{ui._esc(imp['new_matchup_score'])} "
                         f"({imp['delta']:+}).</p>")
        elif rep and "error" in rep:
            body += f"<p style='color:#8aa0c0;font-size:.82rem'>Replacement: {ui._esc(rep['error'])}</p>"
        ui.panel("Missing Key Player / Weak Link", body)
    else:
        ui.panel("Missing Key Player / Weak Link",
                 "<p style='margin:0;color:#16e0a4'>No weak link flagged in this XI.</p>")

with ar:
    rows = [
        ("Executive decision", briefing["executive_decision"]),
        ("Recommended formation", briefing["recommended_formation"]),
        ("Weak link", briefing["weak_link"]),
        ("Biggest risk", briefing["biggest_risk"]),
        ("Biggest advantage", briefing["biggest_advantage"]),
        ("Recommended substitution", briefing["recommended_substitution"]),
        ("Tactical adjustment", briefing["tactical_adjustment"]),
    ]
    body = "".join(
        f"<p style='margin:0 0 .5rem 0'><span style='color:#8aa0c0;font-size:.68rem;"
        f"letter-spacing:.1em;text-transform:uppercase'>{ui._esc(k)}</span><br>"
        f"{ui._esc(v)}</p>" for k, v in rows
    )
    ui.panel("Agent Recommendation", body)

st.markdown("")

# ---- Matchup analysis table ---------------------------------------------- #
st.markdown("#### Matchup Analysis")
ui.render_matchup_table(mu.get("matchups", []))

if mu.get("lineup_provisional"):
    st.caption("Lineups are provisional (granular positions derived from coarse "
               "G/D/M/F roster data). Player identities are real BALLDONTLIE data.")

# ---- Formation comparison ------------------------------------------------- #
if opt and opt.get("ranking"):
    with st.expander("Formation comparison detail"):
        import pandas as pd
        df = pd.DataFrame([{
            "Formation": r["formation"], "Score": r["formation_score"],
            **{k.replace("_", " ").title(): v for k, v in r.get("components", {}).items()},
            "Weak links": len(r.get("weak_links", [])),
        } for r in opt["ranking"]])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ---- Save to MongoDB ------------------------------------------------------ #
if save:
    with st.spinner("Saving recommendation to MongoDB Atlas…"):
        try:
            st.session_state.saved = fa.save_recommendation_from_ui(analysis, briefing)
            try:
                from coach_agent import memory
                run = memory.save_agent_run(
                    analysis.get("goal", ""), briefing["executive_decision"],
                    ["evaluate_lineup", "analyze_matchups",
                     "optimize_formation_with_matchups", "recommend_replacement"],
                    briefing.get("data_used", []), briefing.get("memory_used", []),
                    briefing.get("limitations", []))
                st.session_state.saved["run_id"] = run.get("run_id")
            except Exception:  # noqa: BLE001
                pass
            st.success(f"Saved · recommendation id "
                       f"`{st.session_state.saved.get('recommendation_id')}`")
        except Exception as e:  # noqa: BLE001
            st.error(f"Save failed: {e}")

# ---- MongoDB Trace -------------------------------------------------------- #
with st.expander("🛢 MongoDB Trace", expanded=bool(st.session_state.get("saved"))):
    saved = st.session_state.get("saved")
    mem = analysis.get("memory", {}) or {}
    src = sorted({
        c for d in (ev, mu, opt or {})
        for c in (d.get("source", {}) or {}).get("collections", [])
    })
    st.markdown(f"**Database:** `{status['mongo'].get('db')}`")
    st.markdown("**Collections queried:** " + ", ".join(f"`{c}`" for c in src if c))
    st.markdown(f"**Memory items used:** {mem.get('count', 0)} "
                + (", ".join(f"`{m['memory_id']}`" for m in mem.get("memories", [])) or "—"))
    if saved:
        st.markdown(f"**Recommendation id:** `{saved.get('recommendation_id')}` "
                    f"in `{saved.get('collection')}`")
        if saved.get("matchup_report_id"):
            st.markdown(f"**Matchup report id:** `{saved['matchup_report_id']}` "
                        f"in `{saved.get('matchup_reports_collection')}`")
        if saved.get("run_id"):
            st.markdown(f"**Agent run id:** `{saved['run_id']}` in `coach_agent_runs`")
    else:
        st.caption("Press “Save Recommendation” to persist a document and see its id here.")
