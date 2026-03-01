import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import time
import requests
import json
import hashlib

# --- Page config ---
st.set_page_config(
    page_title="مركز الكرة العربية | جميع المباريات العالمية",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Auto-refresh page every 3 minutes ---
st.markdown('<meta http-equiv="refresh" content="180">', unsafe_allow_html=True)

# --- Load secrets ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

# --- Admin password (change this to something secure) ---
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()  # Change this!

# --- Connect to Supabase ---
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = init_supabase()

# --- Session state initialization ---
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False

# --- Inject ad scripts ---
st.markdown("""
<script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
<script type="text/javascript">
    var infolinks_pid = 1234567;
    var infolinks_wsid = 0;
</script>
<script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
""", unsafe_allow_html=True)

# --- Professional RTL styling ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * { font-family: 'Cairo', sans-serif; }
    .main, .block-container, [data-testid="stMarkdownContainer"] { direction: rtl; text-align: right; }
    
    .match-card {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a40 100%);
        color: white;
        padding: 25px;
        border-radius: 20px;
        margin: 20px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        border: 1px solid #333;
        transition: transform 0.3s;
    }
    .match-card:hover { transform: translateY(-5px); }
    
    .featured-card {
        border: 3px solid gold;
        box-shadow: 0 0 20px gold;
    }
    
    .live-badge {
        background: linear-gradient(45deg, #ff4444, #ff6b6b);
        color: white;
        padding: 5px 15px;
        border-radius: 25px;
        font-size: 14px;
        font-weight: bold;
        display: inline-block;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .stream-btn {
        background: #ff6b6b;
        color: white;
        padding: 10px 20px;
        border-radius: 30px;
        text-decoration: none;
        font-weight: 600;
        display: inline-block;
        margin: 5px 10px 5px 0;
        border: none;
        cursor: pointer;
        transition: background 0.3s;
    }
    .stream-btn:hover {
        background: #ff5252;
        color: white;
    }
    
    .admin-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px 20px;
        border-radius: 30px;
        text-decoration: none;
        font-weight: 600;
        display: inline-block;
        margin: 5px;
        border: none;
        cursor: pointer;
    }
    
    .verified {
        background: #4CAF50;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin-left: 5px;
    }
    
    .admin-added {
        background: #ff9800;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin-left: 5px;
    }
    
    .countdown { color: #ffd700; font-weight: bold; }
    .importance-high { color: gold; font-weight: bold; }
    .logo-small { width: 30px; height: 30px; margin: 0 5px; vertical-align: middle; }
    .country-flag { width: 20px; height: 15px; margin: 0 3px; vertical-align: middle; }
    
    .league-filter {
        background: #2a2a40;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    
    .admin-panel {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    st.image("https://img.icons8.com/color/96/000000/football2--v1.png", width=80)
    st.markdown("<h1 style='text-align: center;'>⚽ **مركز الكرة العربية**</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 18px;'>جميع مباريات كرة القدم حول العالم • روابط بث مجانية • تحديثات مباشرة</p>", unsafe_allow_html=True)
    st.markdown("<div class='trust-badge'>✓ أكثر من 1000 بطولة • روابط موثوقة • إدارة يدوية للمباريات الهامة</div>", unsafe_allow_html=True)

st.markdown("---")

# --- Sidebar ---
with st.sidebar:
    st.header("📢 **ادعم الموقع**")
    st.info("الإعلانات تساعدنا في استمرار الخدمة مجاناً للجميع.")
    
    # Affiliate banner
    st.markdown("""
    <a href="https://your-affiliate-link.com" target="_blank">
        <img src="https://your-affiliate-banner-url.com/banner.jpg" style="width:100%; border-radius:10px;">
    </a>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.header("📲 **تابعنا**")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("[![WhatsApp](https://img.icons8.com/color/48/000000/whatsapp--v1.png)](https://whatsapp.com)")
    with cols[1]:
        st.markdown("[![Telegram](https://img.icons8.com/color/48/000000/telegram-app--v1.png)](https://t.me/your_bot)")
    
    st.markdown("---")
    st.header("⚙️ **الإعدادات**")
    low_bandwidth = st.checkbox("وضع الانترنت الضعيف (نص فقط)")
    show_all_leagues = st.checkbox("عرض جميع البطولات", value=True)
    
    # League filter
    st.markdown("---")
    st.header("🏆 **تصفية البطولات**")
    
    # Fetch distinct leagues for filter
    @st.cache_data(ttl=300)
    def get_distinct_leagues():
        response = supabase.table("matches").select("league").execute()
        leagues = list(set([m["league"] for m in response.data if m.get("league")]))
        return sorted(leagues)
    
    all_leagues = get_distinct_leagues()
    selected_leagues = st.multiselect("اختر البطولات", all_leagues, default=[])
    
    # Importance filter
    st.markdown("---")
    st.header("⭐ **أهمية المباراة**")
    min_importance = st.slider("أقل أهمية", 0, 100, 50)
    
    # Admin section
    st.markdown("---")
    st.header("👑 **لوحة التحكم**")
    if not st.session_state.admin_authenticated:
        admin_password = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            if hashlib.sha256(admin_password.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
                st.session_state.admin_authenticated = True
                st.success("تم تسجيل الدخول بنجاح")
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة")
    else:
        st.success("مرحباً أيها المشرف")
        if st.button("إظهار لوحة التحكم"):
            st.session_state.show_admin = not st.session_state.show_admin
        if st.button("تسجيل الخروج"):
            st.session_state.admin_authenticated = False
            st.session_state.show_admin = False
            st.rerun()

# --- Admin Panel (only shown when authenticated) ---
if st.session_state.admin_authenticated and st.session_state.show_admin:
    with st.container():
        st.markdown("<div class='admin-panel'>", unsafe_allow_html=True)
        st.header("👑 **لوحة تحكم المشرف - إضافة روابط يدوية**")
        
        # Fetch upcoming matches for admin selection
        @st.cache_data(ttl=60)
        def get_upcoming_matches():
            response = supabase.table("matches")\
                .select("*")\
                .in_("status", ["UPCOMING", "LIVE"])\
                .order("match_time")\
                .execute()
            return response.data
        
        upcoming = get_upcoming_matches()
        
        if upcoming:
            match_options = {f"{m['home_team']} vs {m['away_team']} ({m['league']})": m['fixture_id'] for m in upcoming}
            selected_match = st.selectbox("اختر المباراة", list(match_options.keys()))
            fixture_id = match_options[selected_match]
            
            col1, col2 = st.columns(2)
            with col1:
                stream_url = st.text_input("رابط البث")
                stream_title = st.text_input("عنوان الرابط (اختياري)")
            with col2:
                stream_source = st.selectbox("المصدر", ["youtube", "facebook", "custom", "official"])
                expiry_hours = st.number_input("عدد ساعات الصلاحية", min_value=1, max_value=24, value=3)
            
            if st.button("إضافة الرابط"):
                if stream_url:
                    expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
                    data = {
                        "fixture_id": fixture_id,
                        "stream_url": stream_url,
                        "stream_title": stream_title or "بث مباشر",
                        "stream_source": stream_source,
                        "expires_at": expires_at,
                        "is_active": True
                    }
                    supabase.table("admin_streams").insert(data).execute()
                    st.success("تم إضافة الرابط بنجاح! سيتم حذفه تلقائياً بعد انتهاء المباراة.")
                    st.cache_data.clear()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("الرجاء إدخال رابط البث")
            
            # Show existing admin streams
            st.markdown("---")
            st.subheader("الروابط الحالية")
            admin_streams = supabase.table("admin_streams")\
                .select("*, matches!inner(home_team, away_team, league, status)")\
                .eq("is_active", True)\
                .execute()\
                .data
            
            if admin_streams:
                for stream in admin_streams:
                    match = stream.get("matches", {})
                    st.markdown(f"""
                    **{match.get('home_team')} vs {match.get('away_team')}**  
                    الرابط: {stream['stream_url']}  
                    ينتهي في: {stream['expires_at'][:16]}
                    """)
                    if st.button(f"حذف #{stream['id']}", key=f"del_{stream['id']}"):
                        supabase.table("admin_streams").update({"is_active": False}).eq("id", stream["id"]).execute()
                        st.success("تم الحذف")
                        st.rerun()
        else:
            st.info("لا توجد مباريات قادمة")
        
        st.markdown("</div>", unsafe_allow_html=True)

# --- Fetch matches with filters ---
@st.cache_data(ttl=60)
def get_filtered_matches(selected_leagues, min_importance, show_all):
    query = supabase.table("matches").select("*")
    
    if selected_leagues:
        query = query.in_("league", selected_leagues)
    
    if min_importance > 0:
        query = query.gte("importance_score", min_importance)
    
    response = query.order("match_time", desc=False).execute()
    return response.data

matches = get_filtered_matches(selected_leagues, min_importance, show_all_leagues)

# --- Helper functions ---
def time_until(match_time_str):
    try:
        match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
        now = datetime.now(match_time.tzinfo)
        diff = match_time - now
        if diff.total_seconds() < 0:
            return "انتهت"
        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)
        return f"{hours} س {minutes} د"
    except:
        return "---"

def get_match_status_display(match):
    if match["status"] == "LIVE":
        minute = match.get("minute")
        if minute:
            return f"🟢 مباشر ({minute}')"
        return "🟢 مباشر"
    elif match["status"] == "UPCOMING":
        return f"⏳ {time_until(match['match_time'])}"
    else:
        return "✅ انتهت"

# --- Featured Matches Section ---
st.header("⭐ **المباريات الهامة اليوم**")
featured = [m for m in matches if m.get("is_featured") or m.get("importance_score", 0) >= 85]

if featured:
    cols = st.columns(3)
    for i, match in enumerate(featured[:6]):  # Show top 6 featured
        with cols[i % 3]:
            streams = match.get("streams", [])
            if isinstance(streams, str):
                try:
                    streams = json.loads(streams)
                except:
                    streams = []
            
            status_display = get_match_status_display(match)
            
            st.markdown(f"""
            <div class="match-card featured-card">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center;">
                        <img src="{match.get('country_logo', '')}" style="width:20px; height:15px; margin-left:5px;">
                        <span style="font-size:12px;">{match.get('country', '')}</span>
                    </div>
                    <span style="color: gold; font-weight: bold;">⭐ مهمة</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin: 10px 0;">
                    <div style="text-align: center;">
                        <img src="{match.get('home_logo', 'https://via.placeholder.com/50')}" style="width:40px; height:40px;">
                        <p>{match['home_team'][:15]}</p>
                    </div>
                    <div style="text-align: center;">
                        <span style="font-size:20px;">vs</span>
                        <p style="font-size:18px; font-weight:bold;">{match['home_score']} - {match['away_score']}</p>
                    </div>
                    <div style="text-align: center;">
                        <img src="{match.get('away_logo', 'https://via.placeholder.com/50')}" style="width:40px; height:40px;">
                        <p>{match['away_team'][:15]}</p>
                    </div>
                </div>
                <p style="text-align: center; color: #ffd700;">{status_display}</p>
                <p style="text-align: center; font-size:12px;">{match['league']}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("لا توجد مباريات مميزة اليوم")

# --- Live Matches Section ---
st.header("🔥 **المباريات المباشرة الآن**")
live_matches = [m for m in matches if m["status"] == "LIVE"]

if live_matches:
    for match in live_matches:
        streams = match.get("streams", [])
        if isinstance(streams, str):
            try:
                streams = json.loads(streams)
            except:
                streams = []
        
        # Check for admin streams
        admin_streams = supabase.table("admin_streams")\
            .select("*")\
            .eq("fixture_id", match["fixture_id"])\
            .eq("is_active", True)\
            .execute()\
            .data
        
        if admin_streams:
            for admin in admin_streams:
                streams.append({
                    "title": admin.get("stream_title", "البث الرسمي"),
                    "url": admin["stream_url"],
                    "source": admin.get("stream_source", "admin"),
                    "verified": True,
                    "admin_added": True
                })
        
        minute = match.get("minute", "")
        with st.container():
            st.markdown(f"""
            <div class="match-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center;">
                        <img src="{match.get('country_logo', '')}" style="width:25px; height:20px; margin-left:10px;">
                        <span>{match.get('country', '')}</span>
                    </div>
                    <span class="live-badge">🔴 مباشر {f"({minute}')" if minute else ""}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin: 15px 0;">
                    <div style="display: flex; align-items: center; flex:1;">
                        <img src="{match.get('home_logo', 'https://via.placeholder.com/50')}" class="logo-small">
                        <h3 style="margin-right:10px;">{match['home_team']}</h3>
                    </div>
                    <div style="font-size: 32px; font-weight: bold; margin: 0 20px;">
                        {match['home_score']} - {match['away_score']}
                    </div>
                    <div style="display: flex; align-items: center; flex:1; justify-content: flex-end;">
                        <h3 style="margin-left:10px;">{match['away_team']}</h3>
                        <img src="{match.get('away_logo', 'https://via.placeholder.com/50')}" class="logo-small">
                    </div>
                </div>
                <p style="margin-top:5px;">🏆 {match['league']} <img src="{match.get('league_logo', '')}" style="width:20px; height:20px; display:inline;"></p>
                <div style="margin-top: 15px;">
                    {"".join([f'<a class="stream-btn" href="{s["url"]}" target="_blank">📺 {s["title"][:30]}... {"<span class=\"verified\">موثوق</span>" if s.get("verified") else ""}{"<span class=\"admin-added\">رسمي</span>" if s.get("admin_added") else ""}</a>' for s in streams]) if streams else "<p>سيتم إضافة روابط البث قريباً...</p>"}
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("لا توجد مباريات مباشرة حالياً. تحقق من المباريات القادمة 👇")

# --- Upcoming Matches by League ---
st.header("📅 **جميع المباريات القادمة**")
upcoming = [m for m in matches if m["status"] == "UPCOMING"]

if upcoming:
    # Group by league
    leagues_dict = {}
    for match in upcoming:
        league = match["league"]
        if league not in leagues_dict:
            leagues_dict[league] = []
        leagues_dict[league].append(match)
    
    # Display each league section
    for league, league_matches in sorted(leagues_dict.items()):
        with st.expander(f"🏆 {league} ({len(league_matches)} مباراة)"):
            cols = st.columns(2)
            for i, match in enumerate(league_matches):
                with cols[i % 2]:
                    streams = match.get("streams", [])
                    if isinstance(streams, str):
                        try:
                            streams = json.loads(streams)
                        except:
                            streams = []
                    
                    time_left = time_until(match['match_time'])
                    match_time = datetime.fromisoformat(match['match_time'].replace('Z', '+00:00')).strftime("%H:%M")
                    
                    importance = match.get("importance_score", 0)
                    star = "⭐" if importance >= 85 else ""
                    
                    st.markdown(f"""
                    <div style="background: #2a2a40; padding: 15px; border-radius: 15px; margin-bottom: 15px;">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center;">
                                <img src="{match.get('home_logo', 'https://via.placeholder.com/30')}" style="width:25px; height:25px; margin-left:5px;">
                                <span>{match['home_team']}</span>
                            </div>
                            <span>vs</span>
                            <div style="display: flex; align-items: center;">
                                <span>{match['away_team']}</span>
                                <img src="{match.get('away_logo', 'https://via.placeholder.com/30')}" style="width:25px; height:25px; margin-right:5px;">
                            </div>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                            <span>⏰ {match_time}</span>
                            <span class="countdown">⏳ {time_left}</span>
                            <span>{star}</span>
                        </div>
                        {"".join([f'<a class="stream-btn" style="padding:5px 10px; font-size:14px;" href="{s["url"]}" target="_blank">▶️ بث</a>' for s in streams[:2]]) if streams else "<p style="color:#aaa">الروابط قبل المباراة بساعة</p>"}
                    </div>
                    """, unsafe_allow_html=True)
else:
    st.write("لا توجد مباريات قادمة حالياً.")

# --- Country/League Statistics ---
st.markdown("---")
st.header("🌍 **البطولات حول العالم**")

@st.cache_data(ttl=3600)
def get_league_stats():
    response = supabase.table("matches").select("league, country, count").execute()
    # Count matches per league
    leagues_count = {}
    for m in response.data:
        league = m.get("league")
        if league:
            leagues_count[league] = leagues_count.get(league, 0) + 1
    
    # Sort by count
    sorted_leagues = sorted(leagues_count.items(), key=lambda x: x[1], reverse=True)[:20]
    return sorted_leagues

league_stats = get_league_stats()

if league_stats:
    cols = st.columns(4)
    for i, (league, count) in enumerate(league_stats[:12]):
        with cols[i % 4]:
            st.markdown(f"**{league}**  \n{count} مباراة")

# --- Footer with donation ---
st.markdown("---")
st.markdown("""
<div style='text-align: center; background: linear-gradient(135deg, #1e1e2f, #2a2a40); padding: 30px; border-radius: 20px;'>
    <h3 style='color: white;'>ادعم استمرارية الموقع</h3>
    <p style='color: #ccc;'>تبرعك يساعد في توفير خدمة أفضل للجميع، خاصة لمن لا يستطيعون الاشتراك.</p>
    <a href='https://www.paypal.com/donate/?hosted_button_id=YOUR_ID' target='_blank'>
        <img src='https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif' alt='Donate'/>
    </a>
    <p style='color: #888; font-size: 12px; margin-top: 20px;'>جميع الروابط مجانية وموثوقة • أكثر من 1000 بطولة حول العالم</p>
</div>
""", unsafe_allow_html=True)

# --- PopAds script ---
st.components.v1.html("""
    <script src="//popads.net/pop.js" async></script>
""", height=0)
