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
    page_title="مشاهدة البث المباشر - Badr TV",
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
# Get and validate stream URL and match ID
# -------------------------------------------------------------------
stream_url = st.query_params.get("url", [None])
if isinstance(stream_url, list):
    stream_url = stream_url[0] if stream_url else None
match_id = st.query_params.get("match", [None])
if isinstance(match_id, list):
    match_id = match_id[0]

if not stream_url:
    st.error("❌ رابط البث غير صحيح أو مفقود")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# Decode URL
try:
    stream_url = unquote(stream_url)
except:
    pass

# -------------------------------------------------------------------
# Fetch match details if match_id provided
# -------------------------------------------------------------------
match_data = None
if match_id:
    try:
        res = supabase.table("matches").select("*").eq("fixture_id", match_id).execute()
        if res.data:
            match_data = res.data[0]
    except Exception as e:
        st.warning("تعذر تحميل معلومات المباراة")

# -------------------------------------------------------------------
# Title and context
# -------------------------------------------------------------------
if match_data:
    st.title(f"⚽ {match_data['home_team']} vs {match_data['away_team']}")
    try:
        utc_time = datetime.fromisoformat(match_data["match_time"].replace('Z', '+00:00'))
        local_time = utc_time.astimezone(tz_tunis)
        st.caption(f"{match_data['league']} – {local_time.strftime('%H:%M %Y-%m-%d')}")
    except:
        st.caption(match_data['league'])
else:
    st.title("⚽ مشاهدة البث المباشر")

# -------------------------------------------------------------------
# Custom CSS – inherits main app theme + stream page specifics
# -------------------------------------------------------------------
def get_css():
    base_css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { font-family: 'Cairo', sans-serif; box-sizing: border-box; }
        .main, .block-container { direction: rtl; text-align: right; padding: 1rem !important; }
        .stButton > button {
            background: linear-gradient(45deg, #ff4d4d, #ff8080);
            color: white; border: none; border-radius: 50px; padding: 12px 24px;
            font-weight: 700; font-size: 1rem; transition: all 0.3s ease;
            box-shadow: 0 8px 20px rgba(255, 75, 75, 0.3);
        }
        .stButton > button:hover { transform: translateY(-3px); box-shadow: 0 12px 28px rgba(255, 75, 75, 0.4); }
        .video-container {
            position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden;
            max-width: 100%; background: #000; border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5); margin: 20px 0; border: 1px solid #333;
        }
        .video-container iframe, .video-container video, .video-container .hls-player {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; border-radius: 20px;
        }
        .share-btn {
            display: inline-flex; align-items: center; justify-content: center; width: 50px; height: 50px;
            border-radius: 50%; background: rgba(255,255,255,0.1); color: white; margin: 0 5px;
            transition: 0.3s; text-decoration: none; font-size: 22px; backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .share-btn:hover { transform: scale(1.15); background: rgba(255,255,255,0.2); }
        .badge {
            display: inline-block; padding: 6px 14px; border-radius: 30px; font-size: 0.85rem;
            font-weight: 600; margin: 2px; background: rgba(255,255,255,0.1);
            backdrop-filter: blur(5px); border: 1px solid rgba(255,255,255,0.1);
        }
        .badge.live { background: #ff4444; color: white; animation: pulse 1.5s infinite; }
        .badge.embed { background: #2ecc71; color: white; }
        .ad-container {
            background: rgba(0,0,0,0.2); border-radius: 15px; padding: 15px; margin: 20px 0;
            text-align: center; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.05);
        }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
    </style>
    """
    if st.session_state.get("theme", "dark") == "dark":
        return base_css + """
        <style>
            .main, .block-container { background: linear-gradient(135deg, #0f0f1a, #1a1a2e); color: white; }
            .stApp { background: #0f0f1a; }
        </style>
        """
    else:
        return base_css + """
        <style>
            .main, .block-container { background: #f5f5f5; color: #333; }
            .stApp { background: #f5f5f5; }
            .badge { background: rgba(0,0,0,0.05); color: #333; }
        </style>
        """

st.markdown(get_css(), unsafe_allow_html=True)

# -------------------------------------------------------------------
# Intelligent source detection (supports 20+ platforms)
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

    # If nothing matched, return unknown (will trigger extraction)
    return {"type": "unknown", "can_embed": False, "name": "رابط خارجي"}

# -------------------------------------------------------------------
# Advanced extraction function (automatic)
# -------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def extract_embed_url(url):
    """Try to find an embeddable video URL from a webpage."""
    # Try multiple proxies in case one fails
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
                    # If YouTube, convert to embed
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
# Top ad zone
# -------------------------------------------------------------------
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
    <script src="//popads.net/pop.js" async></script>
""", height=100)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Main logic: detect source and automatically extract if needed
# -------------------------------------------------------------------
source_info = detect_source(stream_url)

# If not embeddable or unknown, attempt extraction automatically (only once per session)
if not source_info["can_embed"] and not st.session_state.extraction_attempted:
    st.session_state.extraction_attempted = True
    with st.spinner("🔄 جاري تجهيز البث..."):
        extracted = extract_embed_url(stream_url)
        if extracted:
            st.session_state.extracted_url = extracted
            st.session_state.extraction_failed = False
        else:
            st.session_state.extraction_failed = True
    st.rerun()  # Rerun to show the result

# If extraction succeeded, use that URL as embeddable source
if st.session_state.extracted_url:
    embed_url = st.session_state.extracted_url
    source_name = "بث مستخرج"
    can_embed = True
    is_extracted = True
else:
    embed_url = source_info.get("embed_url") if source_info["can_embed"] else None
    source_name = source_info["name"]
    can_embed = source_info["can_embed"]
    is_extracted = False

# -------------------------------------------------------------------
# Display source badge
# -------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    badge_class = 'embed' if can_embed else 'unknown'
    st.markdown(f"<span class='badge {badge_class}'>📺 {source_name}</span>", unsafe_allow_html=True)
with col2:
    if can_embed:
        st.markdown("<span class='badge embed'>✅ متاح للمشاهدة</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='badge unknown'>⚠️ سيتم الفتح في نافذة جديدة</span>", unsafe_allow_html=True)
with col3:
    st.markdown("<span class='badge'>⚽ بث مباشر</span>", unsafe_allow_html=True)

st.markdown("---")

# -------------------------------------------------------------------
# Video area
# -------------------------------------------------------------------
if can_embed and embed_url:
    # Show extracted note if applicable
    if is_extracted:
        st.success("✅ تم تجهيز البث بنجاح!")

    # HLS special handling
    if source_info.get("type") == "hls" and not is_extracted:
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
    elif source_info.get("type") == "direct_video" and not is_extracted:
        st.markdown(f"""
        <div class="video-container">
            <video controls autoplay playsinline>
                <source src="{embed_url}" type="video/mp4">
            </video>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Standard iframe
        st.markdown(f"""
        <div class="video-container">
            <iframe src="{embed_url}" 
                    allow="autoplay; encrypted-media; fullscreen; picture-in-picture" 
                    allowfullscreen>
            </iframe>
        </div>
        """, unsafe_allow_html=True)

    # Mid‑video ad
    st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
    st.components.v1.html("""
        <script type="text/javascript">
            var infolinks_pid = 1234567;
            var infolinks_wsid = 0;
        </script>
        <script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
    """, height=100)
    st.markdown("</div>", unsafe_allow_html=True)

else:
    # If extraction failed or cannot embed, fallback to opening in new tab
    if st.session_state.extraction_failed:
        st.warning("⚠️ لم نتمكن من تجهيز البث داخل الصفحة. سيتم فتحه في نافذة جديدة.")

    # Countdown and auto-open
    st.info("جاري تحويلك إلى البث...")
    countdown_ph = st.empty()
    for i in range(5, 0, -1):
        countdown_ph.markdown(f"<div class='countdown'>{i}</div>", unsafe_allow_html=True)
        time.sleep(1)
    countdown_ph.empty()

    st.markdown(f"""
    <script>
        window.open("{stream_url}", "_blank");
    </script>
    """, unsafe_allow_html=True)

    st.markdown(f'<a href="{stream_url}" target="_blank" style="display:block; text-align:center; padding:15px; background:#ff4d4d; color:white; text-decoration:none; border-radius:50px; font-weight:bold; margin:20px 0;">🔗 اضغط لفتح البث</a>', unsafe_allow_html=True)

    # Fallback ad
    st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
    st.components.v1.html("""
        <ins class="adsbygoogle"
             style="display:block"
             data-ad-client="ca-pub-xxxxxxxx"
             data-ad-slot="yyyyyy"
             data-ad-format="auto"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
    """, height=100)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Match context & alternative streams (if match_id known)
# -------------------------------------------------------------------
if match_data:
    st.markdown("---")
    st.subheader("📋 معلومات المباراة")
    col1, col2 = st.columns(2)
    with col1:
        st.image(match_data.get('home_logo') or 'https://via.placeholder.com/100', width=80)
        st.write(f"**{match_data['home_team']}**")
        st.write(f" goals: {match_data['home_score']}")
    with col2:
        st.image(match_data.get('away_logo') or 'https://via.placeholder.com/100', width=80)
        st.write(f"**{match_data['away_team']}**")
        st.write(f" goals: {match_data['away_score']}")

    # Fetch other streams for this match (admin and regular)
    all_streams = match_data.get("streams", [])
    if isinstance(all_streams, str):
        try:
            all_streams = json.loads(all_streams)
        except:
            all_streams = []
    try:
        admin_streams = supabase.table("admin_streams").select("*").eq("fixture_id", match_id).eq("is_active", True).execute().data
        for a in admin_streams:
            all_streams.append({"title": a.get("stream_title", "بث إضافي"), "url": a["stream_url"]})
    except:
        pass

    if all_streams:
        st.subheader("🔗 روابط بديلة")
        for s in all_streams:
            st.markdown(f'<a href="/watch_stream?url={quote(s["url"])}&match={match_id}" target="_self" style="display:block; background:#1976d2; color:white; padding:8px; margin:4px 0; border-radius:30px; text-align:center; text-decoration:none;">{s["title"]}</a>', unsafe_allow_html=True)

    # Back to match details
    st.markdown(f'<a href="/match_details?match_id={match_id}" target="_self" style="display:block; margin-top:16px; background:#666; color:white; padding:10px; border-radius:30px; text-align:center; text-decoration:none;">📄 العودة إلى صفحة المباراة</a>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Chat / Comments (lightweight version)
# -------------------------------------------------------------------
st.markdown("---")
st.subheader("💬 تعليقات المشاهدين")
if "user" in st.session_state and st.session_state.user:
    new_comment = st.text_input("اكتب تعليقاً...", key="stream_comment")
    if st.button("إرسال") and new_comment and match_id:
        try:
            supabase.table("comments").insert({
                "match_id": match_id,
                "user_id": st.session_state.user.id,
                "content": new_comment
            }).execute()
            st.success("تم الإرسال")
            st.rerun()
        except:
            st.error("حدث خطأ")
else:
    st.info("سجل الدخول للمشاركة في التعليقات")

if match_id:
    comments = supabase.table("comments").select("*, users(email)").eq("match_id", match_id).order("created_at", desc=True).limit(20).execute()
    if comments.data:
        for c in comments.data:
            user = c.get("users", {}).get("email", "مستخدم") if c.get("users") else "مستخدم"
            st.markdown(f"**{user}**: {c['content']}")
    else:
        st.write("لا توجد تعليقات بعد")

# -------------------------------------------------------------------
# Share buttons – share page URL
# -------------------------------------------------------------------
st.markdown("---")
cols = st.columns(4)
try:
    host = st.context.headers.get('host', '')
    protocol = 'https' if st.context.headers.get('x-forwarded-proto', 'http') == 'https' else 'http'
    base_url = f"{protocol}://{host}"
except:
    base_url = ""
page_url_str = f"{base_url}/watch_stream?url={quote(stream_url)}{'&match='+match_id if match_id else ''}"
share_text = "شاهد البث المباشر على Badr TV"
with cols[0]:
    st.markdown(f'<a href="https://wa.me/?text={quote(share_text+" "+page_url_str)}" target="_blank" class="share-btn whatsapp">📱</a>', unsafe_allow_html=True)
with cols[1]:
    st.markdown(f'<a href="https://twitter.com/intent/tweet?text={quote(share_text+" "+page_url_str)}" target="_blank" class="share-btn twitter">🐦</a>', unsafe_allow_html=True)
with cols[2]:
    st.markdown(f'<a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url_str)}" target="_blank" class="share-btn facebook">📘</a>', unsafe_allow_html=True)
with cols[3]:
    if st.button("📱 رمز QR"):
        qr_data = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={quote(page_url_str)}"
        st.image(qr_data, width=150)

# -------------------------------------------------------------------
# Report broken link
# -------------------------------------------------------------------
st.markdown("---")
with st.expander("🚨 الإبلاغ عن رابط معطل"):
    reason = st.text_area("تفاصيل المشكلة (اختياري)", height=100)
    if st.button("إرسال البلاغ", use_container_width=True):
        # In a real app, you'd save to a reports table
        st.success("تم استلام البلاغ، شكراً لك!")

# -------------------------------------------------------------------
# Back to home
# -------------------------------------------------------------------
st.markdown("---")
if st.button("🏠 العودة إلى الصفحة الرئيسية", use_container_width=True):
    st.switch_page("app.py")

# -------------------------------------------------------------------
# Footer ad
# -------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"></script>
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="ca-pub-xxxxxxxx"
         data-ad-slot="zzzzzz"
         data-ad-format="auto"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
""", height=100)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# GDPR / Privacy notice
# -------------------------------------------------------------------
st.markdown("""
<div style="text-align: center; font-size: 12px; color: #888; margin-top: 20px;">
    باستخدام هذا الموقع، أنت توافق على استخدام ملفات تعريف الارتباط والإعلانات المخصصة.
    <a href="#">سياسة الخصوصية</a>
</div>
""", unsafe_allow_html=True)
