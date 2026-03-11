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

# --- Inject ad scripts (replace with actual codes) ---
st.markdown("""
<script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
<script type="text/javascript">
    var infolinks_pid = 1234567;
    var infolinks_wsid = 0;
</script>
<script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
""", unsafe_allow_html=True)

# --- Custom CSS: hide native header, create custom header, remove all whitespace ---
st.markdown("""
<style>
    /* Reset body and app margins */
    body {
        margin: 0 !important;
        padding: 0 !important;
    }
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

    /* Completely hide the native Streamlit header */
    header[data-testid="stHeader"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
        position: absolute !important;
        top: -9999px !important;
    }

    /* Custom header */
    .custom-header {
        background: linear-gradient(135deg, #1976D2, #0D47A1);
        color: white;
        padding: 10px 20px;
        border-radius: 0 0 20px 20px;
        margin: 0 0 20px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        direction: ltr; /* Keep hamburger on left */
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        height: 80px;
        position: relative;
        z-index: 1000;
    }
    .custom-header .hamburger {
        font-size: 2.5rem;
        cursor: pointer;
        user-select: none;
    }
    .custom-header .brand {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-left: auto; /* push to right */
        direction: rtl; /* logo on right, text on left */
    }
    .custom-header .brand img {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        object-fit: cover;
    }
    .custom-header .brand h1 {
        font-size: 2.2rem;
        margin: 0;
        font-weight: 700;
    }

    /* Match list styling (unchanged) */
    .match-list-item {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid #333;
        direction: rtl;
    }
    .match-list-time {
        color: #ffd700;
        font-weight: bold;
        min-width: 50px;
        text-align: center;
        font-size: 0.9rem;
    }
    .match-list-teams {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .match-list-teams img {
        width: 24px;
        height: 24px;
        object-fit: contain;
    }
    .match-list-status {
        color: #888;
        font-size: 0.85rem;
        min-width: 65px;
        text-align: left;
    }
    .match-list-live {
        color: #ff4444;
        animation: pulse 1.5s infinite;
        font-weight: bold;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }

    /* Mobile adjustments */
    @media only screen and (max-width: 768px) {
        .custom-header .brand h1 { font-size: 1.6rem; }
        .custom-header .brand img { width: 45px; height: 45px; }
        .custom-header { height: 70px; }
    }
</style>

<!-- Custom header -->
<div class="custom-header">
    <div class="hamburger" id="hamburgerBtn">☰</div>
    <div class="brand">
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg">
        <h1>Badr TV</h1>
    </div>
</div>

<!-- JavaScript to make hamburger open sidebar -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburgerBtn');
    if (!hamburger) return;

    // Function to find and click the native sidebar toggle
    function clickSidebarToggle() {
        const selectors = [
            'button[data-testid="stSidebarNavToggle"]',
            'button[kind="header"]',
            'button[data-testid="baseButton-header"]',
            'button[title="View sidebar"]',
            'button[aria-label="View sidebar"]'
        ];
        for (const selector of selectors) {
            const btn = document.querySelector(selector);
            if (btn) {
                btn.click();
                return true;
            }
        }
        return false;
    }

    hamburger.addEventListener('click', function() {
        if (!clickSidebarToggle()) {
            // If not found, retry after a short delay (DOM might not be ready)
            setTimeout(clickSidebarToggle, 500);
        }
    });
});
</script>
""", unsafe_allow_html=True)

# --- Sidebar (simplified) ---
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

# --- Admin Panel (only when authenticated) ---
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

# --- Logo auto-linker (only when authenticated) ---
if st.session_state.admin_authenticated and st.session_state.show_admin:
    with st.expander("🖼️ **ربط الشعارات تلقائياً (نسخة محسنة)**"):
        st.markdown("""
        **سيقوم هذا الأمر بالبحث عن شعارات الفرق في مخزن Supabase باستخدام عدة صيغ للأسماء.**  
        يمكنك بعد ذلك تنزيل قائمة الفرق التي لم يتم العثور على شعار لها لمعالجتها يدوياً.
        """)

        st.info("""
        **المجلدات المتوقعة:**
        - Italy - Serie A
        - England - Premier League
        - Spain - LaLiga
        - Germany - Bundesliga
        - France - Ligue 1
        - Portugal - Liga Portugal
        - International - Champions League
        - International - World Cup
        """)

        if st.button("🔍 بدء البحث المتقدم"):
            with st.spinner("جاري البحث عن الشعارات..."):
                teams_resp = supabase.table("matches").select("home_team, away_team").execute()
                teams = set()
                for row in teams_resp.data:
                    if row.get("home_team"):
                        teams.add(row["home_team"])
                    if row.get("away_team"):
                        teams.add(row["away_team"])
                teams = sorted(list(teams))
                total = len(teams)
                st.info(f"تم العثور على {total} فريق في قاعدة البيانات.")

                league_folders = [
                    "Italy - Serie A",
                    "England - Premier League",
                    "Spain - LaLiga",
                    "Germany - Bundesliga",
                    "France - Ligue 1",
                    "Portugal - Liga Portugal",
                    "International - Champions League",
                    "International - World Cup"
                ]

                BUCKET_BASE = f"{SUPABASE_URL}/storage/v1/object/public/logos"
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = {"found": 0, "not_found": 0}
                missing_teams = []

                def generate_name_variations(team_name):
                    variations = [team_name]
                    suffixes = [" FC", " AFC", " United", " City", " Real", " CF", " AC", " AS", " SS", " SC", " Club", " Deportivo", " Futebol", " Clube"]
                    base = team_name
                    for suffix in suffixes:
                        if base.endswith(suffix):
                            base = base[:-len(suffix)]
                            variations.append(base)
                            break
                    variations.append(team_name.replace(" ", "_"))
                    if base != team_name:
                        variations.append(base.replace(" ", "_"))
                    return list(set(variations))

                for i, team in enumerate(teams):
                    status_text.text(f"معالجة {team}... ({i+1}/{total})")
                    name_variations = generate_name_variations(team)
                    found = False
                    for name in name_variations:
                        filename = f"{name}.png"
                        for folder in league_folders:
                            url = f"{BUCKET_BASE}/{folder}/{filename}"
                            try:
                                resp = requests.head(url, timeout=3)
                                if resp.status_code == 200:
                                    supabase.table("team_logos").upsert(
                                        {"team_name": team, "logo_url": url},
                                        on_conflict="team_name"
                                    ).execute()
                                    results["found"] += 1
                                    found = True
                                    st.success(f"✅ {team} -> {folder}/{filename}")
                                    break
                            except:
                                continue
                        if found:
                            break
                    if not found:
                        results["not_found"] += 1
                        missing_teams.append(team)
                        st.warning(f"❌ {team} – لم يتم العثور على شعار")
                    progress_bar.progress((i+1)/total)

                status_text.text("اكتمل البحث!")
                st.success(f"النتائج: تم العثور على {results['found']} شعار، لم يتم العثور على {results['not_found']}")

                if missing_teams:
                    missing_text = "\n".join(missing_teams)
                    st.download_button(
                        label="📥 تنزيل قائمة الفرق بدون شعار",
                        data=missing_text,
                        file_name="missing_logos.txt",
                        mime="text/plain"
                    )
                    st.info("يمكنك استخدام هذه القائمة لإضافة الشعارات يدوياً إلى المجلد المناسب في Supabase.")

        if st.button("🔍 تحديث شعارات البطولات"):
            leagues = get_distinct_leagues()
            if not leagues:
                st.warning("لا توجد بطولات لعرضها.")
            else:
                with st.spinner("جاري البحث عن شعارات البطولات..."):
                    found = 0
                    not_found = 0
                    for league in leagues:
                        name = league.replace(' ', '_')
                        url = f"{SUPABASE_URL}/storage/v1/object/public/logos/leagues/{name}.png"
                        try:
                            resp = requests.head(url, timeout=3)
                            if resp.status_code == 200:
                                supabase.table("league_logos").upsert(
                                    {"league_name": league, "logo_url": url},
                                    on_conflict="league_name"
                                ).execute()
                                st.success(f"✅ {league}")
                                found += 1
                            else:
                                st.warning(f"❌ {league}")
                                not_found += 1
                        except:
                            st.warning(f"❌ {league} (فشل الاتصال)")
                            not_found += 1
                    st.info(f"النتائج: {found} تم العثور عليها، {not_found} لم يتم العثور عليها.")

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
        st.error("عذراً، حدث خطأ في تحميل المباريات.")
        print(f"Error fetching matches: {e}")
        return []

matches = get_filtered_matches(hide_old_finished)

# --- Live Matches ---
st.header("🔥 **المباريات المباشرة الآن**")
live_matches = [m for m in matches if m["status"] == "LIVE"]
if live_matches:
    render_matches_list(live_matches)
else:
    st.info("لا توجد مباريات مباشرة حالياً.")

# --- Upcoming Matches ---
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
    <p style='color: #ccc;'>تبرعك يساعد في توفير خدمة أفضل للجميع.</p>
    <a href='https://www.paypal.com/donate/?hosted_button_id=YOUR_ID' target='_blank'>
        <img src='https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif' alt='Donate'/>
    </a>
</div>
""", unsafe_allow_html=True)

# --- PopAds ---
st.components.v1.html("""
    <script src="//popads.net/pop.js" async></script>
""", height=0)
