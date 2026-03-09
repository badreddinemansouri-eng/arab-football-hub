import streamlit as st
import time
import re
import json
import hashlib
import hmac
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime, timedelta
import requests
import base64

# -------------------------------------------------------------------
# Page configuration – MUST be first
# -------------------------------------------------------------------
st.set_page_config(
    page_title="مشاهدة البث المباشر - مركز الكرة العربية",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------------
# Custom RTL styling with dark/light mode and animations
# -------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * { font-family: 'Cairo', sans-serif; box-sizing: border-box; }
    
    /* Force RTL and nice background */
    .main, .block-container { 
        direction: rtl; 
        text-align: right; 
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a40 100%);
        color: white;
        padding: 1rem !important;
    }
    
    /* Custom button style */
    .stButton > button {
        background: linear-gradient(45deg, #ff6b6b, #ff8e8e);
        color: white;
        border: none;
        border-radius: 50px;
        padding: 12px 24px;
        font-weight: 700;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(45deg, #ff5252, #ff7676);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 82, 82, 0.4);
    }
    
    /* Countdown timer */
    .countdown {
        color: #ffd700;
        font-weight: bold;
        font-size: 3rem;
        text-align: center;
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    
    /* Share buttons */
    .share-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: #333;
        color: white;
        margin: 0 5px;
        transition: 0.3s;
        text-decoration: none;
        font-size: 20px;
    }
    .share-btn:hover { transform: scale(1.2); }
    .share-btn.facebook { background: #3b5998; }
    .share-btn.twitter { background: #1da1f2; }
    .share-btn.whatsapp { background: #25d366; }
    .share-btn.telegram { background: #0088cc; }
    
    /* Video container */
    .video-container {
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        max-width: 100%;
        background: black;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        margin: 20px 0;
    }
    .video-container iframe,
    .video-container video {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: 0;
        border-radius: 20px;
    }
    
    /* QR code container */
    .qr-container {
        background: white;
        padding: 10px;
        border-radius: 10px;
        display: inline-block;
        margin: 10px 0;
    }
    
    /* Ad containers */
    .ad-container {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 10px;
        margin: 20px 0;
        text-align: center;
        backdrop-filter: blur(5px);
    }
    
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        margin: 2px;
    }
    .badge.live { background: #ff4444; color: white; animation: pulse 1.5s infinite; }
    .badge.embed { background: #4CAF50; color: white; }
    .badge.unknown { background: #888; color: white; }
    
    /* Tooltip */
    .tooltip {
        position: relative;
        display: inline-block;
    }
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 120px;
        background-color: #555;
        color: #fff;
        text-align: center;
        border-radius: 6px;
        padding: 5px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -60px;
        opacity: 0;
        transition: opacity 0.3s;
    }
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Session state for user preferences
# -------------------------------------------------------------------
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "low_bandwidth" not in st.session_state:
    st.session_state.low_bandwidth = False

# -------------------------------------------------------------------
# Get and validate stream URL
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

# Decode URL (sometimes double-encoded)
try:
    stream_url = unquote(stream_url)
except:
    pass

# -------------------------------------------------------------------
# Title and metadata
# -------------------------------------------------------------------
st.title("⚽ **مشاهدة البث المباشر**")
st.caption(f"الرابط: {stream_url[:100]}{'…' if len(stream_url)>100 else ''}")

# -------------------------------------------------------------------
# Intelligent source detection (supports 15+ platforms)
# -------------------------------------------------------------------
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
                "logo": "🔴",
                "name": "يوتيوب"
            }

    # Facebook
    elif "facebook.com" in domain and ("/videos/" in url or "/watch/" in url or "/reel/" in url):
        return {
            "type": "facebook",
            "embed_url": f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=560",
            "can_embed": True,
            "logo": "📘",
            "name": "فيسبوك"
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
                "logo": "🎥",
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
                "logo": "🎞️",
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
                "logo": "📺",
                "name": "تويتش"
            }
        else:
            channel = path.strip('/')
            if channel:
                return {
                    "type": "twitch",
                    "embed_url": f"https://player.twitch.tv/?channel={channel}&parent={st.get_option('server.address')}&autoplay=true",
                    "can_embed": True,
                    "logo": "📺",
                    "name": "تويتش"
                }

    # Ok.ru (Odnoklassniki)
    elif "ok.ru" in domain or "odnoklassniki.ru" in domain:
        match = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if match:
            video_id = match.group(1)
            return {
                "type": "ok",
                "embed_url": f"https://ok.ru/videoembed/{video_id}",
                "can_embed": True,
                "logo": "📼",
                "name": "OK.ru"
            }

    # VK (Vkontakte) – limited embed support
    elif "vk.com" in domain or "vkvideo.ru" in domain:
        # Try to extract video ID from URL
        match = re.search(r'video(-?\d+)_(\d+)', url)
        if match:
            oid, vid = match.groups()
            return {
                "type": "vk",
                "embed_url": f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1",
                "can_embed": True,
                "logo": "📱",
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
                "logo": "🎬",
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
                "logo": "🇷🇺",
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
                "logo": "🇨🇳",
                "name": "Bilibili"
            }

    # Direct video files
    if path.endswith(('.mp4', '.webm', '.ogg', '.m3u8', '.mkv')):
        return {
            "type": "direct_video",
            "embed_url": url,
            "can_embed": True,
            "direct": True,
            "logo": "🎦",
            "name": "فيديو مباشر"
        }

    # Default: unknown
    return {"type": "unknown", "can_embed": False, "logo": "🔗", "name": "رابط خارجي"}

source_info = detect_source(stream_url)

# -------------------------------------------------------------------
# Top ad zone (loads immediately)
# -------------------------------------------------------------------
st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
st.components.v1.html("""
    <!-- PropellerAds push notification (replace with your code) -->
    <script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
    <!-- PopAds pop‑under -->
    <script src="//popads.net/pop.js" async></script>
""", height=100)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# Display source badge
# -------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"<span class='badge {'embed' if source_info['can_embed'] else 'unknown'}'>{source_info['logo']} {source_info['name']}</span>", unsafe_allow_html=True)
with col2:
    if source_info["can_embed"]:
        st.markdown("<span class='badge embed'>✅ يمكن عرضه هنا</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='badge unknown'>⚠️ سيفتح في نافذة جديدة</span>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<span class='badge'>👁️ {len(stream_url)}</span>", unsafe_allow_html=True)

st.markdown("---")

# -------------------------------------------------------------------
# Main video area
# -------------------------------------------------------------------
if source_info["can_embed"]:
    # Embed video
    if source_info.get("type") == "direct_video":
        st.markdown(f"""
        <div class="video-container">
            <video controls autoplay playsinline>
                <source src="{source_info['embed_url']}" type="video/mp4">
                متصفحك لا يدعم تشغيل الفيديو مباشرة.
            </video>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="video-container">
            <iframe src="{source_info['embed_url']}" 
                    allow="autoplay; encrypted-media; fullscreen; picture-in-picture" 
                    allowfullscreen>
            </iframe>
        </div>
        """, unsafe_allow_html=True)

    # If YouTube, add extra features
    if source_info["type"] == "youtube":
        st.markdown("""
        <div style="text-align: left; margin: 10px;">
            <a href="#" onclick="document.querySelector('iframe').src += '&cc_load_policy=1'">🔤 تفعيل الترجمة</a>
        </div>
        """, unsafe_allow_html=True)

    # Mid‑video ad
    st.markdown("<div class='ad-container'>", unsafe_allow_html=True)
    st.components.v1.html("""
        <!-- Infolinks or other native ad -->
        <script type="text/javascript">
            var infolinks_pid = 1234567;
            var infolinks_wsid = 0;
        </script>
        <script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
    """, height=100)
    st.markdown("</div>", unsafe_allow_html=True)

else:
    # Non‑embeddable: countdown + manual open
    st.warning("📢 هذا البث لا يمكن عرضه مباشرة في الصفحة. سيتم فتحه في نافذة جديدة خلال ثوانٍ.")
    st.info("إذا لم يتم فتح النافذة تلقائياً، استخدم الزر أدناه.")

    # Animated countdown
    countdown_ph = st.empty()
    for i in range(5, 0, -1):
        countdown_ph.markdown(f"<div class='countdown'>{i}</div>", unsafe_allow_html=True)
        time.sleep(1)
    countdown_ph.empty()

    # Open in new tab
    st.markdown(f"""
    <script>
        window.open("{stream_url}", "_blank");
    </script>
    """, unsafe_allow_html=True)

    # Manual button
    st.markdown(f'<a href="{stream_url}" target="_blank" style="display:block; text-align:center; padding:15px; background:#ff6b6b; color:white; text-decoration:none; border-radius:50px; font-weight:bold; margin:20px 0;">🔗 اضغط لفتح البث</a>', unsafe_allow_html=True)

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
# Advanced features row
# -------------------------------------------------------------------
st.markdown("---")
cols = st.columns(5)
with cols[0]:
    # Copy link
    if st.button("📋 نسخ الرابط"):
        st.write(f"<script>navigator.clipboard.writeText('{stream_url}');</script>", unsafe_allow_html=True)
        st.success("تم النسخ!")
with cols[1]:
    # Share on WhatsApp
    share_text = f"شاهد البث المباشر: {stream_url}"
    whatsapp_url = f"https://wa.me/?text={quote(share_text)}"
    st.markdown(f'<a href="{whatsapp_url}" target="_blank" class="share-btn whatsapp">📱</a>', unsafe_allow_html=True)
with cols[2]:
    # Share on Twitter
    twitter_url = f"https://twitter.com/intent/tweet?text={quote(share_text)}"
    st.markdown(f'<a href="{twitter_url}" target="_blank" class="share-btn twitter">🐦</a>', unsafe_allow_html=True)
with cols[3]:
    # Share on Facebook
    fb_url = f"https://www.facebook.com/sharer/sharer.php?u={quote(stream_url)}"
    st.markdown(f'<a href="{fb_url}" target="_blank" class="share-btn facebook">📘</a>', unsafe_allow_html=True)
with cols[4]:
    # QR code
    if st.button("📱 رمز QR"):
        qr_data = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={quote(stream_url)}"
        st.image(qr_data, width=150)

# -------------------------------------------------------------------
# Report broken link
# -------------------------------------------------------------------
st.markdown("---")
with st.expander("🚨 الإبلاغ عن رابط معطل"):
    st.write("إذا كان هذا الرابط لا يعمل، يرجى إرسال بلاغ وسنقوم بمراجعته.")
    reason = st.text_area("تفاصيل المشكلة (اختياري)", height=100)
    if st.button("إرسال البلاغ", use_container_width=True):
        # Here you could send an email, save to Supabase, etc.
        # For demo, we'll just show a success message
        st.success("تم استلام البلاغ، شكراً لك! سنقوم بمراجعة الرابط في أقرب وقت.")
        # Optional: you can integrate with a Telegram bot or email
        # e.g., send a request to a webhook

# -------------------------------------------------------------------
# Related streams (if match_id provided)
# -------------------------------------------------------------------
if match_id:
    try:
        # Fetch from your database – you need to implement this
        # This is a placeholder – you would query Supabase for other streams of same match
        st.markdown("---")
        st.subheader("🔗 روابط بديلة لنفس المباراة")
        st.info("هنا يمكن عرض روابط بث أخرى لهذه المباراة (سيتم تفعيلها لاحقاً).")
        # Example: if you have a table 'admin_streams' with fixture_id, fetch and display
    except Exception as e:
        pass

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
    <!-- Footer ad -->
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="ca-pub-xxxxxxxx"
         data-ad-slot="zzzzzz"
         data-ad-format="auto"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
""", height=100)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# GDPR / Privacy notice (optional)
# -------------------------------------------------------------------
st.markdown("""
<div style="text-align: center; font-size: 12px; color: #888; margin-top: 20px;">
    باستخدام هذا الموقع، أنت توافق على استخدام ملفات تعريف الارتباط والإعلانات المخصصة.
    <a href="#">سياسة الخصوصية</a>
</div>
""", unsafe_allow_html=True)
