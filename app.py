import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import hashlib
import random
import time
import requests
import zoneinfo
from urllib.parse import quote
import html
import textwrap
from utils.auth import sign_up, sign_in, sign_out, load_favorites, load_profile, toggle_favorite
from utils.logos import get_team_logo, get_league_logo

# -------------------- Page Config --------------------
st.set_page_config(
    page_title="Badr TV | منصة كرة القدم الشاملة",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------- Load Secrets --------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------- Timezone --------------------
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

# -------------------- Session State --------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "profile" not in st.session_state:
    st.session_state.profile = None
if "favorites" not in st.session_state:
    st.session_state.favorites = []
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = False
if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False

# -------------------- Custom CSS --------------------
def get_css():
    base_css = textwrap.dedent("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { font-family: 'Cairo', sans-serif; }
        .main, .block-container { direction: rtl; text-align: right; }

        /* Hide the default Streamlit header completely */
        header[data-testid="stHeader"] {
            display: none !important;
        }

        /* Style the hamburger button (Streamlit button) */
        .stButton > button {
            background: none !important;
            border: none !important;
            font-size: 1.8rem !important;
            font-weight: bold !important;
            color: white !important;
            padding: 0 !important;
            margin: 0 !important;
            width: auto !important;
        }

        /* Match card styling */
        .match-card {
            border-radius: 20px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { border-radius: 20px; padding: 8px 16px; }
        /* Professional search bar */
        .search-container {
            position: relative;
            width: 100%;
            margin-bottom: 20px;
        }
        .search-container input {
            width: 100%;
            padding: 12px 45px 12px 15px;
            border: 1px solid #444;
            border-radius: 30px;
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 1rem;
            outline: none;
            transition: all 0.3s;
        }
        .search-container input:focus {
            border-color: #1976d2;
            box-shadow: 0 0 8px #1976d2;
        }
        .search-container::after {
            content: "🔍";
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1.2rem;
            color: #aaa;
            pointer-events: none;
        }
        .last-updated {
            text-align: left;
            color: #888;
            font-size: 0.8rem;
            margin-bottom: 10px;
        }
        /* News card styles */
        .news-card {
            background: #ffffff;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
            transition: transform 0.2s;
            direction: rtl;
        }
        .news-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }
        .news-image {
            width: 100%;
            max-height: 150px;
            object-fit: cover;
            border-radius: 12px;
            margin-bottom: 10px;
        }
        .news-title {
            font-size: 1.3rem;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: #333;
            text-decoration: none;
        }
        .news-title a {
            color: #333;
            text-decoration: none;
        }
        .news-title a:hover {
            color: #1976d2;
        }
        .news-content {
            color: #666;
            margin: 0 0 12px 0;
            line-height: 1.6;
        }
        .news-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #888;
            font-size: 0.9rem;
            flex-wrap: wrap;
        }
        .source-badge {
            background: #1976d2;
            color: white;
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
        }
        .lang-badge {
            background: #166534;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
        }
        .lang-badge.en {
            background: #1e3a8a;
        }
        @media (prefers-color-scheme: dark) {
            .news-card {
                background: #1e1e2e;
                border-color: #333;
            }
            .news-title a {
                color: #f0f0f0;
            }
            .news-content {
                color: #aaa;
            }
        }
        /* Table styling for standings */
        .standings-table {
            width: 100%;
            border-collapse: collapse;
            text-align: center;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            overflow: hidden;
        }
        .standings-table th {
            background: #1976d2;
            color: white;
            padding: 10px;
        }
        .standings-table td {
            padding: 8px;
            border-bottom: 1px solid #444;
        }
        .standings-table a {
            color: inherit;
            text-decoration: none;
        }
        .standings-table a:hover {
            text-decoration: underline;
        }
        .live-badge {
            background: #ff4d4d;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            display: inline-block;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.05); }
            100% { opacity: 1; transform: scale(1); }
        }
        /* Hide deploy button and GitHub icon (just in case) */
        .stDeployButton,
        .stAppDeployButton,
        [data-testid="stToolbar"] {
            display: none !important;
        }
        /* Ensure the custom header container uses flex and columns are transparent */
        .custom-header-container {
            display: flex;
            align-items: center;
        }
        .custom-header-container div[data-testid="column"] {
            background: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        .custom-header-container .stButton > button {
            background: none !important;
            border: none !important;
            font-size: 1.8rem !important;
            font-weight: bold !important;
            color: white !important;
            padding: 0 !important;
            margin: 0 !important;
            width: auto !important;
        }
    </style>
    """)
    if st.session_state.theme == "dark":
        return base_css + textwrap.dedent("""
        <style>
            .main, .block-container { background: #0f0f1a; color: white; }
            .match-card { background: #1a1a2e; }
            .stTabs [data-baseweb="tab"] { background-color: transparent; color: white; }
            .stTabs [aria-selected="true"] { background-color: #1976d2; }
            .search-container input { background: rgba(255,255,255,0.1); color: white; border-color: #444; }
            .standings-table { background: #1a1a2e; }
        </style>
        """)
    else:
        return base_css + textwrap.dedent("""
        <style>
            .main, .block-container { background: #f5f5f5; color: #333; }
            .match-card { background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .stTabs [data-baseweb="tab"] { background-color: transparent; color: #333; }
            .stTabs [aria-selected="true"] { background-color: #1976d2; color: white; }
            .search-container input { background: white; color: #333; border-color: #ccc; }
            .standings-table { background: white; }
        </style>
        """)

st.markdown(get_css(), unsafe_allow_html=True)

# -------------------- Custom Header with Hamburger Button --------------------
st.markdown("""
<div class="custom-header-container" style="background: linear-gradient(135deg, #1976D2, #0D47A1);
            border-radius: 0 0 20px 20px;
            padding: 10px 20px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;">
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 10])   # button left, content right
with col1:
    if st.button("☰", key="sidebar_toggle", use_container_width=True):
        st.session_state.sidebar_open = not st.session_state.sidebar_open
        st.rerun()
with col2:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 15px;">
        <img src="https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg" style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover;">
        <h1 style="font-size: 2.2rem; margin: 0; font-weight: 700; color: white;">Badr TV</h1>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
# Keep the timestamp as originally placed
st.markdown(f'<div class="last-updated">آخر تحديث: {datetime.now(tz_tunis).strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

# -------------------- Custom Sidebar (controlled by button) --------------------
if st.session_state.sidebar_open:
    sidebar_col, main_col = st.columns([1, 3])   # adjust sidebar width as needed
    with sidebar_col:
        # ---------- SIDEBAR CONTENT (copied from your original) ----------
        st.header("👤 الحساب")
        if st.session_state.user:
            st.write(f"مرحباً {st.session_state.user.email}")
            if st.button("تسجيل الخروج", key="logout_main"):
                sign_out()
        else:
            with st.expander("تسجيل الدخول"):
                email = st.text_input("البريد الإلكتروني", key="login_email")
                password = st.text_input("كلمة المرور", type="password", key="login_password")
                if st.button("دخول", key="login_main"):
                    sign_in(email, password)
            with st.expander("إنشاء حساب"):
                new_email = st.text_input("البريد الإلكتروني", key="signup_email")
                new_pass = st.text_input("كلمة المرور", type="password", key="signup_pass")
                if st.button("تسجيل", key="signup_main"):
                    sign_up(new_email, new_pass)

        st.markdown("---")
        st.header("⚙️ الإعدادات")
        theme = st.radio("المظهر", ["داكن", "فاتح"], index=0 if st.session_state.theme=="dark" else 1, key="theme_radio")
        if theme == "داكن" and st.session_state.theme != "dark":
            st.session_state.theme = "dark"
            st.rerun()
        elif theme == "فاتح" and st.session_state.theme != "light":
            st.session_state.theme = "light"
            st.rerun()
        
        st.markdown("---")
        st.markdown('<div class="search-container">', unsafe_allow_html=True)
        search_query = st.text_input(" ", label_visibility="collapsed", key="search_input", placeholder="ابحث عن فريق أو لاعب")
        st.markdown('</div>', unsafe_allow_html=True)
        if search_query:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**الفرق**")
                teams = supabase.table("teams").select("id, name, logo").ilike("name", f"%{search_query}%").execute()
                for t in teams.data:
                    st.markdown(f"[{t['name']}](/team?team_id={t['id']})")
            with col2:
                st.markdown("**اللاعبين**")
                players = supabase.table("players").select("id, name, photo").ilike("name", f"%{search_query}%").execute()
                for p in players.data:
                    st.markdown(f"[{p['name']}](/player?player_id={p['id']})")

        st.markdown("---")
        st.header("⭐ المفضلة")
        if st.session_state.user:
            if st.session_state.favorites:
                for team in st.session_state.favorites:
                    st.write(f"• {team}")
            else:
                st.info("لا توجد فرق مفضلة بعد")
        else:
            st.info("سجل الدخول لرؤية مفضلتك")

        # -------------------- Admin Panel --------------------
        st.markdown("---")
        with st.expander("👑 **لوحة التحكم**", expanded=False):
            if not st.session_state.admin_auth:
                admin_pass = st.text_input("كلمة المرور", type="password", key="admin_pass")
                if st.button("دخول", key="admin_login"):
                    if hashlib.sha256(admin_pass.encode()).hexdigest() == "f00bf9d13f09fa3962d4a7d21de2479699adc840b74e34195a0eedb6dd45ceb4":
                        st.session_state.admin_auth = True
                        st.success("تم تسجيل الدخول بنجاح")
                        st.rerun()
                    else:
                        st.error("كلمة المرور غير صحيحة")
            else:
                st.success("مرحباً أيها المشرف")
                if st.button("إظهار لوحة التحكم", key="show_admin_btn"):
                    st.session_state.show_admin = not st.session_state.show_admin
                if st.button("تسجيل الخروج", key="admin_logout"):
                    st.session_state.admin_auth = False
                    st.session_state.show_admin = False
                    st.rerun()

        if st.session_state.get("admin_auth") and st.session_state.get("show_admin"):
            with st.container():
                st.markdown("---")
                st.markdown("### 👑 لوحة تحكم المشرف - إضافة روابط يدوية")

                @st.cache_data(ttl=60)
                def get_upcoming_matches():
                    try:
                        resp = supabase.table("matches")\
                            .select("*")\
                            .in_("status", ["UPCOMING", "LIVE"])\
                            .order("match_time")\
                            .execute()
                        return resp.data
                    except Exception as e:
                        print(f"Error fetching upcoming matches: {e}")
                        return []

                upcoming = get_upcoming_matches()
                if upcoming:
                    match_data = {}
                    for m in upcoming:
                        try:
                            utc_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
                            local_time = utc_time.astimezone(tz_tunis)
                            time_str = local_time.strftime("%H:%M")
                        except:
                            time_str = "--:--"
                        label = f"{time_str} - {m['home_team']} vs {m['away_team']} ({m['league']})"
                        match_data[label] = (m['fixture_id'], m['source'])
                    selected_match = st.selectbox("اختر المباراة", list(match_data.keys()), key="match_select")
                    fixture_id, match_source = match_data[selected_match]

                    col1, col2 = st.columns(2)
                    with col1:
                        stream_url = st.text_input("رابط البث", key="stream_url")
                        stream_title = st.text_input("عنوان الرابط (اختياري)", key="stream_title")
                    with col2:
                        stream_source = st.selectbox("المصدر", ["youtube", "facebook", "custom", "official"], key="stream_source")
                        expiry_hours = st.number_input("عدد ساعات الصلاحية", min_value=1, max_value=24, value=3, key="expiry_hours")

                    if st.button("إضافة الرابط", key="add_stream_btn"):
                        if stream_url:
                            expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
                            data = {
                                "fixture_id": fixture_id,
                                "source": match_source,
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
                                st.error(f"حدث خطأ أثناء إضافة الرابط: {str(e)}")
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
                                try:
                                    utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                                    local_time = utc_time.astimezone(tz_tunis)
                                    time_str = local_time.strftime("%H:%M")
                                except:
                                    time_str = "--:--"
                                st.markdown(f"""
                                **{match.get('home_team')} vs {match.get('away_team')}**  
                                الوقت: {time_str}  
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
                with st.form("add_custom_match_form"):
                    custom_home = st.text_input("الفريق المستضيف")
                    custom_away = st.text_input("الفريق الضيف")
                    custom_league = st.text_input("الدوري")
                    custom_date = st.date_input("التاريخ", datetime.now())
                    custom_time = st.time_input("الوقت", datetime.now().time(), key="custom_match_time")
                    custom_stream = st.text_input("رابط البث (اختياري)")
                    submitted = st.form_submit_button("إضافة المباراة")
                    if submitted and custom_home and custom_away:
                        print(f"Input local datetime: {custom_date} {custom_time} (assumed Africa/Tunis)")
                        local_dt = datetime.combine(custom_date, custom_time).replace(tzinfo=tz_tunis)
                        utc_dt = local_dt.astimezone(timezone.utc)
                        match_time = utc_dt.isoformat()
                        new_id = -random.randint(10000, 99999)
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
                            "league_logo": None,
                            "source": "custom",
                            "is_custom": True
                        }
                        supabase.table("matches").insert(data).execute()
                        st.success("تمت إضافة المباراة بنجاح")
                        st.rerun()

                st.markdown("---")
                st.subheader("🖼️ ربط الشعارات تلقائياً")
                with st.expander("ربط شعارات الفرق"):
                    st.markdown("""
                    **سيقوم هذا الأمر بالبحث عن شعارات الفرق في مخزن Supabase باستخدام عدة صيغ للأسماء.**  
                    يمكنك بعد ذلك تنزيل قائمة الفرق التي لم يتم العثور على شعار لها لمعالجتها يدوياً.
                    """)
                    st.info("""
                    **المجلدات المتوقعة:**  
                    Italy - Serie A, England - Premier League, Spain - LaLiga, Germany - Bundesliga, France - Ligue 1, Portugal - Liga Portugal, International - Champions League, International - World Cup
                    """)

                    if st.button("🔍 بدء البحث المتقدم", key="search_team_logos"):
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
                                "Italy - Serie A", "England - Premier League", "Spain - LaLiga",
                                "Germany - Bundesliga", "France - Ligue 1", "Portugal - Liga Portugal",
                                "International - Champions League", "International - World Cup"
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

                with st.expander("ربط شعارات البطولات"):
                    if st.button("🔍 تحديث شعارات البطولات", key="search_league_logos"):
                        leagues_resp = supabase.table("matches").select("league").execute()
                        leagues = list(set([m["league"] for m in leagues_resp.data if m.get("league")]))
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

    with main_col:
        # -------------------- Data Fetching --------------------
        def get_matches():
            resp = supabase.table("matches").select("*").order("match_time", desc=False).execute()
            return resp.data

        matches = get_matches()

        # -------------------- Helper Functions --------------------
        def time_until(match_time_str):
            try:
                match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
                now = datetime.now(datetime.timezone.utc)
                diff = match_time - now
                if diff.total_seconds() < 0:
                    return "انتهت"
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                return f"{hours} س {minutes} د"
            except:
                return "---"

        def render_match_card(match, show_favorite=True):
            home_team = html.escape(match.get('home_team', '???'))
            away_team = html.escape(match.get('away_team', '???'))
            home_logo = match.get('home_logo') or get_team_logo(home_team)
            away_logo = match.get('away_logo') or get_team_logo(away_team)
            league_logo = match.get('league_logo') or get_league_logo(match.get('league', ''))
            league_name = html.escape(match.get('league', ''))

            effective_status = match['status']
            if effective_status != 'FINISHED':
                try:
                    match_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                    now = datetime.now(datetime.timezone.utc)
                    if now - match_time > timedelta(hours=3):
                        effective_status = 'FINISHED'
                except:
                    pass

            if effective_status == 'LIVE':
                center = f"<span style='color:#d32f2f; font-weight:bold; font-size:1.8rem;'>{match['home_score']} - {match['away_score']}</span>"
                status_display = '<span class="live-badge">🔴 مباشر</span>'
            elif effective_status == 'UPCOMING':
                try:
                    utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    today = datetime.now(tz_tunis).date()
                    match_date = local_time.date()
                    if match_date == today:
                        diff = (local_time - datetime.now(tz_tunis)).total_seconds() / 60
                        if 0 < diff <= 30:
                            status_display = "<span style='color:#ff8c00;'>⏳ بعد قليل</span>"
                        else:
                            status_display = "<span style='color:#666;'>لم تبدأ بعد</span>"
                        center = f"<span style='color:#1976d2; font-weight:bold; font-size:1.8rem;'>{local_time.strftime('%H:%M')}</span>"
                    else:
                        status_display = f"<span style='color:#888;'>{match_date.strftime('%m-%d')}</span>"
                        center = f"<span style='color:#1976d2; font-weight:bold; font-size:1.8rem;'>{local_time.strftime('%H:%M')}</span>"
                except Exception as e:
                    status_display = "<span style='color:#666;'>لم تبدأ بعد</span>"
                    center = "--:--"
            else:
                try:
                    utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    status_display = f"<span style='color:#888;'>{local_time.strftime('%m-%d')}</span>"
                    center = f"<span style='color:#888; font-weight:bold; font-size:1.5rem;'>{match['home_score']} - {match['away_score']}</span>"
                except:
                    status_display = "<span style='color:#888;'>انتهت</span>"
                    center = f"{match['home_score']} - {match['away_score']}"

            return f"""
            <a href="/watch_stream?match_id={match['fixture_id']}" style="text-decoration:none; color:inherit; display:block;">
                <div class="match-card">
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                        <div style="flex:1; text-align:center;">
                            <img src="{home_logo}" style="width:48px; height:48px; object-fit:contain; margin-bottom:6px;">
                            <div style="font-weight:600; font-size:0.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px; margin:0 auto;">{home_team}</div>
                        </div>
                        <div style="flex:1; text-align:center;">
                            {center}
                            <div style="margin-top:4px;">{status_display}</div>
                        </div>
                        <div style="flex:1; text-align:center;">
                            <img src="{away_logo}" style="width:48px; height:48px; object-fit:contain; margin-bottom:6px;">
                            <div style="font-weight:600; font-size:0.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px; margin:0 auto;">{away_team}</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap:8px; margin-top:12px; padding-top:8px; border-top:1px solid #444;">
                        <img src="{league_logo}" style="width:20px; height:20px; object-fit:contain;">
                        <span style="color:#aaa;">{league_name}</span>
                    </div>
                </div>
            </a>
            """

        # -------------------- Tabs --------------------
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📅 المباريات", "📊 النتائج", "🏆 الترتيب", "⭐ المفضلة", "📰 الأخبار", "🔮 التوقعات"])

        with tab1:
            st.header("🔥 المباريات المباشرة الآن")
            live_result = supabase.table("matches").select("*").eq("status", "LIVE").execute()
            live_matches = live_result.data
            if live_matches:
                for m in live_matches:
                    st.markdown(render_match_card(m), unsafe_allow_html=True)
            else:
                st.info("لا توجد مباريات مباشرة حالياً")

            st.header("📅 المباريات القادمة")
            upcoming_result = supabase.table("matches")\
                .select("*")\
                .eq("status", "UPCOMING")\
                .order("match_time")\
                .execute()
            upcoming = upcoming_result.data
            if upcoming:
                for m in upcoming:
                    st.markdown(render_match_card(m), unsafe_allow_html=True)
            else:
                st.write("لا توجد مباريات قادمة")

        with tab2:
            st.header("📊 النتائج")
            finished_result = supabase.table("matches")\
                .select("*")\
                .eq("status", "FINISHED")\
                .order("match_time", desc=True)\
                .execute()
            finished = finished_result.data
            if finished:
                for m in finished:
                    home_team = html.escape(m['home_team'])
                    away_team = html.escape(m['away_team'])
                    home_logo = m.get('home_logo') or get_team_logo(home_team)
                    away_logo = m.get('away_logo') or get_team_logo(away_team)
                    try:
                        utc_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
                        local_time = utc_time.astimezone(tz_tunis)
                        date_str = local_time.strftime('%Y-%m-%d')
                    except:
                        date_str = "---"
                    st.markdown(f"""
                    <a href="/match_details?match_id={m['fixture_id']}" style="text-decoration:none; color:inherit; display:block;">
                        <div class="match-card">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <div style="flex:1; text-align:center;">
                                    <img src="{home_logo}" style="width:32px; height:32px; object-fit:contain;">
                                    <div>{home_team}</div>
                                </div>
                                <div><strong style="font-size:1.2rem;">{m['home_score']} - {m['away_score']}</strong></div>
                                <div style="flex:1; text-align:center;">
                                    <img src="{away_logo}" style="width:32px; height:32px; object-fit:contain;">
                                    <div>{away_team}</div>
                                </div>
                            </div>
                            <div style="text-align:center; color:#aaa; margin-top:8px;">
                                {html.escape(m.get('league',''))} • {date_str}
                            </div>
                        </div>
                    </a>
                    """, unsafe_allow_html=True)
            else:
                st.info("لا توجد نتائج بعد")

        with tab3:
            st.header("🏆 جدول الترتيب")
            try:
                @st.cache_data(ttl=3600)
                def get_competitions_with_standings():
                    resp = supabase.table("standings").select("competition_code, competition_name, data").execute()
                    return resp.data if resp.data else []

                comps = get_competitions_with_standings()
                if not comps:
                    st.info("لا توجد ترتيبات متاحة حالياً")
                else:
                    comp_names = [c["competition_name"] for c in comps]
                    selected_comp = st.selectbox("اختر البطولة", comp_names, key="standings_select")
                    comp_data = next(c for c in comps if c["competition_name"] == selected_comp)
                    standings = comp_data["data"].get("standings", [])
                    if not standings:
                        st.warning("لا توجد معلومات ترتيب لهذه البطولة")
                    else:
                        table = standings[0].get("table", [])
                        if table:
                            html_table = '<div style="overflow-x: auto;">'
                            html_table += '<table class="standings-table">'
                            html_table += '<thead> capital< th>المركز</th><th>الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له</th><th>عليه</th><th>فارق</th><th>نقاط</th> </thead>'
                            for row in table:
                                team_id = row["team"]["id"]
                                team_name = row["team"]["name"]
                                html_table += '<tr>'
                                html_table += f'<td>{row["position"]}</td>'
                                html_table += f'<td><a href="/team?team_id={team_id}" style="color: inherit; text-decoration: none;">{team_name}</a></td>'
                                html_table += f'<td>{row["playedGames"]}</td>'
                                html_table += f'<td>{row["won"]}</td>'
                                html_table += f'<td>{row["draw"]}</td>'
                                html_table += f'<td>{row["lost"]}</td>'
                                html_table += f'<td>{row["goalsFor"]}</td>'
                                html_table += f'<td>{row["goalsAgainst"]}</td>'
                                html_table += f'<td>{row["goalDifference"]}</td>'
                                html_table += f'<td>{row["points"]}</td>'
                                html_table += '</tr>'
                            html_table += '</table>'
                            html_table += '</div>'
                            st.markdown(html_table, unsafe_allow_html=True)
                        else:
                            st.info("لا توجد بيانات جدول متاحة")
            except Exception as e:
                if "relation" in str(e) or "does not exist" in str(e):
                    st.warning("جدول الترتيب غير موجود. يرجى تشغيل السكربت الكامل لإنشاء الجداول المطلوبة.")
                else:
                    st.error(f"حدث خطأ: {e}")

        with tab4:
            st.header("⭐ مبارياتي المفضلة")
            if st.session_state.user:
                if st.session_state.favorites:
                    fav_matches = [m for m in matches if m['home_team'] in st.session_state.favorites or m['away_team'] in st.session_state.favorites]
                    if fav_matches:
                        for m in fav_matches:
                            st.markdown(render_match_card(m, show_favorite=False), unsafe_allow_html=True)
                    else:
                        st.info("لا توجد مباريات لفرقك المفضلة حالياً")
                else:
                    st.info("أضف فرقاً إلى المفضلة من خلال الضغط على ☆ في بطاقة المباراة")
            else:
                st.info("سجل الدخول لاستخدام المفضلة")

        with tab5:
            st.header("📰 آخر الأخبار")

            @st.cache_data(ttl=3600)
            def get_news():
                cutoff = (datetime.now() - timedelta(days=14)).isoformat()
                try:
                    res = supabase.table("news")\
                        .select("*")\
                        .gte("published_at", cutoff)\
                        .order("published_at", desc=True)\
                        .limit(50)\
                        .execute()
                    return res.data
                except Exception as e:
                    st.error(f"حدث خطأ في جلب الأخبار: {e}")
                    return []

            news = get_news()
            if not news:
                st.info("لا توجد أخبار حالياً")
            else:
                for item in news:
                    safe_title = html.escape(item.get('title', ''))
                    safe_content = html.escape(item.get('content', ''))[:200] + "..." if item.get('content') else ''
                    safe_source = html.escape(item.get('source', 'مصدر غير معروف'))
                    safe_url = html.escape(item.get('url', ''))
                    safe_image = html.escape(item.get('image', '')) if item.get('image') else None

                    try:
                        pub_date = datetime.fromisoformat(item["published_at"].replace('Z', '+00:00'))
                        date_str = pub_date.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_str = "تاريخ غير معروف"

                    lang = item.get("language", "ar")
                    lang_badge = '<span class="lang-badge en">🇬🇧 EN</span>' if lang == "en" else '<span class="lang-badge">🇸🇦 AR</span>'

                    card_html = '<div class="news-card">'
                    if safe_image:
                        card_html += f'<img src="{safe_image}" class="news-image">'
                    card_html += f'''
                        <a href="{safe_url}" target="_blank" class="news-title">
                            <h3>{safe_title}</h3>
                        </a>
                        <div class="news-content">{safe_content}</div>
                        <div class="news-meta">
                            <span class="source-badge">📰 {safe_source}</span>
                            <span>🕒 {date_str}</span>
                            {lang_badge}
                        </div>
                    </div>
                    '''
                    try:
                        if hasattr(st, 'html'):
                            st.html(card_html)
                        else:
                            st.markdown(card_html, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"حدث خطأ في عرض الخبر: {e}")

        with tab6:
            st.header("🔮 توقعات المباريات")
            upcoming_pred = supabase.table("matches").select("fixture_id, home_team, away_team, match_time").eq("status", "UPCOMING").order("match_time").limit(10).execute()
            for m in upcoming_pred.data:
                pred = supabase.table("predictions").select("*").eq("fixture_id", m["fixture_id"]).execute()
                if pred.data:
                    p = pred.data[0]
                    st.write(f"{m['home_team']} vs {m['away_team']}")
                    st.progress(p["home_win_prob"], text=f"فوز {m['home_team']}")
                    st.progress(p["draw_prob"], text="تعادل")
                    st.progress(p["away_win_prob"], text=f"فوز {m['away_team']}")
                else:
                    st.write(f"{m['home_team']} vs {m['away_team']} – لا توجد توقعات بعد")

else:
    # When sidebar is closed, use a single column for the main content
    main_col = st.container()
    with main_col:
        # -------------------- Data Fetching --------------------
        def get_matches():
            resp = supabase.table("matches").select("*").order("match_time", desc=False).execute()
            return resp.data

        matches = get_matches()

        # -------------------- Helper Functions --------------------
        def time_until(match_time_str):
            try:
                match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
                now = datetime.now(datetime.timezone.utc)
                diff = match_time - now
                if diff.total_seconds() < 0:
                    return "انتهت"
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                return f"{hours} س {minutes} د"
            except:
                return "---"

        def render_match_card(match, show_favorite=True):
            home_team = html.escape(match.get('home_team', '???'))
            away_team = html.escape(match.get('away_team', '???'))
            home_logo = match.get('home_logo') or get_team_logo(home_team)
            away_logo = match.get('away_logo') or get_team_logo(away_team)
            league_logo = match.get('league_logo') or get_league_logo(match.get('league', ''))
            league_name = html.escape(match.get('league', ''))

            effective_status = match['status']
            if effective_status != 'FINISHED':
                try:
                    match_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                    now = datetime.now(datetime.timezone.utc)
                    if now - match_time > timedelta(hours=3):
                        effective_status = 'FINISHED'
                except:
                    pass

            if effective_status == 'LIVE':
                center = f"<span style='color:#d32f2f; font-weight:bold; font-size:1.8rem;'>{match['home_score']} - {match['away_score']}</span>"
                status_display = '<span class="live-badge">🔴 مباشر</span>'
            elif effective_status == 'UPCOMING':
                try:
                    utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    today = datetime.now(tz_tunis).date()
                    match_date = local_time.date()
                    if match_date == today:
                        diff = (local_time - datetime.now(tz_tunis)).total_seconds() / 60
                        if 0 < diff <= 30:
                            status_display = "<span style='color:#ff8c00;'>⏳ بعد قليل</span>"
                        else:
                            status_display = "<span style='color:#666;'>لم تبدأ بعد</span>"
                        center = f"<span style='color:#1976d2; font-weight:bold; font-size:1.8rem;'>{local_time.strftime('%H:%M')}</span>"
                    else:
                        status_display = f"<span style='color:#888;'>{match_date.strftime('%m-%d')}</span>"
                        center = f"<span style='color:#1976d2; font-weight:bold; font-size:1.8rem;'>{local_time.strftime('%H:%M')}</span>"
                except Exception as e:
                    status_display = "<span style='color:#666;'>لم تبدأ بعد</span>"
                    center = "--:--"
            else:
                try:
                    utc_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    status_display = f"<span style='color:#888;'>{local_time.strftime('%m-%d')}</span>"
                    center = f"<span style='color:#888; font-weight:bold; font-size:1.5rem;'>{match['home_score']} - {match['away_score']}</span>"
                except:
                    status_display = "<span style='color:#888;'>انتهت</span>"
                    center = f"{match['home_score']} - {match['away_score']}"

            return f"""
            <a href="/watch_stream?match_id={match['fixture_id']}" style="text-decoration:none; color:inherit; display:block;">
                <div class="match-card">
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                        <div style="flex:1; text-align:center;">
                            <img src="{home_logo}" style="width:48px; height:48px; object-fit:contain; margin-bottom:6px;">
                            <div style="font-weight:600; font-size:0.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px; margin:0 auto;">{home_team}</div>
                        </div>
                        <div style="flex:1; text-align:center;">
                            {center}
                            <div style="margin-top:4px;">{status_display}</div>
                        </div>
                        <div style="flex:1; text-align:center;">
                            <img src="{away_logo}" style="width:48px; height:48px; object-fit:contain; margin-bottom:6px;">
                            <div style="font-weight:600; font-size:0.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px; margin:0 auto;">{away_team}</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap:8px; margin-top:12px; padding-top:8px; border-top:1px solid #444;">
                        <img src="{league_logo}" style="width:20px; height:20px; object-fit:contain;">
                        <span style="color:#aaa;">{league_name}</span>
                    </div>
                </div>
            </a>
            """

        # -------------------- Tabs --------------------
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📅 المباريات", "📊 النتائج", "🏆 الترتيب", "⭐ المفضلة", "📰 الأخبار", "🔮 التوقعات"])

        with tab1:
            st.header("🔥 المباريات المباشرة الآن")
            live_result = supabase.table("matches").select("*").eq("status", "LIVE").execute()
            live_matches = live_result.data
            if live_matches:
                for m in live_matches:
                    st.markdown(render_match_card(m), unsafe_allow_html=True)
            else:
                st.info("لا توجد مباريات مباشرة حالياً")

            st.header("📅 المباريات القادمة")
            upcoming_result = supabase.table("matches")\
                .select("*")\
                .eq("status", "UPCOMING")\
                .order("match_time")\
                .execute()
            upcoming = upcoming_result.data
            if upcoming:
                for m in upcoming:
                    st.markdown(render_match_card(m), unsafe_allow_html=True)
            else:
                st.write("لا توجد مباريات قادمة")

        with tab2:
            st.header("📊 النتائج")
            finished_result = supabase.table("matches")\
                .select("*")\
                .eq("status", "FINISHED")\
                .order("match_time", desc=True)\
                .execute()
            finished = finished_result.data
            if finished:
                for m in finished:
                    home_team = html.escape(m['home_team'])
                    away_team = html.escape(m['away_team'])
                    home_logo = m.get('home_logo') or get_team_logo(home_team)
                    away_logo = m.get('away_logo') or get_team_logo(away_team)
                    try:
                        utc_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
                        local_time = utc_time.astimezone(tz_tunis)
                        date_str = local_time.strftime('%Y-%m-%d')
                    except:
                        date_str = "---"
                    st.markdown(f"""
                    <a href="/match_details?match_id={m['fixture_id']}" style="text-decoration:none; color:inherit; display:block;">
                        <div class="match-card">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <div style="flex:1; text-align:center;">
                                    <img src="{home_logo}" style="width:32px; height:32px; object-fit:contain;">
                                    <div>{home_team}</div>
                                </div>
                                <div><strong style="font-size:1.2rem;">{m['home_score']} - {m['away_score']}</strong></div>
                                <div style="flex:1; text-align:center;">
                                    <img src="{away_logo}" style="width:32px; height:32px; object-fit:contain;">
                                    <div>{away_team}</div>
                                </div>
                            </div>
                            <div style="text-align:center; color:#aaa; margin-top:8px;">
                                {html.escape(m.get('league',''))} • {date_str}
                            </div>
                        </div>
                    </a>
                    """, unsafe_allow_html=True)
            else:
                st.info("لا توجد نتائج بعد")

        with tab3:
            st.header("🏆 جدول الترتيب")
            try:
                @st.cache_data(ttl=3600)
                def get_competitions_with_standings():
                    resp = supabase.table("standings").select("competition_code, competition_name, data").execute()
                    return resp.data if resp.data else []

                comps = get_competitions_with_standings()
                if not comps:
                    st.info("لا توجد ترتيبات متاحة حالياً")
                else:
                    comp_names = [c["competition_name"] for c in comps]
                    selected_comp = st.selectbox("اختر البطولة", comp_names, key="standings_select")
                    comp_data = next(c for c in comps if c["competition_name"] == selected_comp)
                    standings = comp_data["data"].get("standings", [])
                    if not standings:
                        st.warning("لا توجد معلومات ترتيب لهذه البطولة")
                    else:
                        table = standings[0].get("table", [])
                        if table:
                            html_table = '<div style="overflow-x: auto;">'
                            html_table += '<table class="standings-table">'
                            html_table += '<thead><tr><th>المركز</th><th>الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له</th><th>عليه</th><th>فارق</th><th>نقاط</th></tr></thead>'
                            for row in table:
                                team_id = row["team"]["id"]
                                team_name = row["team"]["name"]
                                html_table += '<tr>'
                                html_table += f'<td>{row["position"]}</td>'
                                html_table += f'<td><a href="/team?team_id={team_id}" style="color: inherit; text-decoration: none;">{team_name}</a></td>'
                                html_table += f'<td>{row["playedGames"]}</td>'
                                html_table += f'<td>{row["won"]}</td>'
                                html_table += f'<td>{row["draw"]}</td>'
                                html_table += f'<td>{row["lost"]}</td>'
                                html_table += f'<td>{row["goalsFor"]}</td>'
                                html_table += f'<td>{row["goalsAgainst"]}</td>'
                                html_table += f'<td>{row["goalDifference"]}</td>'
                                html_table += f'<td>{row["points"]}</td>'
                                html_table += '</tr>'
                            html_table += '</table>'
                            html_table += '</div>'
                            st.markdown(html_table, unsafe_allow_html=True)
                        else:
                            st.info("لا توجد بيانات جدول متاحة")
            except Exception as e:
                if "relation" in str(e) or "does not exist" in str(e):
                    st.warning("جدول الترتيب غير موجود. يرجى تشغيل السكربت الكامل لإنشاء الجداول المطلوبة.")
                else:
                    st.error(f"حدث خطأ: {e}")

        with tab4:
            st.header("⭐ مبارياتي المفضلة")
            if st.session_state.user:
                if st.session_state.favorites:
                    fav_matches = [m for m in matches if m['home_team'] in st.session_state.favorites or m['away_team'] in st.session_state.favorites]
                    if fav_matches:
                        for m in fav_matches:
                            st.markdown(render_match_card(m, show_favorite=False), unsafe_allow_html=True)
                    else:
                        st.info("لا توجد مباريات لفرقك المفضلة حالياً")
                else:
                    st.info("أضف فرقاً إلى المفضلة من خلال الضغط على ☆ في بطاقة المباراة")
            else:
                st.info("سجل الدخول لاستخدام المفضلة")

        with tab5:
            st.header("📰 آخر الأخبار")

            @st.cache_data(ttl=3600)
            def get_news():
                cutoff = (datetime.now() - timedelta(days=14)).isoformat()
                try:
                    res = supabase.table("news")\
                        .select("*")\
                        .gte("published_at", cutoff)\
                        .order("published_at", desc=True)\
                        .limit(50)\
                        .execute()
                    return res.data
                except Exception as e:
                    st.error(f"حدث خطأ في جلب الأخبار: {e}")
                    return []

            news = get_news()
            if not news:
                st.info("لا توجد أخبار حالياً")
            else:
                for item in news:
                    safe_title = html.escape(item.get('title', ''))
                    safe_content = html.escape(item.get('content', ''))[:200] + "..." if item.get('content') else ''
                    safe_source = html.escape(item.get('source', 'مصدر غير معروف'))
                    safe_url = html.escape(item.get('url', ''))
                    safe_image = html.escape(item.get('image', '')) if item.get('image') else None

                    try:
                        pub_date = datetime.fromisoformat(item["published_at"].replace('Z', '+00:00'))
                        date_str = pub_date.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_str = "تاريخ غير معروف"

                    lang = item.get("language", "ar")
                    lang_badge = '<span class="lang-badge en">🇬🇧 EN</span>' if lang == "en" else '<span class="lang-badge">🇸🇦 AR</span>'

                    card_html = '<div class="news-card">'
                    if safe_image:
                        card_html += f'<img src="{safe_image}" class="news-image">'
                    card_html += f'''
                        <a href="{safe_url}" target="_blank" class="news-title">
                            <h3>{safe_title}</h3>
                        </a>
                        <div class="news-content">{safe_content}</div>
                        <div class="news-meta">
                            <span class="source-badge">📰 {safe_source}</span>
                            <span>🕒 {date_str}</span>
                            {lang_badge}
                        </div>
                    </div>
                    '''
                    try:
                        if hasattr(st, 'html'):
                            st.html(card_html)
                        else:
                            st.markdown(card_html, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"حدث خطأ في عرض الخبر: {e}")

        with tab6:
            st.header("🔮 توقعات المباريات")
            upcoming_pred = supabase.table("matches").select("fixture_id, home_team, away_team, match_time").eq("status", "UPCOMING").order("match_time").limit(10).execute()
            for m in upcoming_pred.data:
                pred = supabase.table("predictions").select("*").eq("fixture_id", m["fixture_id"]).execute()
                if pred.data:
                    p = pred.data[0]
                    st.write(f"{m['home_team']} vs {m['away_team']}")
                    st.progress(p["home_win_prob"], text=f"فوز {m['home_team']}")
                    st.progress(p["draw_prob"], text="تعادل")
                    st.progress(p["away_win_prob"], text=f"فوز {m['away_team']}")
                else:
                    st.write(f"{m['home_team']} vs {m['away_team']} – لا توجد توقعات بعد")
