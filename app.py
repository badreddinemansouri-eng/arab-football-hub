import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import hashlib
import random
import time
import requests
import zoneinfo
from urllib.parse import quote
import html
import textwrap
from utils.auth import sign_up, sign_in, sign_out, load_favorites, load_profile, toggle_favorite
from utils.logos import get_team_logo, get_league_logo

# ═══════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════
st.set_page_config(
    page_title="Badr TV | منصة كرة القدم الشاملة",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════
#  SUPABASE CLIENT
# ═══════════════════════════════════════════════
SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client  = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ═══════════════════════════════════════════════
#  TIMEZONE
# ═══════════════════════════════════════════════
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

# ═══════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════
_defaults = {
    "user":         None,
    "profile":      None,
    "favorites":    [],
    "theme":        "dark",
    "sidebar_open": False,
    "admin_auth":   False,
    "show_admin":   False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════
#  LOGO FALLBACK HELPER
#  FIX #1 — wrap every logo call so a Supabase
#  502/network error never crashes the whole app.
#  Returns a reliable UI-Avatars URL as fallback.
# ═══════════════════════════════════════════════
def safe_team_logo(team_name: str) -> str:
    """Return team logo URL, never raises an exception."""
    try:
        return get_team_logo(team_name) or _avatar_url(team_name)
    except Exception:
        return _avatar_url(team_name)

def safe_league_logo(league_name: str) -> str:
    """Return league logo URL, never raises an exception."""
    try:
        return get_league_logo(league_name) or _avatar_url(league_name, bg="1565c0")
    except Exception:
        return _avatar_url(league_name, bg="1565c0")

def _avatar_url(name: str, bg: str = "0d47a1") -> str:
    """Reliable UI-Avatars fallback — always works, no DB call."""
    initials = quote(name[:2]) if name else "?"
    return f"https://ui-avatars.com/api/?name={initials}&background={bg}&color=fff&size=64&bold=true&format=png"


# ═══════════════════════════════════════════════
#  CACHED DATA FETCHERS
# ═══════════════════════════════════════════════
@st.cache_data(ttl=30)
def get_live_matches():
    try:
        return supabase.table("matches").select("*").eq("status", "LIVE").execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=60)
def get_upcoming_matches_main():
    try:
        return supabase.table("matches").select("*").eq("status", "UPCOMING").order("match_time").execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=120)
def get_finished_matches():
    try:
        return supabase.table("matches").select("*").eq("status", "FINISHED").order("match_time", desc=True).execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=3600)
def get_news():
    cutoff = (datetime.now() - timedelta(days=14)).isoformat()
    try:
        return supabase.table("news").select("*").gte("published_at", cutoff).order("published_at", desc=True).limit(50).execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=3600)
def get_competitions_with_standings():
    try:
        return supabase.table("standings").select("competition_code, competition_name, data").execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=60)
def get_all_matches():
    try:
        return supabase.table("matches").select("*").order("match_time").execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=60)
def get_admin_upcoming():
    try:
        return supabase.table("matches").select("*").in_("status", ["UPCOMING", "LIVE"]).order("match_time").execute().data or []
    except Exception:
        return []

@st.cache_data(ttl=300)
def get_predictions_for_match(fixture_id):
    try:
        return supabase.table("predictions").select("*").eq("fixture_id", fixture_id).execute().data or []
    except Exception:
        return []


# ═══════════════════════════════════════════════
#  CSS
# ═══════════════════════════════════════════════
def get_css():
    is_dark = st.session_state.theme == "dark"

    if is_dark:
        bg_primary    = "#0a0e1a"
        bg_secondary  = "#111827"
        bg_card       = "#1a2035"
        bg_card_hover = "#1e2845"
        text_primary  = "#f0f4ff"
        text_secondary= "#8899bb"
        border_color  = "#1e2d50"
        sidebar_bg    = "#0d1526"
        input_bg      = "#151f35"
        skeleton_base = "#1a2035"
        skeleton_shine= "#1e2845"
    else:
        bg_primary    = "#f0f4ff"
        bg_secondary  = "#e4eaf8"
        bg_card       = "#ffffff"
        bg_card_hover = "#f5f8ff"
        text_primary  = "#0a0e1a"
        text_secondary= "#5a6a8a"
        border_color  = "#d0daf0"
        sidebar_bg    = "#ffffff"
        input_bg      = "#eef2fc"
        skeleton_base = "#e4eaf8"
        skeleton_shine= "#f0f4ff"

    return f"""
<style>
/* ── FONT ─────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap');
*, *::before, *::after {{ font-family: 'Cairo', sans-serif !important; box-sizing: border-box; }}

/* ── HIDE STREAMLIT CHROME ───────────────── */
header[data-testid="stHeader"], footer, #MainMenu, .stDeployButton {{ display: none !important; }}

/* ── PAGE ────────────────────────────────── */
.stApp {{ background: {bg_primary} !important; }}
.main, .block-container {{
    background: {bg_primary} !important;
    direction: rtl; text-align: right;
    padding-top: 0 !important;
    padding-bottom: 5rem;
    max-width: 100% !important;
}}

/* ── HEADER ──────────────────────────────── */
.badrtv-header {{
    background: linear-gradient(135deg, #0d47a1 0%, #1565c0 50%, #1976d2 100%);
    padding: 0 20px; height: 64px;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 900;
    box-shadow: 0 4px 24px rgba(13,71,161,0.45);
    border-bottom: 1px solid rgba(255,255,255,0.07);
}}
.badrtv-header-brand {{ display: flex; align-items: center; gap: 11px; }}
.badrtv-header-brand img {{
    width: 42px; height: 42px; border-radius: 50%; object-fit: cover;
    border: 2px solid rgba(255,255,255,0.28);
    box-shadow: 0 0 12px rgba(255,255,255,0.12);
}}
.badrtv-header-title {{
    font-size: 1.4rem; font-weight: 900; color: #fff;
    margin: 0; letter-spacing: .4px; text-shadow: 0 2px 8px rgba(0,0,0,.3);
}}
.badrtv-header-sub {{
    font-size: .68rem; color: rgba(255,255,255,.55);
    font-weight: 400; display: block; margin-top: -3px; letter-spacing: 1px;
}}
.badrtv-time-badge {{
    background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.14);
    border-radius: 20px; padding: 4px 13px;
    font-size: .76rem; color: rgba(255,255,255,.8); font-weight: 600;
}}

/* ── HAMBURGER ───────────────────────────── */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child .stButton > button {{
    background: rgba(255,255,255,.12) !important;
    border: 1px solid rgba(255,255,255,.2) !important;
    color: white !important; font-size: 1.25rem !important; font-weight: 700 !important;
    width: 40px !important; height: 40px !important;
    border-radius: 11px !important; padding: 0 !important;
    transition: background .2s !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
}}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child .stButton > button:hover {{
    background: rgba(255,255,255,.22) !important;
}}

/* ── DRAWER ──────────────────────────────── */
/*
  FIX: sidebar-overlay used z-index:1000 with no pointer-events:none,
  which completely blocked all Streamlit React widget clicks (buttons,
  radio, text inputs). The overlay is now visual-only.
  The drawer keeps pointer-events:auto so its own content works.
*/
.sidebar-overlay {{
    position: fixed; inset: 0; background: rgba(0,0,0,.5);
    z-index: 999;
    backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px);
    pointer-events: none;
}}
.sidebar-drawer {{
    position: fixed; top: 0; right: 0;
    pointer-events: auto;
    width: min(340px, 88vw); height: 100dvh;
    background: {sidebar_bg}; z-index: 1001;
    overflow-y: auto;
    box-shadow: -8px 0 40px rgba(0,0,0,.4);
    border-left: 1px solid {border_color};
    direction: rtl;
    animation: slideInRight .28s cubic-bezier(.32,.72,0,1);
}}
@keyframes slideInRight {{
    from {{ transform: translateX(100%); opacity: 0; }}
    to   {{ transform: translateX(0);   opacity: 1; }}
}}
.sidebar-drawer-header {{
    background: linear-gradient(135deg, #0d47a1, #1976d2);
    padding: 18px 18px 14px;
    display: flex; align-items: center; justify-content: space-between;
}}
.sidebar-drawer-header h3 {{ color: white; margin: 0; font-size: .95rem; font-weight: 700; }}
.sidebar-section {{ padding: 14px 18px; border-bottom: 1px solid {border_color}; }}
.sidebar-section-title {{
    font-size: .7rem; font-weight: 700; color: #1976d2;
    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;
}}

/* ── BOTTOM NAV ──────────────────────────── */
.bottom-nav {{
    position: fixed; bottom: 0; left: 0; right: 0;
    height: 60px; z-index: 800;
    background: {sidebar_bg};
    border-top: 1px solid {border_color};
    display: flex; align-items: center; justify-content: space-around;
    box-shadow: 0 -4px 20px rgba(0,0,0,.15);
    direction: ltr;
}}
.bottom-nav a {{
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    text-decoration: none; gap: 2px;
    color: {text_secondary}; font-size: .62rem; font-weight: 600;
    transition: color .18s;
}}
.bottom-nav a.active {{ color: #1976d2; }}
.bottom-nav a .bn-icon {{ font-size: 1.3rem; line-height: 1; }}
@media (min-width: 768px) {{ .bottom-nav {{ display: none; }} }}

/* ── TABS ────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px; background: {bg_secondary} !important;
    border-radius: 14px; padding: 5px;
    border: 1px solid {border_color}; margin-bottom: 18px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px !important; padding: 8px 13px !important;
    font-size: .83rem !important; font-weight: 600 !important;
    color: {text_secondary} !important; background: transparent !important;
    border: none !important; transition: all .2s ease !important;
}}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(135deg, #1565c0, #1976d2) !important;
    color: white !important; box-shadow: 0 4px 12px rgba(25,118,210,.4) !important;
}}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
@media (max-width: 600px) {{
    .stTabs [data-baseweb="tab-list"] {{ overflow-x: auto; flex-wrap: nowrap; scrollbar-width: none; }}
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {{ display: none; }}
    .stTabs [data-baseweb="tab"] {{ padding: 7px 10px !important; font-size: .73rem !important; white-space: nowrap; }}
}}

/* ── SECTION HEADER ──────────────────────── */
.section-header {{
    display: flex; align-items: center; gap: 10px;
    margin: 18px 0 12px; padding-bottom: 10px;
    border-bottom: 2px solid {border_color};
}}
.section-header-icon {{
    width: 34px; height: 34px;
    background: linear-gradient(135deg, #1565c0, #1976d2);
    border-radius: 10px; display: flex; align-items: center; justify-content: center;
    font-size: 1rem; box-shadow: 0 4px 10px rgba(25,118,210,.3); flex-shrink: 0;
}}
.section-header-text {{ font-size: 1.05rem; font-weight: 700; color: {text_primary}; }}
.live-count-badge {{
    background: #dc2626; color: white; font-size: .68rem; font-weight: 700;
    padding: 2px 8px; border-radius: 20px; margin-right: auto;
    animation: pulseBadge 1.5s infinite;
}}
@keyframes pulseBadge {{ 0%,100%{{ opacity:1; transform:scale(1); }} 50%{{ opacity:.75; transform:scale(1.06); }} }}

/* ── MATCH CARD ──────────────────────────── */
.match-card {{
    background: {bg_card}; border-radius: 16px; padding: 15px 17px;
    margin-bottom: 11px; border: 1px solid {border_color};
    box-shadow: 0 2px 10px rgba(0,0,0,.1);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    cursor: pointer; position: relative; overflow: hidden;
}}
.match-card::before {{
    content: ''; position: absolute; top: 0; right: 0;
    width: 4px; height: 100%;
    background: linear-gradient(180deg, #1565c0, #1976d2);
    border-radius: 0 16px 16px 0;
}}
.match-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 28px rgba(25,118,210,.18); border-color: #1976d2; }}
.match-card.live-card::before {{ background: linear-gradient(180deg, #dc2626, #ef4444); }}

/* ── SKELETON LOADER ─────────────────────── */
.skeleton {{
    background: linear-gradient(90deg, {skeleton_base} 25%, {skeleton_shine} 50%, {skeleton_base} 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s infinite;
    border-radius: 10px;
}}
@keyframes shimmer {{ 0%{{ background-position: 200% 0; }} 100%{{ background-position: -200% 0; }} }}
.skeleton-card {{
    background: {bg_card}; border-radius: 16px; padding: 15px 17px;
    margin-bottom: 11px; border: 1px solid {border_color};
}}
.skeleton-line {{ height: 14px; margin-bottom: 8px; }}
.skeleton-circle {{ border-radius: 50% !important; }}
.skeleton-row {{ display: flex; align-items: center; gap: 12px; justify-content: space-between; }}
.skeleton-col {{ display: flex; flex-direction: column; align-items: center; gap: 8px; flex: 1; }}

/* ── NEWS CARD ───────────────────────────── */
.news-card {{
    background: {bg_card}; border-radius: 16px; padding: 16px;
    margin-bottom: 13px; border: 1px solid {border_color};
    box-shadow: 0 2px 10px rgba(0,0,0,.07);
    transition: transform .18s ease, box-shadow .18s ease;
    direction: rtl; overflow: hidden;
}}
.news-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.13); }}
.news-image {{ width: 100%; max-height: 175px; object-fit: cover; border-radius: 10px; margin-bottom: 11px; }}
.news-title h3 {{ font-size: 1rem; font-weight: 700; margin: 0 0 7px 0; color: {text_primary}; line-height: 1.5; }}
.news-title {{ text-decoration: none; color: inherit; }}
.news-title:hover h3 {{ color: #1976d2; }}
.news-content {{ color: {text_secondary}; font-size: .86rem; line-height: 1.7; margin-bottom: 11px; }}
.news-meta {{ display: flex; justify-content: flex-start; align-items: center; gap: 9px; flex-wrap: wrap; color: {text_secondary}; font-size: .78rem; }}
.source-badge {{ background: linear-gradient(135deg, #1565c0, #1976d2); color: white; padding: 3px 11px; border-radius: 20px; font-size: .72rem; font-weight: 600; }}
.lang-badge {{ background: #166534; color: white; padding: 3px 9px; border-radius: 12px; font-size: .7rem; font-weight: 600; }}
.lang-badge.en {{ background: #1e3a8a; }}

/* ── LIVE BADGE ──────────────────────────── */
.live-badge {{
    background: linear-gradient(135deg, #dc2626, #ef4444); color: white;
    padding: 4px 13px; border-radius: 20px; font-size: .73rem; font-weight: 700;
    display: inline-block; animation: pulse 1.5s infinite;
    box-shadow: 0 0 12px rgba(220,38,38,.5); letter-spacing: .4px;
}}
@keyframes pulse {{ 0%,100%{{ opacity:1; transform:scale(1); }} 50%{{ opacity:.8; transform:scale(1.04); }} }}

/* ── STANDINGS TABLE ─────────────────────── */
.standings-table {{
    width: 100%; border-collapse: separate; border-spacing: 0;
    text-align: center; border-radius: 14px; overflow: hidden;
    border: 1px solid {border_color}; font-size: .83rem;
}}
.standings-table thead th {{
    background: linear-gradient(135deg, #0d47a1, #1976d2);
    color: white; padding: 11px 7px; font-weight: 700; font-size: .78rem;
}}
.standings-table tbody tr {{ background: {bg_card}; transition: background .15s; }}
.standings-table tbody tr:nth-child(even) {{ background: {bg_secondary}; }}
.standings-table tbody tr:hover {{ background: {bg_card_hover}; }}
.standings-table td {{ padding: 9px 7px; border-bottom: 1px solid {border_color}; color: {text_primary}; }}
.standings-table a {{ color: {text_primary}; text-decoration: none; font-weight: 600; }}
.standings-table a:hover {{ color: #1976d2; }}
.standings-table tbody tr:nth-child(-n+4) td:first-child {{ border-right: 3px solid #1976d2; }}

/* ── INPUTS ──────────────────────────────── */
.stTextInput > div > div > input {{
    background: {input_bg} !important; border: 1.5px solid {border_color} !important;
    border-radius: 12px !important; color: {text_primary} !important;
    padding: 9px 15px !important; font-size: .88rem !important; direction: rtl;
    transition: border-color .2s !important;
}}
.stTextInput > div > div > input:focus {{ border-color: #1976d2 !important; box-shadow: 0 0 0 3px rgba(25,118,210,.13) !important; }}
.stSelectbox > div > div {{ background: {input_bg} !important; border: 1.5px solid {border_color} !important; border-radius: 12px !important; color: {text_primary} !important; }}
.stRadio label {{ color: {text_primary} !important; }}
.stExpander {{ background: {bg_card} !important; border: 1px solid {border_color} !important; border-radius: 12px !important; }}
.stExpander summary {{ color: {text_primary} !important; font-weight: 600 !important; }}

/* ── SIDEBAR BUTTONS ─────────────────────── */
div[data-testid="stVerticalBlock"] .stButton > button {{
    background: linear-gradient(135deg, #1565c0, #1976d2) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; font-size: .88rem !important;
    padding: 8px 18px !important; width: 100% !important;
    transition: opacity .2s, transform .2s !important;
    box-shadow: 0 4px 12px rgba(25,118,210,.3) !important;
}}
div[data-testid="stVerticalBlock"] .stButton > button:hover {{ opacity: .9 !important; transform: translateY(-1px) !important; }}

/* ── PROGRESS BAR ────────────────────────── */
.stProgress > div > div {{ background: linear-gradient(90deg, #1565c0, #1976d2) !important; border-radius: 10px !important; }}
.stProgress > div {{ background: {border_color} !important; border-radius: 10px !important; }}

/* ── MISC ────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: #1976d2; border-radius: 4px; }}
.last-updated {{ text-align: left; color: {text_secondary}; font-size: .73rem; margin: 5px 0 14px; display: flex; align-items: center; gap: 5px; padding: 0 3px; }}
.empty-state {{ text-align: center; padding: 38px 18px; color: {text_secondary}; font-size: .93rem; }}
.empty-state-icon {{ font-size: 2.4rem; margin-bottom: 9px; display: block; }}
.prediction-card {{ background: {bg_card}; border: 1px solid {border_color}; border-radius: 16px; padding: 18px; margin-bottom: 13px; }}
.prediction-teams {{ font-size: .98rem; font-weight: 700; color: {text_primary}; margin-bottom: 13px; text-align: center; }}
.pred-label {{ font-size: .8rem; color: {text_secondary}; margin-bottom: 3px; font-weight: 600; }}
.fav-team-tag {{ display: inline-flex; align-items: center; gap: 5px; background: {bg_secondary}; border: 1px solid {border_color}; border-radius: 20px; padding: 4px 13px; font-size: .8rem; color: {text_primary}; margin: 3px; font-weight: 600; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 10px !important; padding-right: 10px !important; }}
    .match-card {{ padding: 12px 13px; }}
    .badrtv-header {{ padding: 0 12px; height: 58px; }}
    .badrtv-header-title {{ font-size: 1.2rem; }}
    .badrtv-time-badge {{ display: none; }}
}}
</style>
"""

st.markdown(get_css(), unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  SKELETON HELPERS
# ═══════════════════════════════════════════════
def render_match_skeletons(n=3):
    skels = ""
    for _ in range(n):
        skels += """
        <div class="skeleton-card">
            <div class="skeleton-row">
                <div class="skeleton-col">
                    <div class="skeleton skeleton-circle" style="width:48px;height:48px;"></div>
                    <div class="skeleton skeleton-line" style="width:70px;"></div>
                </div>
                <div class="skeleton-col">
                    <div class="skeleton skeleton-line" style="width:80px;height:24px;"></div>
                    <div class="skeleton skeleton-line" style="width:50px;"></div>
                </div>
                <div class="skeleton-col">
                    <div class="skeleton skeleton-circle" style="width:48px;height:48px;"></div>
                    <div class="skeleton skeleton-line" style="width:70px;"></div>
                </div>
            </div>
            <div class="skeleton skeleton-line" style="width:55%;margin:12px auto 0;"></div>
        </div>"""
    st.markdown(skels, unsafe_allow_html=True)

def render_news_skeletons(n=3):
    skels = ""
    for _ in range(n):
        skels += """
        <div class="skeleton-card" style="margin-bottom:13px;">
            <div class="skeleton" style="height:140px;border-radius:10px;margin-bottom:12px;"></div>
            <div class="skeleton skeleton-line" style="width:90%;"></div>
            <div class="skeleton skeleton-line" style="width:70%;"></div>
            <div class="skeleton skeleton-line" style="width:40%;"></div>
        </div>"""
    st.markdown(skels, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  MATCH CARD RENDERER
#  FIX #1 applied: safe_team_logo / safe_league_logo
# ═══════════════════════════════════════════════
def render_match_card(match, show_favorite=True):
    home_team   = html.escape(match.get('home_team', '???'))
    away_team   = html.escape(match.get('away_team', '???'))
    # FIX #1: use safe wrappers — a 502 from Supabase will never crash the page
    home_logo   = match.get('home_logo')   or safe_team_logo(home_team)
    away_logo   = match.get('away_logo')   or safe_team_logo(away_team)
    league_logo = match.get('league_logo') or safe_league_logo(match.get('league', ''))
    league_name = html.escape(match.get('league', ''))

    effective_status = match['status']
    if effective_status != 'FINISHED':
        try:
            mt  = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            if now - mt > timedelta(hours=3):
                effective_status = 'FINISHED'
        except Exception:
            pass

    live_class = ""
    if effective_status == 'LIVE':
        center         = f"<span style='color:#ef4444;font-weight:900;font-size:1.85rem;letter-spacing:2px;'>{match['home_score']} - {match['away_score']}</span>"
        status_display = '<span class="live-badge">🔴 مباشر</span>'
        live_class     = "live-card"
    elif effective_status == 'UPCOMING':
        try:
            utc_time   = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            local_time = utc_time.astimezone(tz_tunis)
            today      = datetime.now(tz_tunis).date()
            match_date = local_time.date()
            time_str   = local_time.strftime('%H:%M')
            if match_date == today:
                diff = (local_time - datetime.now(tz_tunis)).total_seconds() / 60
                status_display = "<span style='color:#f59e0b;font-size:.78rem;font-weight:700;'>⏳ بعد قليل</span>" if 0 < diff <= 30 else "<span style='color:#6b7280;font-size:.78rem;'>لم تبدأ</span>"
            else:
                status_display = f"<span style='color:#9ca3af;font-size:.78rem;'>{match_date.strftime('%m/%d')}</span>"
            center = f"<span style='color:#1976d2;font-weight:900;font-size:1.6rem;'>{time_str}</span>"
        except Exception:
            status_display = "<span style='color:#6b7280;font-size:.78rem;'>لم تبدأ</span>"
            center         = "--:--"
    else:
        try:
            utc_time   = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            local_time = utc_time.astimezone(tz_tunis)
            status_display = f"<span style='color:#9ca3af;font-size:.78rem;'>{local_time.strftime('%m/%d')}</span>"
            center         = f"<span style='color:#6b7280;font-weight:900;font-size:1.6rem;'>{match['home_score']} - {match['away_score']}</span>"
        except Exception:
            status_display = "<span style='color:#9ca3af;font-size:.78rem;'>انتهت</span>"
            center         = f"{match['home_score']} - {match['away_score']}"

    return f"""
    <a href="/watch_stream?match_id={match['fixture_id']}" style="text-decoration:none;color:inherit;display:block;">
      <div class="match-card {live_class}">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
          <div style="flex:1;text-align:center;">
            <img src="{home_logo}" style="width:50px;height:50px;object-fit:contain;margin-bottom:7px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.18));">
            <div style="font-weight:700;font-size:.83rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:88px;margin:0 auto;">{home_team}</div>
          </div>
          <div style="flex:1;text-align:center;padding:0 6px;">
            {center}
            <div style="margin-top:5px;">{status_display}</div>
          </div>
          <div style="flex:1;text-align:center;">
            <img src="{away_logo}" style="width:50px;height:50px;object-fit:contain;margin-bottom:7px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.18));">
            <div style="font-weight:700;font-size:.83rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:88px;margin:0 auto;">{away_team}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:7px;margin-top:11px;padding-top:9px;border-top:1px solid rgba(128,128,128,.13);">
          <img src="{league_logo}" style="width:17px;height:17px;object-fit:contain;opacity:.75;">
          <span style="font-size:.76rem;opacity:.55;font-weight:600;">{league_name}</span>
        </div>
      </div>
    </a>"""


# ═══════════════════════════════════════════════
#  SMALL UI HELPERS
# ═══════════════════════════════════════════════
def render_section_header(icon, title, badge=None):
    badge_html = f'<span class="live-count-badge">{badge}</span>' if badge else ''
    st.markdown(f"""
    <div class="section-header">
      <div class="section-header-icon">{icon}</div>
      <span class="section-header-text">{title}</span>
      {badge_html}
    </div>""", unsafe_allow_html=True)

def render_empty(icon, msg):
    st.markdown(f"""
    <div class="empty-state">
      <span class="empty-state-icon">{icon}</span>{msg}
    </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  HEADER BAR
# ═══════════════════════════════════════════════
now_str = datetime.now(tz_tunis).strftime("%H:%M:%S")
col_burger, col_brand = st.columns([1, 11])

with col_brand:
    st.markdown(f"""
    <div class="badrtv-header">
      <div class="badrtv-header-brand">
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg" alt="Badr TV">
        <div>
          <div class="badrtv-header-title">Badr TV</div>
          <span class="badrtv-header-sub">منصة كرة القدم الشاملة</span>
        </div>
      </div>
      <div><div class="badrtv-time-badge">🕐 {now_str}</div></div>
    </div>""", unsafe_allow_html=True)

with col_burger:
    st.markdown('<div style="padding-top:11px;">', unsafe_allow_html=True)
    if st.button("☰", key="sidebar_toggle"):
        st.session_state.sidebar_open = not st.session_state.sidebar_open
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  BOTTOM NAVIGATION (mobile only)
# ═══════════════════════════════════════════════
st.markdown("""
<div class="bottom-nav">
  <a href="/" class="active">
    <span class="bn-icon">📅</span>المباريات
  </a>
  <a href="/results">
    <span class="bn-icon">📊</span>النتائج
  </a>
  <a href="/news_page">
    <span class="bn-icon">📰</span>الأخبار
  </a>
  <a href="/standings_page">
    <span class="bn-icon">🏆</span>الترتيب
  </a>
  <a href="/predictions_page">
    <span class="bn-icon">🔮</span>التوقعات
  </a>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  SIDEBAR DRAWER
# ═══════════════════════════════════════════════
if st.session_state.sidebar_open:
    st.markdown('<div class="sidebar-overlay"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-drawer">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-drawer-header"><h3>⚙️ القائمة الرئيسية</h3></div>', unsafe_allow_html=True)

    if st.button("✕ إغلاق", key="close_sidebar"):
        st.session_state.sidebar_open = False
        st.rerun()

    # ── Account ──
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">👤 الحساب</div>', unsafe_allow_html=True)
    if st.session_state.user:
        st.markdown(f"<p style='margin:0 0 10px;font-size:.86rem;opacity:.8;'>مرحباً 👋<br><strong>{st.session_state.user.email}</strong></p>", unsafe_allow_html=True)
        if st.button("تسجيل الخروج", key="logout_main"):
            sign_out()
    else:
        with st.expander("تسجيل الدخول"):
            email    = st.text_input("البريد الإلكتروني", key="login_email")
            password = st.text_input("كلمة المرور", type="password", key="login_password")
            if st.button("دخول", key="login_main"):
                sign_in(email, password)
        with st.expander("إنشاء حساب"):
            new_email = st.text_input("البريد الإلكتروني", key="signup_email")
            new_pass  = st.text_input("كلمة المرور", type="password", key="signup_pass")
            if st.button("تسجيل", key="signup_main"):
                sign_up(new_email, new_pass)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Theme ──
    # FIX #2: give the radio a real label + label_visibility="collapsed"
    # Passing "" as label is deprecated in Streamlit 1.56 and will become an error.
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">🎨 المظهر</div>', unsafe_allow_html=True)
    theme = st.radio(
        "اختر المظهر",
        ["داكن", "فاتح"],
        index=0 if st.session_state.theme == "dark" else 1,
        key="theme_radio",
        horizontal=True,
        label_visibility="collapsed",   # ← hides the label visually but keeps it for accessibility
    )
    if theme == "داكن" and st.session_state.theme != "dark":
        st.session_state.theme = "dark"; st.rerun()
    elif theme == "فاتح" and st.session_state.theme != "light":
        st.session_state.theme = "light"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Search ──
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">🔍 البحث</div>', unsafe_allow_html=True)
    # FIX #2 also applies here: text_input with real label + collapsed visibility
    search_query = st.text_input(
        "البحث عن فريق أو لاعب",
        key="search_input",
        placeholder="ابحث عن فريق أو لاعب...",
        label_visibility="collapsed",
    )
    if search_query:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**الفرق**")
            try:
                teams = supabase.table("teams").select("id,name,logo").ilike("name", f"%{search_query}%").execute()
                for t in teams.data:
                    st.markdown(f"[{t['name']}](/team?team_id={t['id']})")
            except Exception:
                st.caption("تعذّر تحميل الفرق")
        with c2:
            st.markdown("**اللاعبين**")
            try:
                players = supabase.table("players").select("id,name,photo").ilike("name", f"%{search_query}%").execute()
                for p in players.data:
                    st.markdown(f"[{p['name']}](/player?player_id={p['id']})")
            except Exception:
                st.caption("تعذّر تحميل اللاعبين")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Favorites ──
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">⭐ المفضلة</div>', unsafe_allow_html=True)
    if st.session_state.user:
        if st.session_state.favorites:
            favs_html = "".join([f'<span class="fav-team-tag">⭐ {team}</span>' for team in st.session_state.favorites])
            st.markdown(f'<div style="margin-top:6px;">{favs_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="font-size:.83rem;opacity:.55;margin:0;">لا توجد فرق مفضلة بعد</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="font-size:.83rem;opacity:.55;margin:0;">سجل الدخول لرؤية مفضلتك</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Admin ──
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">👑 لوحة التحكم</div>', unsafe_allow_html=True)
    with st.expander("دخول المشرف", expanded=False):
        if not st.session_state.admin_auth:
            admin_pass = st.text_input("كلمة المرور", type="password", key="admin_pass")
            if st.button("دخول", key="admin_login"):
                if hashlib.sha256(admin_pass.encode()).hexdigest() == "f00bf9d13f09fa3962d4a7d21de2479699adc840b74e34195a0eedb6dd45ceb4":
                    st.session_state.admin_auth = True
                    st.success("تم تسجيل الدخول بنجاح"); st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة")
        else:
            st.success("مرحباً أيها المشرف 👑")
            if st.button("إظهار لوحة التحكم", key="show_admin_btn"):
                st.session_state.show_admin = not st.session_state.show_admin
            if st.button("تسجيل الخروج", key="admin_logout"):
                st.session_state.admin_auth = False
                st.session_state.show_admin = False
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # close drawer


# ═══════════════════════════════════════════════
#  ADMIN PANEL (inline)
# ═══════════════════════════════════════════════
if st.session_state.get("admin_auth") and st.session_state.get("show_admin"):
    with st.container():
        st.markdown("---")
        st.markdown("### 👑 لوحة تحكم المشرف")

        upcoming = get_admin_upcoming()
        if upcoming:
            match_data = {}
            for m in upcoming:
                try:
                    lt    = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                    t_str = lt.strftime("%H:%M")
                except Exception:
                    t_str = "--:--"
                label = f"{t_str} - {m['home_team']} vs {m['away_team']} ({m['league']})"
                match_data[label] = (m['fixture_id'], m['source'])

            selected_match           = st.selectbox("اختر المباراة", list(match_data.keys()), key="match_select")
            fixture_id, match_source = match_data[selected_match]

            c1, c2 = st.columns(2)
            with c1:
                stream_url   = st.text_input("رابط البث", key="stream_url")
                stream_title = st.text_input("عنوان الرابط (اختياري)", key="stream_title")
            with c2:
                stream_source = st.selectbox("المصدر", ["youtube", "facebook", "custom", "official"], key="stream_source")
                expiry_hours  = st.number_input("ساعات الصلاحية", min_value=1, max_value=24, value=3, key="expiry_hours")

            if st.button("إضافة الرابط", key="add_stream_btn"):
                if stream_url:
                    expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
                    data = {
                        "fixture_id": fixture_id, "source": match_source,
                        "stream_url": stream_url, "stream_title": stream_title or "بث مباشر",
                        "stream_source": stream_source, "expires_at": expires_at, "is_active": True
                    }
                    try:
                        supabase.table("admin_streams").insert(data).execute()
                        st.success("تم إضافة الرابط بنجاح!")
                        st.cache_data.clear(); time.sleep(1.5); st.rerun()
                    except Exception as e:
                        st.error(f"خطأ: {e}")
                else:
                    st.error("الرجاء إدخال رابط البث")

            st.markdown("---")
            st.subheader("الروابط الحالية")
            try:
                admin_streams = supabase.table("admin_streams")\
                    .select("*, matches!inner(home_team,away_team,league,status)")\
                    .eq("is_active", True).execute().data
                if admin_streams:
                    for stream in admin_streams:
                        match = stream.get("matches", {})
                        st.markdown(f"**{match.get('home_team')} vs {match.get('away_team')}** — {stream['stream_url']}  \nينتهي: {stream['expires_at'][:16]}")
                        if st.button(f"حذف #{stream['id']}", key=f"del_{stream['id']}"):
                            supabase.table("admin_streams").update({"is_active": False}).eq("id", stream["id"]).execute()
                            st.success("تم الحذف"); st.rerun()
            except Exception as e:
                st.error("خطأ في تحميل الروابط")
        else:
            st.info("لا توجد مباريات قادمة")

        st.markdown("---")
        st.subheader("➕ إضافة مباراة يدوية")
        with st.form("add_custom_match_form"):
            custom_home   = st.text_input("الفريق المستضيف")
            custom_away   = st.text_input("الفريق الضيف")
            custom_league = st.text_input("الدوري")
            custom_date   = st.date_input("التاريخ", datetime.now())
            custom_time   = st.time_input("الوقت", datetime.now().time(), key="custom_match_time")
            custom_stream = st.text_input("رابط البث (اختياري)")
            if st.form_submit_button("إضافة المباراة") and custom_home and custom_away:
                local_dt   = datetime.combine(custom_date, custom_time).replace(tzinfo=tz_tunis)
                match_time = local_dt.astimezone(timezone.utc).isoformat()
                new_id     = -random.randint(10000, 99999)
                data = {
                    "fixture_id": new_id, "home_team": custom_home, "away_team": custom_away,
                    "league": custom_league, "match_time": match_time,
                    "status": "UPCOMING", "home_score": 0, "away_score": 0,
                    "streams": json.dumps([{"title": "بث يدوي", "url": custom_stream, "source": "admin", "verified": True, "admin_added": True}]) if custom_stream else "[]",
                    "home_logo": None, "away_logo": None, "league_logo": None,
                    "source": "custom", "is_custom": True
                }
                try:
                    supabase.table("matches").insert(data).execute()
                    st.success("تمت إضافة المباراة بنجاح"); st.rerun()
                except Exception as e:
                    st.error(f"خطأ في الإضافة: {e}")


# ═══════════════════════════════════════════════
#  TIMESTAMP
# ═══════════════════════════════════════════════
st.markdown(f'<div class="last-updated">🔄 آخر تحديث: {now_str}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  TABS
# ═══════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅 المباريات",
    "📊 النتائج",
    "📰 الأخبار",
    "🏆 الترتيب",
    "⭐ المفضلة",
    "🔮 التوقعات",
])


# ─── TAB 1 : MATCHES ────────────────────────────
with tab1:
    live_matches = get_live_matches()
    live_count   = len(live_matches) if live_matches else None
    render_section_header("🔴", "المباريات المباشرة الآن", badge=live_count)

    if live_matches:
        for m in live_matches:
            st.markdown(render_match_card(m), unsafe_allow_html=True)
    else:
        render_empty("📡", "لا توجد مباريات مباشرة حالياً")

    render_section_header("📅", "المباريات القادمة")
    upcoming = get_upcoming_matches_main()
    if upcoming:
        for m in upcoming:
            st.markdown(render_match_card(m), unsafe_allow_html=True)
    else:
        render_empty("📆", "لا توجد مباريات قادمة")


# ─── TAB 2 : RESULTS ────────────────────────────
with tab2:
    render_section_header("📊", "النتائج الأخيرة")
    finished = get_finished_matches()
    if finished:
        for m in finished:
            ht = html.escape(m['home_team'])
            at = html.escape(m['away_team'])
            # FIX #1 applied here too
            hl = m.get('home_logo') or safe_team_logo(ht)
            al = m.get('away_logo') or safe_team_logo(at)
            try:
                lt = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                ds = lt.strftime('%Y-%m-%d')
            except Exception:
                ds = "---"
            st.markdown(f"""
            <a href="/match_details?match_id={m['fixture_id']}" style="text-decoration:none;color:inherit;display:block;">
              <div class="match-card">
                <div style="display:flex;align-items:center;gap:8px;">
                  <div style="flex:1;text-align:center;">
                    <img src="{hl}" style="width:40px;height:40px;object-fit:contain;margin-bottom:5px;">
                    <div style="font-weight:700;font-size:.83rem;">{ht}</div>
                  </div>
                  <div style="flex:1;text-align:center;">
                    <strong style="font-size:1.55rem;font-weight:900;letter-spacing:3px;">{m['home_score']} - {m['away_score']}</strong>
                    <div style="margin-top:3px;font-size:.72rem;opacity:.45;">نهائي</div>
                  </div>
                  <div style="flex:1;text-align:center;">
                    <img src="{al}" style="width:40px;height:40px;object-fit:contain;margin-bottom:5px;">
                    <div style="font-weight:700;font-size:.83rem;">{at}</div>
                  </div>
                </div>
                <div style="text-align:center;opacity:.45;margin-top:8px;font-size:.75rem;font-weight:600;">
                  {html.escape(m.get('league',''))} • {ds}
                </div>
              </div>
            </a>""", unsafe_allow_html=True)
    else:
        render_empty("📭", "لا توجد نتائج بعد")


# ─── TAB 3 : NEWS ───────────────────────────────
with tab3:
    render_section_header("📰", "آخر الأخبار")
    news = get_news()
    if not news:
        render_empty("📭", "لا توجد أخبار حالياً")
    else:
        for item in news:
            safe_title   = html.escape(item.get('title', ''))
            safe_content = (html.escape(item.get('content', ''))[:200] + "...") if item.get('content') else ''
            safe_source  = html.escape(item.get('source', 'مصدر غير معروف'))
            safe_url     = html.escape(item.get('url', ''))
            safe_image   = html.escape(item.get('image', '')) if item.get('image') else None
            try:
                pub_date = datetime.fromisoformat(item["published_at"].replace('Z', '+00:00'))
                date_str = pub_date.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = "تاريخ غير معروف"
            lang       = item.get("language", "ar")
            lang_badge = '<span class="lang-badge en">🇬🇧 EN</span>' if lang == "en" else '<span class="lang-badge">🇸🇦 AR</span>'
            card_html  = '<div class="news-card">'
            if safe_image:
                card_html += f'<img src="{safe_image}" class="news-image">'
            card_html += f'''
                <a href="{safe_url}" target="_blank" class="news-title"><h3>{safe_title}</h3></a>
                <div class="news-content">{safe_content}</div>
                <div class="news-meta">
                  <span class="source-badge">📰 {safe_source}</span>
                  <span>🕒 {date_str}</span>
                  {lang_badge}
                </div>
            </div>'''
            try:
                # FIX: st.html() is broken in Streamlit 1.56 — outputs raw protobuf debug
                # text instead of rendering HTML. Always use st.markdown() instead.
                st.markdown(card_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"خطأ في عرض الخبر: {e}")


# ─── TAB 4 : STANDINGS ──────────────────────────
with tab4:
    render_section_header("🏆", "جدول الترتيب")
    try:
        comps = get_competitions_with_standings()
        if not comps:
            render_empty("🏆", "لا توجد ترتيبات متاحة حالياً")
        else:
            comp_names    = [c["competition_name"] for c in comps]
            selected_comp = st.selectbox("اختر البطولة", comp_names, key="standings_select")
            comp_data     = next(c for c in comps if c["competition_name"] == selected_comp)
            standings     = comp_data["data"].get("standings", [])
            if not standings:
                st.warning("لا توجد معلومات ترتيب لهذه البطولة")
            else:
                table = standings[0].get("table", [])
                if table:
                    html_table  = '<div style="overflow-x:auto;border-radius:14px;margin-top:12px;">'
                    html_table += '<table class="standings-table"><thead><tr>'
                    html_table += '<th>#</th><th>الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له</th><th>عليه</th><th>فارق</th><th>نقاط</th>'
                    html_table += '</tr></thead><tbody>'
                    for row in table:
                        team_id   = row["team"]["id"]
                        team_name = row["team"]["name"]
                        gd        = row["goalDifference"]
                        gd_color  = "#22c55e" if gd > 0 else ("#ef4444" if gd < 0 else "inherit")
                        gd_str    = f"+{gd}" if gd > 0 else str(gd)
                        html_table += f"""<tr>
                          <td><strong>{row["position"]}</strong></td>
                          <td style="text-align:right;padding-right:12px;">
                            <a href="/team?team_id={team_id}">{team_name}</a>
                          </td>
                          <td>{row["playedGames"]}</td>
                          <td style="color:#22c55e;font-weight:700;">{row["won"]}</td>
                          <td>{row["draw"]}</td>
                          <td style="color:#ef4444;">{row["lost"]}</td>
                          <td>{row["goalsFor"]}</td>
                          <td>{row["goalsAgainst"]}</td>
                          <td style="color:{gd_color};font-weight:700;">{gd_str}</td>
                          <td><strong style="font-size:.98rem;">{row["points"]}</strong></td>
                        </tr>"""
                    html_table += '</tbody></table></div>'
                    st.markdown(html_table, unsafe_allow_html=True)
                else:
                    render_empty("📋", "لا توجد بيانات جدول متاحة")
    except Exception as e:
        if "relation" in str(e) or "does not exist" in str(e):
            st.warning("جدول الترتيب غير موجود.")
        else:
            st.error(f"حدث خطأ: {e}")


# ─── TAB 5 : FAVORITES ──────────────────────────
with tab5:
    render_section_header("⭐", "مبارياتي المفضلة")
    if st.session_state.user:
        if st.session_state.favorites:
            all_matches = get_all_matches()
            fav_matches = [m for m in all_matches
                           if m['home_team'] in st.session_state.favorites
                           or m['away_team'] in st.session_state.favorites]
            if fav_matches:
                for m in fav_matches:
                    st.markdown(render_match_card(m, show_favorite=False), unsafe_allow_html=True)
            else:
                render_empty("📡", "لا توجد مباريات لفرقك المفضلة حالياً")
        else:
            render_empty("☆", "أضف فرقاً إلى المفضلة من خلال الضغط على ☆ في بطاقة المباراة")
    else:
        render_empty("🔐", "سجل الدخول لاستخدام المفضلة")


# ─── TAB 6 : PREDICTIONS ────────────────────────
with tab6:
    render_section_header("🔮", "توقعات المباريات")
    try:
        upcoming_pred = supabase.table("matches")\
            .select("fixture_id,home_team,away_team,match_time")\
            .eq("status", "UPCOMING").order("match_time").limit(10).execute()

        if not upcoming_pred.data:
            render_empty("🔮", "لا توجد مباريات قادمة للتوقع عليها")
        else:
            for m in upcoming_pred.data:
                pred_data = get_predictions_for_match(m["fixture_id"])
                if pred_data:
                    p = pred_data[0]
                    st.markdown(f"""
                    <div class="prediction-card">
                      <div class="prediction-teams">{html.escape(m['home_team'])} ⚔️ {html.escape(m['away_team'])}</div>
                    </div>""", unsafe_allow_html=True)
                    st.markdown(f'<div class="pred-label">فوز {html.escape(m["home_team"])} — {round(p["home_win_prob"] * 100)}%</div>', unsafe_allow_html=True)
                    st.progress(float(p["home_win_prob"]))
                    st.markdown(f'<div class="pred-label">تعادل — {round(p["draw_prob"] * 100)}%</div>', unsafe_allow_html=True)
                    st.progress(float(p["draw_prob"]))
                    st.markdown(f'<div class="pred-label">فوز {html.escape(m["away_team"])} — {round(p["away_win_prob"] * 100)}%</div>', unsafe_allow_html=True)
                    st.progress(float(p["away_win_prob"]))
                else:
                    st.markdown(f"""
                    <div class="prediction-card">
                      <div class="prediction-teams">{html.escape(m['home_team'])} ⚔️ {html.escape(m['away_team'])}</div>
                      <div style="text-align:center;opacity:.45;font-size:.83rem;">لا توجد توقعات بعد</div>
                    </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"خطأ في تحميل التوقعات: {e}")
