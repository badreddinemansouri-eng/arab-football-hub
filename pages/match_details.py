import streamlit as st
from supabase import create_client
from datetime import datetime
import zoneinfo
import json
import html

st.set_page_config(page_title="تفاصيل المباراة", page_icon="⚽", layout="wide")

# -------------------- Supabase and timezone --------------------
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

# -------------------- Check admin auth (from main app) --------------------
is_admin = st.session_state.get("admin_auth", False)

# -------------------- Get match_id from URL --------------------
match_id = st.query_params.get("match_id")
if not match_id:
    st.error("لم يتم تحديد المباراة")
    st.stop()

# -------------------- Cache match data (30 sec) --------------------
@st.cache_data(ttl=30)
def get_match(mid):
    res = supabase.table("matches").select("*, home_team_id, away_team_id").eq("fixture_id", mid).execute()
    return res.data[0] if res.data else None

match = get_match(match_id)
if not match:
    st.error("المباراة غير موجودة")
    st.stop()

# -------------------- Fetch additional data --------------------
@st.cache_data(ttl=60)
def get_stats(mid):
    return supabase.table("match_statistics").select("*").eq("fixture_id", mid).execute().data

@st.cache_data(ttl=60)
def get_lineups(mid):
    return supabase.table("lineups").select("*").eq("fixture_id", mid).execute().data

@st.cache_data(ttl=60)
def get_events(mid):
    return supabase.table("match_events").select("*").eq("fixture_id", mid).order("elapsed").execute().data

@st.cache_data(ttl=60)
def get_predictions(mid):
    return supabase.table("predictions").select("*").eq("fixture_id", mid).execute().data

@st.cache_data(ttl=60)
def get_h2h(team1, team2):
    return supabase.table("head2head").select("*").eq("team1_id", team1).eq("team2_id", team2).execute().data

stats = get_stats(match_id)
lineups = get_lineups(match_id)
events = get_events(match_id)
predictions = get_predictions(match_id)
h2h = get_h2h(match.get("home_team_id"), match.get("away_team_id")) if match.get("home_team_id") and match.get("away_team_id") else []

# -------------------- Helper functions --------------------
def format_time(utc_str):
    try:
        dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00')).astimezone(tz_tunis)
        return dt.strftime("%H:%M %Y-%m-%d")
    except:
        return ""

def empty_state(message):
    """Display a styled empty state message"""
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.05); border-radius: 20px; padding: 40px; text-align: center; border: 1px dashed rgba(255,255,255,0.2); margin: 20px 0;">
        <span style="font-size: 3rem;">📭</span>
        <h3 style="color: #aaa;">{message}</h3>
    </div>
    """, unsafe_allow_html=True)

# -------------------- CSS (same glass style as watch_stream) --------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap');
    * { font-family: 'Cairo', sans-serif; }
    .main, .block-container { direction: rtl; text-align: right; padding: 1rem !important; }
    .glass-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 30px;
        padding: 30px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        margin-bottom: 30px;
    }
    .match-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
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
        margin-bottom: 15px;
        filter: drop-shadow(0 10px 15px rgba(0,0,0,0.3));
    }
    .team-name {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }
    .score {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(45deg, #ff416c, #ff4b2b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        padding: 0 20px;
    }
    .match-meta {
        text-align: center;
        margin-top: 20px;
        color: rgba(255,255,255,0.8);
        font-size: 1.1rem;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 20px; padding: 8px 16px; background: rgba(255,255,255,0.05); }
    .stTabs [aria-selected="true"] { background: #ff4d4d; }
    .event-card {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 8px 12px;
        margin: 5px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .progress-bar {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        height: 8px;
        overflow: hidden;
        margin: 5px 0;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #ff416c, #ff4b2b);
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Back button --------------------
st.markdown("""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
    <a href="/" style="background: rgba(255,255,255,0.1); padding: 10px 20px; border-radius: 50px; color: white; text-decoration: none;">
        ← الرئيسية
    </a>
    {admin_btn}
</div>
""".format(admin_btn="""
    <button class="admin-fetch-btn" onclick="alert('سيتم جلب البيانات قريباً')">🔄 تحديث البيانات</button>
""" if is_admin else ""), unsafe_allow_html=True)

# -------------------- Match header (glass card) --------------------
home_team = match['home_team']
away_team = match['away_team']
home_logo = match.get('home_logo') or "https://via.placeholder.com/100?text=Home"
away_logo = match.get('away_logo') or "https://via.placeholder.com/100?text=Away"
league = match.get('league', '')
match_time = format_time(match['match_time'])
score = f"{match['home_score']} - {match['away_score']}" if match['home_score'] is not None else "VS"
status = match['status']

st.markdown(f"""
<div class="glass-card">
    <div class="match-header">
        <div class="team-block">
            <img src="{home_logo}" class="team-logo">
            <div class="team-name">{home_team}</div>
        </div>
        <div class="score">{score}</div>
        <div class="team-block">
            <img src="{away_logo}" class="team-logo">
            <div class="team-name">{away_team}</div>
        </div>
    </div>
    <div class="match-meta">
        <i>🏆 {league}</i> • <i>⏱️ {match_time}</i> • <i>⚽ {status}</i>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------- Build tabs dynamically based on data --------------------
tab_definitions = []

# Tab 0: Overview (always present)
def overview_tab():
    st.subheader("ملخص المباراة")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**الدوري:** {league}")
        st.markdown(f"**التاريخ:** {match_time}")
        st.markdown(f"**الحالة:** {status}")
        if match.get('referee'):
            st.markdown(f"**الحكم:** {match['referee']}")
        if match.get('venue'):
            st.markdown(f"**الملعب:** {match['venue']}")
    with col2:
        if match.get('attendance'):
            st.markdown(f"**الحضور:** {match['attendance']:,}")
        if match.get('broadcasters'):
            bc = match['broadcasters']
            if isinstance(bc, str):
                bc = json.loads(bc)
            if bc:
                st.markdown("**القنوات الناقلة:**")
                for ch in bc:
                    st.markdown(f"- {ch}")

    st.markdown("---")
    # Streams
    streams = match.get("streams", [])
    if isinstance(streams, str):
        streams = json.loads(streams)
    try:
        admin_streams = supabase.table("admin_streams").select("*").eq("fixture_id", match_id).eq("is_active", True).execute().data
        if admin_streams:
            for a in admin_streams:
                streams.append({"title": a.get("stream_title", "بث إضافي"), "url": a["stream_url"]})
    except:
        pass
    if streams:
        st.subheader("🔗 روابط البث")
        for s in streams:
            st.markdown(f'<a href="{s["url"]}" target="_blank" style="display:block; background:#1976d2; color:white; padding:10px; margin:5px 0; border-radius:30px; text-align:center; text-decoration:none;">{s.get("title", "بث مباشر")}</a>', unsafe_allow_html=True)
    else:
        empty_state("لا توجد روابط بث متاحة")

tab_definitions.append(("📋 ملخص", overview_tab))

# Tab 1: Statistics
if stats:
    def stats_tab():
        st.subheader("إحصائيات المباراة")
        stats_by_team = {s.get("team_id"): s for s in stats}
        home_stats = stats_by_team.get(match.get("home_team_id"))
        away_stats = stats_by_team.get(match.get("away_team_id"))

        if home_stats and away_stats:
            stat_keys = [
                ("possession", "الاستحواذ", "%"),
                ("shots", "التسديدات", ""),
                ("shots_on_target", "على المرمى", ""),
                ("fouls", "أخطاء", ""),
                ("corners", "ركنيات", ""),
                ("offsides", "تسلل", ""),
                ("yellow_cards", "بطاقات صفراء", ""),
                ("red_cards", "بطاقات حمراء", ""),
            ]
            for key, name, unit in stat_keys:
                hv = home_stats.get(key, 0)
                av = away_stats.get(key, 0)
                total = hv + av
                st.markdown(f"**{name}**")
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    st.write(f"{hv}{unit}")
                with col2:
                    if key == "possession":
                        st.progress(hv/100 if hv else 0, text="")
                    else:
                        bar_width = (hv/total*100) if total else 0
                        st.markdown(f"<div class='progress-bar'><div class='progress-fill' style='width:{bar_width}%'></div></div>", unsafe_allow_html=True)
                with col3:
                    st.write(f"{av}{unit}")
        else:
            empty_state("إحصائيات غير مكتملة")
    tab_definitions.append(("📊 إحصائيات", stats_tab))

# Tab 2: Lineups
if lineups:
    def lineups_tab():
        st.subheader("التشكيلة الأساسية والبدلاء")
        home_lineup = [l for l in lineups if l.get("team_id") == match.get("home_team_id")]
        away_lineup = [l for l in lineups if l.get("team_id") == match.get("away_team_id")]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{home_team}**")
            if home_lineup:
                lineup = home_lineup[0]
                st.write(f"التشكيل: {lineup.get('formation', 'غير معروف')}")
                st.write("**التشكيلة الأساسية:**")
                for player in lineup.get('starting_xi', []):
                    st.write(f"{player.get('number', '')} - {player.get('name', '')} ({player.get('pos', '')})")
                st.write("**البدلاء:**")
                for sub in lineup.get('substitutes', []):
                    st.write(f"{sub.get('number', '')} - {sub.get('name', '')}")
            else:
                empty_state("لا توجد تشكيلة")
        with col2:
            st.markdown(f"**{away_team}**")
            if away_lineup:
                lineup = away_lineup[0]
                st.write(f"التشكيل: {lineup.get('formation', 'غير معروف')}")
                st.write("**التشكيلة الأساسية:**")
                for player in lineup.get('starting_xi', []):
                    st.write(f"{player.get('number', '')} - {player.get('name', '')} ({player.get('pos', '')})")
                st.write("**البدلاء:**")
                for sub in lineup.get('substitutes', []):
                    st.write(f"{sub.get('number', '')} - {sub.get('name', '')}")
            else:
                empty_state("لا توجد تشكيلة")
    tab_definitions.append(("👥 التشكيلة", lineups_tab))

# Tab 3: Events
if events:
    def events_tab():
        st.subheader("أحداث المباراة")
        for e in events:
            icon = "⚽" if e.get('type') == 'Goal' else "🟨" if e.get('detail') == 'Yellow Card' else "🟥" if e.get('detail') == 'Red Card' else "🔄" if e.get('type') == 'substitution' else "•"
            player_name = e.get('player', '')
            st.markdown(f"""
            <div class="event-card">
                <span>{icon}</span>
                <span>{e.get('elapsed')}'</span>
                <span>{player_name}</span>
                <span>{e.get('detail', '')}</span>
            </div>
            """, unsafe_allow_html=True)
    tab_definitions.append(("⏱️ الأحداث", events_tab))

# Tab 4: Head-to-Head
if h2h:
    def h2h_tab():
        st.subheader("سجل المواجهات المباشرة")
        data = h2h[0]
        st.markdown(f"""
        **لعب الفريقان {data.get('played', 0)} مرة.**  
        **{home_team} فاز {data.get('team1_wins', 0)}**  
        **{away_team} فاز {data.get('team2_wins', 0)}**  
        **تعادل {data.get('draws', 0)}**  
        """)
        if data.get('last_meetings'):
            st.markdown("**آخر المواجهات:**")
            for fid in data['last_meetings'][:5]:
                st.markdown(f"- [مباراة {fid}](/match_details?match_id={fid})")
    tab_definitions.append(("⚔️ وجهاً لوجه", h2h_tab))

# Tab 5: Predictions
if predictions:
    def pred_tab():
        st.subheader("التوقعات")
        p = predictions[0]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"فوز {home_team}", f"{p.get('home_win_prob', 0)}%")
        with col2:
            st.metric("تعادل", f"{p.get('draw_prob', 0)}%")
        with col3:
            st.metric(f"فوز {away_team}", f"{p.get('away_win_prob', 0)}%")
        st.progress(p.get('home_win_prob', 0)/100, text=f"{home_team}")
        st.progress(p.get('draw_prob', 0)/100, text="تعادل")
        st.progress(p.get('away_win_prob', 0)/100, text=f"{away_team}")
    tab_definitions.append(("🔮 التوقعات", pred_tab))

# -------------------- Render tabs --------------------
if tab_definitions:
    tab_labels = [t[0] for t in tab_definitions]
    tabs = st.tabs(tab_labels)
    for i, (_, content_func) in enumerate(tab_definitions):
        with tabs[i]:
            content_func()
else:
    st.warning("لا توجد تفاصيل إضافية لهذه المباراة")

# -------------------- Footer --------------------
st.markdown("---")
st.markdown("<div style='text-align:center; color:#888;'>جميع البيانات مقدمة من Badr TV</div>", unsafe_allow_html=True)
