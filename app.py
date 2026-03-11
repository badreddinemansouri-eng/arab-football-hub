import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta, timezone
import time
import requests
import json
import hashlib
import random
import html
import unicodedata
import re
from urllib.parse import quote

# --- Page config ---
st.set_page_config(
    page_title="Badr TV",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------------
# Mobile detection (optional, but keep)
# -------------------------------------------------------------------
st.markdown("""
<script>
(function() {
    const isMobile = window.innerWidth < 768;
    const url = new URL(window.location);
    if (isMobile && !url.searchParams.has('mobile')) {
        url.searchParams.set('mobile', 'true');
        window.location.replace(url);
    } else if (!isMobile && url.searchParams.has('mobile')) {
        url.searchParams.delete('mobile');
        window.location.replace(url);
    }
})();
</script>
""", unsafe_allow_html=True)

mobile_param = st.query_params.get("mobile", [None])
if isinstance(mobile_param, list):
    mobile_param = mobile_param[0]
st.session_state.mobile_view = (mobile_param == "true")

# --- Auto-refresh ---
st.markdown('<meta http-equiv="refresh" content="180">', unsafe_allow_html=True)

# --- Load secrets ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
ADMIN_PASSWORD_HASH = hashlib.sha256("badr11101999.".encode()).hexdigest()

# --- Connect to Supabase ---
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase = init_supabase()

# --- Session state ---
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False

# --- Ad scripts (replace with actual codes) ---
st.markdown("""
<script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
<script type="text/javascript">
    var infolinks_pid = 1234567;
    var infolinks_wsid = 0;
</script>
<script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
""", unsafe_allow_html=True)

# --- Custom CSS: style native header blue, remove top space, add custom logo/title ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * { font-family: 'Cairo', sans-serif; }
    .main, .block-container, [data-testid="stMarkdownContainer"] { direction: rtl; text-align: right; }
    
    /* Remove default top padding */
    .stApp {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    .main > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    .block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
        max-width: 100%;
    }
    
    /* Style the native header */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1976D2 0%, #0D47A1 100%) !important;
        color: white !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        padding: 5px 20px !important;
        height: 60px !important;
        border-radius: 0 0 20px 20px;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
    }
    
    /* Hide the default title text (the page_title) */
    header[data-testid="stHeader"] div:has(> p) {
        display: none !important;
    }
    
    /* Style the hamburger icon (native) */
    header[data-testid="stHeader"] button {
        color: white !important;
    }
    
    /* Our custom elements will be added via JavaScript */
    .custom-header-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .custom-header-left img {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
    }
    .custom-header-left span {
        font-size: 1.8rem;
        font-weight: 700;
    }
</style>

<!-- JavaScript to inject custom logo and title into the native header -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const header = document.querySelector('header[data-testid="stHeader"]');
    if (!header) return;
    
    // Create custom left section
    const customLeft = document.createElement('div');
    customLeft.className = 'custom-header-left';
    customLeft.innerHTML = `
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg">
        <span>Badr TV</span>
    `;
    
    // Insert at the beginning of the header (after the native hamburger maybe)
    // The native hamburger is the first button, we want to keep it.
    const firstChild = header.firstChild;
    header.insertBefore(customLeft, firstChild.nextSibling);
});
</script>
""", unsafe_allow_html=True)

# --- Sidebar (unchanged) ---
with st.sidebar:
    st.header("📢 **ادعم الموقع**")
    st.info("الإعلانات تساعدنا في استمرار الخدمة مجاناً للجميع.")
    
    st.markdown("""
    <a href="https://your-affiliate-link.com" target="_blank">
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/baner.png" style="width:100%; border-radius:10px;">
    </a>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    with st.expander("⚙️ **الإعدادات**", expanded=True):
        low_bandwidth = st.checkbox("وضع الانترنت الضعيف (نص فقط)")
        hide_old_finished = st.checkbox("إخفاء المباريات المنتهية بعد ساعتين", value=True)
    
    with st.expander("👑 **لوحة التحكم**", expanded=False):
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
    
    st.markdown("---")
    st.header("📲 **تابعنا**")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("[![WhatsApp](https://img.icons8.com/color/48/000000/whatsapp--v1.png)](https://whatsapp.com)")
    with cols[1]:
        st.markdown("[![Telegram](https://img.icons8.com/color/48/000000/telegram-app--v1.png)](https://t.me/your_bot)")

# --- Admin Panel (keep as is) ---
if st.session_state.admin_authenticated and st.session_state.show_admin:
    with st.container():
        st.markdown("<div class='admin-panel'>", unsafe_allow_html=True)
        st.header("👑 **لوحة تحكم المشرف - إضافة روابط يدوية**")
        
        @st.cache_data(ttl=60)
        def get_upcoming_matches():
            try:
                response = supabase.table("matches")\
                    .select("*")\
                    .in_("status", ["UPCOMING", "LIVE"])\
                    .order("match_time")\
                    .execute()
                return response.data
            except Exception as e:
                print(f"Error fetching upcoming matches: {e}")
                return []
        
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
                    try:
                        supabase.table("admin_streams").insert(data).execute()
                        st.success("تم إضافة الرابط بنجاح! سيتم حذفه تلقائياً بعد انتهاء المباراة.")
                        st.cache_data.clear()
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error("حدث خطأ أثناء إضافة الرابط.")
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
                        st.markdown(f"""
                        **{match.get('home_team')} vs {match.get('away_team')}**  
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
        with st.form("add_custom_match"):
            custom_home = st.text_input("الفريق المستضيف")
            custom_away = st.text_input("الفريق الضيف")
            custom_league = st.text_input("الدوري")
            custom_date = st.date_input("التاريخ", datetime.now())
            custom_time = st.time_input("الوقت", datetime.now().time())
            custom_stream = st.text_input("رابط البث (اختياري)")
            submitted = st.form_submit_button("إضافة المباراة")
            if submitted and custom_home and custom_away:
                new_id = -random.randint(10000, 99999)
                match_time = datetime.combine(custom_date, custom_time).isoformat()
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
                    "league_logo": None
                }
                supabase.table("matches").insert(data).execute()
                st.success("تمت إضافة المباراة بنجاح")
                st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

# --- Logo auto-linker (keep as is) ---
if st.session_state.admin_authenticated and st.session_state.show_admin:
    with st.expander("🖼️ **ربط الشعارات تلقائياً (نسخة محسنة)**"):
        # ... (unchanged, keep your existing code) ...
        pass

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
        return "<span class='match-list-live'>🔴 مباشر</span>"
    elif match["status"] == "UPCOMING":
        return f"⏳ {time_until(match['match_time'])}"
    else:
        return "✅ انتهت"

def render_matches_list(matches):
    if not matches:
        return
    for match in matches:
        status_display = get_match_status_display(match)
        try:
            match_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00')).strftime("%H:%M")
        except:
            match_time = "--:--"
        
        home_logo = match.get('home_logo') or 'https://upload.wikimedia.org/wikipedia/commons/c/ce/Transparent.gif'
        away_logo = match.get('away_logo') or 'https://upload.wikimedia.org/wikipedia/commons/c/ce/Transparent.gif'
        
        st.markdown(f"""
        <div class="match-list-item">
            <span class="match-list-time">{match_time}</span>
            <span class="match-list-teams">
                <img src="{home_logo}">
                <span>{html.escape(match['home_team'])}</span>
                <span>-</span>
                <span>{html.escape(match['away_team'])}</span>
                <img src="{away_logo}">
            </span>
            <span class="match-list-status">{status_display}</span>
        </div>
        """, unsafe_allow_html=True)

def get_distinct_leagues():
    try:
        response = supabase.table("matches").select("league").execute()
        leagues = list(set([m["league"] for m in response.data if m.get("league")]))
        return sorted(leagues)
    except Exception as e:
        print(f"Error fetching leagues: {e}")
        return []

# --- Fetch matches ---
@st.cache_data(ttl=60)
def get_filtered_matches(hide_old_finished):
    try:
        query = supabase.table("matches").select("*")
        response = query.order("match_time", desc=False).execute()
        matches = response.data
        if hide_old_finished:
            now_utc = datetime.now(timezone.utc)
            cutoff = now_utc - timedelta(hours=2)
            filtered = []
            for match in matches:
                if match["status"] == "FINISHED":
                    try:
                        match_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                        if match_time < cutoff:
                            continue
                    except:
                        pass
                filtered.append(match)
            return filtered
        else:
            return matches
    except Exception as e:
        st.error("عذراً، حدث خطأ في تحميل المباريات. يرجى تحديث الصفحة.")
        print(f"Error fetching matches: {e}")
        return []

matches = get_filtered_matches(hide_old_finished)

# -------------------------------------------------------------------
# Live Matches
# -------------------------------------------------------------------
st.header("🔥 **المباريات المباشرة الآن**")
live_matches = [m for m in matches if m["status"] == "LIVE"]
if live_matches:
    render_matches_list(live_matches)
else:
    st.info("لا توجد مباريات مباشرة حالياً.")

# -------------------------------------------------------------------
# Upcoming Matches
# -------------------------------------------------------------------
st.header("📅 **المباريات القادمة**")
upcoming = [m for m in matches if m["status"] == "UPCOMING"]
if upcoming:
    render_matches_list(upcoming)
else:
    st.write("لا توجد مباريات قادمة حالياً.")

# --- Statistics ---
st.markdown("---")
st.header("🌍 **البطولات حول العالم**")

@st.cache_data(ttl=3600)
def get_league_stats():
    try:
        response = supabase.table("matches").select("league").execute()
        if response.data:
            league_counts = {}
            for match in response.data:
                league = match.get("league")
                if league:
                    league_counts[league] = league_counts.get(league, 0) + 1
            sorted_leagues = sorted(league_counts.items(), key=lambda x: x[1], reverse=True)
            return sorted_leagues[:20]
        return []
    except Exception as e:
        print(f"Error in league stats: {e}")
        return []

league_stats = get_league_stats()
if league_stats:
    cols = st.columns(4)
    for i, (league, count) in enumerate(league_stats[:12]):
        with cols[i % 4]:
            st.markdown(f"**{league}**  \n{count} مباراة")

# --- Footer ---
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
