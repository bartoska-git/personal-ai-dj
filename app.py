import streamlit as st
from query import get_playlist

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal AI DJ",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Colours ───────────────────────────────────────────────────────────────────
ACCENT       = "#b8820d"
ACCENT_HOVER = "#96690a"
ACCENT_GLOW  = "rgba(184,130,13,0.15)"

st.markdown(f"""
<style>
  /* ── Base ── */
  .stApp {{ background-color: #f5f1ea; }}
  .block-container {{
    padding-top: 4rem !important;
    padding-bottom: 3rem !important;
    max-width: 680px !important;
  }}
  [data-testid="stVerticalBlock"] > div {{ gap: 0 !important; }}
  #MainMenu, footer, header {{ visibility: hidden; }}

  /* ── Hero — centred ── */
  .hero {{
    text-align: center;
    margin-bottom: 2.8rem;
  }}
  .hero-byline {{
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: {ACCENT};
    margin-bottom: 0.5rem;
  }}
  .hero-title {{
    font-size: 3rem;
    font-weight: 900;
    color: #3a3530;
    line-height: 1.05;
    letter-spacing: -0.02em;
    margin-bottom: 1.1rem;
  }}
  .hero-sub {{
    font-size: 1.02rem;
    color: #7a6e5e;
    line-height: 1.65;
    font-style: italic;
    max-width: 500px;
    margin: 0 auto;
  }}

  /* ── Input focus ring — override Streamlit's default orange ── */
  /* Target the Base Web input container */
  [data-baseweb="input"] {{
    border: none !important;
    box-shadow: none !important;
  }}
  [data-baseweb="base-input"] {{
    background-color: #ffffff !important;
    border: 1.5px solid #ddd5c5 !important;
    border-radius: 10px !important;
  }}
  [data-baseweb="base-input"]:focus-within {{
    border-color: {ACCENT} !important;
    box-shadow: 0 0 0 3px {ACCENT_GLOW} !important;
  }}
  /* Kill any remaining focus outlines */
  .stTextInput input, .stTextInput input:focus {{
    outline: none !important;
    box-shadow: none !important;
    border: none !important;
    background: transparent !important;
    color: #1c1710 !important;
    font-size: 1rem !important;
    padding: 0.75rem 1rem !important;
  }}
  .stTextInput input::placeholder {{
    color: #b8b0a0 !important;
  }}
  .stTextInput > label {{ display: none; }}
  /* Hide "Press Enter to submit form" tooltip */
  [data-testid="InputInstructions"] {{ display: none !important; }}
  /* Remove the form border */
  [data-testid="stForm"] {{
    border: none !important;
    padding: 0 !important;
  }}

  /* ── Buttons — centred ── */
  div[data-testid="stButton"],
  div[data-testid="stFormSubmitButton"] {{
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
  }}

  /* Primary (submit) — covers both st.button and st.form_submit_button */
  button[kind="primary"],
  button[kind="primaryFormSubmit"] {{
    background-color: {ACCENT} !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 24px !important;
    padding: 0.6rem 2.2rem !important;
    font-size: 0.9rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em;
    white-space: nowrap !important;
    transition: background-color 0.2s ease;
    margin-top: 0.5rem;
  }}
  button[kind="primary"]:hover,
  button[kind="primaryFormSubmit"]:hover {{
    background-color: {ACCENT_HOVER} !important;
  }}

  /* Secondary (Start over / New suggestions) */
  button[kind="secondary"] {{
    background-color: transparent !important;
    color: #9a8e7e !important;
    border: 1.5px solid #d8d0be !important;
    border-radius: 24px !important;
    padding: 0.45rem 1.4rem !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    transition: border-color 0.2s, color 0.2s;
  }}
  button[kind="secondary"]:hover {{
    border-color: {ACCENT} !important;
    color: {ACCENT} !important;
    background-color: transparent !important;
  }}

  /* ── Results section ── */
  .results-header {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 2.8rem;
    margin-bottom: 0.8rem;
  }}
  .results-label {{
    font-size: 0.67rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #b8b0a0;
    flex-shrink: 0;
  }}
  .results-rule {{
    flex: 1;
    height: 1px;
    background: #e4ddd0;
  }}

  /* ── Song card ── */
  .song-card {{
    background-color: #ffffff;
    border: 1px solid #e4ddd0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-top: 0.5rem;
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    transition: border-color 0.2s, box-shadow 0.2s;
    text-align: left;
  }}
  .song-card:hover {{
    border-color: #ccc3b0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
  }}
  .song-num {{
    color: #d8cfc0;
    font-size: 0.78rem;
    font-weight: 700;
    min-width: 1.4rem;
    padding-top: 4px;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }}
  .song-body {{ flex: 1; min-width: 0; }}
  .song-title a {{
    color: #3a3530 !important;
    font-size: 0.95rem;
    font-weight: 600;
    text-decoration: none;
    transition: color 0.15s;
  }}
  .song-title a:hover {{
    color: {ACCENT} !important;
    text-decoration: underline;
    text-underline-offset: 2px;
  }}
  .song-artist {{
    color: #9a8e7e;
    font-size: 0.81rem;
    margin-top: 0.1rem;
    margin-bottom: 0.35rem;
  }}
  .song-reason {{
    color: #7a7060;
    font-size: 0.8rem;
    line-height: 1.5;
    font-style: italic;
  }}

  /* ── Action row ── */
  .action-row {{
    margin-top: 1.5rem;
    padding-top: 1.2rem;
    border-top: 1px solid #e4ddd0;
  }}

  /* ── Spinner ── */
  .stSpinner > div {{ color: #9a8e7e !important; }}

  /* ── Footer ── */
  .footer {{
    text-align: center;
    color: #9a9080;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    margin-top: 1rem;
  }}
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
if "playlist" not in st.session_state:
    st.session_state.playlist = None
if "last_query" not in st.session_state:
    st.session_state.last_query = ""


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-byline">Anna Barto</div>
  <div class="hero-title">Personal AI DJ</div>
  <div class="hero-sub">Tell me what you are in the mood for.
  I will give you song suggestions from your YouTube Music library.</div>
</div>
""", unsafe_allow_html=True)


# ── Input + button (wrapped in form — removes "Press enter to apply" tooltip) ──
with st.form("search_form", border=False):
    query = st.text_input(
        "mood",
        placeholder="e.g. something melancholy for a rainy afternoon · upbeat for a morning run · late-night jazz",
        label_visibility="collapsed",
    )
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        generate = st.form_submit_button(
            "Get suggestions →",
            type="primary",
            use_container_width=True,
        )


# ── Trigger generation ────────────────────────────────────────────────────────
def run_query(q: str):
    with st.spinner("Building your suggestions…"):
        try:
            st.session_state.playlist = get_playlist(q)
            st.session_state.last_query = q
        except Exception as e:
            st.error(f"Something went wrong: {e}")

if generate:
    if query.strip():
        run_query(query.strip())
    else:
        st.warning("Type a mood or moment first.")


# ── Results ───────────────────────────────────────────────────────────────────
if st.session_state.playlist:
    playlist = st.session_state.playlist

    st.markdown("""
    <div class="results-header">
      <span class="results-label">Song suggestions</span>
      <div class="results-rule"></div>
    </div>
    """, unsafe_allow_html=True)

    for i, song in enumerate(playlist["songs"], 1):
        vid = song.get("video_id")
        if vid:
            link = f"https://music.youtube.com/watch?v={vid}"
        else:
            q_enc = f"{song['title']} {song['artist']}".replace(" ", "+")
            link = f"https://music.youtube.com/search?q={q_enc}"

        st.markdown(f"""
        <div class="song-card">
          <div class="song-num">{i:02d}</div>
          <div class="song-body">
            <div class="song-title"><a href="{link}" target="_blank">{song['title']}</a></div>
            <div class="song-artist">{song['artist']}</div>
            <div class="song-reason">{song['reason']}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Action buttons below
    st.markdown('<div class="action-row">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.3, 2.5])
    with col1:
        if st.button("↺  Start over", type="secondary"):
            st.session_state.playlist = None
            st.session_state.last_query = ""
            st.rerun()
    with col2:
        if st.button("↻  New suggestions", type="secondary"):
            run_query(st.session_state.last_query)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div class="footer">Built with Claude Code · OpenAI · Supabase pgvector</div>',
    unsafe_allow_html=True
)
