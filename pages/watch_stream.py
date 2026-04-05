import streamlit as st
import re
import json
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime, timedelta
import requests
import zoneinfo
from supabase import create_client

st.set_page_config(
    page_title="Badr TV - بث مباشر",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

for k, v in {
    "extraction_attempted": False,
    "extracted_url": None,
    "extraction_failed": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────
#  THE REAL FIX FOR STREAMLIT 1.56:
#  st.markdown with <style> tags alone is unreliable — Streamlit's
#  markdown parser in v1.56 strips or text-renders <style> blocks
#  when they appear before a st.stop() rerun boundary.
#
#  The solution: inject CSS via st.markdown using a hidden <div>
#  wrapper. The HTML renderer in Streamlit will process the entire
#  <div> block as HTML, including the embedded <style> tag, because
#  it's wrapped in a valid HTML element.
# ─────────────────────────────────────────────────────────────────────

CSS = """
<div style="display:none" id="badr-css-injector">__STYLE_OPEN__
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');

/* ── HIDE STREAMLIT UI CHROME ── */
header[data-testid="stHeader"],
footer,
#MainMenu,
.stDeployButton,
div[data-testid="stToolbar"],
div[data-testid="stDecoration"] {
    display: none !important;
}

/* ── GLOBAL ── */
*, *::before, *::after {
    font-family: 'Cairo', sans-serif !important;
    box-sizing: border-box;
}

/* ── LIGHT BACKGROUND ── */
.stApp,
.stApp > div,
section[data-testid="stAppViewContainer"],
section[data-testid="stAppViewContainer"] > div {
    background: #f4f7ff !important;
}
.main, .block-container {
    background: #f4f7ff !important;
    direction: rtl;
    text-align: right;
    padding-top: 0 !important;
    padding-bottom: 5rem;
    max-width: 100% !important;
    color: #0f1829;
}

/* ── TOP NAV ── */
.top-nav {
    position: sticky;
    top: 0;
    z-index: 9999;
    background: linear-gradient(135deg, #0d47a1 0%, #1565c0 55%, #1976d2 100%);
    height: 58px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;
    border-radius: 0 0 18px 18px;
    box-shadow: 0 6px 28px rgba(13,71,161,.4);
    margin-bottom: 20px;
}
.top-nav-title {
    font-size: 1rem;
    font-weight: 900;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 9px;
    letter-spacing: .2px;
}
.live-dot {
    width: 9px; height: 9px;
    background: #ef4444;
    border-radius: 50%;
    box-shadow: 0 0 10px #ef4444;
    animation: bdot 1.2s infinite;
    display: inline-block;
    flex-shrink: 0;
}
@keyframes bdot { 0%,100%{ opacity:1; } 50%{ opacity:.2; } }

.back-link {
    background: rgba(255,255,255,.18);
    border: 1px solid rgba(255,255,255,.3);
    color: #fff;
    text-decoration: none;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: .8rem;
    font-weight: 700;
    transition: background .2s;
    white-space: nowrap;
}
.back-link:hover { background: rgba(255,255,255,.3); }

/* ── MATCH HERO ── */
.match-hero {
    background: #ffffff;
    border-radius: 22px;
    padding: 24px 18px 18px;
    margin-bottom: 20px;
    border: 1px solid #dce6f7;
    box-shadow: 0 6px 30px rgba(25,118,210,.1);
    position: relative;
    overflow: hidden;
}
.match-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, #0d47a1, #1976d2, #ef4444);
}
.match-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}
.team-block { flex: 1; text-align: center; }
.team-logo {
    width: 78px; height: 78px;
    object-fit: contain;
    filter: drop-shadow(0 4px 8px rgba(0,0,0,.12));
    margin-bottom: 8px;
    transition: transform .25s;
}
.team-logo:hover { transform: scale(1.09); }
.team-name {
    font-size: 1rem;
    font-weight: 800;
    color: #0f1829;
    word-break: break-word;
    line-height: 1.3;
}
.score-block {
    flex-shrink: 0;
    text-align: center;
    min-width: 90px;
}
.score-value {
    font-size: 2.6rem;
    font-weight: 900;
    color: #1976d2;
    letter-spacing: 3px;
    display: block;
    line-height: 1;
}
.score-value.live-score { color: #ef4444; text-shadow: 0 0 18px rgba(239,68,68,.3); }
.score-sep {
    font-size: .72rem;
    color: #8899bb;
    font-weight: 600;
    margin-top: 5px;
    display: block;
}
.match-chips {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid #e8eef8;
}
.chip {
    background: #eef2fc;
    border: 1px solid #dce6f7;
    border-radius: 20px;
    padding: 4px 13px;
    font-size: .74rem;
    font-weight: 600;
    color: #4a6090;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.chip.live {
    background: linear-gradient(135deg, #dc2626, #ef4444);
    border-color: #ef4444;
    color: #fff;
    box-shadow: 0 0 14px rgba(239,68,68,.35);
    animation: pulseLive 1.4s infinite;
}
@keyframes pulseLive {
    0%,100%{ box-shadow: 0 0 14px rgba(239,68,68,.35); }
    50%{ box-shadow: 0 0 26px rgba(239,68,68,.65); }
}

/* ── SECTION TITLE ── */
.sec-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 24px 0 14px;
    padding-bottom: 10px;
    border-bottom: 2px solid #dce6f7;
}
.sec-icon {
    width: 34px; height: 34px;
    background: linear-gradient(135deg, #1565c0, #1976d2);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(25,118,210,.25);
}
.sec-text {
    font-size: 1.1rem;
    font-weight: 800;
    color: #0f1829;
}

/* ── AD SLOT ── */
.ad-slot {
    background: #eef2fc;
    border: 1.5px dashed #b8cef0;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 14px 0;
    text-align: center;
    color: #8899bb;
    font-size: .82rem;
    min-height: 70px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

/* ── STREAM GRID ── */
.stream-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 13px;
    margin-bottom: 22px;
}
.stream-card {
    background: #ffffff;
    border: 1.5px solid #dce6f7;
    border-radius: 18px;
    padding: 20px 14px 16px;
    text-align: center;
    text-decoration: none;
    color: #0f1829;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    transition: all .22s cubic-bezier(.34,1.56,.64,1);
    cursor: pointer;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(25,118,210,.07);
}
.stream-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #1565c0, #1976d2);
    opacity: 0;
    transition: opacity .22s;
}
.stream-card:hover {
    transform: translateY(-6px) scale(1.02);
    border-color: #1976d2;
    box-shadow: 0 16px 36px rgba(25,118,210,.18);
}
.stream-card:hover::before { opacity: 1; }
.stream-icon { font-size: 2.5rem; }
.stream-title { font-weight: 700; font-size: .92rem; color: #0f1829; line-height: 1.3; }
.stream-source { font-size: .74rem; color: #6a82a8; }
.verified-badge {
    background: #10b981;
    color: #fff;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: .68rem;
    font-weight: 700;
}
.no-streams {
    background: #fff8ec;
    border: 1px solid #fde68a;
    border-right: 4px solid #f59e0b;
    border-radius: 12px;
    padding: 14px 18px;
    color: #92400e;
    font-size: .88rem;
    margin: 12px 0;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* ── VIDEO PLAYER ── */
.player-wrap {
    position: relative;
    padding-bottom: 56.25%;
    height: 0;
    overflow: hidden;
    background: #000814;
    border-radius: 20px;
    border: 1px solid #dce6f7;
    box-shadow: 0 16px 50px rgba(25,118,210,.15);
    margin: 14px 0 22px;
}
.player-wrap iframe,
.player-wrap video,
.player-wrap #hls-player {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    border: 0;
    border-radius: 20px;
}
.player-shimmer::after {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent);
    animation: pshimmer 1.6s infinite;
    z-index: 3;
}
@keyframes pshimmer { 0%{ transform:translateX(-100%); } 100%{ transform:translateX(100%); } }

.cant-embed {
    background: #fff8ec;
    border: 1px solid #fde68a;
    border-right: 4px solid #f59e0b;
    border-radius: 14px;
    padding: 16px 18px;
    color: #92400e;
    font-size: .9rem;
    margin: 10px 0;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}
.cant-embed a { color: #1565c0; font-weight: 700; text-decoration: none; }
.cant-embed a:hover { text-decoration: underline; }

/* ── NEWS MINI GRID ── */
.news-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
    margin-bottom: 22px;
}
.news-mini {
    background: #ffffff;
    border: 1px solid #dce6f7;
    border-radius: 14px;
    padding: 14px;
    transition: all .18s;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(25,118,210,.05);
}
.news-mini::before {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 3px; height: 100%;
    background: linear-gradient(180deg, #1565c0, #ef4444);
    border-radius: 0 14px 14px 0;
}
.news-mini:hover {
    border-color: #1976d2;
    box-shadow: 0 6px 20px rgba(25,118,210,.14);
    transform: translateY(-2px);
}
.news-mini a {
    font-size: .88rem;
    font-weight: 700;
    color: #0f1829;
    text-decoration: none;
    line-height: 1.55;
    display: block;
    margin-bottom: 9px;
    padding-right: 8px;
}
.news-mini a:hover { color: #1976d2; }
.news-mini-meta {
    display: flex;
    gap: 10px;
    color: #6a82a8;
    font-size: .71rem;
    flex-wrap: wrap;
    padding-right: 8px;
}

/* ── SHARE BUTTONS ── */
.share-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 22px;
}
.share-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    padding: 12px 8px;
    border-radius: 14px;
    text-decoration: none;
    font-weight: 700;
    font-size: .83rem;
    transition: all .18s;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,.1);
}
.share-btn:hover { filter: brightness(.9); transform: translateY(-2px); }
.share-wa  { background: #25D366; color: #fff; }
.share-tw  { background: #1DA1F2; color: #fff; }
.share-fb  { background: #4267B2; color: #fff; }

/* ── STREAMLIT WIDGET OVERRIDES ── */
div[data-testid="stVerticalBlock"] .stButton > button {
    background: linear-gradient(135deg, #1565c0, #1976d2) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 8px 20px !important;
    box-shadow: 0 4px 14px rgba(25,118,210,.25) !important;
}
div[data-testid="stVerticalBlock"] .stButton > button:hover {
    opacity: .9 !important;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1976d2; border-radius: 4px; }

/* ── MOBILE ── */
@media (max-width: 640px) {
    .block-container { padding-left: 10px !important; padding-right: 10px !important; }
    .top-nav { height: 52px; padding: 0 12px; border-radius: 0 0 14px 14px; }
    .top-nav-title { font-size: .84rem; }
    .team-logo { width: 56px; height: 56px; }
    .team-name { font-size: .82rem; }
    .score-value { font-size: 2rem; }
    .stream-grid { grid-template-columns: repeat(2, 1fr); gap: 9px; }
    .share-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
    .news-grid { grid-template-columns: 1fr; }
    .sec-text { font-size: .95rem; }
}
__STYLE_CLOSE__</div>
"""

# Replace placeholders with actual <style> tags
CSS = CSS.replace("__STYLE_OPEN__", "<style>").replace("__STYLE_CLOSE__", "</style>")
st.markdown(CSS, unsafe_allow_html=True)

# Also inject Font Awesome via a separate call for reliability
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">',
    unsafe_allow_html=True
)

# ═══════════════════════════════════════════════
#  QUERY PARAMS
# ═══════════════════════════════════════════════
match_id = st.query_params.get("match_id", None)
if isinstance(match_id, list):
    match_id = match_id[0]

if not match_id:
    st.markdown("""
    <div class="top-nav">
      <div class="top-nav-title"><span class="live-dot"></span> Badr TV</div>
      <a href="/" class="back-link">← الرئيسية</a>
    </div>""", unsafe_allow_html=True)
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
    st.markdown("""
    <div class="top-nav">
      <div class="top-nav-title"><span class="live-dot"></span> Badr TV</div>
      <a href="/" class="back-link">← الرئيسية</a>
    </div>""", unsafe_allow_html=True)
    st.error("❌ المباراة غير موجودة")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# ═══════════════════════════════════════════════
#  COLLECT STREAMS
# ═══════════════════════════════════════════════
all_streams = []
raw_streams = match_data.get("streams", [])
if isinstance(raw_streams, str):
    try:
        raw_streams = json.loads(raw_streams)
    except Exception:
        raw_streams = []
all_streams.extend(raw_streams)

try:
    admin_rows = supabase.table("admin_streams")\
        .select("*").eq("fixture_id", match_id).eq("is_active", True)\
        .execute().data or []
    for a in admin_rows:
        all_streams.append({
            "title":    a.get("stream_title", "بث إضافي"),
            "url":      a["stream_url"],
            "source":   a.get("stream_source", "admin"),
            "verified": True,
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
            .gte("published_at", cutoff).order("published_at", desc=True)\
            .limit(limit).execute().data or []
    except Exception:
        return []

recent_news = get_recent_news()

# ═══════════════════════════════════════════════
#  URL HELPERS
# ═══════════════════════════════════════════════
def _clean_embed(u):
    if 'youtube.com' in u or 'youtu.be' in u:
        m = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', u)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}?autoplay=1"
    return u

def _find_in_ld(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('embedUrl','contentUrl','url') and isinstance(v,str) and 'http' in v:
                return v
            r = _find_in_ld(v)
            if r: return r
    elif isinstance(obj, list):
        for i in obj:
            r = _find_in_ld(i)
            if r: return r
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def extract_embed_url(url):
    for proxy in [
        f"https://api.allorigins.win/raw?url={quote(url)}",
        f"https://thingproxy.freeboard.io/fetch/{url}",
        f"https://api.codetabs.com/v1/proxy?quest={quote(url)}",
    ]:
        try:
            r = requests.get(proxy, headers={'User-Agent':'Mozilla/5.0'}, timeout=8)
            if r.status_code == 200:
                t = r.text
                for pat in [r'<meta property="og:video"[^>]+content="([^"]+)"',
                             r'<meta property="twitter:player"[^>]+content="([^"]+)"']:
                    m = re.search(pat, t)
                    if m: return _clean_embed(m.group(1))
                for j in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.DOTALL):
                    try:
                        found = _find_in_ld(json.loads(j))
                        if found: return _clean_embed(found)
                    except Exception: pass
                m = re.search(r'<iframe[^>]+src="([^"]+)"', t)
                if m: return _clean_embed(m.group(1))
                m = re.search(r'<video[^>]+src="([^"]+)"', t)
                if m: return m.group(1)
        except Exception: pass
    return None

@st.cache_data(ttl=3600)
def detect_source(url):
    p = urlparse(url); d = p.netloc.lower(); path = p.path.lower(); q = parse_qs(p.query)
    if any(x in d for x in ["youtube.com","youtu.be"]):
        vid = path.strip('/') if "youtu.be" in d else q.get("v",[None])[0]
        if vid: return {"type":"youtube","embed_url":f"https://www.youtube.com/embed/{vid}?autoplay=1&rel=0","can_embed":True}
    elif "facebook.com" in d and ("/videos/" in url or "/watch/" in url):
        return {"type":"facebook","embed_url":f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=560","can_embed":True}
    elif "instagram.com" in d and ("/p/" in path or "/reel/" in path):
        parts = path.split('/')
        if len(parts)>=3: return {"type":"instagram","embed_url":f"https://www.instagram.com/p/{parts[2]}/embed","can_embed":True}
    elif "twitter.com" in d or "x.com" in d:
        m = re.search(r'/status/(\d+)', path)
        if m: return {"type":"twitter","embed_url":f"https://twitframe.com/show?url={quote(url)}","can_embed":True}
    elif "tiktok.com" in d:
        m = re.search(r'/video/(\d+)', path)
        if m: return {"type":"tiktok","embed_url":f"https://www.tiktok.com/embed/v2/{m.group(1)}","can_embed":True}
    elif "dailymotion.com" in d or "dai.ly" in d:
        vid = path.strip('/') if "dai.ly" in d else None
        if not vid:
            m = re.search(r'/video/([^_?]+)', url)
            vid = m.group(1) if m else None
        if vid: return {"type":"dailymotion","embed_url":f"https://www.dailymotion.com/embed/video/{vid}?autoplay=1","can_embed":True}
    elif "vimeo.com" in d:
        vid = path.strip('/').split('/')[0]
        if vid.isdigit(): return {"type":"vimeo","embed_url":f"https://player.vimeo.com/video/{vid}?autoplay=1","can_embed":True}
    elif "ok.ru" in d:
        m = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if m: return {"type":"ok","embed_url":f"https://ok.ru/videoembed/{m.group(1)}","can_embed":True}
    elif "vk.com" in d:
        m = re.search(r'video(-?\d+)_(\d+)', url)
        if m:
            oid,vid=m.groups()
            return {"type":"vk","embed_url":f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1","can_embed":True}
    elif "streamable.com" in d:
        vid = path.strip('/')
        if vid: return {"type":"streamable","embed_url":f"https://streamable.com/e/{vid}","can_embed":True}
    elif "rutube.ru" in d:
        m = re.search(r'/video/([a-zA-Z0-9]+)', url)
        if m: return {"type":"rutube","embed_url":f"https://rutube.ru/play/embed/{m.group(1)}","can_embed":True}
    if path.endswith(('.mp4','.webm','.ogg')): return {"type":"direct_video","embed_url":url,"can_embed":True}
    if path.endswith('.m3u8'): return {"type":"hls","embed_url":url,"can_embed":True}
    return {"type":"unknown","can_embed":False}

# ═══════════════════════════════════════════════
#  MATCH META
# ═══════════════════════════════════════════════
home_team = match_data['home_team']
away_team = match_data['away_team']
_fb = lambda n: f"https://ui-avatars.com/api/?name={quote(n[:2])}&background=1565c0&color=fff&size=80&bold=true"
home_logo = match_data.get('home_logo') or _fb(home_team)
away_logo = match_data.get('away_logo') or _fb(away_team)
league    = match_data.get('league', '')
status    = match_data.get('status', '')

try:
    local_time = datetime.fromisoformat(match_data["match_time"].replace('Z','+00:00')).astimezone(tz_tunis)
    time_str   = local_time.strftime('%H:%M — %d/%m/%Y')
except Exception:
    time_str = "---"

hs  = match_data.get('home_score')
aws = match_data.get('away_score')
score_display = f"{hs} - {aws}" if hs is not None else "VS"
score_label   = "نهائي" if status == "FINISHED" else ("جارية" if status == "LIVE" else "لم تبدأ")
score_class   = "score-value live-score" if status == "LIVE" else "score-value"

status_chip = (
    '<span class="chip live"><span style="width:7px;height:7px;background:#fff;border-radius:50%;'
    'display:inline-block;animation:bdot 1.2s infinite;flex-shrink:0;margin-left:3px;"></span> مباشر</span>'
    if status == "LIVE"
    else f'<span class="chip">{score_label}</span>'
)

# ═══════════════════════════════════════════════
#  RENDER: TOP NAV
# ═══════════════════════════════════════════════
st.markdown(f"""
<div class="top-nav">
  <div class="top-nav-title">
    <span class="live-dot"></span>
    {home_team[:14]} vs {away_team[:14]}
  </div>
  <a href="/" class="back-link">← الرئيسية</a>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  RENDER: MATCH HERO
# ═══════════════════════════════════════════════
st.markdown(f"""
<div class="match-hero">
  <div class="match-header">
    <div class="team-block">
      <img src="{home_logo}" class="team-logo">
      <div class="team-name">{home_team}</div>
    </div>
    <div class="score-block">
      <span class="{score_class}">{score_display}</span>
      <span class="score-sep">{score_label}</span>
    </div>
    <div class="team-block">
      <img src="{away_logo}" class="team-logo">
      <div class="team-name">{away_team}</div>
    </div>
  </div>
  <div class="match-chips">
    <span class="chip">🏆 {league}</span>
    <span class="chip">🕐 {time_str}</span>
    {status_chip}
  </div>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  AD SLOT
# ═══════════════════════════════════════════════
st.markdown('<div class="ad-slot">📢 مساحة إعلانية</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  STREAM LIST
# ═══════════════════════════════════════════════
st.markdown("""
<div class="sec-title">
  <div class="sec-icon">📺</div>
  <span class="sec-text">قائمة البث المتاحة</span>
</div>""", unsafe_allow_html=True)

if not all_streams:
    st.markdown('<div class="no-streams">⚠️ لا توجد روابط بث متاحة حالياً. تحقق لاحقاً.</div>', unsafe_allow_html=True)
else:
    _icons = {
        "youtube":  ('<i class="fab fa-youtube" style="color:#FF0000;font-size:2.4rem;"></i>', "يوتيوب"),
        "facebook": ('<i class="fab fa-facebook" style="color:#4267B2;font-size:2.4rem;"></i>', "فيسبوك"),
        "twitch":   ('<i class="fab fa-twitch" style="color:#9146FF;font-size:2.4rem;"></i>', "تويتش"),
        "admin":    ('<i class="fas fa-satellite-dish" style="color:#1976d2;font-size:2.4rem;"></i>', "بث مباشر"),
        "official": ('<i class="fas fa-shield-alt" style="color:#10b981;font-size:2.4rem;"></i>', "رسمي"),
    }
    html_cards = '<div class="stream-grid">'
    for s in all_streams:
        src = s.get("source","").lower()
        icon, lbl = next(((v for k,v in _icons.items() if k in src)),
                         ('<i class="fas fa-play-circle" style="color:#1976d2;font-size:2.4rem;"></i>', "بث"))
        verified  = '<span class="verified-badge">✓ رسمي</span>' if s.get("verified") else ''
        link      = f"/watch_stream?match_id={match_id}&stream_url={quote(s['url'], safe='')}"
        title     = s.get("title","بث مباشر")[:28]
        html_cards += f"""
        <a href="{link}" class="stream-card">
          {icon}
          <span class="stream-title">{title}</span>
          <span class="stream-source">{lbl}</span>
          {verified}
        </a>"""
    html_cards += '</div>'
    st.markdown(html_cards, unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  EMBEDDED PLAYER
# ═══════════════════════════════════════════════
selected_url = st.query_params.get("stream_url", None)
if isinstance(selected_url, list):
    selected_url = selected_url[0]

if selected_url:
    selected_url = unquote(selected_url)
    st.markdown("""
    <div class="sec-title">
      <div class="sec-icon">▶️</div>
      <span class="sec-text">البث المحدد</span>
    </div>""", unsafe_allow_html=True)

    source = detect_source(selected_url)

    if not source["can_embed"] and not st.session_state.extraction_attempted:
        st.session_state.extraction_attempted = True
        with st.spinner("🔄 جاري تجهيز البث..."):
            extracted = extract_embed_url(selected_url)
            st.session_state.extracted_url     = extracted
            st.session_state.extraction_failed = extracted is None
        st.rerun()

    embed_url = st.session_state.extracted_url or (source.get("embed_url") if source["can_embed"] else None)
    can_embed  = bool(embed_url)

    if can_embed:
        stype = source.get("type","")
        if stype == "hls" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="player-wrap player-shimmer">
              <div id="hls-player"></div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <script>
            (function(){{
              var el=document.getElementById('hls-player');
              var v=document.createElement('video');
              v.controls=true; v.autoplay=true;
              v.style.cssText='width:100%;height:100%;border-radius:20px;';
              el.appendChild(v);
              if(Hls.isSupported()){{
                var h=new Hls(); h.loadSource('{embed_url}'); h.attachMedia(v);
                h.on(Hls.Events.MANIFEST_PARSED,function(){{v.play();}});
              }} else if(v.canPlayType('application/vnd.apple.mpegurl')){{
                v.src='{embed_url}'; v.play();
              }}
            }})();
            </script>""", unsafe_allow_html=True)
        elif stype == "direct_video" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="player-wrap player-shimmer">
              <video controls autoplay playsinline style="border-radius:20px;">
                <source src="{embed_url}" type="video/mp4">
              </video>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="player-wrap player-shimmer">
              <iframe src="{embed_url}"
                allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
                allowfullscreen>
              </iframe>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="cant-embed">
          ⚠️ لا يمكن عرض البث مباشرةً.
          <a href="{selected_url}" target="_blank">فتح البث في نافذة جديدة ↗</a>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="ad-slot">📢 مساحة إعلانية</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  RECENT NEWS
# ═══════════════════════════════════════════════
if recent_news:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-icon">📰</div>
      <span class="sec-text">آخر الأخبار</span>
    </div>""", unsafe_allow_html=True)

    html_news = '<div class="news-grid">'
    for item in recent_news:
        title = item.get('title','')
        src   = item.get('source','')
        nurl  = item.get('url','#')
        try:
            dt = datetime.fromisoformat(item["published_at"].replace('Z','+00:00')).astimezone(tz_tunis)
            ds = dt.strftime("%H:%M — %d/%m")
        except Exception:
            ds = ""
        html_news += f"""
        <div class="news-mini">
          <a href="{nurl}" target="_blank">{title}</a>
          <div class="news-mini-meta">
            <span>📰 {src}</span>
            <span>🕒 {ds}</span>
          </div>
        </div>"""
    html_news += '</div>'
    st.markdown(html_news, unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  SHARE
# ═══════════════════════════════════════════════
st.markdown("""
<div class="sec-title">
  <div class="sec-icon">📤</div>
  <span class="sec-text">شارك هذه المباراة</span>
</div>""", unsafe_allow_html=True)

try:
    host     = st.context.headers.get('host','')
    protocol = 'https' if st.context.headers.get('x-forwarded-proto','http')=='https' else 'http'
    base_url = f"{protocol}://{host}"
except Exception:
    base_url = ""

page_url   = f"{base_url}/watch_stream?match_id={match_id}"
share_text = f"شاهد {home_team} vs {away_team} بث مباشر على Badr TV"

st.markdown(f"""
<div class="share-grid">
  <a href="https://wa.me/?text={quote(share_text+' '+page_url)}" target="_blank" class="share-btn share-wa">
    <i class="fab fa-whatsapp"></i> واتساب
  </a>
  <a href="https://twitter.com/intent/tweet?text={quote(share_text+' '+page_url)}" target="_blank" class="share-btn share-tw">
    <i class="fab fa-twitter"></i> تويتر
  </a>
  <a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}" target="_blank" class="share-btn share-fb">
    <i class="fab fa-facebook-f"></i> فيسبوك
  </a>
</div>""", unsafe_allow_html=True)

if st.button("📱 عرض رمز QR", key="qr_btn"):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(page_url)}&bgcolor=ffffff&color=0d47a1"
    st.image(qr_url, width=180)

# ═══════════════════════════════════════════════
#  FOOTER AD
# ═══════════════════════════════════════════════
st.markdown("---")
st.markdown('<div class="ad-slot">📢 مساحة إعلانية</div>', unsafe_allow_html=True)
