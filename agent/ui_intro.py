"""Full-screen video intro with an animated 'Enter' button for the
Scout.AI Coach Agent Streamlit app.

render_intro() renders the splash screen. The video plays immediately as a
full-bleed looping background (via an unsanitized iframe component, since
st.markdown strips <video>/data-URI content); a HUD-style brand mark sits
top-left, and the ENTER control fades/slides in ~2 seconds after load.
Clicking it sets st.session_state.entered=True and reruns into the dashboard.
"""
import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

VIDEO_PATH = Path(__file__).resolve().parent / "assets" / "logo_intro.mp4"


@st.cache_data(show_spinner=False)
def _video_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def render_intro() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, header, footer { visibility: hidden !important; height: 0 !important; }
        [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
        html, body, .stApp,
        [data-testid="stAppViewContainer"], [data-testid="stMain"],
        .main, .block-container, [data-testid="stVerticalBlock"] {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
            gap: 0 !important;
            background: #0a0a0a !important;
        }

        /* Full-bleed video iframe */
        [data-testid="stIFrame"] {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
            z-index: 0 !important;
        }

        /* Bottom scrim for legibility */
        .scout-scrim {
            position: fixed;
            left: 0; right: 0; bottom: 0;
            height: 38vh;
            background: linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0) 100%);
            z-index: 1;
            pointer-events: none;
        }

        /* Brand mark, top-left HUD style */
        .scout-brand {
            position: fixed;
            top: 5vh;
            left: 5vw;
            z-index: 2;
            pointer-events: none;
            font-family: 'Arial Black', Arial, sans-serif;
        }
        .scout-brand .mark {
            font-size: 2.4rem;
            font-weight: 900;
            line-height: 1;
            letter-spacing: 0.06em;
            color: #f4f4f0;
            text-shadow: 0 2px 16px rgba(0,0,0,0.7);
        }
        .scout-brand .mark span { color: #d6ff3f; }
        .scout-brand .sub {
            font-family: 'Courier New', monospace;
            font-weight: 700;
            font-size: 0.7rem;
            letter-spacing: 0.35em;
            text-transform: uppercase;
            color: rgba(244,244,240,0.65);
            margin-top: 0.5rem;
            border-top: 1px solid rgba(214,255,63,0.5);
            padding-top: 0.4rem;
        }

        /* ENTER zone, bottom-center, delayed reveal */
        .scout-enter-label {
            position: fixed;
            bottom: 13vh;
            left: 50%;
            transform: translate(-50%, 14px);
            z-index: 2;
            font-family: 'Courier New', monospace;
            font-weight: 700;
            font-size: 0.7rem;
            letter-spacing: 0.4em;
            text-transform: uppercase;
            color: rgba(244,244,240,0.55);
            pointer-events: none;
            opacity: 0;
            animation: scout-rise-in 0.7s ease-out 2s forwards;
        }
        div[data-testid="stButton"] {
            position: fixed !important;
            bottom: 6vh !important;
            left: 50% !important;
            right: auto !important;
            transform: translate(-50%, 14px) !important;
            width: auto !important;
            z-index: 3 !important;
            display: flex !important;
            justify-content: center !important;
            opacity: 0;
            animation: scout-rise-in 0.7s ease-out 2.15s forwards;
        }
        div[data-testid="stButton"] > button {
            font-family: 'Arial Black', Arial, sans-serif;
            font-weight: 900;
            padding: 0.7em 3.4em !important;
            font-size: 1.2rem;
            letter-spacing: 0.5em;
            color: #f4f4f0;
            background: rgba(10, 10, 10, 0.45);
            border: 1px solid rgba(244, 244, 240, 0.55);
            border-bottom: 4px solid #d6ff3f;
            border-radius: 0 !important;
            backdrop-filter: blur(6px);
            transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, transform 0.15s ease;
        }
        div[data-testid="stButton"] > button:hover {
            background: #d6ff3f;
            color: #0a0a0a;
            border-color: #d6ff3f;
            transform: translateY(-2px);
        }
        div[data-testid="stButton"] > button:focus {
            outline: 2px solid #d6ff3f;
            outline-offset: 2px;
        }

        @keyframes scout-rise-in {
            from { opacity: 0; transform: translate(-50%, 14px); }
            to   { opacity: 1; transform: translate(-50%, 0); }
        }
        </style>

        <div class="scout-scrim"></div>
        <div class="scout-brand">
            <div class="mark">SCOUT<span>.AI</span></div>
            <div class="sub">World Cup 2026 &mdash; Coach Console</div>
        </div>
        <div class="scout-enter-label">Press enter to begin</div>
        """,
        unsafe_allow_html=True,
    )

    video_b64 = _video_base64(VIDEO_PATH)
    components.html(
        f"""
        <html>
          <body style="margin:0; padding:0; overflow:hidden; background:#0a0a0a;">
            <video autoplay loop muted playsinline
                   style="width:100vw; height:100vh; object-fit:cover; display:block;">
              <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
            </video>
          </body>
        </html>
        """,
        height=0,
    )

    if st.button("ENTER", key="enter_btn"):
        st.session_state.entered = True
        st.rerun()
