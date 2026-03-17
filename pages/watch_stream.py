import streamlit as st
import time
import re
import json
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime, timedelta
import requests
import zoneinfo
from supabase import create_client

# -------------------------------------------------------------------
# Page configuration – MUST be first
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Badr TV - مشاهدة البث المباشر",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------------
# Load secrets and init Supabase
# -------------------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------------------------------------------------------
# Timezone
# -------------------------------------------------------------------
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

# -------------------------------------------------------------------
# Session state
# -------------------------------------------------------------------
if "extraction_attempted" not in st.session_state:
    st.session_state.extraction_attempted = False
if "extracted_url" not in st.session_state:
    st.session_state.extracted_url = None
if "extraction_failed" not in st.session_state:
    st.session_state.extraction_failed = False

# -------------------------------------------------------------------
# Get match_id from query params
# -------------------------------------------------------------------
match_id = st.query_params.get("match_id", [None])
if isinstance(match_id, list):
    match_id = match_id[0]

if not match_id:
    st.error("❌ لم يتم تحديد المباراة")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# -------------------------------------------------------------------
# Fetch match details
# -------------------------------------------------------------------
match_data = None
try:
    res = supabase.table("matches").select("*").eq("fixture_id", match_id).execute()
    if res.data:
        match_data = res.data[0]
except Exception as e:
    st.warning("تعذر تحميل معلومات المباراة")

if not match_data:
    st.error("المباراة غير موجودة")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# -------------------------------------------------------------------
# Collect all streams (from match + admin)
# -------------------------------------------------------------------
all_streams = []

# From match streams field
match_streams = match_data.get("streams", [])
if isinstance(match_streams, str):
    try:
        match_streams = json.loads(match_streams)
    except:
        match_streams = []
all_streams.extend(match_streams)

# From admin_streams table
try:
    admin_streams = supabase.table("admin_streams").select("*").eq("fixture_id", match_id).eq("is_active", True).execute().data
    for a in admin_streams:
        all_streams.append({
            "title": a.get("stream_title", "بث إضافي"),
            "url": a["stream_url"],
            "source": a.get("stream_source", "admin"),
            "verified": True,
            "admin_added": True
        })
except Exception as e:
    pass

# -------------------------------------------------------------------
# Fetch recent news (for bottom section)
# -------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_recent_news(limit=4):
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    res = supabase.table("news").select("*").gte("published_at", cutoff).order("published_at", desc=True).limit(limit).execute()
    return res.data

recent_news = get_recent_news(4)

# -------------------------------------------------------------------
# Ultra‑aggressive extraction helpers
# -------------------------------------------------------------------
def _clean_embed_url(video_url):
    """Convert various video URLs to embed format."""
    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        yt_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', video_url)
        if yt_match:
            return f"https://www.youtube.com/embed/{yt_match.group(1)}?autoplay=1"
    return video_url

def _extract_from_json_ld(obj):
    """Recursively search JSON‑LD for a video URL."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('embedUrl', 'contentUrl', 'url') and isinstance(v, str) and ('http' in v):
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
    """Ultra‑aggressive extraction: tries 6 proxies, multiple meta tags, JSON‑LD, and video elements."""
    proxies = [
        f"https://api.allorigins.win/raw?url={quote(url)}",
        f"https://cors-anywhere.herokuapp.com/{url}",
        f"https://thingproxy.freeboard.io/fetch/{url}",
        f"https://api.codetabs.com/v1/proxy?quest={quote(url)}",
        f"https://proxy.cors.sh/{url}",
        f"https://crossorigin.me/{url}"
    ]
    headers_list = [
        {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'},
        {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G975F)'}
    ]
    
    for proxy in proxies:
        for headers in headers_list:
            try:
                resp = requests.get(proxy, headers=headers, timeout=8)
                if resp.status_code == 200:
                    html = resp.text
                    # 1. Standard meta tags
                    og_video = re.search(r'<meta property="og:video"[^>]+content="([^"]+)"', html)
                    if og_video:
                        return _clean_embed_url(og_video.group(1))
                    twitter_player = re.search(r'<meta property="twitter:player"[^>]+content="([^"]+)"', html)
                    if twitter_player:
                        return _clean_embed_url(twitter_player.group(1))
                    
                    # 2. JSON‑LD (structured data)
                    json_ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                    for j in json_ld:
                        try:
                            data = json.loads(j)
                            video_url = _extract_from_json_ld(data)
                            if video_url:
                                return _clean_embed_url(video_url)
                        except:
                            pass
                    
                    # 3. First iframe src
                    iframe_src = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                    if iframe_src:
                        return _clean_embed_url(iframe_src.group(1))
                    
                    # 4. Direct video tags
                    video_src = re.search(r'<video[^>]+src="([^"]+)"', html)
                    if video_src:
                        return video_src.group(1)
            except:
                continue
    return None

# -------------------------------------------------------------------
# Intelligent source detection (your original, untouched)
# -------------------------------------------------------------------
@st.cache_data(ttl=3600)
def detect_source(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parse_qs(parsed.query)

    # YouTube
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        if "youtu.be" in domain:
            video_id = path.strip('/')
        else:
            video_id = query.get("v", [None])[0]
        if video_id:
            return {
                "type": "youtube",
                "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1",
                "can_embed": True,
                "name": "يوتيوب"
            }

    # Facebook
    elif "facebook.com" in domain and ("/videos/" in url or "/watch/" in url or "/reel/" in url):
        return {
            "type": "facebook",
            "embed_url": f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=560",
            "can_embed": True,
            "name": "فيسبوك"
        }

    # Instagram
    elif "instagram.com" in domain and ("/p/" in path or "/reel/" in path):
        parts = path.split('/')
        if len(parts) >= 3:
            post_id = parts[2]
            return {
                "type": "instagram",
                "embed_url": f"https://www.instagram.com/p/{post_id}/embed",
                "can_embed": True,
                "name": "انستغرام"
            }

    # Twitter/X
    elif "twitter.com" in domain or "x.com" in domain:
        match = re.search(r'/status/(\d+)', path)
        if match:
            status_id = match.group(1)
            return {
                "type": "twitter",
                "embed_url": f"https://twitframe.com/show?url={quote(url)}",
                "can_embed": True,
                "name": "تويتر"
            }

    # TikTok
    elif "tiktok.com" in domain:
        match = re.search(r'/video/(\d+)', path)
        if match:
            video_id = match.group(1)
            return {
                "type": "tiktok",
                "embed_url": f"https://www.tiktok.com/embed/v2/{video_id}",
                "can_embed": True,
                "name": "تيك توك"
            }

    # Dailymotion
    elif "dailymotion.com" in domain or "dai.ly" in domain:
        if "dai.ly" in domain:
            video_id = path.strip('/')
        else:
            match = re.search(r'/video/([^_?]+)', url)
            video_id = match.group(1) if match else None
        if video_id:
            return {
                "type": "dailymotion",
                "embed_url": f"https://www.dailymotion.com/embed/video/{video_id}?autoplay=1",
                "can_embed": True,
                "name": "ديلي موشن"
            }

    # Vimeo
    elif "vimeo.com" in domain:
        video_id = path.strip('/').split('/')[0]
        if video_id.isdigit():
            return {
                "type": "vimeo",
                "embed_url": f"https://player.vimeo.com/video/{video_id}?autoplay=1",
                "can_embed": True,
                "name": "فيميو"
            }

    # Twitch
    elif "twitch.tv" in domain:
        if "/videos/" in path:
            video_id = path.split('/')[-1]
            return {
                "type": "twitch",
                "embed_url": f"https://player.twitch.tv/?video=v{video_id}&parent={st.get_option('server.address')}&autoplay=true",
                "can_embed": True,
                "name": "تويتش"
            }
        else:
            channel = path.strip('/')
            if channel:
                return {
                    "type": "twitch",
                    "embed_url": f"https://player.twitch.tv/?channel={channel}&parent={st.get_option('server.address')}&autoplay=true",
                    "can_embed": True,
                    "name": "تويتش"
                }

    # Ok.ru
    elif "ok.ru" in domain or "odnoklassniki.ru" in domain:
        match = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if match:
            video_id = match.group(1)
            return {
                "type": "ok",
                "embed_url": f"https://ok.ru/videoembed/{video_id}",
                "can_embed": True,
                "name": "OK.ru"
            }

    # VK
    elif "vk.com" in domain or "vkvideo.ru" in domain:
        match = re.search(r'video(-?\d+)_(\d+)', url)
        if match:
            oid, vid = match.groups()
            return {
                "type": "vk",
                "embed_url": f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1",
                "can_embed": True,
                "name": "VK"
            }

    # Coub
    elif "coub.com" in domain:
        match = re.search(r'/view/([a-zA-Z0-9]+)', url)
        if match:
            video_id = match.group(1)
            return {
                "type": "coub",
                "embed_url": f"https://coub.com/embed/{video_id}?muted=false&autostart=true",
                "can_embed": True,
                "name": "Coub"
            }

    # Rutube
    elif "rutube.ru" in domain:
        match = re.search(r'/video/([a-zA-Z0-9]+)', url)
        if match:
            video_id = match.group(1)
            return {
                "type": "rutube",
                "embed_url": f"https://rutube.ru/play/embed/{video_id}",
                "can_embed": True,
                "name": "Rutube"
            }

    # Bilibili
    elif "bilibili.com" in domain:
        match = re.search(r'/video/(BV[a-zA-Z0-9]+)', url)
        if match:
            video_id = match.group(1)
            return {
                "type": "bilibili",
                "embed_url": f"https://player.bilibili.com/player.html?bvid={video_id}&page=1&autoplay=1",
                "can_embed": True,
                "name": "Bilibili"
            }

    # Streamable
    elif "streamable.com" in domain:
        video_id = path.strip('/')
        if video_id:
            return {
                "type": "streamable",
                "embed_url": f"https://streamable.com/e/{video_id}",
                "can_embed": True,
                "name": "Streamable"
            }

    # Direct video files
    if path.endswith(('.mp4', '.webm', '.ogg', '.mkv')):
        return {
            "type": "direct_video",
            "embed_url": url,
            "can_embed": True,
            "name": "فيديو مباشر"
        }

    # HLS (m3u8)
    if path.endswith('.m3u8'):
        return {
            "type": "hls",
            "embed_url": url,
            "can_embed": True,
            "name": "بث HLS"
        }

    return {"type": "unknown", "can_embed": False, "name": "رابط خارجي"}

# -------------------------------------------------------------------
# Modern light‑mode CSS with Font Awesome
# -------------------------------------------------------------------
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap');
    * { font-family: 'Cairo', sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
    .main, .block-container { 
        direction: rtl; 
        text-align: right; 
        padding: 1.5rem !important; 
        background: #f8fafc; 
        color: #1e293b;
    }
    /* Clean card design */
    .card {
        background: white;
        border-radius: 28px;
        padding: 1.8rem;
        box-shadow: 0 15px 35px -10px rgba(0,0,0,0.1);
        border: 1px solid rgba(0,0,0,0.03);
        margin-bottom: 2rem;
        transition: all 0.2s ease;
    }
    .card:hover {
        box-shadow: 0 20px 40px -12px rgba(0,0,0,0.15);
    }
    /* Match header */
    .match-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1.5rem;
        flex-wrap: wrap;
    }
    .team-block {
        flex: 1;
        text-align: center;
    }
    .team-logo {
        width: 100px;
        height: 100px;
        object-fit: contain;
        margin-bottom: 0.8rem;
        filter: drop-shadow(0 5px 10px rgba(0,0,0,0.1));
    }
    .team-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
    }
    .vs-divider {
        font-size: 2.8rem;
        font-weight: 800;
        color: #ef4444;
        padding: 0 1rem;
    }
    .match-meta {
        text-align: center;
        margin-top: 1rem;
        color: #64748b;
        font-size: 1.1rem;
    }
    .match-meta i { margin: 0 0.3rem; color: #ef4444; }
    /* Stream grid */
    .stream-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 1.2rem;
        margin: 2rem 0;
    }
    .stream-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 1.5rem 1rem;
        text-align: center;
        text-decoration: none;
        color: #1e293b;
        transition: 0.2s;
        box-shadow: 0 4px 10px rgba(0,0,0,0.02);
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
    }
    .stream-card:hover {
        transform: translateY(-5px);
        border-color: #ef4444;
        box-shadow: 0 15px 25px -10px rgba(239,68,68,0.3);
    }
    .stream-icon {
        font-size: 2.8rem;
        color: #ef4444;
    }
    .stream-title {
        font-weight: 700;
        font-size: 1.2rem;
        color: #0f172a;
    }
    .stream-source {
        font-size: 0.9rem;
        color: #64748b;
    }
    .verified-badge {
        background: #10b981;
        color: white;
        padding: 0.25rem 1rem;
        border-radius: 30px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin-top: 0.3rem;
    }
    /* Video container */
    .video-container {
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        background: #0b1120;
        border-radius: 28px;
        box-shadow: 0 25px 50px -12px rgba(0,0,0,0.3);
        margin: 2rem 0;
        border: 1px solid #e2e8f0;
    }
    .video-container iframe, .video-container video, .video-container .hls-player {
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        border: 0;
        border-radius: 28px;
    }
    /* Loading shimmer */
    .video-container.loading::after {
        content: "";
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        animation: shimmer 1.5s infinite;
        z-index: 2;
    }
    @keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
    /* Section title */
    .section-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 2.5rem 0 1.5rem;
        color: #0f172a;
        position: relative;
        padding-bottom: 0.5rem;
    }
    .section-title::after {
        content: "";
        position: absolute;
        bottom: 0; right: 0;
        width: 80px;
        height: 4px;
        background: #ef4444;
        border-radius: 4px;
    }
    /* News grid */
    .news-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    .news-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 1.5rem;
        transition: 0.2s;
    }
    .news-card:hover {
        box-shadow: 0 10px 25px -8px rgba(0,0,0,0.1);
        border-color: #ef4444;
    }
    .news-title {
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        line-height: 1.5;
        color: #0f172a;
    }
    .news-title a {
        color: #0f172a;
        text-decoration: none;
    }
    .news-title a:hover {
        color: #ef4444;
    }
    .news-meta {
        display: flex;
        gap: 1rem;
        color: #64748b;
        font-size: 0.9rem;
    }
    .news-meta i { margin-left: 0.3rem; }
    /* Buttons */
    .btn {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 60px;
        padding: 0.7rem 1.8rem;
        color: #1e293b;
        text-decoration: none;
        font-weight: 600;
        transition: 0.2s;
        box-shadow: 0 4px 8px rgba(0,0,0,0.02);
    }
    .btn:hover {
        border-color: #ef4444;
        background: #fef2f2;
        transform: translateY(-2px);
    }
    .btn-primary {
        background: #ef4444;
        border-color: #ef4444;
        color: white;
    }
    .btn-primary:hover {
        background: #dc2626;
    }
    .btn-wa { background: #25D366; border-color: #25D366; color: white; }
    .btn-tw { background: #1DA1F2; border-color: #1DA1F2; color: white; }
    .btn-fb { background: #4267B2; border-color: #4267B2; color: white; }
    .btn-wa:hover, .btn-tw:hover, .btn-fb:hover { filter: brightness(0.9); }
    /* Ad container */
    .ad-container {
        background: #f1f5f9;
        border-radius: 20px;
        padding: 1.5rem;
        margin: 2rem 0;
        text-align: center;
        border: 1px dashed #cbd5e1;
        color: #64748b;
    }
    /* Back button */
    .back-link {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        color: #64748b;
        text-decoration: none;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .back-link:hover { color: #ef4444; }
    /* QR code button */
    .qr-btn {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 60px;
        padding: 0.7rem 1.8rem;
        cursor: pointer;
        font-weight: 600;
        color: #1e293b;
        transition: 0.2s;
    }
    .qr-btn:hover { border-color: #ef4444; background: #fef2f2; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Back to home link
# -------------------------------------------------------------------
st.markdown(f'<a href="/" class="back-link"><i class="fas fa-arrow-right"></i> العودة إلى الرئيسية</a>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Match header (card)
# -------------------------------------------------------------------
home_team = match_data['home_team']
away_team = match_data['away_team']
home_logo = match_data.get('home_logo') or "https://via.placeholder.com/100?text=Home"
away_logo = match_data.get('away_logo') or "https://via.placeholder.com/100?text=Away"
league = match_data.get('league', '')
try:
    utc_time = datetime.fromisoformat(match_data["match_time"].replace('Z', '+00:00'))
    local_time = utc_time.astimezone(tz_tunis)
    time_str = local_time.strftime('%H:%M %Y-%m-%d')
except:
    time_str = "الوقت غير معروف"
status = match_data.get('status', '')
score = f"{match_data.get('home_score','')} - {match_data.get('away_score','')}" if match_data.get('home_score') is not None else "VS"

st.markdown(f"""
<div class="card">
    <div class="match-header">
        <div class="team-block">
            <img src="{home_logo}" class="team-logo">
            <div class="team-name">{home_team}</div>
        </div>
        <div class="vs-divider">{score}</div>
        <div class="team-block">
            <img src="{away_logo}" class="team-logo">
            <div class="team-name">{away_team}</div>
        </div>
    </div>
    <div class="match-meta">
        <i class="fas fa-trophy"></i> {league} • <i class="far fa-clock"></i> {time_str} • <i class="fas fa-futbol"></i> {status}
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Top ad container
# -------------------------------------------------------------------
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <!-- ضع كود الإعلان هنا -->
    <i class="fas fa-ad" style="color: #94a3b8;"></i> مساحة إعلانية
""", height=80)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Streams section
# -------------------------------------------------------------------
st.markdown("<h2 class='section-title'><i class='fas fa-tv'></i> قائمة البث المتاحة</h2>", unsafe_allow_html=True)

if not all_streams:
    st.warning("لا توجد روابط بث متاحة لهذه المباراة.")
else:
    st.markdown('<div class="stream-grid">', unsafe_allow_html=True)
    for stream in all_streams:
        # Choose icon based on source
        src = stream.get("source", "custom").lower()
        if "youtube" in src:
            icon = '<i class="fab fa-youtube"></i>'
        elif "facebook" in src:
            icon = '<i class="fab fa-facebook"></i>'
        elif "twitch" in src:
            icon = '<i class="fab fa-twitch"></i>'
        elif "admin" in src:
            icon = '<i class="fas fa-circle" style="color:#ef4444;"></i>'
        else:
            icon = '<i class="fas fa-link"></i>'
        verified_badge = '<span class="verified-badge"><i class="fas fa-check-circle"></i> رسمي</span>' if stream.get("verified") else ''
        base = f"/watch_stream?match_id={match_id}"
        stream_url_enc = quote(stream['url'], safe='')
        btn_link = f"{base}&stream_url={stream_url_enc}"
        st.markdown(f'''
        <a href="{btn_link}" class="stream-card">
            <span class="stream-icon">{icon}</span>
            <span class="stream-title">{stream.get("title", "بث مباشر")[:30]}</span>
            <span class="stream-source">{stream.get("source", "مصدر")}</span>
            {verified_badge}
        </a>
        ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Embedded player if a stream URL is selected
# -------------------------------------------------------------------
selected_stream_url = st.query_params.get("stream_url", [None])
if isinstance(selected_stream_url, list):
    selected_stream_url = selected_stream_url[0]

if selected_stream_url:
    selected_stream_url = unquote(selected_stream_url)
    st.markdown("<h2 class='section-title'><i class='fas fa-play-circle'></i> البث المحدد</h2>", unsafe_allow_html=True)

    source_info = detect_source(selected_stream_url)

    # Automatic extraction if needed
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
        can_embed = source_info["can_embed"]

    # Display video
    if can_embed and embed_url:
        container_class = "video-container loading"
        if source_info.get("type") == "hls" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="{container_class}">
                <div class="hls-player" id="hls-player"></div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <script>
              if(Hls.isSupported()) {{
                var video = document.createElement('video');
                video.controls = true;
                video.autoplay = true;
                video.style.width = '100%';
                video.style.height = '100%';
                document.getElementById('hls-player').appendChild(video);
                var hls = new Hls();
                hls.loadSource('{embed_url}');
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED,function() {{
                  video.play();
                }});
              }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                var video = document.createElement('video');
                video.controls = true;
                video.autoplay = true;
                video.style.width = '100%';
                video.style.height = '100%';
                video.src = '{embed_url}';
                document.getElementById('hls-player').appendChild(video);
                video.play();
              }}
            </script>
            """, unsafe_allow_html=True)
        elif source_info.get("type") == "direct_video" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="{container_class}">
                <video controls autoplay playsinline>
                    <source src="{embed_url}" type="video/mp4">
                </video>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="{container_class}">
                <iframe src="{embed_url}" 
                        allow="autoplay; encrypted-media; fullscreen; picture-in-picture" 
                        allowfullscreen>
                </iframe>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ لا يمكن عرض البث داخل الصفحة. سيتم فتحه في نافذة جديدة.")
        st.markdown(f'<a href="{selected_stream_url}" target="_blank" class="btn btn-primary" style="display:block; text-align:center;"><i class="fas fa-external-link-alt"></i> فتح البث في نافذة جديدة</a>', unsafe_allow_html=True)

    # Mid‑video ad
    st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
    st.components.v1.html("""
        <!-- ضع كود الإعلان هنا -->
        <i class="fas fa-ad" style="color: #94a3b8;"></i> مساحة إعلانية
    """, height=80)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Recent news section
# -------------------------------------------------------------------
if recent_news:
    st.markdown("<h2 class='section-title'><i class='far fa-newspaper'></i> آخر الأخبار</h2>", unsafe_allow_html=True)
    st.markdown('<div class="news-grid">', unsafe_allow_html=True)
    for item in recent_news:
        title = item.get('title', '')
        source = item.get('source', 'مصدر')
        published = item.get('published_at', '')
        if published:
            try:
                pub_date = datetime.fromisoformat(published.replace('Z', '+00:00')).astimezone(tz_tunis)
                date_str = pub_date.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = ""
        else:
            date_str = ""
        st.markdown(f'''
        <div class="news-card">
            <div class="news-title"><a href="{item.get('url','#')}" target="_blank">{title}</a></div>
            <div class="news-meta">
                <span><i class="fas fa-newspaper"></i> {source}</span>
                <span><i class="far fa-clock"></i> {date_str}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Share buttons
# -------------------------------------------------------------------
st.markdown("<h2 class='section-title'><i class='fas fa-share-alt'></i> شارك هذه المباراة</h2>", unsafe_allow_html=True)
cols = st.columns(4)
try:
    host = st.context.headers.get('host', '')
    protocol = 'https' if st.context.headers.get('x-forwarded-proto', 'http') == 'https' else 'http'
    base_url = f"{protocol}://{host}"
except:
    base_url = ""
page_url = f"{base_url}/watch_stream?match_id={match_id}"
share_text = f"شاهد {home_team} vs {away_team} بث مباشر على Badr TV"
with cols[0]:
    st.markdown(f'<a href="https://wa.me/?text={quote(share_text+" "+page_url)}" target="_blank" class="btn btn-wa" style="display:flex; justify-content:center;"><i class="fab fa-whatsapp"></i> واتساب</a>', unsafe_allow_html=True)
with cols[1]:
    st.markdown(f'<a href="https://twitter.com/intent/tweet?text={quote(share_text+" "+page_url)}" target="_blank" class="btn btn-tw" style="display:flex; justify-content:center;"><i class="fab fa-twitter"></i> تويتر</a>', unsafe_allow_html=True)
with cols[2]:
    st.markdown(f'<a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}" target="_blank" class="btn btn-fb" style="display:flex; justify-content:center;"><i class="fab fa-facebook-f"></i> فيسبوك</a>', unsafe_allow_html=True)
with cols[3]:
    if st.button("📱 رمز QR", key="qr_btn"):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={quote(page_url)}"
        st.image(qr_url, width=150)

# -------------------------------------------------------------------
# Footer ad
# -------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <!-- ضع كود الإعلان هنا -->
    <i class="fas fa-ad" style="color: #94a3b8;"></i> مساحة إعلانية
""", height=80)
st.markdown("</div>", unsafe_allow_html=True)
