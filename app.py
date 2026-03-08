import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta, timezone
import time
import requests
import json
import hashlib
import random

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

# --- Admin password ---
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

# --- Inject ad scripts (replace with your actual codes) ---
st.markdown("""
<script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
<script type="text/javascript">
    var infolinks_pid = 1234567;   // Replace with your Infolinks PID
    var infolinks_wsid = 0;
</script>
<script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
""", unsafe_allow_html=True)

# --- Professional RTL styling with mobile responsiveness ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * { font-family: 'Cairo', sans-serif; }
    .main, .block-container, [data-testid="stMarkdownContainer"] { direction: rtl; text-align: right; }
    
    .match-card {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a40 100%);
        color: white;
        padding: 20px;
        border-radius: 20px;
        margin: 15px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        border: 1px solid #333;
        transition: transform 0.3s;
    }
    .match-card:hover { transform: translateY(-5px); }
    
    .featured-card { border: 3px solid gold; box-shadow: 0 0 20px gold; }
    
    .live-badge {
        background: linear-gradient(45deg, #ff4444, #ff6b6b);
        color: white;
        padding: 5px 12px;
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
        padding: 8px 16px;
        border-radius: 30px;
        text-decoration: none;
        font-weight: 600;
        display: inline-block;
        margin: 5px 10px 5px 0;
        border: none;
        cursor: pointer;
        transition: background 0.3s;
        font-size: 14px;
    }
    .stream-btn:hover { background: #ff5252; color: white; }
    
    .verified { background: #4CAF50; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 5px; }
    .admin-added { background: #ff9800; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 5px; }
    .countdown { color: #ffd700; font-weight: bold; }
    .logo-small { width: 30px; height: 30px; margin: 0 5px; vertical-align: middle; }
    .country-flag { width: 20px; height: 15px; margin: 0 3px; vertical-align: middle; }
    .admin-panel { background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; padding: 20px; border-radius: 10px; margin: 10px 0; }
    
    @media only screen and (max-width: 768px) {
        .match-card { padding: 15px; }
        .match-card h2, .match-card h3 { font-size: 1.2rem; }
        .match-card .logo-small { width: 24px; height: 24px; }
        .stream-btn { padding: 6px 12px; font-size: 12px; }
        .live-badge { font-size: 12px; padding: 4px 8px; }
    }
    @media only screen and (max-width: 480px) {
        .match-card h2, .match-card h3 { font-size: 1rem; }
        .match-card .logo-small { width: 20px; height: 20px; }
        .stream-btn { padding: 4px 8px; font-size: 11px; }
        .live-badge { font-size: 10px; padding: 3px 6px; }
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

# --- Sidebar with three sections ---
with st.sidebar:
    st.header("📢 **ادعم الموقع**")
    st.info("الإعلانات تساعدنا في استمرار الخدمة مجاناً للجميع.")
    
    st.markdown("""
    <a href="https://your-affiliate-link.com" target="_blank">
        <img src="https://your-affiliate-banner-url.com/banner.jpg" style="width:100%; border-radius:10px;">
    </a>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    with st.expander("⚙️ **الإعدادات**", expanded=True):
        low_bandwidth = st.checkbox("وضع الانترنت الضعيف (نص فقط)")
        show_all_leagues = st.checkbox("عرض جميع البطولات", value=True)
        hide_old_finished = st.checkbox("إخفاء المباريات المنتهية بعد ساعتين", value=True)
    
    with st.expander("🏆 **تصفية البطولات**", expanded=True):
        @st.cache_data(ttl=300)
        def get_distinct_leagues():
            try:
                response = supabase.table("matches").select("league").execute()
                leagues = list(set([m["league"] for m in response.data if m.get("league")]))
                return sorted(leagues)
            except Exception as e:
                print(f"Error fetching leagues: {e}")
                return []
        
        all_leagues = get_distinct_leagues()
        selected_leagues = st.multiselect("اختر البطولات", all_leagues, default=[])
        
        st.markdown("---")
        st.subheader("⭐ **أهمية المباراة**")
        min_importance = st.slider("أقل أهمية", 0, 100, 0)
    
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
            
            # Show existing admin streams
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
                # Create a negative fixture_id to avoid conflicts
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
        # --- Logo Auto-Linker (inside admin panel, after the manual stream section) ---
if st.session_state.admin_authenticated and st.session_state.show_admin:
    with st.expander("🖼️ **ربط الشعارات تلقائياً**"):
        st.markdown("سيقوم هذا الأمر بالبحث عن شعارات الفرق في مخزن Supabase وإضافتها إلى قاعدة البيانات.")
        if st.button("🔍 بدء البحث عن الشعارات"):
            with st.spinner("جاري البحث عن الشعارات..."):
                # 1. Fetch all unique team names from matches
                teams_resp = supabase.table("matches").select("home_team, away_team").execute()
                teams = set()
                for row in teams_resp.data:
                    if row.get("home_team"):
                        teams.add(row["home_team"])
                    if row.get("away_team"):
                        teams.add(row["away_team"])
                teams = sorted(list(teams))
                st.info(f"تم العثور على {len(teams)} فريق في قاعدة البيانات.")

                # 2. Define possible league folders (adjust to match your bucket structure)
                league_folders = [
                    "England-Premier-League",
                    "Spain-LaLiga",
                    "Germany-Bundesliga",
                    "Italy-Serie A",
                    "France-Ligue-1",
                    "champions-league",
                    "Portugal-Liga Portugal"
                ]

                # 3. Base URL of your bucket
                BUCKET_BASE = f"{SUPABASE_URL}/storage/v1/object/sign/logos"

                # 4. Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()

                results = {"found": 0, "not_found": 0, "errors": 0}
                for i, team in enumerate(teams):
                    status_text.text(f"معالجة {team}... ({i+1}/{len(teams)})")
                    # Generate filename variations
                    # Remove common suffixes
                    base = team
                    for suffix in [" FC", " AFC", " United", " City", " Real", " CF", " AC", " AS", " SS", " SC", " Club", " Deportivo", " Futebol", " Clube"]:
                        if base.endswith(suffix):
                            base = base[:-len(suffix)]
                    # Replace spaces and special chars
                    base_underscore = base.replace(" ", "_").replace("-", "_").replace("&", "and")
                    original_underscore = team.replace(" ", "_").replace("-", "_").replace("&", "and")
                    variations = [
                        (f"{base_underscore}.png", base_underscore),
                        (f"{original_underscore}.png", original_underscore),
                        (f"{base}.png", base),
                    ]
                    found = False
                    for filename, _ in variations:
                        for folder in league_folders:
                            url = f"{BUCKET_BASE}/{folder}/{filename}"
                            try:
                                resp = requests.head(url, timeout=3)
                                if resp.status_code == 200:
                                    # Insert into team_logos
                                    supabase.table("team_logos").upsert(
                                        {"team_name": team, "logo_url": url},
                                        on_conflict="team_name"
                                    ).execute()
                                    results["found"] += 1
                                    found = True
                                    st.success(f"✅ {team} -> {url}")
                                    break
                            except Exception as e:
                                # ignore timeouts
                                pass
                        if found:
                            break
                    if not found:
                        results["not_found"] += 1
                        st.warning(f"❌ {team} – لم يتم العثور على شعار")
                    
                    # Update progress
                    progress_bar.progress((i+1)/len(teams))

                status_text.text("اكتمل البحث!")
                st.success(f"النتائج: تم العثور على {results['found']} شعار، لم يتم العثور على {results['not_found']}، أخطاء {results['errors']}")

# --- Fetch matches with filters ---
@st.cache_data(ttl=60)
def get_filtered_matches(selected_leagues, min_importance, show_all, hide_old_finished):
    try:
        query = supabase.table("matches").select("*")
        if selected_leagues:
            query = query.in_("league", selected_leagues)
        if min_importance > 0:
            query = query.gte("importance_score", min_importance)
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

matches = get_filtered_matches(selected_leagues, min_importance, show_all_leagues, hide_old_finished)

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
        # Safety filter: if started more than 3 hours ago, treat as finished
        try:
            match_time = datetime.fromisoformat(match["match_time"].replace('Z', '+00:00'))
            now = datetime.now(match_time.tzinfo)
            if now > match_time + timedelta(hours=3):
                return "✅ انتهت (تأخير)"
        except:
            pass
        minute = match.get("minute")
        if minute:
            return f"🟢 مباشر ({minute}')"
        return "🟢 مباشر"
    elif match["status"] == "UPCOMING":
        return f"⏳ {time_until(match['match_time'])}"
    else:
        return "✅ انتهت"

# --- Featured Matches (placeholder) ---
st.header("⭐ **المباريات الهامة اليوم**")
featured = [m for m in matches if m.get("is_featured") or m.get("importance_score", 0) >= 85]

if featured:
    cols = st.columns(3)
    for i, match in enumerate(featured[:6]):
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
live_matches = []
for m in matches:
    if m["status"] == "LIVE":
        # Apply the same safety filter
        try:
            match_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
            now = datetime.now(match_time.tzinfo)
            if now <= match_time + timedelta(hours=3):
                live_matches.append(m)
        except:
            live_matches.append(m)

if live_matches:
    for match in live_matches:
        streams = match.get("streams", [])
        if isinstance(streams, str):
            try:
                streams = json.loads(streams)
            except:
                streams = []
        try:
            admin_streams = supabase.table("admin_streams")\
                .select("*")\
                .eq("fixture_id", match["fixture_id"])\
                .eq("is_active", True)\
                .execute()\
                .data
        except Exception as e:
            admin_streams = []
            print(f"Error fetching admin streams: {e}")
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
                <p style="margin-top:5px;">🏆 {match['league']} <img src="{match.get('league_logo', 'https://via.placeholder.com/50')}" style="width:20px; height:20px; display:inline;"></p>
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
    leagues_dict = {}
    for match in upcoming:
        league = match["league"]
        if league not in leagues_dict:
            leagues_dict[league] = []
        leagues_dict[league].append(match)
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
                        { "".join([f'<a class="stream-btn" style="padding:5px 10px; font-size:14px;" href="{s["url"]}" target="_blank">▶️ بث</a>' for s in streams[:2]]) if streams else '<p style="color:#aaa">الروابط قبل المباراة بساعة</p>' }
                    </div>
                    """, unsafe_allow_html=True)
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

st.components.v1.html("""
    <script src="//popads.net/pop.js" async></script>
""", height=0)
