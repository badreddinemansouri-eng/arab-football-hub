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

# -------------------- Page Config --------------------
st.set_page_config(
    page_title="Badr TV | منصة كرة القدم الشاملة",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------- Load Secrets --------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------- Timezone --------------------
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

# -------------------- Session State --------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "profile" not in st.session_state:
    st.session_state.profile = None
if "favorites" not in st.session_state:
    st.session_state.favorites = []
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = False
if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False

# -------------------- Custom CSS --------------------
def get_css():
    is_dark = st.session_state.theme == "dark"

    # Color tokens
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

    return f"""
<style>
    /* ===== GOOGLE FONT ===== */
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap');

    /* ===== GLOBAL RESET ===== */
    *, *::before, *::after {{
        font-family: 'Cairo', sans-serif !important;
        box-sizing: border-box;
    }}

    /* ===== HIDE STREAMLIT CHROME ===== */
    header[data-testid="stHeader"],
    footer,
    #MainMenu,
    .stDeployButton {{
        display: none !important;
    }}

    /* ===== PAGE BACKGROUND ===== */
    .stApp {{
        background: {bg_primary} !important;
    }}
    .main, .block-container {{
        background: {bg_primary} !important;
        direction: rtl;
        text-align: right;
        padding-top: 0 !important;
        padding-bottom: 2rem;
        max-width: 100% !important;
    }}

    /* ===== HEADER BAR ===== */
    .badrtv-header {{
        background: linear-gradient(135deg, #0d47a1 0%, #1565c0 50%, #1976d2 100%);
        padding: 0 24px;
        height: 68px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: sticky;
        top: 0;
        z-index: 900;
        box-shadow: 0 4px 24px rgba(13,71,161,0.5);
        border-bottom: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 0;
    }}
    .badrtv-header-brand {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .badrtv-header-brand img {{
        width: 44px;
        height: 44px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid rgba(255,255,255,0.3);
        box-shadow: 0 0 12px rgba(255,255,255,0.15);
    }}
    .badrtv-header-title {{
        font-size: 1.5rem;
        font-weight: 900;
        color: #ffffff;
        margin: 0;
        letter-spacing: 0.5px;
        text-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }}
    .badrtv-header-sub {{
        font-size: 0.7rem;
        color: rgba(255,255,255,0.6);
        font-weight: 400;
        display: block;
        margin-top: -4px;
        letter-spacing: 1px;
    }}
    .badrtv-header-right {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .badrtv-time-badge {{
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.78rem;
        color: rgba(255,255,255,0.8);
        font-weight: 600;
        letter-spacing: 0.5px;
    }}

    /* ===== HAMBURGER BUTTON ===== */
    /* Target the hamburger button column specifically */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child .stButton > button {{
        background: rgba(255,255,255,0.12) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: white !important;
        font-size: 1.3rem !important;
        font-weight: 700 !important;
        width: 42px !important;
        height: 42px !important;
        border-radius: 12px !important;
        padding: 0 !important;
        line-height: 1 !important;
        cursor: pointer;
        transition: background 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child .stButton > button:hover {{
        background: rgba(255,255,255,0.22) !important;
    }}

    /* ===== DRAWER OVERLAY ===== */
    .sidebar-overlay {{
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.55);
        z-index: 1000;
        backdrop-filter: blur(2px);
        -webkit-backdrop-filter: blur(2px);
    }}
    .sidebar-drawer {{
        position: fixed;
        top: 0;
        right: 0;
        width: min(340px, 88vw);
        height: 100dvh;
        background: {sidebar_bg};
        z-index: 1001;
        overflow-y: auto;
        box-shadow: -8px 0 40px rgba(0,0,0,0.4);
        border-left: 1px solid {border_color};
        direction: rtl;
        animation: slideInRight 0.28s cubic-bezier(0.32, 0.72, 0, 1);
    }}
    @keyframes slideInRight {{
        from {{ transform: translateX(100%); opacity: 0; }}
        to   {{ transform: translateX(0);    opacity: 1; }}
    }}
    .sidebar-drawer-header {{
        background: linear-gradient(135deg, #0d47a1, #1976d2);
        padding: 20px 20px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .sidebar-drawer-header h3 {{
        color: white;
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
    }}
    .sidebar-close-btn {{
        background: rgba(255,255,255,0.15);
        border: none;
        border-radius: 8px;
        color: white;
        font-size: 1.2rem;
        width: 34px;
        height: 34px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.2s;
    }}
    .sidebar-close-btn:hover {{ background: rgba(255,255,255,0.28); }}
    .sidebar-section {{
        padding: 16px 20px;
        border-bottom: 1px solid {border_color};
    }}
    .sidebar-section-title {{
        font-size: 0.72rem;
        font-weight: 700;
        color: #1976d2;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 12px;
    }}

    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: {bg_secondary} !important;
        border-radius: 14px;
        padding: 5px;
        border: 1px solid {border_color};
        margin-bottom: 20px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 10px !important;
        padding: 8px 14px !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: {text_secondary} !important;
        background: transparent !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, #1565c0, #1976d2) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(25,118,210,0.4) !important;
    }}
    .stTabs [data-baseweb="tab-highlight"] {{ display: none !important; }}
    .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}

    /* Mobile tabs: scroll */
    @media (max-width: 600px) {{
        .stTabs [data-baseweb="tab-list"] {{
            overflow-x: auto;
            flex-wrap: nowrap;
            scrollbar-width: none;
        }}
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {{ display: none; }}
        .stTabs [data-baseweb="tab"] {{
            padding: 7px 10px !important;
            font-size: 0.75rem !important;
            white-space: nowrap;
        }}
    }}

    /* ===== SECTION HEADERS ===== */
    .section-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 20px 0 14px;
        padding-bottom: 10px;
        border-bottom: 2px solid {border_color};
    }}
    .section-header-icon {{
        width: 36px;
        height: 36px;
        background: linear-gradient(135deg, #1565c0, #1976d2);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        box-shadow: 0 4px 10px rgba(25,118,210,0.35);
    }}
    .section-header-text {{
        font-size: 1.1rem;
        font-weight: 700;
        color: {text_primary};
    }}
    .live-count-badge {{
        background: #dc2626;
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 20px;
        margin-right: auto;
        animation: pulseBadge 1.5s infinite;
    }}
    @keyframes pulseBadge {{
        0%,100% {{ opacity: 1; transform: scale(1); }}
        50%      {{ opacity: 0.75; transform: scale(1.06); }}
    }}

    /* ===== MATCH CARD ===== */
    .match-card {{
        background: {bg_card};
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 12px;
        border: 1px solid {border_color};
        box-shadow: 0 2px 12px rgba(0,0,0,0.12);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }}
    .match-card::before {{
        content: '';
        position: absolute;
        top: 0; right: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(180deg, #1565c0, #1976d2);
        border-radius: 0 16px 16px 0;
    }}
    .match-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 28px rgba(25,118,210,0.18);
        border-color: #1976d2;
    }}
    .match-card.live-card::before {{
        background: linear-gradient(180deg, #dc2626, #ef4444);
    }}

    /* ===== NEWS CARD ===== */
    .news-card {{
        background: {bg_card};
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 14px;
        border: 1px solid {border_color};
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        direction: rtl;
        overflow: hidden;
    }}
    .news-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    }}
    .news-image {{
        width: 100%;
        max-height: 180px;
        object-fit: cover;
        border-radius: 10px;
        margin-bottom: 12px;
    }}
    .news-title h3 {{
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0 0 8px 0;
        color: {text_primary};
        line-height: 1.5;
    }}
    .news-title {{ text-decoration: none; color: inherit; }}
    .news-title:hover h3 {{ color: #1976d2; }}
    .news-content {{
        color: {text_secondary};
        font-size: 0.88rem;
        line-height: 1.7;
        margin-bottom: 12px;
    }}
    .news-meta {{
        display: flex;
        justify-content: flex-start;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        color: {text_secondary};
        font-size: 0.8rem;
    }}
    .source-badge {{
        background: linear-gradient(135deg, #1565c0, #1976d2);
        color: white;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    .lang-badge {{
        background: #166534;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.72rem;
        font-weight: 600;
    }}
    .lang-badge.en {{ background: #1e3a8a; }}

    /* ===== LIVE BADGE ===== */
    .live-badge {{
        background: linear-gradient(135deg, #dc2626, #ef4444);
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
        animation: pulse 1.5s infinite;
        box-shadow: 0 0 12px rgba(220,38,38,0.5);
        letter-spacing: 0.5px;
    }}
    @keyframes pulse {{
        0%,100% {{ opacity: 1; transform: scale(1); }}
        50%      {{ opacity: 0.8; transform: scale(1.04); }}
    }}

    /* ===== STANDINGS TABLE ===== */
    .standings-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        text-align: center;
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid {border_color};
        font-size: 0.85rem;
    }}
    .standings-table thead th {{
        background: linear-gradient(135deg, #0d47a1, #1976d2);
        color: white;
        padding: 12px 8px;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.3px;
    }}
    .standings-table tbody tr {{
        background: {bg_card};
        transition: background 0.15s;
    }}
    .standings-table tbody tr:nth-child(even) {{
        background: {bg_secondary};
    }}
    .standings-table tbody tr:hover {{
        background: {bg_card_hover};
    }}
    .standings-table td {{
        padding: 10px 8px;
        border-bottom: 1px solid {border_color};
        color: {text_primary};
    }}
    .standings-table a {{
        color: {text_primary};
        text-decoration: none;
        font-weight: 600;
    }}
    .standings-table a:hover {{ color: #1976d2; }}

    /* Top 4 highlight */
    .standings-table tbody tr:nth-child(-n+4) td:first-child {{
        border-right: 3px solid #1976d2;
    }}

    /* ===== SEARCH BAR ===== */
    .stTextInput > div > div > input {{
        background: {input_bg} !important;
        border: 1.5px solid {border_color} !important;
        border-radius: 12px !important;
        color: {text_primary} !important;
        font-family: 'Cairo', sans-serif !important;
        padding: 10px 16px !important;
        font-size: 0.9rem !important;
        direction: rtl;
        transition: border-color 0.2s ease !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: #1976d2 !important;
        box-shadow: 0 0 0 3px rgba(25,118,210,0.15) !important;
    }}

    /* ===== SELECTBOX ===== */
    .stSelectbox > div > div {{
        background: {input_bg} !important;
        border: 1.5px solid {border_color} !important;
        border-radius: 12px !important;
        color: {text_primary} !important;
    }}

    /* ===== RADIO BUTTONS ===== */
    .stRadio label {{
        color: {text_primary} !important;
    }}

    /* ===== EXPANDER ===== */
    .stExpander {{
        background: {bg_card} !important;
        border: 1px solid {border_color} !important;
        border-radius: 12px !important;
    }}
    .stExpander summary {{
        color: {text_primary} !important;
        font-weight: 600 !important;
    }}

    /* ===== SIDEBAR STREAMLIT BUTTONS (inside drawer) ===== */
    div[data-testid="stVerticalBlock"] .stButton > button {{
        background: linear-gradient(135deg, #1565c0, #1976d2) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 8px 20px !important;
        width: 100% !important;
        transition: opacity 0.2s, transform 0.2s !important;
        box-shadow: 0 4px 12px rgba(25,118,210,0.3) !important;
        cursor: pointer;
    }}
    div[data-testid="stVerticalBlock"] .stButton > button:hover {{
        opacity: 0.9 !important;
        transform: translateY(-1px) !important;
    }}

    /* ===== INFO / SUCCESS / ERROR MESSAGES ===== */
    .stInfo, .stSuccess, .stWarning, .stError {{
        border-radius: 12px !important;
        font-family: 'Cairo', sans-serif !important;
    }}

    /* ===== PROGRESS BAR (predictions) ===== */
    .stProgress > div > div {{
        background: linear-gradient(90deg, #1565c0, #1976d2) !important;
        border-radius: 10px !important;
    }}
    .stProgress > div {{
        background: {border_color} !important;
        border-radius: 10px !important;
    }}

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #1976d2; border-radius: 4px; }}

    /* ===== LAST UPDATED ===== */
    .last-updated {{
        text-align: left;
        color: {text_secondary};
        font-size: 0.75rem;
        margin: 6px 0 16px;
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 0 4px;
    }}

    /* ===== EMPTY STATE ===== */
    .empty-state {{
        text-align: center;
        padding: 40px 20px;
        color: {text_secondary};
        font-size: 0.95rem;
    }}
    .empty-state-icon {{
        font-size: 2.5rem;
        margin-bottom: 10px;
        display: block;
    }}

    /* ===== PREDICTION CARD ===== */
    .prediction-card {{
        background: {bg_card};
        border: 1px solid {border_color};
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 14px;
    }}
    .prediction-teams {{
        font-size: 1rem;
        font-weight: 700;
        color: {text_primary};
        margin-bottom: 14px;
        text-align: center;
    }}
    .pred-label {{
        font-size: 0.82rem;
        color: {text_secondary};
        margin-bottom: 4px;
        font-weight: 600;
    }}

    /* ===== FAVORITE TEAM TAG ===== */
    .fav-team-tag {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: {bg_secondary};
        border: 1px solid {border_color};
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.82rem;
        color: {text_primary};
        margin: 4px;
        font-weight: 600;
    }}

    /* ===== FORM INPUTS in admin ===== */
    .stNumberInput > div > div > input {{
        background: {input_bg} !important;
        border: 1.5px solid {border_color} !important;
        border-radius: 10px !important;
        color: {text_primary} !important;
    }}

    /* ===== MOBILE PADDING ===== */
    @media (max-width: 640px) {{
        .block-container {{
            padding-left: 12px !important;
            padding-right: 12px !important;
        }}
        .match-card {{
            padding: 13px 14px;
        }}
        .badrtv-header {{
            padding: 0 14px;
            height: 60px;
        }}
        .badrtv-header-title {{
            font-size: 1.2rem;
        }}
        .badrtv-time-badge {{
            display: none;
        }}
    }}
</style>
"""

st.markdown(get_css(), unsafe_allow_html=True)

# -------------------- Helper Functions --------------------
def get_matches():
    resp = supabase.table("matches").select("*").order("match_time", desc=False).execute()
    return resp.data

def time_until(match_time_str):
    try:
        match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = match_time - now
        if diff.total_seconds() < 0:
            return "انتهت"
        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)
        return f"{hours} س {minutes} د"
    except:
        return "---"

def render_match_card(match, show_favorite=True):
    home_team = html.escape(match.get('home_team', '???'))
    away_team = html.escape(match.get('away_team', '???'))
    home_logo = match.get('home_logo') or get_team_logo(home_team)
    away_logo = match.get('away_logo') or get_team_logo(away_team)
    league_logo = match.get('league_logo') or get_league_logo(match.get('league', ''))
    league_name = html.escape(match.get('league', ''))

    effective_status = match['status']
    if effective_status != 'FINISHED':
        try:
            match_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            if now - match_time > timedelta(hours=3):
                effective_status = 'FINISHED'
        except:
            pass

    live_class = ""
    if effective_status == 'LIVE':
        center = f"<span style='color:#ef4444; font-weight:900; font-size:1.9rem; letter-spacing:2px;'>{match['home_score']} - {match['away_score']}</span>"
        status_display = '<span class="live-badge">🔴 مباشر</span>'
        live_class = "live-card"
    elif effective_status == 'UPCOMING':
        try:
            utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            local_time = utc_time.astimezone(tz_tunis)
            today = datetime.now(tz_tunis).date()
            match_date = local_time.date()
            if match_date == today:
                diff = (local_time - datetime.now(tz_tunis)).total_seconds() / 60
                if 0 < diff <= 30:
                    status_display = "<span style='color:#f59e0b; font-size:0.8rem; font-weight:700;'>⏳ بعد قليل</span>"
                else:
                    status_display = "<span style='color:#6b7280; font-size:0.8rem;'>لم تبدأ</span>"
                center = f"<span style='color:#1976d2; font-weight:900; font-size:1.6rem;'>{local_time.strftime('%H:%M')}</span>"
            else:
                status_display = f"<span style='color:#9ca3af; font-size:0.8rem;'>{match_date.strftime('%m/%d')}</span>"
                center = f"<span style='color:#1976d2; font-weight:900; font-size:1.6rem;'>{local_time.strftime('%H:%M')}</span>"
        except:
            status_display = "<span style='color:#6b7280; font-size:0.8rem;'>لم تبدأ</span>"
            center = "--:--"
    else:
        try:
            utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            local_time = utc_time.astimezone(tz_tunis)
            status_display = f"<span style='color:#9ca3af; font-size:0.8rem;'>{local_time.strftime('%m/%d')}</span>"
            center = f"<span style='color:#6b7280; font-weight:900; font-size:1.6rem;'>{match['home_score']} - {match['away_score']}</span>"
        except:
            status_display = "<span style='color:#9ca3af; font-size:0.8rem;'>انتهت</span>"
            center = f"{match['home_score']} - {match['away_score']}"

    return f"""
    <a href="/watch_stream?match_id={match['fixture_id']}" style="text-decoration:none; color:inherit; display:block;">
        <div class="match-card {live_class}">
            <div style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
                <div style="flex:1; text-align:center;">
                    <img src="{home_logo}" style="width:52px; height:52px; object-fit:contain; margin-bottom:8px; filter:drop-shadow(0 2px 4px rgba(0,0,0,0.2));">
                    <div style="font-weight:700; font-size:0.85rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:90px; margin:0 auto;">{home_team}</div>
                </div>
                <div style="flex:1; text-align:center; padding:0 8px;">
                    {center}
                    <div style="margin-top:6px;">{status_display}</div>
                </div>
                <div style="flex:1; text-align:center;">
                    <img src="{away_logo}" style="width:52px; height:52px; object-fit:contain; margin-bottom:8px; filter:drop-shadow(0 2px 4px rgba(0,0,0,0.2));">
                    <div style="font-weight:700; font-size:0.85rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:90px; margin:0 auto;">{away_team}</div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px; margin-top:12px; padding-top:10px; border-top:1px solid rgba(128,128,128,0.15);">
                <img src="{league_logo}" style="width:18px; height:18px; object-fit:contain; opacity:0.8;">
                <span style="font-size:0.78rem; opacity:0.6; font-weight:600;">{league_name}</span>
            </div>
        </div>
    </a>
    """

def render_section_header(icon, title, badge=None):
    badge_html = f'<span class="live-count-badge">{badge}</span>' if badge else ''
    st.markdown(f"""
    <div class="section-header">
        <div class="section-header-icon">{icon}</div>
        <span class="section-header-text">{title}</span>
        {badge_html}
    </div>
    """, unsafe_allow_html=True)

# ==================== HEADER ====================
now_str = datetime.now(tz_tunis).strftime("%H:%M:%S")

col_burger, col_brand = st.columns([1, 11])

with col_brand:
    st.markdown(f"""
    <div class="badrtv-header">
        <div class="badrtv-header-brand">
            <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg" alt="Badr TV Logo">
            <div>
                <div class="badrtv-header-title">Badr TV</div>
                <span class="badrtv-header-sub">منصة كرة القدم الشاملة</span>
            </div>
        </div>
        <div class="badrtv-header-right">
            <div class="badrtv-time-badge">🕐 {now_str}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_burger:
    st.markdown('<div style="padding-top: 12px;">', unsafe_allow_html=True)
    if st.button("☰", key="sidebar_toggle", use_container_width=False):
        st.session_state.sidebar_open = not st.session_state.sidebar_open
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== SIDEBAR DRAWER ====================
if st.session_state.sidebar_open:
    st.markdown('<div class="sidebar-overlay"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-drawer">', unsafe_allow_html=True)

    # Drawer header
    st.markdown("""
    <div class="sidebar-drawer-header">
        <h3>⚙️ القائمة الرئيسية</h3>
    </div>
    """, unsafe_allow_html=True)

    # Close button (Streamlit button, full width)
    if st.button("✕ إغلاق", key="close_sidebar"):
        st.session_state.sidebar_open = False
        st.rerun()

    # ---- ACCOUNT SECTION ----
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">👤 الحساب</div>', unsafe_allow_html=True)
    if st.session_state.user:
        st.markdown(f"<p style='margin:0 0 10px; font-size:0.88rem; opacity:0.8;'>مرحباً 👋<br><strong>{st.session_state.user.email}</strong></p>", unsafe_allow_html=True)
        if st.button("تسجيل الخروج", key="logout_main"):
            sign_out()
    else:
        with st.expander("تسجيل الدخول"):
            email = st.text_input("البريد الإلكتروني", key="login_email")
            password = st.text_input("كلمة المرور", type="password", key="login_password")
            if st.button("دخول", key="login_main"):
                sign_in(email, password)
        with st.expander("إنشاء حساب"):
            new_email = st.text_input("البريد الإلكتروني", key="signup_email")
            new_pass = st.text_input("كلمة المرور", type="password", key="signup_pass")
            if st.button("تسجيل", key="signup_main"):
                sign_up(new_email, new_pass)
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- THEME SECTION ----
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">🎨 المظهر</div>', unsafe_allow_html=True)
    theme = st.radio("", ["داكن", "فاتح"], index=0 if st.session_state.theme == "dark" else 1, key="theme_radio", horizontal=True)
    if theme == "داكن" and st.session_state.theme != "dark":
        st.session_state.theme = "dark"
        st.rerun()
    elif theme == "فاتح" and st.session_state.theme != "light":
        st.session_state.theme = "light"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- SEARCH SECTION ----
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">🔍 البحث</div>', unsafe_allow_html=True)
    search_query = st.text_input(" ", label_visibility="collapsed", key="search_input", placeholder="ابحث عن فريق أو لاعب...")
    if search_query:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**الفرق**")
            teams = supabase.table("teams").select("id, name, logo").ilike("name", f"%{search_query}%").execute()
            for t in teams.data:
                st.markdown(f"[{t['name']}](/team?team_id={t['id']})")
        with col2:
            st.markdown("**اللاعبين**")
            players = supabase.table("players").select("id, name, photo").ilike("name", f"%{search_query}%").execute()
            for p in players.data:
                st.markdown(f"[{p['name']}](/player?player_id={p['id']})")
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- FAVORITES SECTION ----
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">⭐ المفضلة</div>', unsafe_allow_html=True)
    if st.session_state.user:
        if st.session_state.favorites:
            favs_html = "".join([f'<span class="fav-team-tag">⭐ {team}</span>' for team in st.session_state.favorites])
            st.markdown(f'<div style="margin-top:6px;">{favs_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="font-size:0.85rem; opacity:0.6; margin:0;">لا توجد فرق مفضلة بعد</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="font-size:0.85rem; opacity:0.6; margin:0;">سجل الدخول لرؤية مفضلتك</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- ADMIN PANEL ----
    st.markdown('<div class="sidebar-section"><div class="sidebar-section-title">👑 لوحة التحكم</div>', unsafe_allow_html=True)
    with st.expander("دخول المشرف", expanded=False):
        if not st.session_state.admin_auth:
            admin_pass = st.text_input("كلمة المرور", type="password", key="admin_pass")
            if st.button("دخول", key="admin_login"):
                if hashlib.sha256(admin_pass.encode()).hexdigest() == "f00bf9d13f09fa3962d4a7d21de2479699adc840b74e34195a0eedb6dd45ceb4":
                    st.session_state.admin_auth = True
                    st.success("تم تسجيل الدخول بنجاح")
                    st.rerun()
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

    st.markdown('</div>', unsafe_allow_html=True)  # close sidebar-drawer

# ==================== ADMIN PANEL (main area) ====================
if st.session_state.get("admin_auth") and st.session_state.get("show_admin"):
    with st.container():
        st.markdown("---")
        st.markdown("### 👑 لوحة تحكم المشرف - إضافة روابط يدوية")

        @st.cache_data(ttl=60)
        def get_upcoming_matches():
            try:
                resp = supabase.table("matches")\
                    .select("*")\
                    .in_("status", ["UPCOMING", "LIVE"])\
                    .order("match_time")\
                    .execute()
                return resp.data
            except Exception as e:
                print(f"Error fetching upcoming matches: {e}")
                return []

        upcoming = get_upcoming_matches()
        if upcoming:
            match_data = {}
            for m in upcoming:
                try:
                    utc_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    time_str = local_time.strftime("%H:%M")
                except:
                    time_str = "--:--"
                label = f"{time_str} - {m['home_team']} vs {m['away_team']} ({m['league']})"
                match_data[label] = (m['fixture_id'], m['source'])
            selected_match = st.selectbox("اختر المباراة", list(match_data.keys()), key="match_select")
            fixture_id, match_source = match_data[selected_match]

            col1, col2 = st.columns(2)
            with col1:
                stream_url = st.text_input("رابط البث", key="stream_url")
                stream_title = st.text_input("عنوان الرابط (اختياري)", key="stream_title")
            with col2:
                stream_source = st.selectbox("المصدر", ["youtube", "facebook", "custom", "official"], key="stream_source")
                expiry_hours = st.number_input("عدد ساعات الصلاحية", min_value=1, max_value=24, value=3, key="expiry_hours")

            if st.button("إضافة الرابط", key="add_stream_btn"):
                if stream_url:
                    expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
                    data = {
                        "fixture_id": fixture_id,
                        "source": match_source,
                        "stream_url": stream_url,
                        "stream_title": stream_title or "بث مباشر",
                        "stream_source": stream_source,
                        "expires_at": expires_at,
                        "is_active": True
                    }
                    try:
                        supabase.table("admin_streams").insert(data).execute()
                        st.success("تم إضافة الرابط بنجاح! سيتم حذفه تلقائياً بعد انتهاء المباراة.")
                        st.cache_data.clear()
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء إضافة الرابط: {str(e)}")
                        print(f"Error inserting admin stream: {e}")
                else:
                    st.error("الرجاء إدخال رابط البث")

            st.markdown("---")
            st.subheader("الروابط الحالية")
            try:
                admin_streams = supabase.table("admin_streams")\
                    .select("*, matches!inner(home_team, away_team, league, status)")\
                    .eq("is_active", True)\
                    .execute()\
                    .data
                if admin_streams:
                    for stream in admin_streams:
                        match = stream.get("matches", {})
                        try:
                            utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                            local_time = utc_time.astimezone(tz_tunis)
                            time_str = local_time.strftime("%H:%M")
                        except:
                            time_str = "--:--"
                        st.markdown(f"""
                        **{match.get('home_team')} vs {match.get('away_team')}**  
                        الوقت: {time_str}  
                        الرابط: {stream['stream_url']}  
                        ينتهي في: {stream['expires_at'][:16]}
                        """)
                        if st.button(f"حذف #{stream['id']}", key=f"del_{stream['id']}"):
                            supabase.table("admin_streams").update({"is_active": False}).eq("id", stream["id"]).execute()
                            st.success("تم الحذف")
                            st.rerun()
            except Exception as e:
                st.error("حدث خطأ أثناء تحميل الروابط.")
                print(f"Error loading admin streams: {e}")
        else:
            st.info("لا توجد مباريات قادمة")

        st.markdown("---")
        st.subheader("➕ إضافة مباراة يدوية")
        with st.form("add_custom_match_form"):
            custom_home = st.text_input("الفريق المستضيف")
            custom_away = st.text_input("الفريق الضيف")
            custom_league = st.text_input("الدوري")
            custom_date = st.date_input("التاريخ", datetime.now())
            custom_time = st.time_input("الوقت", datetime.now().time(), key="custom_match_time")
            custom_stream = st.text_input("رابط البث (اختياري)")
            submitted = st.form_submit_button("إضافة المباراة")
            if submitted and custom_home and custom_away:
                print(f"Input local datetime: {custom_date} {custom_time} (assumed Africa/Tunis)")
                local_dt = datetime.combine(custom_date, custom_time).replace(tzinfo=tz_tunis)
                utc_dt = local_dt.astimezone(timezone.utc)
                match_time = utc_dt.isoformat()
                new_id = -random.randint(10000, 99999)
                data = {
                    "fixture_id": new_id,
                    "home_team": custom_home,
                    "away_team": custom_away,
                    "league": custom_league,
                    "match_time": match_time,
                    "status": "UPCOMING",
                    "home_score": 0,
                    "away_score": 0,
                    "streams": json.dumps([{"title": "بث يدوي", "url": custom_stream, "source": "admin", "verified": True, "admin_added": True}]) if custom_stream else "[]",
                    "home_logo": None,
                    "away_logo": None,
                    "league_logo": None,
                    "source": "custom",
                    "is_custom": True
                }
                supabase.table("matches").insert(data).execute()
                st.success("تمت إضافة المباراة بنجاح")
                st.rerun()

# ==================== MAIN CONTENT ====================
st.markdown(f'<div class="last-updated">🔄 آخر تحديث: {now_str}</div>', unsafe_allow_html=True)

matches = get_matches()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅 المباريات",
    "📊 النتائج",
    "📰 الأخبار",
    "🏆 الترتيب",
    "⭐ المفضلة",
    "🔮 التوقعات"
])

# ---- TAB 1: MATCHES ----
with tab1:
    live_result = supabase.table("matches").select("*").eq("status", "LIVE").execute()
    live_matches = live_result.data

    live_count = len(live_matches) if live_matches else None
    render_section_header("🔴", "المباريات المباشرة الآن", badge=live_count)

    if live_matches:
        for m in live_matches:
            st.markdown(render_match_card(m), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon">📡</span>
            لا توجد مباريات مباشرة حالياً
        </div>
        """, unsafe_allow_html=True)

    render_section_header("📅", "المباريات القادمة")
    upcoming_result = supabase.table("matches")\
        .select("*")\
        .eq("status", "UPCOMING")\
        .order("match_time")\
        .execute()
    upcoming = upcoming_result.data
    if upcoming:
        for m in upcoming:
            st.markdown(render_match_card(m), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon">📆</span>
            لا توجد مباريات قادمة
        </div>
        """, unsafe_allow_html=True)

# ---- TAB 2: RESULTS ----
with tab2:
    render_section_header("📊", "النتائج الأخيرة")
    finished_result = supabase.table("matches")\
        .select("*")\
        .eq("status", "FINISHED")\
        .order("match_time", desc=True)\
        .execute()
    finished = finished_result.data
    if finished:
        for m in finished:
            home_team = html.escape(m['home_team'])
            away_team = html.escape(m['away_team'])
            home_logo = m.get('home_logo') or get_team_logo(home_team)
            away_logo = m.get('away_logo') or get_team_logo(away_team)
            try:
                utc_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
                local_time = utc_time.astimezone(tz_tunis)
                date_str = local_time.strftime('%Y-%m-%d')
            except:
                date_str = "---"
            st.markdown(f"""
            <a href="/match_details?match_id={m['fixture_id']}" style="text-decoration:none; color:inherit; display:block;">
                <div class="match-card">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <div style="flex:1; text-align:center;">
                            <img src="{home_logo}" style="width:40px; height:40px; object-fit:contain; margin-bottom:6px;">
                            <div style="font-weight:700; font-size:0.85rem;">{home_team}</div>
                        </div>
                        <div style="flex:1; text-align:center;">
                            <strong style="font-size:1.6rem; font-weight:900; letter-spacing:3px;">{m['home_score']} - {m['away_score']}</strong>
                            <div style="margin-top:4px; font-size:0.75rem; opacity:0.5;">نهائي</div>
                        </div>
                        <div style="flex:1; text-align:center;">
                            <img src="{away_logo}" style="width:40px; height:40px; object-fit:contain; margin-bottom:6px;">
                            <div style="font-weight:700; font-size:0.85rem;">{away_team}</div>
                        </div>
                    </div>
                    <div style="text-align:center; opacity:0.5; margin-top:8px; font-size:0.78rem; font-weight:600;">
                        {html.escape(m.get('league',''))} • {date_str}
                    </div>
                </div>
            </a>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon">📭</span>
            لا توجد نتائج بعد
        </div>
        """, unsafe_allow_html=True)

# ---- TAB 3: NEWS ----
with tab3:
    render_section_header("📰", "آخر الأخبار")

    @st.cache_data(ttl=3600)
    def get_news():
        cutoff = (datetime.now() - timedelta(days=14)).isoformat()
        try:
            res = supabase.table("news")\
                .select("*")\
                .gte("published_at", cutoff)\
                .order("published_at", desc=True)\
                .limit(50)\
                .execute()
            return res.data
        except Exception as e:
            st.error(f"حدث خطأ في جلب الأخبار: {e}")
            return []

    news = get_news()
    if not news:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon">📭</span>
            لا توجد أخبار حالياً
        </div>
        """, unsafe_allow_html=True)
    else:
        for item in news:
            safe_title = html.escape(item.get('title', ''))
            safe_content = html.escape(item.get('content', ''))[:200] + "..." if item.get('content') else ''
            safe_source = html.escape(item.get('source', 'مصدر غير معروف'))
            safe_url = html.escape(item.get('url', ''))
            safe_image = html.escape(item.get('image', '')) if item.get('image') else None

            try:
                pub_date = datetime.fromisoformat(item["published_at"].replace('Z', '+00:00'))
                date_str = pub_date.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = "تاريخ غير معروف"

            lang = item.get("language", "ar")
            lang_badge = '<span class="lang-badge en">🇬🇧 EN</span>' if lang == "en" else '<span class="lang-badge">🇸🇦 AR</span>'

            card_html = '<div class="news-card">'
            if safe_image:
                card_html += f'<img src="{safe_image}" class="news-image">'
            card_html += f'''
                <a href="{safe_url}" target="_blank" class="news-title">
                    <h3>{safe_title}</h3>
                </a>
                <div class="news-content">{safe_content}</div>
                <div class="news-meta">
                    <span class="source-badge">📰 {safe_source}</span>
                    <span style="font-size:0.75rem;">🕒 {date_str}</span>
                    {lang_badge}
                </div>
            </div>
            '''
            try:
                if hasattr(st, 'html'):
                    st.html(card_html)
                else:
                    st.markdown(card_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"حدث خطأ في عرض الخبر: {e}")

# ---- TAB 4: STANDINGS ----
with tab4:
    render_section_header("🏆", "جدول الترتيب")
    try:
        @st.cache_data(ttl=3600)
        def get_competitions_with_standings():
            resp = supabase.table("standings").select("competition_code, competition_name, data").execute()
            return resp.data if resp.data else []

        comps = get_competitions_with_standings()
        if not comps:
            st.info("لا توجد ترتيبات متاحة حالياً")
        else:
            comp_names = [c["competition_name"] for c in comps]
            selected_comp = st.selectbox("اختر البطولة", comp_names, key="standings_select")
            comp_data = next(c for c in comps if c["competition_name"] == selected_comp)
            standings = comp_data["data"].get("standings", [])
            if not standings:
                st.warning("لا توجد معلومات ترتيب لهذه البطولة")
            else:
                table = standings[0].get("table", [])
                if table:
                    html_table = '<div style="overflow-x: auto; border-radius:14px; margin-top:12px;">'
                    html_table += '<table class="standings-table">'
                    html_table += '<thead><tr><th>#</th><th>الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له</th><th>عليه</th><th>فارق</th><th>نقاط</th></tr></thead>'
                    html_table += '<tbody>'
                    for row in table:
                        team_id = row["team"]["id"]
                        team_name = row["team"]["name"]
                        pos = row["position"]
                        pts = row["points"]
                        html_table += f'<tr>'
                        html_table += f'<td><strong>{pos}</strong></td>'
                        html_table += f'<td style="text-align:right; padding-right:12px;"><a href="/team?team_id={team_id}" style="color: inherit; text-decoration: none;">{team_name}</a></td>'
                        html_table += f'<td>{row["playedGames"]}</td>'
                        html_table += f'<td style="color:#22c55e; font-weight:700;">{row["won"]}</td>'
                        html_table += f'<td>{row["draw"]}</td>'
                        html_table += f'<td style="color:#ef4444;">{row["lost"]}</td>'
                        html_table += f'<td>{row["goalsFor"]}</td>'
                        html_table += f'<td>{row["goalsAgainst"]}</td>'
                        gd = row["goalDifference"]
                        gd_color = "#22c55e" if gd > 0 else ("#ef4444" if gd < 0 else "inherit")
                        gd_str = f"+{gd}" if gd > 0 else str(gd)
                        html_table += f'<td style="color:{gd_color}; font-weight:700;">{gd_str}</td>'
                        html_table += f'<td><strong style="font-size:1rem;">{pts}</strong></td>'
                        html_table += '</tr>'
                    html_table += '</tbody></table></div>'
                    st.markdown(html_table, unsafe_allow_html=True)
                else:
                    st.info("لا توجد بيانات جدول متاحة")
    except Exception as e:
        if "relation" in str(e) or "does not exist" in str(e):
            st.warning("جدول الترتيب غير موجود. يرجى تشغيل السكربت الكامل لإنشاء الجداول المطلوبة.")
        else:
            st.error(f"حدث خطأ: {e}")

# ---- TAB 5: FAVORITES ----
with tab5:
    render_section_header("⭐", "مبارياتي المفضلة")
    if st.session_state.user:
        if st.session_state.favorites:
            fav_matches = [m for m in matches if m['home_team'] in st.session_state.favorites or m['away_team'] in st.session_state.favorites]
            if fav_matches:
                for m in fav_matches:
                    st.markdown(render_match_card(m, show_favorite=False), unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    <span class="empty-state-icon">📡</span>
                    لا توجد مباريات لفرقك المفضلة حالياً
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
                <span class="empty-state-icon">☆</span>
                أضف فرقاً إلى المفضلة من خلال الضغط على ☆ في بطاقة المباراة
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon">🔐</span>
            سجل الدخول لاستخدام المفضلة
        </div>
        """, unsafe_allow_html=True)

# ---- TAB 6: PREDICTIONS ----
with tab6:
    render_section_header("🔮", "توقعات المباريات")
    upcoming_pred = supabase.table("matches").select("fixture_id, home_team, away_team, match_time").eq("status", "UPCOMING").order("match_time").limit(10).execute()
    for m in upcoming_pred.data:
        pred = supabase.table("predictions").select("*").eq("fixture_id", m["fixture_id"]).execute()
        if pred.data:
            p = pred.data[0]
            st.markdown(f"""
            <div class="prediction-card">
                <div class="prediction-teams">{m['home_team']} ⚔️ {m['away_team']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f'<div class="pred-label">فوز {m["home_team"]}</div>', unsafe_allow_html=True)
            st.progress(p["home_win_prob"])
            st.markdown('<div class="pred-label">تعادل</div>', unsafe_allow_html=True)
            st.progress(p["draw_prob"])
            st.markdown(f'<div class="pred-label">فوز {m["away_team"]}</div>', unsafe_allow_html=True)
            st.progress(p["away_win_prob"])
        else:
            st.markdown(f"""
            <div class="prediction-card">
                <div class="prediction-teams">{m['home_team']} ⚔️ {m['away_team']}</div>
                <div style="text-align:center; opacity:0.5; font-size:0.85rem;">لا توجد توقعات بعد</div>
            </div>
            """, unsafe_allow_html=True)
