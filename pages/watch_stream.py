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
    "active_stream_idx": 0,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════
#  CSS — injected via hidden div wrapper (Streamlit 1.56 safe method)
# ═══════════════════════════════════════════════════════════════════════
CSS = """
<div style="display:none" id="badr-styles">__STYLE__
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&display=swap');

/* ── RESET & CHROME HIDE ── */
header[data-testid="stHeader"],footer,#MainMenu,.stDeployButton,
div[data-testid="stToolbar"],div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] { display:none !important; }
*,*::before,*::after { font-family:'Cairo',sans-serif !important; box-sizing:border-box; }

/* ── PAGE BASE ── */
.stApp,
section[data-testid="stAppViewContainer"],
section[data-testid="stAppViewContainer"] > div { background:#f0f4ff !important; }
.main,.block-container {
    background:#f0f4ff !important;
    direction:rtl; text-align:right;
    padding-top:0 !important; padding-bottom:6rem;
    max-width:100% !important; color:#0d1829;
}

/* ══════════════════════════════════════════
   TOP NAV BAR
══════════════════════════════════════════ */
.bnav {
    position:sticky; top:0; z-index:9999;
    background:linear-gradient(135deg,#0a2d7a 0%,#1148b8 50%,#1976d2 100%);
    height:62px;
    display:flex; align-items:center; justify-content:space-between;
    padding:0 22px;
    border-radius:0 0 20px 20px;
    box-shadow:0 8px 32px rgba(10,45,122,.35);
    margin-bottom:0;
}
.bnav-brand { display:flex; align-items:center; gap:10px; }
.bnav-brand img { width:36px; height:36px; border-radius:50%; border:2px solid rgba(255,255,255,.3); object-fit:cover; }
.bnav-brand-name { font-size:.95rem; font-weight:900; color:#fff; letter-spacing:.3px; }
.bnav-brand-sub { font-size:.62rem; color:rgba(255,255,255,.55); display:block; margin-top:-3px; }
.bnav-right { display:flex; align-items:center; gap:10px; }
.live-pill {
    background:linear-gradient(135deg,#dc2626,#ef4444);
    color:#fff; border-radius:20px; padding:4px 12px;
    font-size:.72rem; font-weight:800; letter-spacing:.8px;
    display:flex; align-items:center; gap:5px;
    box-shadow:0 0 14px rgba(239,68,68,.5);
    animation:liveglow 1.5s infinite;
}
@keyframes liveglow{0%,100%{box-shadow:0 0 14px rgba(239,68,68,.5);}50%{box-shadow:0 0 26px rgba(239,68,68,.85);}}
.live-pill-dot { width:7px;height:7px;background:#fff;border-radius:50%;animation:blink 1s infinite; }
@keyframes blink{0%,100%{opacity:1;}50%{opacity:.1;}}
.back-btn {
    background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25);
    color:#fff; text-decoration:none; padding:7px 16px; border-radius:20px;
    font-size:.78rem; font-weight:700; transition:background .2s; white-space:nowrap;
}
.back-btn:hover { background:rgba(255,255,255,.28); color:#fff; }

/* ══════════════════════════════════════════
   MATCH HERO CARD
══════════════════════════════════════════ */
.hero {
    background:#fff;
    border-radius:24px;
    margin:18px 0 0;
    border:1px solid #dde8f8;
    box-shadow:0 8px 40px rgba(25,118,210,.1);
    overflow:hidden;
    position:relative;
}
.hero-bar {
    height:5px;
    background:linear-gradient(90deg,#0a2d7a,#1976d2 50%,#ef4444);
}
.hero-body { padding:24px 20px 18px; }
.hero-teams {
    display:flex; align-items:center; justify-content:space-between; gap:10px;
}
.hero-team { flex:1; text-align:center; }
.hero-logo {
    width:82px; height:82px; object-fit:contain;
    filter:drop-shadow(0 6px 12px rgba(0,0,0,.14));
    margin-bottom:10px; transition:transform .3s cubic-bezier(.34,1.56,.64,1);
    display:block; margin-left:auto; margin-right:auto;
}
.hero-logo:hover { transform:scale(1.12); }
.hero-team-name { font-size:1rem; font-weight:800; color:#0d1829; line-height:1.3; word-break:break-word; }
.hero-score {
    flex-shrink:0; text-align:center;
    background:linear-gradient(135deg,#f0f4ff,#e6edfc);
    border-radius:18px; padding:14px 20px;
    border:1px solid #dde8f8; min-width:100px;
}
.hero-score-val {
    font-size:2.8rem; font-weight:900; line-height:1;
    background:linear-gradient(135deg,#0a2d7a,#1976d2);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; display:block; letter-spacing:2px;
}
.hero-score-val.is-live {
    background:linear-gradient(135deg,#dc2626,#ef4444);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hero-score-label { font-size:.7rem; color:#8899bb; font-weight:700; margin-top:5px; display:block; letter-spacing:.5px; }
.hero-meta {
    display:flex; align-items:center; justify-content:center;
    flex-wrap:wrap; gap:8px; margin-top:16px;
    padding-top:14px; border-top:1px solid #edf2fc;
}
.meta-tag {
    background:#f0f4ff; border:1px solid #dde8f8; border-radius:20px;
    padding:5px 14px; font-size:.74rem; font-weight:600; color:#4a5f90;
    display:inline-flex; align-items:center; gap:5px;
}
.meta-tag.is-live-tag {
    background:linear-gradient(135deg,#dc2626,#ef4444);
    border-color:#ef4444; color:#fff;
    box-shadow:0 0 12px rgba(239,68,68,.35);
}

/* ══════════════════════════════════════════
   STREAM SELECTOR TABS
══════════════════════════════════════════ */
.stream-section { margin:24px 0 0; }
.stream-tabs-header {
    display:flex; align-items:center; gap:10px; margin-bottom:14px;
    padding-bottom:12px; border-bottom:2px solid #dde8f8;
}
.stream-tabs-icon {
    width:36px; height:36px;
    background:linear-gradient(135deg,#1148b8,#1976d2);
    border-radius:11px; display:flex; align-items:center; justify-content:center;
    font-size:1.05rem; flex-shrink:0;
    box-shadow:0 4px 14px rgba(25,118,210,.3);
}
.stream-tabs-title { font-size:1.1rem; font-weight:800; color:#0d1829; }
.stream-count {
    background:#1976d2; color:#fff; border-radius:20px;
    padding:2px 10px; font-size:.7rem; font-weight:700;
    margin-right:auto;
}
.stream-grid {
    display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
    gap:12px; margin-bottom:10px;
}
.stream-btn {
    background:#fff; border:2px solid #dde8f8; border-radius:18px;
    padding:18px 12px 14px; text-align:center; text-decoration:none;
    color:#0d1829; display:flex; flex-direction:column; align-items:center; gap:7px;
    cursor:pointer; transition:all .22s cubic-bezier(.34,1.56,.64,1);
    position:relative; overflow:hidden;
    box-shadow:0 3px 14px rgba(25,118,210,.06);
}
.stream-btn::after {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    background:linear-gradient(90deg,#1148b8,#1976d2,#ef4444);
    opacity:0; transition:opacity .22s;
}
.stream-btn:hover { border-color:#1976d2; transform:translateY(-5px) scale(1.02); box-shadow:0 14px 32px rgba(25,118,210,.18); }
.stream-btn:hover::after { opacity:1; }
.stream-btn.active-stream { border-color:#1976d2; background:linear-gradient(135deg,#f0f4ff,#e6edfc); box-shadow:0 8px 24px rgba(25,118,210,.2); }
.stream-btn.active-stream::after { opacity:1; }
.stream-src-icon { font-size:2.5rem; line-height:1; }
.stream-name { font-weight:700; font-size:.9rem; color:#0d1829; line-height:1.3; }
.stream-type { font-size:.72rem; color:#7a90b8; }
.stream-badge-wrap { display:flex; gap:5px; flex-wrap:wrap; justify-content:center; }
.badge-official { background:#10b981; color:#fff; padding:2px 9px; border-radius:12px; font-size:.65rem; font-weight:800; }
.badge-hd { background:#7c3aed; color:#fff; padding:2px 9px; border-radius:12px; font-size:.65rem; font-weight:800; }
.no-streams-card {
    background:#fffbeb; border:1.5px solid #fde68a; border-right:5px solid #f59e0b;
    border-radius:16px; padding:18px 20px; color:#92400e; font-size:.9rem;
    display:flex; align-items:center; gap:12px;
    box-shadow:0 4px 16px rgba(245,158,11,.1);
}

/* ══════════════════════════════════════════
   UNIVERSAL VIDEO PLAYER
══════════════════════════════════════════ */
.player-section { margin:20px 0 0; }
.player-shell {
    background:#000814;
    border-radius:22px;
    overflow:hidden;
    border:2px solid #1e3060;
    box-shadow:0 20px 60px rgba(10,45,122,.25),0 0 0 1px rgba(255,255,255,.04);
    position:relative;
    margin-bottom:18px;
}
.player-topbar {
    background:linear-gradient(90deg,rgba(10,45,122,.9),rgba(25,118,210,.6));
    padding:10px 16px;
    display:flex; align-items:center; justify-content:space-between;
    backdrop-filter:blur(10px);
}
.player-topbar-left { display:flex; align-items:center; gap:8px; }
.player-live-badge {
    background:linear-gradient(135deg,#dc2626,#ef4444);
    color:#fff; border-radius:6px; padding:3px 9px;
    font-size:.7rem; font-weight:800; letter-spacing:1px;
    animation:liveglow 1.5s infinite;
}
.player-title { font-size:.82rem; font-weight:700; color:rgba(255,255,255,.85); }
.player-actions { display:flex; gap:8px; }
.player-action-btn {
    background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.15);
    color:rgba(255,255,255,.8); padding:5px 12px; border-radius:10px;
    font-size:.72rem; font-weight:600; text-decoration:none; cursor:pointer;
    transition:background .2s; white-space:nowrap;
}
.player-action-btn:hover { background:rgba(255,255,255,.2); color:#fff; }
.player-frame-wrap {
    position:relative; padding-bottom:56.25%; height:0; overflow:hidden;
    background:radial-gradient(ellipse at center,#0a1830 0%,#000814 100%);
}
.player-frame-wrap iframe,
.player-frame-wrap video,
.player-frame-wrap #hls-player {
    position:absolute; top:0; left:0; width:100%; height:100%; border:0;
}
.player-loading {
    position:absolute; top:0; left:0; width:100%; height:100%;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    background:radial-gradient(ellipse at center,#0a1830 0%,#000814 100%);
    z-index:5;
}
.player-loading-icon { font-size:3.5rem; animation:pulse 1.5s infinite; margin-bottom:14px; }
@keyframes pulse{0%,100%{transform:scale(1);}50%{transform:scale(1.1);}}
.player-loading-text { color:rgba(255,255,255,.6); font-size:.88rem; font-weight:600; }
.player-shimmer-bar {
    height:3px; background:linear-gradient(90deg,transparent,#1976d2,#ef4444,transparent);
    background-size:200% 100%; animation:shimbar 1.5s infinite;
}
@keyframes shimbar{0%{background-position:200% 0;}100%{background-position:-200% 0;}}

/* External link player */
.ext-player {
    background:linear-gradient(135deg,#0a2d7a 0%,#1148b8 100%);
    border-radius:22px; padding:40px 24px;
    text-align:center; margin-bottom:18px;
    border:1px solid rgba(255,255,255,.08);
    box-shadow:0 20px 60px rgba(10,45,122,.3);
}
.ext-player-icon { font-size:4rem; margin-bottom:16px; display:block; }
.ext-player-title { font-size:1.2rem; font-weight:800; color:#fff; margin-bottom:8px; }
.ext-player-sub { font-size:.85rem; color:rgba(255,255,255,.6); margin-bottom:24px; }
.ext-open-btn {
    display:inline-flex; align-items:center; gap:8px;
    background:linear-gradient(135deg,#ef4444,#dc2626);
    color:#fff; text-decoration:none; padding:12px 30px;
    border-radius:14px; font-weight:800; font-size:.95rem;
    box-shadow:0 8px 24px rgba(239,68,68,.4);
    transition:all .2s;
}
.ext-open-btn:hover { transform:translateY(-2px); box-shadow:0 12px 32px rgba(239,68,68,.5); color:#fff; }

/* ══════════════════════════════════════════
   AD SLOT
══════════════════════════════════════════ */
.ad-slot {
    background:linear-gradient(135deg,#f0f4ff,#e8eef8);
    border:1.5px dashed #b8cef0; border-radius:16px;
    padding:14px 18px; margin:16px 0;
    text-align:center; color:#8899bb; font-size:.82rem;
    min-height:72px; display:flex; align-items:center; justify-content:center; gap:8px;
}

/* ══════════════════════════════════════════
   NEWS SECTION
══════════════════════════════════════════ */
.news-section { margin:24px 0 0; }
.section-hdr {
    display:flex; align-items:center; gap:10px; margin-bottom:14px;
    padding-bottom:12px; border-bottom:2px solid #dde8f8;
}
.section-hdr-icon {
    width:36px; height:36px;
    background:linear-gradient(135deg,#1148b8,#1976d2);
    border-radius:11px; display:flex; align-items:center; justify-content:center;
    font-size:1rem; flex-shrink:0; box-shadow:0 4px 14px rgba(25,118,210,.3);
}
.section-hdr-title { font-size:1.1rem; font-weight:800; color:#0d1829; }
.news-grid {
    display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
    gap:12px; margin-bottom:10px;
}
.news-card {
    background:#fff; border:1px solid #dde8f8; border-radius:16px; padding:15px;
    transition:all .18s; position:relative; overflow:hidden;
    box-shadow:0 2px 10px rgba(25,118,210,.05);
}
.news-card::before {
    content:''; position:absolute; top:0; right:0;
    width:3px; height:100%;
    background:linear-gradient(180deg,#1148b8,#ef4444);
    border-radius:0 16px 16px 0;
}
.news-card:hover { border-color:#1976d2; box-shadow:0 8px 24px rgba(25,118,210,.14); transform:translateY(-2px); }
.news-card a { font-size:.87rem; font-weight:700; color:#0d1829; text-decoration:none; line-height:1.55; display:block; margin-bottom:9px; padding-right:8px; }
.news-card a:hover { color:#1976d2; }
.news-card-meta { display:flex; gap:8px; color:#7a90b8; font-size:.7rem; flex-wrap:wrap; padding-right:8px; }

/* ══════════════════════════════════════════
   SHARE SECTION
══════════════════════════════════════════ */
.share-section { margin:24px 0 0; }
.share-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:16px; }
.share-btn {
    display:flex; align-items:center; justify-content:center; gap:7px;
    padding:12px 8px; border-radius:14px; text-decoration:none;
    font-weight:700; font-size:.84rem; transition:all .18s;
    box-shadow:0 4px 14px rgba(0,0,0,.1); border:none; cursor:pointer;
}
.share-btn:hover { transform:translateY(-3px); filter:brightness(.9); }
.sw { background:#25D366; color:#fff; }
.st { background:#1DA1F2; color:#fff; }
.sf { background:#4267B2; color:#fff; }

/* ══════════════════════════════════════════
   STREAMLIT OVERRIDES
══════════════════════════════════════════ */
.stButton > button {
    background:linear-gradient(135deg,#1148b8,#1976d2) !important;
    color:#fff !important; border:none !important; border-radius:12px !important;
    font-weight:700 !important; box-shadow:0 4px 14px rgba(25,118,210,.3) !important;
    transition:all .2s !important;
}
.stButton > button:hover { opacity:.9 !important; transform:translateY(-1px) !important; }

::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:#1976d2; border-radius:4px; }

@media (max-width:640px) {
    .block-container { padding-left:10px !important; padding-right:10px !important; }
    .bnav { height:54px; padding:0 14px; border-radius:0 0 14px 14px; }
    .bnav-brand-name { font-size:.84rem; }
    .hero-logo { width:60px; height:60px; }
    .hero-team-name { font-size:.84rem; }
    .hero-score-val { font-size:2.2rem; }
    .stream-grid { grid-template-columns:repeat(2,1fr); gap:9px; }
    .share-grid { grid-template-columns:1fr 1fr; gap:8px; }
    .news-grid { grid-template-columns:1fr; }
    .player-topbar { flex-direction:column; align-items:flex-start; gap:6px; padding:8px 12px; }
    .player-actions { align-self:flex-end; }
}
__STYLE_END__</div>
"""
CSS = CSS.replace("__STYLE__", "<style>").replace("__STYLE_END__", "</style>")
st.markdown(CSS, unsafe_allow_html=True)

# Font Awesome separate call for reliability
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  QUERY PARAMS
# ═══════════════════════════════════════════════
match_id = st.query_params.get("match_id", None)
if isinstance(match_id, list):
    match_id = match_id[0]

if not match_id:
    st.markdown("""
    <div class="bnav">
      <div class="bnav-brand">
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg">
        <div><div class="bnav-brand-name">Badr TV</div></div>
      </div>
      <a href="/" class="back-btn">← الرئيسية</a>
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
    <div class="bnav">
      <div class="bnav-brand">
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg">
        <div><div class="bnav-brand-name">Badr TV</div></div>
      </div>
      <a href="/" class="back-btn">← الرئيسية</a>
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
            "title":    a.get("stream_title", "بث مباشر"),
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
#  URL INTELLIGENCE
#  Converts ANY stream URL → embeddable format.
#  Falls back to direct iframe for unknown sources
#  so the stream always shows inside the page.
# ═══════════════════════════════════════════════
def _clean_yt(u):
    m = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', u)
    return f"https://www.youtube.com/embed/{m.group(1)}?autoplay=1&rel=0" if m else u

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
    """Try multiple proxies to extract embeddable URL from any page."""
    for proxy in [
        f"https://api.allorigins.win/raw?url={quote(url)}",
        f"https://thingproxy.freeboard.io/fetch/{url}",
        f"https://api.codetabs.com/v1/proxy?quest={quote(url)}",
    ]:
        try:
            r = requests.get(proxy, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=9)
            if r.status_code == 200:
                t = r.text
                for pat in [
                    r'<meta[^>]+property="og:video(?::url)?"[^>]+content="([^"]+)"',
                    r'<meta[^>]+content="([^"]+)"[^>]+property="og:video(?::url)?"',
                    r'<meta[^>]+property="twitter:player"[^>]+content="([^"]+)"',
                    r'<meta[^>]+content="([^"]+)"[^>]+property="twitter:player"',
                ]:
                    m = re.search(pat, t)
                    if m: return _clean_yt(m.group(1))
                for j in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', t, re.DOTALL):
                    try:
                        found = _find_in_ld(json.loads(j))
                        if found: return _clean_yt(found)
                    except Exception: pass
                # First iframe src
                m = re.search(r'<iframe[^>]+src="(https?://[^"]+)"', t)
                if m: return _clean_yt(m.group(1))
                # HLS manifest inside JS
                m = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', t)
                if m: return m.group(1)
                # MP4 direct
                m = re.search(r'["\']([^"\']+\.mp4[^"\']*)["\']', t)
                if m: return m.group(1)
        except Exception:
            pass
    return None

@st.cache_data(ttl=3600)
def build_embed(url):
    """
    Universal embed builder.
    Returns dict: { embed_url, type, can_direct_embed, name }
    For UNKNOWN sources: returns the original URL directly in an iframe
    (most streaming sites allow this). This is the key to making any
    live stream work inside the page.
    """
    p = urlparse(url); d = p.netloc.lower(); path = p.path.lower(); q = parse_qs(p.query)

    # ── Known platforms ──
    if any(x in d for x in ["youtube.com","youtu.be"]):
        vid = path.strip('/') if "youtu.be" in d else q.get("v",[None])[0]
        if vid:
            return {"embed_url": f"https://www.youtube.com/embed/{vid}?autoplay=1&rel=0", "type":"youtube","can_direct_embed":True,"name":"يوتيوب"}

    if "facebook.com" in d and any(x in url for x in ["/videos/","/watch/","/reel/"]):
        return {"embed_url": f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=1280&autoplay=1", "type":"facebook","can_direct_embed":True,"name":"فيسبوك"}

    if "instagram.com" in d and any(x in path for x in ["/p/","/reel/"]):
        parts = path.split('/')
        if len(parts)>=3:
            return {"embed_url": f"https://www.instagram.com/p/{parts[2]}/embed", "type":"instagram","can_direct_embed":True,"name":"انستغرام"}

    if "twitter.com" in d or "x.com" in d:
        m = re.search(r'/status/(\d+)', path)
        if m:
            return {"embed_url": f"https://twitframe.com/show?url={quote(url)}", "type":"twitter","can_direct_embed":True,"name":"تويتر"}

    if "tiktok.com" in d:
        m = re.search(r'/video/(\d+)', path)
        if m:
            return {"embed_url": f"https://www.tiktok.com/embed/v2/{m.group(1)}", "type":"tiktok","can_direct_embed":True,"name":"تيك توك"}

    if "dailymotion.com" in d or "dai.ly" in d:
        vid = path.strip('/') if "dai.ly" in d else None
        if not vid:
            m = re.search(r'/video/([^_?/]+)', url)
            vid = m.group(1) if m else None
        if vid:
            return {"embed_url": f"https://www.dailymotion.com/embed/video/{vid}?autoplay=1", "type":"dailymotion","can_direct_embed":True,"name":"ديلي موشن"}

    if "vimeo.com" in d:
        vid = path.strip('/').split('/')[0]
        if vid.isdigit():
            return {"embed_url": f"https://player.vimeo.com/video/{vid}?autoplay=1", "type":"vimeo","can_direct_embed":True,"name":"فيميو"}

    if "ok.ru" in d or "odnoklassniki.ru" in d:
        m = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if m:
            return {"embed_url": f"https://ok.ru/videoembed/{m.group(1)}", "type":"ok","can_direct_embed":True,"name":"OK.ru"}

    if "vk.com" in d or "vkvideo.ru" in d:
        m = re.search(r'video(-?\d+)_(\d+)', url)
        if m:
            oid,vid=m.groups()
            return {"embed_url": f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1", "type":"vk","can_direct_embed":True,"name":"VK"}

    if "streamable.com" in d:
        vid = path.strip('/')
        if vid:
            return {"embed_url": f"https://streamable.com/e/{vid}", "type":"streamable","can_direct_embed":True,"name":"Streamable"}

    if "rutube.ru" in d:
        m = re.search(r'/video/([a-zA-Z0-9]+)', url)
        if m:
            return {"embed_url": f"https://rutube.ru/play/embed/{m.group(1)}", "type":"rutube","can_direct_embed":True,"name":"Rutube"}

    if "twitch.tv" in d:
        if "/videos/" in path:
            vid = path.split('/')[-1]
            return {"embed_url": f"https://player.twitch.tv/?video={vid}&parent=localhost&autoplay=true", "type":"twitch","can_direct_embed":True,"name":"تويتش"}
        ch = path.strip('/')
        if ch:
            return {"embed_url": f"https://player.twitch.tv/?channel={ch}&parent=localhost&autoplay=true", "type":"twitch","can_direct_embed":True,"name":"تويتش"}

    # ── Media files ──
    if path.endswith(('.mp4','.webm','.ogg','.mkv')):
        return {"embed_url": url, "type":"direct_video","can_direct_embed":True,"name":"فيديو مباشر"}

    if path.endswith('.m3u8') or 'm3u8' in url:
        return {"embed_url": url, "type":"hls","can_direct_embed":True,"name":"بث HLS"}

    # ── FALLBACK: embed ANY URL directly in iframe ──
    # Many sports streaming sites (e.g. خماسة, بث مباشر, yalla shoot variants)
    # are iframeable. We try it directly — if it fails the browser shows an error
    # inside the player frame, not on our page. We also provide an "open new tab" button.
    return {"embed_url": url, "type":"direct_iframe","can_direct_embed":True,"name":"بث مباشر"}


# ═══════════════════════════════════════════════
#  MATCH META
# ═══════════════════════════════════════════════
home_team = match_data['home_team']
away_team = match_data['away_team']
_fb = lambda n,bg="1148b8": f"https://ui-avatars.com/api/?name={quote(n[:2])}&background={bg}&color=fff&size=100&bold=true&font-size=0.4"
home_logo  = match_data.get('home_logo')  or _fb(home_team)
away_logo  = match_data.get('away_logo')  or _fb(away_team, "0a2d7a")
league     = match_data.get('league','')
status     = match_data.get('status','')
is_live    = status == "LIVE"

try:
    local_time = datetime.fromisoformat(match_data["match_time"].replace('Z','+00:00')).astimezone(tz_tunis)
    time_str   = local_time.strftime('%H:%M — %d/%m/%Y')
except Exception:
    time_str = "---"

hs  = match_data.get('home_score')
aws = match_data.get('away_score')
score_display = f"{hs} - {aws}" if hs is not None else "VS"
score_label   = "نهائي" if status=="FINISHED" else ("🔴 جارية" if is_live else "لم تبدأ")
score_cls     = "hero-score-val is-live" if is_live else "hero-score-val"

live_tag = (
    '<span class="meta-tag is-live-tag">'
    '<span style="width:7px;height:7px;background:#fff;border-radius:50%;display:inline-block;animation:blink 1s infinite;"></span>'
    ' مباشر الآن</span>'
) if is_live else f'<span class="meta-tag">{score_label}</span>'


# ═══════════════════════════════════════════════
#  ── NAV BAR
# ═══════════════════════════════════════════════
st.markdown(f"""
<div class="bnav">
  <div class="bnav-brand">
    <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg" alt="logo">
    <div>
      <div class="bnav-brand-name">Badr TV</div>
      <span class="bnav-brand-sub">منصة كرة القدم الشاملة</span>
    </div>
  </div>
  <div class="bnav-right">
    {"<div class='live-pill'><span class='live-pill-dot'></span> LIVE</div>" if is_live else ""}
    <a href="/" class="back-btn">← الرئيسية</a>
  </div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  ── MATCH HERO
# ═══════════════════════════════════════════════
st.markdown(f"""
<div class="hero">
  <div class="hero-bar"></div>
  <div class="hero-body">
    <div class="hero-teams">
      <div class="hero-team">
        <img src="{home_logo}" class="hero-logo">
        <div class="hero-team-name">{home_team}</div>
      </div>
      <div class="hero-score">
        <span class="{score_cls}">{score_display}</span>
        <span class="hero-score-label">{'FT' if status=='FINISHED' else ('LIVE' if is_live else 'VS')}</span>
      </div>
      <div class="hero-team">
        <img src="{away_logo}" class="hero-logo">
        <div class="hero-team-name">{away_team}</div>
      </div>
    </div>
    <div class="hero-meta">
      <span class="meta-tag">🏆 {league}</span>
      <span class="meta-tag">🕐 {time_str}</span>
      {live_tag}
    </div>
  </div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  ── TOP AD
# ═══════════════════════════════════════════════
st.markdown('<div class="ad-slot">📢 مساحة إعلانية</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  ── STREAM SELECTOR
# ═══════════════════════════════════════════════
count_badge = f'<span class="stream-count">{len(all_streams)} بث</span>' if all_streams else ''
st.markdown(f"""
<div class="stream-section">
  <div class="stream-tabs-header">
    <div class="stream-tabs-icon">📡</div>
    <div class="stream-tabs-title">اختر قناة البث</div>
    {count_badge}
  </div>
</div>""", unsafe_allow_html=True)

# Get selected stream from URL
selected_url = st.query_params.get("stream_url", None)
if isinstance(selected_url, list):
    selected_url = selected_url[0]
if selected_url:
    selected_url = unquote(selected_url)

if not all_streams:
    st.markdown("""
    <div class="no-streams-card">
      <span style="font-size:1.8rem;">📡</span>
      <div>
        <div style="font-weight:800; margin-bottom:3px;">لا توجد روابط بث متاحة</div>
        <div style="font-size:.82rem; opacity:.75;">يتم إضافة روابط البث قبل انطلاق المباراة مباشرةً</div>
      </div>
    </div>""", unsafe_allow_html=True)
else:
    _src_map = {
        "youtube":  ('<i class="fab fa-youtube" style="color:#FF0000"></i>', "يوتيوب"),
        "facebook": ('<i class="fab fa-facebook" style="color:#4267B2"></i>', "فيسبوك"),
        "twitch":   ('<i class="fab fa-twitch" style="color:#9146FF"></i>', "تويتش"),
        "instagram":('<i class="fab fa-instagram" style="color:#E1306C"></i>', "انستغرام"),
        "tiktok":   ('<i class="fab fa-tiktok" style="color:#010101"></i>', "تيك توك"),
        "vk":       ('<i class="fab fa-vk" style="color:#4a76a8"></i>', "VK"),
        "ok.ru":    ('<i class="fas fa-circle-play" style="color:#f7941e"></i>', "OK.ru"),
        "admin":    ('<i class="fas fa-satellite-dish" style="color:#1976d2"></i>', "بث مباشر"),
        "official": ('<i class="fas fa-shield-halved" style="color:#10b981"></i>', "رسمي"),
        "hls":      ('<i class="fas fa-tower-broadcast" style="color:#ef4444"></i>', "HLS"),
    }

    cards_html = '<div class="stream-grid">'
    for i, s in enumerate(all_streams):
        src = s.get("source","").lower()
        stream_url_raw = s.get("url","")
        is_selected = selected_url == stream_url_raw

        icon, label = next(
            ((v for k,v in _src_map.items() if k in src or k in stream_url_raw.lower())),
            ('<i class="fas fa-play-circle" style="color:#1976d2"></i>', "بث مباشر")
        )

        # Detect HLS/m3u8
        if '.m3u8' in stream_url_raw or 'hls' in src:
            icon, label = _src_map["hls"]

        badges = ''
        if s.get("verified"):
            badges += '<span class="badge-official">✓ رسمي</span>'
        if 'hd' in s.get("title","").lower() or '1080' in s.get("title","") or '720' in s.get("title",""):
            badges += '<span class="badge-hd">HD</span>'

        enc_url = quote(stream_url_raw, safe='')
        link    = f"/watch_stream?match_id={match_id}&stream_url={enc_url}"
        title   = s.get("title","بث مباشر")[:26]
        active_cls = "active-stream" if is_selected else ""

        cards_html += f"""
        <a href="{link}" class="stream-btn {active_cls}">
          <div class="stream-src-icon" style="font-size:2.4rem;">{icon}</div>
          <div class="stream-name">{title}</div>
          <div class="stream-type">{label}</div>
          {"<div class='stream-badge-wrap'>" + badges + "</div>" if badges else ""}
        </a>"""
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  ── UNIVERSAL VIDEO PLAYER
# ═══════════════════════════════════════════════
if selected_url:
    source = build_embed(selected_url)
    embed_url = source.get("embed_url")
    stype     = source.get("type","")

    # Try extraction for non-embeddable if needed
    # (build_embed now always returns an embed_url, so this is just for HLS extraction)
    if stype == "direct_iframe" and not st.session_state.extraction_attempted:
        # Try once to extract a cleaner embed URL
        st.session_state.extraction_attempted = True
        with st.spinner("🔄 جاري تحضير البث..."):
            extracted = extract_embed_url(selected_url)
            if extracted and extracted != selected_url:
                st.session_state.extracted_url = extracted
        if st.session_state.extracted_url:
            embed_url = st.session_state.extracted_url
            stype     = "extracted"
    elif st.session_state.extracted_url and stype == "direct_iframe":
        embed_url = st.session_state.extracted_url

    # Build player topbar
    try:
        host     = st.context.headers.get('host','')
        protocol = 'https' if st.context.headers.get('x-forwarded-proto','http') == 'https' else 'http'
        base_url = f"{protocol}://{host}"
    except Exception:
        base_url = ""

    page_url = f"{base_url}/watch_stream?match_id={match_id}"

    live_badge_html = '<span class="player-live-badge">● LIVE</span>' if is_live else ''
    player_title    = f"{home_team} vs {away_team}"

    st.markdown(f"""
    <div class="player-section">
      <div class="section-hdr">
        <div class="section-hdr-icon">▶️</div>
        <div class="section-hdr-title">المشغّل</div>
      </div>
      <div class="player-shell">
        <div class="player-shimmer-bar"></div>
        <div class="player-topbar">
          <div class="player-topbar-left">
            {live_badge_html}
            <span class="player-title">{player_title}</span>
          </div>
          <div class="player-actions">
            <a href="{selected_url}" target="_blank" class="player-action-btn">
              <i class="fas fa-external-link-alt"></i> فتح خارجياً
            </a>
          </div>
        </div>
        <div class="player-frame-wrap">""", unsafe_allow_html=True)

    # Render correct player based on type
    if stype == "hls":
        st.markdown(f"""
          <div id="hls-player" style="width:100%;height:100%;background:#000;"></div>
        </div>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script>
    (function(){{
      var c=document.getElementById('hls-player');
      var v=document.createElement('video');
      v.controls=true; v.autoplay=true; v.playsinline=true;
      v.style.cssText='width:100%;height:100%;background:#000;';
      c.appendChild(v);
      if(Hls.isSupported()){{
        var h=new Hls({{maxBufferLength:60,enableWorker:true}});
        h.loadSource('{embed_url}');
        h.attachMedia(v);
        h.on(Hls.Events.MANIFEST_PARSED,function(){{v.play();}});
        h.on(Hls.Events.ERROR,function(e,d){{
          if(d.fatal){{ v.src='{embed_url}'; v.play(); }}
        }});
      }}else if(v.canPlayType('application/vnd.apple.mpegurl')){{
        v.src='{embed_url}'; v.play();
      }}
    }})();
    </script>""", unsafe_allow_html=True)

    elif stype == "direct_video":
        st.markdown(f"""
          <video controls autoplay playsinline
                 style="width:100%;height:100%;background:#000;">
            <source src="{embed_url}" type="video/mp4">
            <source src="{embed_url}" type="video/webm">
          </video>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    else:
        # iframe: works for YouTube, Facebook, Dailymotion, VK, OK.ru,
        # Streamable, custom streams, AND direct_iframe fallback.
        # The sandbox allows scripts+same-origin so most streams load fine.
        st.markdown(f"""
          <iframe
            src="{embed_url}"
            allow="autoplay; fullscreen; encrypted-media; picture-in-picture; accelerometer; gyroscope"
            allowfullscreen
            referrerpolicy="no-referrer-when-downgrade"
            scrolling="no">
          </iframe>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="ad-slot">📢 مساحة إعلانية</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  ── RECENT NEWS
# ═══════════════════════════════════════════════
if recent_news:
    st.markdown("""
    <div class="news-section">
      <div class="section-hdr">
        <div class="section-hdr-icon">📰</div>
        <div class="section-hdr-title">آخر الأخبار</div>
      </div>
    </div>""", unsafe_allow_html=True)

    html_news = '<div class="news-grid">'
    for item in recent_news:
        title = item.get('title','')
        src   = item.get('source','')
        nurl  = item.get('url','#')
        img   = item.get('image','')
        try:
            dt = datetime.fromisoformat(item["published_at"].replace('Z','+00:00')).astimezone(tz_tunis)
            ds = dt.strftime("%H:%M — %d/%m")
        except Exception:
            ds = ""
        html_news += f"""
        <div class="news-card">
          <a href="{nurl}" target="_blank">{title}</a>
          <div class="news-card-meta">
            <span>📰 {src}</span>
            <span>🕒 {ds}</span>
          </div>
        </div>"""
    html_news += '</div>'
    st.markdown(html_news, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
#  ── SHARE
# ═══════════════════════════════════════════════
try:
    host     = st.context.headers.get('host','')
    protocol = 'https' if st.context.headers.get('x-forwarded-proto','http') == 'https' else 'http'
    base_url = f"{protocol}://{host}"
except Exception:
    base_url = ""

page_url   = f"{base_url}/watch_stream?match_id={match_id}"
share_text = f"شاهد {home_team} vs {away_team} بث مباشر على Badr TV"

st.markdown(f"""
<div class="share-section">
  <div class="section-hdr">
    <div class="section-hdr-icon">📤</div>
    <div class="section-hdr-title">شارك المباراة</div>
  </div>
  <div class="share-grid">
    <a href="https://wa.me/?text={quote(share_text+' '+page_url)}" target="_blank" class="share-btn sw">
      <i class="fab fa-whatsapp"></i> واتساب
    </a>
    <a href="https://twitter.com/intent/tweet?text={quote(share_text+' '+page_url)}" target="_blank" class="share-btn st">
      <i class="fab fa-twitter"></i> تويتر
    </a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}" target="_blank" class="share-btn sf">
      <i class="fab fa-facebook-f"></i> فيسبوك
    </a>
  </div>
</div>""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    if st.button("📱 رمز QR للمشاركة", key="qr_btn", use_container_width=True):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={quote(page_url)}&bgcolor=f0f4ff&color=0a2d7a"
        st.image(qr_url, width=200)
with col2:
    if st.button("🔗 نسخ الرابط", key="copy_btn", use_container_width=True):
        st.code(page_url)


# ═══════════════════════════════════════════════
#  FOOTER AD
# ═══════════════════════════════════════════════
st.markdown("---")
st.markdown('<div class="ad-slot">📢 مساحة إعلانية</div>', unsafe_allow_html=True)
