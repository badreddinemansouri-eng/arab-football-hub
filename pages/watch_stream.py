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
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
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
def get_recent_news(limit=3):
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    res = supabase.table("news").select("*").gte("published_at", cutoff).order("published_at", desc=True).limit(limit).execute()
    return res.data

recent_news = get_recent_news(3)

# -------------------------------------------------------------------
# Intelligent source detection (copied from your original)
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

@st.cache_data(ttl=3600, show_spinner=False)
def extract_embed_url(url):
    """Try to find an embeddable video URL from a webpage."""
    proxies = [
        f"https://api.allorigins.win/raw?url={quote(url)}",
        f"https://cors-anywhere.herokuapp.com/{url}",
        f"https://thingproxy.freeboard.io/fetch/{url}"
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for proxy in proxies:
        try:
            resp = requests.get(proxy, headers=headers, timeout=5)
            if resp.status_code == 200:
                html = resp.text
                # Strategy 1: og:video
                og_video = re.search(r'<meta property="og:video"[^>]+content="([^"]+)"', html)
                if og_video:
                    video_url = og_video.group(1)
                    if 'youtube.com' in video_url or 'youtu.be' in video_url:
                        yt_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', video_url)
                        if yt_match:
                            return f"https://www.youtube.com/embed/{yt_match.group(1)}?autoplay=1"
                    return video_url
                # Strategy 2: twitter:player
                twitter_player = re.search(r'<meta property="twitter:player"[^>]+content="([^"]+)"', html)
                if twitter_player:
                    return twitter_player.group(1)
                # Strategy 3: first iframe src
                iframe_src = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe_src:
                    return iframe_src.group(1)
        except:
            continue
    return None

# -------------------------------------------------------------------
# Custom CSS – modern channel‑list design
# -------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap');
    * { font-family: 'Cairo', sans-serif; }
    .main, .block-container { direction: rtl; text-align: right; padding: 1rem !important; background: linear-gradient(135deg, #0f0f1a, #1a1a2e); }
    .match-header {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border-radius: 30px;
        padding: 25px;
        margin-bottom: 30px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .team-info {
        display: flex;
        align-items: center;
        gap: 20px;
        flex: 1;
    }
    .team-info img {
        width: 60px;
        height: 60px;
        object-fit: contain;
        filter: drop-shadow(0 5px 10px rgba(0,0,0,0.5));
    }
    .team-name {
        font-size: 1.5rem;
        font-weight: 700;
        color: white;
    }
    .match-meta {
        text-align: center;
        color: rgba(255,255,255,0.8);
        font-size: 1.1rem;
    }
    .match-description {
        background: rgba(255,255,255,0.03);
        border-radius: 20px;
        padding: 20px;
        margin: 20px 0;
        color: rgba(255,255,255,0.7);
        line-height: 1.8;
        border: 1px solid rgba(255,255,255,0.05);
    }
    .stream-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 15px;
        margin: 30px 0;
    }
    .stream-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 20px;
        padding: 20px;
        transition: 0.3s;
        text-decoration: none;
        color: white;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
    }
    .stream-card:hover {
        background: rgba(255,255,255,0.15);
        transform: translateY(-5px);
        border-color: #ff4d4d;
    }
    .stream-icon { font-size: 2.5rem; }
    .stream-title { font-weight: 700; font-size: 1.2rem; }
    .stream-source { font-size: 0.9rem; opacity: 0.8; }
    .stream-verified {
        background: #00c853;
        color: white;
        padding: 2px 8px;
        border-radius: 20px;
        font-size: 0.7rem;
        margin-top: 5px;
    }
    .video-container {
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        max-width: 100%;
        background: #000;
        border-radius: 30px;
        box-shadow: 0 25px 50px -12px black;
        margin: 30px 0;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .video-container iframe, .video-container video, .video-container .hls-player {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: 0;
        border-radius: 30px;
    }
    .section-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 40px 0 20px;
        background: linear-gradient(45deg, #ff416c, #ff4b2b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
    }
    .news-card {
        background: rgba(255,255,255,0.05);
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid rgba(255,255,255,0.1);
        transition: 0.3s;
    }
    .news-card:hover { background: rgba(255,255,255,0.08); }
    .news-title {
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 8px;
        color: white;
    }
    .news-title a { color: white; text-decoration: none; }
    .news-meta {
        display: flex;
        gap: 15px;
        color: rgba(255,255,255,0.6);
        font-size: 0.9rem;
    }
    .back-btn {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 50px;
        padding: 8px 20px;
        color: white;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        margin-bottom: 20px;
    }
    .back-btn:hover { background: rgba(255,255,255,0.2); }
    .ad-container {
        background: rgba(0,0,0,0.2);
        border-radius: 20px;
        padding: 15px;
        margin: 20px 0;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.05);
    }
    .theme-toggle {
        position: fixed;
        top: 20px;
        left: 20px;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        border-radius: 50px;
        padding: 10px 20px;
        cursor: pointer;
        border: 1px solid rgba(255,255,255,0.2);
        z-index: 999;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Theme toggle (simple)
# -------------------------------------------------------------------
st.markdown("""
<div class="theme-toggle" onclick="document.body.classList.toggle('light')">
    <span>🌓</span> تبديل المظهر
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Back to home link
# -------------------------------------------------------------------
st.markdown(f'<a href="/" class="back-btn">← العودة إلى الرئيسية</a>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Match header with logos and info
# -------------------------------------------------------------------
home_team = match_data['home_team']
away_team = match_data['away_team']
home_logo = match_data.get('home_logo') or "https://via.placeholder.com/60?text=Home"
away_logo = match_data.get('away_logo') or "https://via.placeholder.com/60?text=Away"
league = match_data.get('league', '')
try:
    utc_time = datetime.fromisoformat(match_data["match_time"].replace('Z', '+00:00'))
    local_time = utc_time.astimezone(tz_tunis)
    time_str = local_time.strftime("%H:%M %Y-%m-%d")
except:
    time_str = "الوقت غير معروف"
status = match_data.get('status', '')
score = f"{match_data.get('home_score','')} - {match_data.get('away_score','')}" if match_data.get('home_score') is not None else "VS"

st.markdown(f"""
<div class="match-header">
    <div class="team-info">
        <img src="{home_logo}">
        <span class="team-name">{home_team}</span>
    </div>
    <div class="match-meta">
        <div>{league}</div>
        <div style="font-size:2rem; font-weight:700; margin:5px 0;">{score}</div>
        <div>{time_str} • {status}</div>
    </div>
    <div class="team-info" style="justify-content:flex-end;">
        <span class="team-name">{away_team}</span>
        <img src="{away_logo}">
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Description (if available)
# -------------------------------------------------------------------
if match_data.get('description'):
    st.markdown(f"<div class='match-description'>{match_data['description']}</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Ad space (top)
# -------------------------------------------------------------------
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <!-- Place your top ad code here -->
    <div style="color: white;">إعلان</div>
""", height=80)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Streams section – modern channel grid
# -------------------------------------------------------------------
st.markdown("<h2 class='section-title'>📺 قائمة البث المتاحة</h2>", unsafe_allow_html=True)

if not all_streams:
    st.warning("لا توجد روابط بث متاحة لهذه المباراة.")
else:
    st.markdown('<div class="stream-grid">', unsafe_allow_html=True)
    for stream in all_streams:
        src = stream.get("source", "custom").lower()
        if "youtube" in src:
            icon = "📺"
        elif "facebook" in src:
            icon = "📘"
        elif "twitch" in src:
            icon = "🎮"
        elif "admin" in src:
            icon = "🔴"
        else:
            icon = "🔗"
        verified_badge = '<span class="stream-verified">✔ رسمي</span>' if stream.get("verified") else ''
        # If we have a selected stream, we might want to embed, but here we just link.
        # We'll pass the stream URL as a query param to reload the page with embedded player.
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
    st.markdown("---")
    st.markdown("<h2 class='section-title'>📺 البث المحدد</h2>", unsafe_allow_html=True)

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
        if source_info.get("type") == "hls" and not st.session_state.extracted_url:
            st.markdown(f"""
            <div class="video-container">
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
            <div class="video-container">
                <video controls autoplay playsinline>
                    <source src="{embed_url}" type="video/mp4">
                </video>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="video-container">
                <iframe src="{embed_url}" 
                        allow="autoplay; encrypted-media; fullscreen; picture-in-picture" 
                        allowfullscreen>
                </iframe>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ لا يمكن عرض البث داخل الصفحة. سيتم فتحه في نافذة جديدة.")
        st.markdown(f'<a href="{selected_stream_url}" target="_blank" style="display:block; background:#ff4d4d; color:white; padding:15px; border-radius:50px; text-align:center; text-decoration:none; font-weight:bold; margin:20px 0;">🔗 فتح البث في نافذة جديدة</a>', unsafe_allow_html=True)

    # Mid‑video ad
    st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
    st.components.v1.html("""
        <!-- Mid‑video ad code here -->
        <div style="color: white;">إعلان</div>
    """, height=80)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Recent news section
# -------------------------------------------------------------------
if recent_news:
    st.markdown("<h2 class='section-title'>📰 آخر الأخبار</h2>", unsafe_allow_html=True)
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
                <span>📰 {source}</span>
                <span>🕒 {date_str}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Share buttons
# -------------------------------------------------------------------
st.markdown("---")
st.markdown("<h2 class='section-title'>📤 شارك هذه المباراة</h2>", unsafe_allow_html=True)
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
    st.markdown(f'<a href="https://wa.me/?text={quote(share_text+" "+page_url)}" target="_blank" class="share-btn" style="display:inline-block; background:#25D366; color:white; padding:10px 20px; border-radius:50px; text-decoration:none;">📱 واتساب</a>', unsafe_allow_html=True)
with cols[1]:
    st.markdown(f'<a href="https://twitter.com/intent/tweet?text={quote(share_text+" "+page_url)}" target="_blank" class="share-btn" style="display:inline-block; background:#1DA1F2; color:white; padding:10px 20px; border-radius:50px; text-decoration:none;">🐦 تويتر</a>', unsafe_allow_html=True)
with cols[2]:
    st.markdown(f'<a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}" target="_blank" class="share-btn" style="display:inline-block; background:#4267B2; color:white; padding:10px 20px; border-radius:50px; text-decoration:none;">📘 فيسبوك</a>', unsafe_allow_html=True)
with cols[3]:
    if st.button("📱 رمز QR"):
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={quote(page_url)}"
        st.image(qr_url, width=150)

# -------------------------------------------------------------------
# Footer ad
# -------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <!-- Footer ad code here -->
    <div style="color: white;">إعلان</div>
""", height=80)
st.markdown("</div>", unsafe_allow_html=True)
