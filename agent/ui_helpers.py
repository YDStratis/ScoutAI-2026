"""Presentation helpers for the Scout.AI dashboard.

Pure rendering: CSS injection, the header, a CSS-only football pitch with
absolutely-positioned player cards, risk badges and small stat helpers. All
data passed in here already comes from the backend tools (via frontend_adapter)
— nothing here computes scores or invents values.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

import streamlit as st

# --------------------------------------------------------------------------- #
# Theme                                                                        #
# --------------------------------------------------------------------------- #
ACCENT = "#16e0a4"          # pitch / signal green
NAVY = "#0b1220"            # app background
PANEL = "#121a2b"           # card background
LINE = "#26324a"            # hairline borders
TEXT = "#e8eef7"
MUTED = "#8aa0c0"

RISK_COLORS = {
    "high": "#ff4d4f",
    "medium": "#ffb020",
    "manageable": "#4aa3ff",
    "advantage": "#16e0a4",
}

# Pitch coordinates (left%, top%) per formation, matched 1:1 to the backend
# FORMATIONS slot order. Vertical pitch: our GK at the bottom, attack upward.
PITCH_COORDS: Dict[str, List[tuple]] = {
    "4-3-3": [(50, 90), (83, 71), (61, 76), (39, 76), (17, 71),
              (50, 57), (69, 47), (31, 47), (83, 24), (50, 15), (17, 24)],
    "4-2-3-1": [(50, 90), (83, 71), (61, 76), (39, 76), (17, 71),
                (62, 56), (38, 56), (80, 30), (50, 38), (20, 30), (50, 15)],
    "3-5-2": [(50, 90), (69, 76), (50, 79), (31, 76), (87, 54),
              (66, 49), (50, 55), (34, 49), (13, 54), (60, 17), (40, 17)],
    "4-4-2": [(50, 90), (83, 71), (61, 76), (39, 76), (17, 71),
              (83, 45), (61, 50), (39, 50), (17, 45), (60, 17), (40, 17)],
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background:
            radial-gradient(1200px 600px at 80% -10%, #16223b 0%, {NAVY} 55%) fixed; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        .block-container {{ padding-top: 1.2rem; max-width: 1320px; }}
        h1, h2, h3, h4, p, span, label, div {{ color: {TEXT}; }}

        /* Header */
        .scout-header {{
            display:flex; align-items:center; justify-content:space-between;
            gap:1rem; padding:0.6rem 0 1rem 0; border-bottom:1px solid {LINE};
            margin-bottom:1.1rem;
        }}
        .scout-id {{ display:flex; align-items:baseline; gap:0.7rem; }}
        .scout-id .logo {{
            font-family:'Arial Black',Arial,sans-serif; font-weight:900;
            font-size:1.7rem; letter-spacing:-0.02em; color:{TEXT};
        }}
        .scout-id .logo b {{ color:{ACCENT}; }}
        .scout-id .sub {{
            font-family:'Courier New',monospace; font-size:0.72rem; letter-spacing:0.18em;
            text-transform:uppercase; color:{MUTED};
        }}
        .scout-badges {{ display:flex; gap:0.5rem; flex-wrap:wrap; }}
        .badge {{
            font-family:'Courier New',monospace; font-size:0.68rem; letter-spacing:0.08em;
            text-transform:uppercase; padding:0.32rem 0.6rem; border-radius:4px;
            border:1px solid {LINE}; background:{PANEL}; white-space:nowrap;
        }}
        .badge .dot {{ display:inline-block; width:7px; height:7px; border-radius:50%;
            margin-right:6px; vertical-align:middle; }}
        .badge.ok {{ border-color:#1f7a5a; }} .badge.ok .dot {{ background:{ACCENT}; }}
        .badge.off {{ border-color:#7a2c2c; }} .badge.off .dot {{ background:#ff4d4f; }}

        /* Generic panel/card */
        .panel {{ background:{PANEL}; border:1px solid {LINE}; border-radius:10px;
            padding:1rem 1.1rem; height:100%; }}
        .panel h4 {{ margin:0 0 0.6rem 0; font-size:0.78rem; letter-spacing:0.14em;
            text-transform:uppercase; color:{MUTED}; }}

        /* Metric tiles */
        .tiles {{ display:flex; gap:0.6rem; flex-wrap:wrap; }}
        .tile {{ flex:1 1 120px; background:{PANEL}; border:1px solid {LINE};
            border-radius:9px; padding:0.7rem 0.85rem; }}
        .tile .k {{ font-size:0.66rem; letter-spacing:0.12em; text-transform:uppercase;
            color:{MUTED}; }}
        .tile .v {{ font-size:1.55rem; font-weight:800; color:{TEXT}; line-height:1.1; }}
        .tile .v small {{ font-size:0.8rem; color:{MUTED}; font-weight:600; }}

        /* Risk badge */
        .risk {{ font-family:'Courier New',monospace; font-size:0.66rem; font-weight:700;
            letter-spacing:0.06em; text-transform:uppercase; padding:0.16rem 0.5rem;
            border-radius:4px; color:#0b1220; }}

        /* Pitch */
        .pitch-wrap {{ display:flex; gap:0.6rem; }}
        .pitch {{
            position:relative; flex:1; aspect-ratio: 7 / 9; border-radius:12px;
            background:
              linear-gradient(0deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0) 12%),
              repeating-linear-gradient(0deg, #0f5c3f 0 9%, #0c4f37 9% 18%);
            border:2px solid rgba(255,255,255,0.18); overflow:hidden;
        }}
        .pitch::before {{ content:''; position:absolute; left:8%; right:8%; top:50%;
            border-top:2px solid rgba(255,255,255,0.22); }}
        .pitch::after {{ content:''; position:absolute; left:50%; top:50%;
            width:22%; aspect-ratio:1; transform:translate(-50%,-50%);
            border:2px solid rgba(255,255,255,0.22); border-radius:50%; }}
        .goalbox {{ position:absolute; left:28%; width:44%; height:11%;
            border:2px solid rgba(255,255,255,0.2); }}
        .goalbox.top {{ top:0; border-top:none; }}
        .goalbox.bot {{ bottom:0; border-bottom:none; }}
        .pmark {{
            position:absolute; transform:translate(-50%,-50%); width:84px;
            text-align:center; z-index:2;
        }}
        .pmark .disc {{
            width:40px; height:40px; margin:0 auto 4px auto; border-radius:50%;
            background:{PANEL}; border:2px solid var(--rk,{ACCENT});
            display:flex; align-items:center; justify-content:center;
            font-family:'Courier New',monospace; font-weight:700; font-size:0.7rem;
            color:var(--rk,{ACCENT}); box-shadow:0 3px 10px rgba(0,0,0,0.45);
        }}
        .pmark .nm {{ font-size:0.7rem; font-weight:700; color:#fff;
            text-shadow:0 1px 4px rgba(0,0,0,0.9); line-height:1.05;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
        .pmark .fm {{ font-size:0.62rem; color:#dfe; font-family:'Courier New',monospace; }}
        .pmark.opp .disc {{ background:#1a1320; border-color:#c98; color:#fda; }}

        /* Matchup table */
        table.mu {{ width:100%; border-collapse:collapse; font-size:0.82rem; }}
        table.mu th {{ text-align:left; color:{MUTED}; font-weight:600; font-size:0.68rem;
            letter-spacing:0.08em; text-transform:uppercase; padding:0.4rem 0.5rem;
            border-bottom:1px solid {LINE}; }}
        table.mu td {{ padding:0.5rem 0.5rem; border-bottom:1px solid rgba(38,50,74,0.5);
            vertical-align:top; }}
        table.mu tr:hover td {{ background:rgba(255,255,255,0.02); }}

        .stButton > button {{
            background:{ACCENT}; color:#06140e; font-weight:800; border:none;
            border-radius:7px; letter-spacing:0.02em; }}
        .stButton > button:hover {{ background:#3df0bb; color:#06140e; }}

        /* --- Inputs: dark fields, readable text --- */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"], .stTextInput input, .stTextArea textarea {{
            background:{PANEL} !important; border-color:{LINE} !important;
            color:{TEXT} !important;
        }}
        div[data-baseweb="select"] *, .stTextInput input,
        div[data-baseweb="select"] input {{ color:{TEXT} !important; }}
        div[data-baseweb="select"] svg {{ fill:{MUTED} !important; }}
        .stTextInput input::placeholder, .stTextArea textarea::placeholder {{
            color:{MUTED} !important; }}

        /* Dropdown popover menu (rendered in a body-level portal) */
        div[data-baseweb="popover"], div[data-baseweb="menu"],
        ul[role="listbox"], div[data-baseweb="popover"] ul {{
            background:{PANEL} !important; border:1px solid {LINE} !important;
        }}
        li[role="option"], ul[role="listbox"] li {{
            background:{PANEL} !important; color:{TEXT} !important;
        }}
        li[role="option"]:hover, li[aria-selected="true"],
        ul[role="listbox"] li:hover {{
            background:#1c2740 !important; color:{ACCENT} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Small helpers                                                                #
# --------------------------------------------------------------------------- #
def _esc(x: Any) -> str:
    return html.escape(str(x if x is not None else "—"))


def risk_badge(level: Optional[str]) -> str:
    color = RISK_COLORS.get(level or "", MUTED)
    return f'<span class="risk" style="background:{color}">{_esc(level or "n/a")}</span>'


def status_badge(label: str, ok: bool, detail: str = "") -> str:
    cls = "ok" if ok else "off"
    txt = f"{label}" + (f" · {detail}" if detail else "")
    return f'<span class="badge {cls}"><span class="dot"></span>{_esc(txt)}</span>'


def render_header(status: Dict[str, Any]) -> None:
    mongo = status.get("mongo", {})
    adk = status.get("adk", {})
    badges = [
        status_badge("MongoDB Atlas", mongo.get("ok", False),
                     mongo.get("db", "") if mongo.get("ok") else "offline"),
        status_badge("ADK Agent", adk.get("ok", False),
                     f"{adk.get('tools', 0)} tools" if adk.get("ok") else "tools-only"),
    ]
    st.markdown(
        f"""
        <div class="scout-header">
          <div class="scout-id">
            <div class="logo">SCOUT<b>.AI</b></div>
            <div class="sub">ADK Coach Agent · World Cup 2026</div>
          </div>
          <div class="scout-badges">{''.join(badges)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _player_risk(p: Dict[str, Any]) -> str:
    """Map an evaluate_lineup player row to a pitch-card risk level."""
    wm = p.get("worst_matchup")
    score = wm.get("score") if wm else None
    if score is not None and score < 45:
        return "high"
    if p.get("flags"):
        return "medium"
    return "advantage"


def render_pitch(lineup: Dict[str, Any], eval_players: Optional[List[dict]] = None,
                 opponent: bool = False) -> None:
    """CSS pitch with absolutely-positioned player cards in formation shape."""
    formation = lineup.get("formation", "4-3-3")
    coords = PITCH_COORDS.get(formation, PITCH_COORDS["4-3-3"])
    players = lineup.get("players", [])
    eval_by_name = {p.get("player"): p for p in (eval_players or [])}

    marks = []
    for i, slot in enumerate(players):
        if i >= len(coords):
            break
        left, top = coords[i]
        name = slot.get("player_name") or slot.get("player") or "—"
        short = name.split()[-1] if name and name != "—" else "—"
        pos = slot.get("position", "")
        cls = "pmark opp" if opponent else "pmark"
        rk = ACCENT
        form_line = ""
        ev = eval_by_name.get(name)
        if ev and not opponent:
            rk = RISK_COLORS.get(_player_risk(ev), ACCENT)
            if ev.get("form_score") is not None:
                form_line = f'<div class="fm">form {ev["form_score"]}</div>'
        marks.append(
            f'<div class="{cls}" style="left:{left}%; top:{top}%; --rk:{rk}">'
            f'<div class="disc">{_esc(pos)}</div>'
            f'<div class="nm">{_esc(short)}</div>{form_line}</div>'
        )

    st.markdown(
        f'<div class="pitch"><div class="goalbox top"></div>'
        f'<div class="goalbox bot"></div>{"".join(marks)}</div>',
        unsafe_allow_html=True,
    )
    tag = "Opponent XI" if opponent else "Your XI"
    prov = "provisional (built from roster)" if lineup.get("provisional") else "saved lineup"
    st.caption(f"{tag} · {formation} · {_esc(prov)}")


def render_tiles(tiles: List[tuple]) -> None:
    """tiles = list of (label, value, suffix)."""
    cells = "".join(
        f'<div class="tile"><div class="k">{_esc(k)}</div>'
        f'<div class="v">{_esc(v)}<small>{_esc(s) if s else ""}</small></div></div>'
        for k, v, s in tiles
    )
    st.markdown(f'<div class="tiles">{cells}</div>', unsafe_allow_html=True)


def render_matchup_table(matchups: List[Dict[str, Any]]) -> None:
    if not matchups:
        st.info("Data unavailable. Run importer or add lineup/player attributes.")
        return
    rows = []
    for m in matchups:
        rows.append(
            "<tr>"
            f"<td>{_esc(m.get('zone'))}</td>"
            f"<td><b>{_esc(m.get('our_player'))}</b></td>"
            f"<td>{_esc(m.get('opponent_player'))}</td>"
            f"<td>{_esc(m.get('matchup_score'))}</td>"
            f"<td>{risk_badge(m.get('risk_level'))}</td>"
            f"<td>{_esc(m.get('reason'))}</td>"
            f"<td>{_esc(m.get('tactical_action'))}</td>"
            "</tr>"
        )
    st.markdown(
        '<table class="mu"><thead><tr>'
        "<th>Zone</th><th>Our Player</th><th>Opponent</th><th>Score</th>"
        "<th>Risk</th><th>Tactical Note</th><th>Recommended Action</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>",
        unsafe_allow_html=True,
    )


def panel(title: str, body_md: str) -> None:
    st.markdown(f'<div class="panel"><h4>{_esc(title)}</h4>{body_md}</div>',
                unsafe_allow_html=True)
