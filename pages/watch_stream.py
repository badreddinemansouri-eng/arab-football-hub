import streamlit as st
import time
import re
import json
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime, timedelta
import requests
import zoneinfo
from supabase import create_client

# ═══════════════════════════════════════════════
#  PAGE CONFIG — must be first
# ═══════════════════════════════════════════════
st.set_page_config(
    page_title="Badr TV - مشاهدة البث المباشر",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════
#  SUPABASE
# ═══════════════════════════════════════════════
SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ═══════════════════════════════════════════════
#  TIMEZONE
# ═══════════════════════════════════════════════
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

# ═══════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════
_ss_defaults = {
    "extraction_attempted": False,
    "extracted_url":        None,
    "extraction_failed":    False,
    "theme":                "dark",
}
for k, v in _ss_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════
#  CSS — dark/light theme, matching app.py
# ═══════════════════════════════════════════════
is_dark = st.session_state.theme == "dark"

if is_dark:
    bg_primary    = "#0a0e1a"
    bg_secondary  = "#111827"
    bg_card       = "#1a2035"
    text_primary  = "#f0f4ff"
    text_secondary= "#8899bb"
    border_color  = "#1e2d50"
else:
    bg_primary    = "#f0f4ff"
    bg_secondary  = "#e4eaf8"
    bg_card       = "#ffffff"
    text_primary  = "#0a0e1a"
    text_secondary= "#5a6a8a"
    border_color  = "#d0daf0"

st.markdown(f"""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;900&display=swap');
*, *::before, *::after {{ font-family: 'Cairo', sans-serif !important; box-sizing: border-box; }}

header[data-testid="stHeader"], footer, #MainMenu, .stDeployButton {{ display: none !important; }}

.stApp {{ background: {bg_primary} !important; }}
.main, .block-container {{
    background: {bg_primary} !important;
    direction: rtl; text-align: right;
    padding-top: 0 !important;
    padding-bottom: 3rem;
    max-width: 100% !important;
    color: {text_primary};
}}

/* ── PAGE HEADER ── */
.page-header {{
    background: linear-gradient(135deg, #0d47a1 0%, #1565c0 50%, #1976d2 100%);
    padding: 0 20px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    border-radius: 0 0 18px 18px;
    box-shadow: 0 4px 20px rgba(13,71,161,.4);
    position: sticky; top: 0; z-index: 100;
}}
.page-header-title {{
    font-size: 1.1rem; font-weight: 900; color: white;
    display: flex; align-items: center; gap: 8px;
}}
.back-link {{
    background: rgba(255,255,255,.15);
    border: 1px solid rgba(255,255,255,.25);
    color: white; text-decoration: none;
    padding: 5px 14px; border-radius: 20px;
    font-size: .8rem; font-weight: 600;
    transition: background .2s;
}}
.back-link:hover {{ background: rgba(255,255,255,.25); color: white; }}

/* ── MATCH CARD ── */
.match-hero {{
    background: {bg_card};
    border-radius: 20px;
    padding: 24px 20px 18px;
    margin-bottom: 20px;
    border: 1px solid {border_color};
    box-shadow: 0 4px 20px rgba(0,0,0,.12);
}}
.match-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}}
.team-block {{
    flex: 1;
    text-align: center;
}}
.team-logo {{
    width: 80px; height: 80px;
    object-fit: contain; margin-bottom: 8px;
    filter: drop-shadow(0 4px 8px rgba(0,0,0,.2));
}}
.team-name {{
    font-size: 1.1rem; font-weight: 800; color: {text_primary};
    word-break: break-word;
}}
.vs-divider {{
    font-size: 2.4rem; font-weight: 900; color: #ef4444;
    padding: 0 8px; text-align: center; min-width: 80px;
    text-shadow: 0 2px 8px rgba(239,68,68,.3);
}}
.match-meta {{
    text-align: center; margin-top: 14px;
    color: {text_secondary}; font-size: .9rem;
    display: flex; align-items: center; justify-content: center;
    gap: 12px; flex-wrap: wrap;
}}
.match-meta-chip {{
    background: {bg_secondary}; border: 1px solid {border_color};
    border-radius: 20px; padding: 3px 12px;
    font-size: .78rem; font-weight: 600; color: {text_secondary};
}}
.live-indicator {{
    background: linear-gradient(135deg,#dc2626,#ef4444);
    color: white; border-radius: 20px; padding: 3px 12px;
    font-size: .78rem; font-weight: 700;
    animation: pulseLive 1.5s infinite;
    box-shadow: 0 0 10px rgba(220,38,38,.4);
}}
@keyframes pulseLive {{ 0%,100%{{ opacity:1; }} 50%{{ opacity:.7; }} }}

/* ── SECTION TITLE ── */
.section-title {{
    font-size: 1.2rem; font-weight: 800; color: {text_primary};
    margin: 22px 0 14px;
    display: flex; align-items: center; gap: 10px;
    padding-bottom: 10px;
    border-bottom: 2px solid {border_color};
}}
.section-title-icon {{
    width: 32px; height: 32px;
    background: linear-gradient(135deg,#1565c0,#1976d2);
    border-radius: 9px; display: flex; align-items: center; justify-content: center;
    font-size: .95rem; flex-shrink: 0;
    box-shadow: 0 4px 10px rgba(25,118,210,.3);
}}

/* ── STREAM GRID ── */
.stream-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px; margin-bottom: 24px;
}}
.stream-card {{
    background: {bg_card};
    border: 1.5px solid {border_color};
    border-radius: 18px; padding: 18px 14px;
    text-align: center; text-decoration: none;
    color: {text_primary};
    transition: all .2s ease;
    box-shadow: 0 3px 12px rgba(0,0,0,.08);
    display: flex; flex-direction: column;
    align-items: center; gap: 8px;
    cursor: pointer;
}}
.stream-card:hover {{
    transform: translateY(-5px);
    border-color: #ef4444;
    box-shadow: 0 12px 28px rgba(239,68,68,.2);
}}
.stream-icon {{ font-size: 2.4rem; color: #ef4444; }}
.stream-title {{ font-weight: 700; font-size: 1rem; color: {text_primary}; }}
.stream-source {{ font-size: .8rem; color: {text_secondary}; }}
.verified-badge {{
    background: #10b981; color: white;
    padding: 2px 10px; border-radius: 20px;
    font-size: .7rem; font-weight: 700;
}}

/* ── VIDEO PLAYER ── */
.video-container {{
    position: relative; padding-bottom: 56.25%; height: 0;
    overflow: hidden;
    background: #080c18;
    border-radius: 20px;
    box-shadow: 0 20px 50px rgba(0,0,0,.4);
    margin: 16px 0 24px;
    border: 1px solid {border_color};
}}
.video-container iframe,
.video-container video,
.video-container .hls-player {{
    position: absolute; top: 0; left: 0;
    width: 100%; height: 100%; border: 0; border-radius: 20px;
}}
.video-container.loading::after {{
    content: "";
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.06), transparent);
    animation: shimmer 1.5s infinite; z-index: 2;
}}
@keyframes shimmer {{ 0%{{ transform: translateX(-100%); }} 100%{{ transform: translateX(100%); }} }}

/* ── NEWS MINI GRID ── */
.news-mini-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 14px; margin-bottom: 24px;
}}
.news-mini-card {{
    background: {bg_card};
    border: 1px solid {border_color};
    border-radius: 16px; padding: 14px;
    transition: all .18s;
}}
.news-mini-card:hover {{
    border-color: #1976d2;
    box-shadow: 0 6px 20px rgba(25,118,210,.15);
    transform: translateY(-2px);
}}
.news-mini-title a {{
    font-size: .9rem; font-weight: 700;
    color: {text_primary}; text-decoration: none;
    line-height: 1.5; display: block; margin-bottom: 8px;
}}
.news-mini-title a:hover {{ color: #1976d2; }}
.news-mini-meta {{
    display: flex; gap: 10px;
    color: {text_secondary}; font-size: .75rem;
}}

/* ── SHARE BUTTONS ── */
.btn {{
    display: inline-flex; align-items: center; gap: 6px;
    border-radius: 50px; padding: 8px 18px;
    text-decoration: none; font-weight: 600; font-size: .85rem;
    transition: all .18s; border: 1.5px solid transparent;
    justify-content: center; width: 100%;
}}
.btn:hover {{ filter: brightness(.9); transform: translateY(-2px); }}
.btn-primary {{ background: #ef4444; color: white; }}
.btn-wa  {{ background: #25D366; color: white; }}
.btn-tw  {{ background: #1DA1F2; color: white; }}
.btn-fb  {{ background: #4267B2; color: white; }}

/* ── AD CONTAINER ── */
.ad-slot {{
    background: {bg_secondary};
    border: 1.5px dashed {border_color};
    border-radius: 16px; padding: 16px;
    margin: 16px 0; text-align: center;
    color: {text_secondary}; font-size: .85rem;
    min-height: 80px; display: flex;
    align-items: center; justify-content: center;
}}

/* ── ALERT / WARNING ── */
.stream-warning {{
    background: {bg_secondary};
    border: 1px solid {border_color};
    border-right: 4px solid #f59e0b;
    border-radius: 12px; padding: 12px 16px;
    color: {text_primary}; font-size: .88rem; margin: 12px 0;
}}

::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: #1976d2; border-radius: 4px; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 10px !important; padding-right: 10px !important; }}
    .team-logo {{ width: 60px; height: 60px; }}
    .team-name {{ font-size: .9rem; }}
    .vs-divider {{ font-size: 1.8rem; min-width: 60px; }}
    .stream-grid {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
}}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  QUERY PARAMS
# ═══════════════════════════════════════════════
match_id = st.query_params.get("match_id", None)
if isinstance(match_id, list):
    match_id = match_id[0]

if not match_id:
    st.markdown('<div class="page-header"><div class="page-header-title">⚽ Badr TV</div><a href="/" class="back-link">← الرئيسية</a></div>', unsafe_allow_html=True)
    st.error("❌ لم يتم تحديد المباراة")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# ═══════════════════════════════════════════════
#  FETCH MATCH
# ═══════════════════════════════════════════════
match_data = None
try:
    res = supabase.table("matches").select("*").eq("fixture_id", match_id).execute()
    if res.data:
        match_data = res.data[0]
except Exception:
    pass

if not match_data:
    st.markdown('<div class="page-header"><div class="page-header-title">⚽ Badr TV</div><a href="/" class="back-link">← الرئيسية</a></div>', unsafe_allow_html=True)
    st.error("❌ المباراة غير موجودة")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# ═══════════════════════════════════════════════
#  COLLECT STREAMS
# ═══════════════════════════════════════════════
all_streams = []
match_streams = match_data.get("streams", [])
if isinstance(match_streams, str):
    try:
        match_streams = json.loads(match_streams)
    except Exception:
        match_streams = []
all_streams.extend(match_streams)

try:
    admin_streams = supabase.table("admin_streams")\
        .select("*").eq("fixture_id", match_id).eq("is_active", True)\
        .execute().data or []
    for a in admin_streams:
        all_streams.append({
            "title":       a.get("stream_title", "بث إضافي"),
            "url":         a["stream_url"],
            "source":      a.get("stream_source", "admin"),
            "verified":    True,
            "admin_added": True,
        })
except Exception:
    pass

# ═══════════════════════════════════════════════
#  RECENT NEWS
# ═══════════════════════════════════════════════
@st.cache_data(ttl=3600)
def get_recent_news(limit=4):
    try:
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        return supabase.table("news").select("*")\
            .gte("published_at", cutoff)\
            .order("published_at", desc=True)\
            .limit(limit).execute().data or []
    except Exception:
        return []

recent_news = get_recent_news(4)

# ═══════════════════════════════════════════════
#  EMBED URL HELPERS
# ═══════════════════════════════════════════════
def _clean_embed_url(video_url):
    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        yt_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', video_url)
        if yt_match:
            return f"https://www.youtube.com/embed/{yt_match.group(1)}?autoplay=1"
    return video_url

def _extract_from_json_ld(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('embedUrl', 'contentUrl', 'url') and isinstance(v, str) and 'http' in v:
                return v
            if isinstance(v, (dict, list)):
                result = _extract_from_json_ld(v)
                if result:
                    return result
    elif isinstance(obj, list):
        for item in obj:
            result = _extract_from_json_ld(item)
            if result:
                return result
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def extract_embed_url(url):
    proxies = [
        f"https://api.allorigins.win/raw?url={quote(url)}",
        f"https://thingproxy.freeboard.io/fetch/{url}",
        f"https://api.codetabs.com/v1/proxy?quest={quote(url)}",
        f"https://proxy.cors.sh/{url}",
    ]
    headers_list = [
        {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'},
    ]
    for proxy in proxies:
        for headers in headers_list:
            try:
                resp = requests.get(proxy, headers=headers, timeout=8)
                if resp.status_code == 200:
                    html_text = resp.text
                    og_video = re.search(r'<meta property="og:video"[^>]+content="([^"]+)"', html_text)
                    if og_video:
                        return _clean_embed_url(og_video.group(1))
                    twitter_player = re.search(r'<meta property="twitter:player"[^>]+content="([^"]+)"', html_text)
                    if twitter_player:
                        return _clean_embed_url(twitter_player.group(1))
                    json_lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_text, re.DOTALL)
                    for j in json_lds:
                        try:
                            video_url = _extract_from_json_ld(json.loads(j))
                            if video_url:
                                return _clean_embed_url(video_url)
                        except Exception:
                            pass
                    iframe_src = re.search(r'<iframe[^>]+src="([^"]+)"', html_text)
                    if iframe_src:
                        return _clean_embed_url(iframe_src.group(1))
                    video_src = re.search(r'<video[^>]+src="([^"]+)"', html_text)
                    if video_src:
                        return video_src.group(1)
            except Exception:
                continue
    return None

@st.cache_data(ttl=3600)
def detect_source(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path   = parsed.path.lower()
    query  = parse_qs(parsed.query)

    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        video_id = path.strip('/') if "youtu.be" in domain else query.get("v", [None])[0]
        if video_id:
            return {"type": "youtube", "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0", "can_embed": True, "name": "يوتيوب"}
    elif "facebook.com" in domain and ("/videos/" in url or "/watch/" in url or "/reel/" in url):
        return {"type": "facebook", "embed_url": f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=560", "can_embed": True, "name": "فيسبوك"}
    elif "instagram.com" in domain and ("/p/" in path or "/reel/" in path):
        parts = path.split('/')
        if len(parts) >= 3:
            return {"type": "instagram", "embed_url": f"https://www.instagram.com/p/{parts[2]}/embed", "can_embed": True, "name": "انستغرام"}
    elif "twitter.com" in domain or "x.com" in domain:
        m = re.search(r'/status/(\d+)', path)
        if m:
            return {"type": "twitter", "embed_url": f"https://twitframe.com/show?url={quote(url)}", "can_embed": True, "name": "تويتر"}
    elif "tiktok.com" in domain:
        m = re.search(r'/video/(\d+)', path)
        if m:
            return {"type": "tiktok", "embed_url": f"https://www.tiktok.com/embed/v2/{m.group(1)}", "can_embed": True, "name": "تيك توك"}
    elif "dailymotion.com" in domain or "dai.ly" in domain:
        video_id = path.strip('/') if "dai.ly" in domain else (re.search(r'/video/([^_?]+)', url) or type('', (), {'group': lambda s, x: None})()).group(1)
        if video_id:
            return {"type": "dailymotion", "embed_url": f"https://www.dailymotion.com/embed/video/{video_id}?autoplay=1", "can_embed": True, "name": "ديلي موشن"}
    elif "vimeo.com" in domain:
        video_id = path.strip('/').split('/')[0]
        if video_id.isdigit():
            return {"type": "vimeo", "embed_url": f"https://player.vimeo.com/video/{video_id}?autoplay=1", "can_embed": True, "name": "فيميو"}
    elif "ok.ru" in domain or "odnoklassniki.ru" in domain:
        m = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if m:
            return {"type": "ok", "embed_url": f"https://ok.ru/videoembed/{m.group(1)}", "can_embed": True, "name": "OK.ru"}
    elif "vk.com" in domain or "vkvideo.ru" in domain:
        m = re.search(r'video(-?\d+)_(\d+)', url)
        if m:
            oid, vid = m.groups()
            return {"type": "vk", "embed_url": f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1", "can_embed": True, "name": "VK"}
    elif "streamable.com" in domain:
        video_id = path.strip('/')
        if video_id:
            return {"type": "streamable", "embed_url": f"https://streamable.com/e/{video_id}", "can_embed": True, "name": "Streamable"}
    elif "rutube.ru" in domain:
        m = re.search(r'/video/([a-zA-Z0-9]+)', url)
        if m:
            return {"type": "rutube", "embed_url": f"https://rutube.ru/play/embed/{m.group(1)}", "can_embed": True, "name": "Rutube"}

    if path.endswith(('.mp4', '.webm', '.ogg', '.mkv')):
        return {"type": "direct_video", "embed_url": url, "can_embed": True, "name": "فيديو مباشر"}
    if path.endswith('.m3u8'):
        return {"type": "hls", "embed_url": url, "can_embed": True, "name": "بث HLS"}

    return {"type": "unknown", "can_embed": False, "name": "رابط خارجي"}

# ═══════════════════════════════════════════════
#  BUILD MATCH DATA
# ═══════════════════════════════════════════════
home_team  = match_data['home_team']
away_team  = match_data['away_team']
home_logo  = match_data.get('home_logo')  or f"https://ui-avatars.com/api/?name={quote(home_team[:2])}&background=0d47a1&color=fff&size=80&bold=true"
away_logo  = match_data.get('away_logo')  or f"https://ui-avatars.com/api/?name={quote(away_team[:2])}&background=0d47a1&color=fff&size=80&bold=true"
league     = match_data.get('league', '')
status     = match_data.get('status', '')

try:
    utc_time   = datetime.fromisoformat(match_data["match_time"].replace('Z', '+00:00'))
    local_time = utc_time.astimezone(tz_tunis)
    time_str   = local_time.strftime('%H:%M — %Y/%m/%d')
except Exception:
    time_str = "الوقت غير معروف"

if match_data.get('home_score') is not None and match_data.get('away_score') is not None:
    score_display = f"{match_data['home_score']} - {match_data['away_score']}"
else:
    score_display = "VS"

status_chip = (
    '<span class="live-indicator">🔴 مباشر</span>'
    if status == "LIVE"
    else f'<span class="match-meta-chip">{status}</span>'
)

# ═══════════════════════════════════════════════
#  PAGE HEADER
# ═══════════════════════════════════════════════
st.markdown(f"""
<div class="page-header">
    <div class="page-header-title">⚽ {home_team} vs {away_team}</div>
    <a href="/" class="back-link">← الرئيسية</a>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  MATCH HERO CARD
# ═══════════════════════════════════════════════
st.markdown(f"""
<div class="match-hero">
    <div class="match-header">
        <div class="team-block">
            <img src="{home_logo}" class="team-logo">
            <div class="team-name">{home_team}</div>
        </div>
        <div class="vs-divider">{score_display}</div>
        <div class="team-block">
            <img src="{away_logo}" class="team-logo">
            <div class="team-name">{away_team}</div>
        </div>
    </div>
    <div class="match-meta">
        <span class="match-meta-chip">🏆 {league}</span>
        <span class="match-meta-chip">🕐 {time_str}</span>
        {status_chip}
    </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  AD SLOT (top)
#  FIX: st.components.v1.html is deprecated — replaced with st.markdown
# ═══════════════════════════════════════════════
st.markdown("""
<div class="ad-slot">
    <span style="font-size:1.2rem; margin-left:8px;">📢</span> مساحة إعلانية
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  STREAMS LIST
# ═══════════════════════════════════════════════
st.markdown("""
<div class="section-title">
    <div class="section-title-icon">📺</div>
    قائمة البث المتاحة
</div>
""", unsafe_allow_html=True)

if not all_streams:
    st.markdown('<div class="stream-warning">⚠️ لا توجد روابط بث متاحة لهذه المباراة حالياً. تحقق لاحقاً.</div>', unsafe_allow_html=True)
else:
    cards_html = '<div class="stream-grid">'
    for stream in all_streams:
        src = stream.get("source", "custom").lower()
        if "youtube" in src:
            icon = '<i class="fab fa-youtube" style="color:#ef4444;font-size:2.4rem;"></i>'
        elif "facebook" in src:
            icon = '<i class="fab fa-facebook" style="color:#4267B2;font-size:2.4rem;"></i>'
        elif "twitch" in src:
            icon = '<i class="fab fa-twitch" style="color:#9146FF;font-size:2.4rem;"></i>'
        elif "admin" in src:
            icon = '<i class="fas fa-satellite-dish" style="color:#ef4444;font-size:2.4rem;"></i>'
        else:
            icon = '<i class="fas fa-play-circle" style="color:#1976d2;font-size:2.4rem;"></i>'

        verified_html = '<span class="verified-badge">✓ رسمي</span>' if stream.get("verified") else ''
        stream_url_enc = quote(stream['url'], safe='')
        btn_link = f"/watch_stream?match_id={match_id}&stream_url={stream_url_enc}"

        cards_html += f"""
        <a href="{btn_link}" class="stream-card">
            {icon}
            <span class="stream-title">{stream.get('title', 'بث مباشر')[:30]}</span>
            <span class="stream-source">{stream.get('source', 'مصدر')}</span>
            {verified_html}
        </a>"""
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  EMBEDDED PLAYER
# ═══════════════════════════════════════════════
selected_stream_url = st.query_params.get("stream_url", None)
if isinstance(selected_stream_url, list):
    selected_stream_url = selected_stream_url[0]

if selected_stream_url:
    selected_stream_url = unquote(selected_stream_url)

    st.markdown("""
    <div class="section-title">
        <div class="section-title-icon">▶️</div>
        البث المحدد
    </div>
    """, unsafe_allow_html=True)

    source_info = detect_source(selected_stream_url)

    # Auto-extraction for unknown sources
    if not source_info["can_embed"] and not st.session_state.extraction_attempted:
        st.session_state.extraction_attempted = True
        with st.spinner("🔄 جاري تجهيز البث..."):
            extracted = extract_embed_url(selected_stream_url)
            if extracted:
                st.session_state.extracted_url = extracted
                st.session_state.extraction_failed = False
            else:
                st.session_state.extraction_failed = True
        st.rerun()

    if st.session_state.extracted_url:
        embed_url = st.session_state.extracted_url
        can_embed = True
    else:
        embed_url = source_info.get("embed_url") if source_info["can_embed"] else None
        can_embed  = source_info["can_embed"]

    if can_embed and embed_url:
        if source_info.get("type") == "hls" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="video-container loading">
                <div class="hls-player" id="hls-player"></div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <script>
              (function() {{
                var container = document.getElementById('hls-player');
                var video = document.createElement('video');
                video.controls = true; video.autoplay = true;
                video.style.width = '100%'; video.style.height = '100%';
                container.appendChild(video);
                if (Hls.isSupported()) {{
                  var hls = new Hls();
                  hls.loadSource('{embed_url}');
                  hls.attachMedia(video);
                  hls.on(Hls.Events.MANIFEST_PARSED, function() {{ video.play(); }});
                }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                  video.src = '{embed_url}';
                  video.play();
                }}
              }})();
            </script>
            """, unsafe_allow_html=True)
        elif source_info.get("type") == "direct_video" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="video-container loading">
                <video controls autoplay playsinline>
                    <source src="{embed_url}" type="video/mp4">
                </video>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="video-container loading">
                <iframe src="{embed_url}"
                        allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
                        allowfullscreen>
                </iframe>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="stream-warning">
            ⚠️ لا يمكن عرض البث داخل الصفحة مباشرةً.
            <a href="{selected_stream_url}" target="_blank" style="color:#1976d2; font-weight:700; margin-right:8px;">
                فتح البث في نافذة جديدة ↗
            </a>
        </div>
        """, unsafe_allow_html=True)

    # Mid-video ad slot — FIX: no st.components.v1.html
    st.markdown("""
    <div class="ad-slot" style="margin-top:8px;">
        <span style="font-size:1.2rem; margin-left:8px;">📢</span> مساحة إعلانية
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  RECENT NEWS
# ═══════════════════════════════════════════════
if recent_news:
    st.markdown("""
    <div class="section-title">
        <div class="section-title-icon">📰</div>
        آخر الأخبار
    </div>
    """, unsafe_allow_html=True)

    news_html = '<div class="news-mini-grid">'
    for item in recent_news:
        title    = item.get('title', '')
        source   = item.get('source', 'مصدر')
        news_url = item.get('url', '#')
        published= item.get('published_at', '')
        try:
            pub_dt   = datetime.fromisoformat(published.replace('Z', '+00:00')).astimezone(tz_tunis)
            date_str = pub_dt.strftime("%H:%M %Y/%m/%d")
        except Exception:
            date_str = ""
        news_html += f"""
        <div class="news-mini-card">
            <div class="news-mini-title">
                <a href="{news_url}" target="_blank">{title}</a>
            </div>
            <div class="news-mini-meta">
                <span>📰 {source}</span>
                <span>🕒 {date_str}</span>
            </div>
        </div>"""
    news_html += '</div>'
    st.markdown(news_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  SHARE BUTTONS
# ═══════════════════════════════════════════════
st.markdown("""
<div class="section-title">
    <div class="section-title-icon">📤</div>
    شارك هذه المباراة
</div>
""", unsafe_allow_html=True)

try:
    host     = st.context.headers.get('host', '')
    protocol = 'https' if st.context.headers.get('x-forwarded-proto', 'http') == 'https' else 'http'
    base_url = f"{protocol}://{host}"
except Exception:
    base_url = ""

page_url   = f"{base_url}/watch_stream?match_id={match_id}"
share_text = f"شاهد {home_team} vs {away_team} بث مباشر على Badr TV"

cols = st.columns(4)
with cols[0]:
    st.markdown(f'<a href="https://wa.me/?text={quote(share_text+" "+page_url)}" target="_blank" class="btn btn-wa"><i class="fab fa-whatsapp"></i> واتساب</a>', unsafe_allow_html=True)
with cols[1]:
    st.markdown(f'<a href="https://twitter.com/intent/tweet?text={quote(share_text+" "+page_url)}" target="_blank" class="btn btn-tw"><i class="fab fa-twitter"></i> تويتر</a>', unsafe_allow_html=True)
with cols[2]:
    st.markdown(f'<a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}" target="_blank" class="btn btn-fb"><i class="fab fa-facebook-f"></i> فيسبوك</a>', unsafe_allow_html=True)
with cols[3]:
    if st.button("📱 رمز QR", key="qr_btn"):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={quote(page_url)}"
        st.image(qr_url, width=150)

# ═══════════════════════════════════════════════
#  FOOTER AD — FIX: no st.components.v1.html
# ═══════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div class="ad-slot">
    <span style="font-size:1.2rem; margin-left:8px;">📢</span> مساحة إعلانية
</div>
""", unsafe_allow_html=True)
