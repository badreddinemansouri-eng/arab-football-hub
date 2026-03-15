import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import html
import pandas as pd

st.set_page_config(page_title="فريق", page_icon="🏟️", layout="wide")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

team_id = st.query_params.get("team_id")
if not team_id:
    st.error("لم يتم تحديد الفريق")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

try:
    team_id = int(team_id)
except ValueError:
    st.error("معرف الفريق غير صالح")
    st.stop()

# -------------------------------------------------------------------
# Helper functions for TheSportsDB API
# -------------------------------------------------------------------
@st.cache_data(ttl=3600)
def search_team_by_name(name):
    """Search for team on TheSportsDB and return first result."""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(name)}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("teams"):
                return data["teams"][0]
    except Exception as e:
        print(f"Error searching team: {e}")
    return None

@st.cache_data(ttl=3600)
def get_players_by_team_id(tsdb_team_id):
    """Get all players for a TheSportsDB team ID."""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/lookup_all_players.php?id={tsdb_team_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("player"):
                return data["player"]
    except Exception as e:
        print(f"Error fetching players: {e}")
    return []

@st.cache_data(ttl=3600)
def get_recent_events_by_team_id(tsdb_team_id):
    """Get last 10 events for a team from TheSportsDB."""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/eventslast.php?id={tsdb_team_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results"):
                return data["results"]
    except Exception as e:
        print(f"Error fetching events: {e}")
    return []

@st.cache_data(ttl=3600)
def get_team_honors(tsdb_team_id):
    """Get team honors (trophies) from TheSportsDB."""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchhonours.php?id={tsdb_team_id}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("honours"):
                return data["honours"]
    except Exception as e:
        print(f"Error fetching honors: {e}")
    return []

# -------------------------------------------------------------------
# Get team from local DB
# -------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_local_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_local_team(team_id)
if not team:
    st.warning("الفريق غير موجود في قاعدة البيانات المحلية. سيتم البحث عن معلومات من TheSportsDB...")
    # If not in DB, try to fetch from TheSportsDB by name? We need a name. For now, stop.
    st.stop()

# -------------------------------------------------------------------
# Fetch extended data from TheSportsDB
# -------------------------------------------------------------------
tsdb_team = search_team_by_name(team['name'])
tsdb_team_id = tsdb_team.get('idTeam') if tsdb_team else None
players = get_players_by_team_id(tsdb_team_id) if tsdb_team_id else []
recent_events = get_recent_events_by_team_id(tsdb_team_id) if tsdb_team_id else []
honors = get_team_honors(tsdb_team_id) if tsdb_team_id else []

# -------------------------------------------------------------------
# Display team header
# -------------------------------------------------------------------
col1, col2 = st.columns([1, 3])
with col1:
    logo = team.get('logo') or (tsdb_team.get('strTeamBadge') if tsdb_team else None)
    st.image(logo or 'https://via.placeholder.com/200', width=200)
with col2:
    st.title(team['name'])
    if tsdb_team:
        st.caption(f"**الدوري:** {tsdb_team.get('strLeague')}")
        st.caption(f"**الملعب:** {tsdb_team.get('strStadium')} (السعة: {tsdb_team.get('intStadiumCapacity', 'غير معروف')})")
        st.caption(f"**التأسيس:** {tsdb_team.get('intFormedYear', 'غير معروف')}")
        st.caption(f"**البلد:** {tsdb_team.get('strCountry', 'غير معروف')}")
        st.caption(f"**الموقع الرسمي:** [{tsdb_team.get('strWebsite')}]({tsdb_team.get('strWebsite')})" if tsdb_team.get('strWebsite') else "")
    else:
        st.caption(f"**البلد:** {team.get('country', 'غير معروف')}")
        st.caption(f"**التأسيس:** {team.get('founded', 'غير معروف')}")
        st.caption(f"**الملعب:** {team.get('venue_name', 'غير معروف')}")

if honors:
    st.markdown("---")
    st.subheader("🏆 البطولات")
    cols = st.columns(4)
    for i, h in enumerate(honors[:8]):
        with cols[i % 4]:
            st.markdown(f"**{h.get('strHonour')}**  \n{h.get('strSeason')}")

# -------------------------------------------------------------------
# Tabs: المباريات, التشكيلة, الإحصائيات, السجل
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📅 المباريات", "👥 التشكيلة", "📊 إحصائيات", "📜 السجل"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("المباريات القادمة")
        # Fetch from Supabase
        home_fixtures = supabase.table("matches")\
            .select("*")\
            .eq("home_team_id", team_id)\
            .eq("status", "UPCOMING")\
            .order("match_time")\
            .execute()
        away_fixtures = supabase.table("matches")\
            .select("*")\
            .eq("away_team_id", team_id)\
            .eq("status", "UPCOMING")\
            .order("match_time")\
            .execute()
        fixtures = home_fixtures.data + away_fixtures.data
        fixtures.sort(key=lambda x: x['match_time'])
        if fixtures:
            for f in fixtures[:5]:
                try:
                    utc_time = datetime.fromisoformat(f["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    time_str = local_time.strftime("%H:%M %Y-%m-%d")
                except:
                    time_str = f["match_time"][:16]
                st.write(f"**{f['home_team']} vs {f['away_team']}** – {time_str}")
        else:
            st.info("لا توجد مباريات قادمة")

    with col2:
        st.subheader("آخر النتائج")
        home_results = supabase.table("matches")\
            .select("*")\
            .eq("home_team_id", team_id)\
            .eq("status", "FINISHED")\
            .order("match_time", desc=True)\
            .limit(5)\
            .execute()
        away_results = supabase.table("matches")\
            .select("*")\
            .eq("away_team_id", team_id)\
            .eq("status", "FINISHED")\
            .order("match_time", desc=True)\
            .limit(5)\
            .execute()
        results = home_results.data + away_results.data
        results.sort(key=lambda x: x['match_time'], reverse=True)
        if results:
            for r in results[:5]:
                try:
                    utc_time = datetime.fromisoformat(r["match_time"].replace('Z', '+00:00'))
                    local_time = utc_time.astimezone(tz_tunis)
                    date_str = local_time.strftime("%Y-%m-%d")
                except:
                    date_str = r["match_time"][:10]
                score = f"{r['home_score']} - {r['away_score']}"
                if r['home_team_id'] == team_id:
                    outcome = "فوز" if r['home_score'] > r['away_score'] else "تعادل" if r['home_score'] == r['away_score'] else "خسارة"
                else:
                    outcome = "فوز" if r['away_score'] > r['home_score'] else "تعادل" if r['away_score'] == r['home_score'] else "خسارة"
                st.write(f"**{r['home_team']} {score} {r['away_team']}** – {date_str} ({outcome})")
        else:
            st.info("لا توجد نتائج")

    # Recent form from TheSportsDB (alternative)
    if recent_events:
        st.subheader("آخر المباريات (TheSportsDB)")
        form = []
        for ev in recent_events[:5]:
            home = ev['strHomeTeam']
            away = ev['strAwayTeam']
            home_score = ev['intHomeScore']
            away_score = ev['intAwayScore']
            if home_score is not None and away_score is not None:
                if ev['idHomeTeam'] == tsdb_team_id:
                    outcome = "فوز" if home_score > away_score else "تعادل" if home_score == away_score else "خسارة"
                else:
                    outcome = "فوز" if away_score > home_score else "تعادل" if away_score == home_score else "خسارة"
                st.write(f"**{home} {home_score}-{away_score} {away}** – {outcome}")

with tab2:
    st.subheader("التشكيلة الحالية")
    if players:
        # Group by position
        positions = {}
        for p in players:
            pos = p.get('strPosition', 'أخرى')
            if pos not in positions:
                positions[pos] = []
            positions[pos].append(p)

        for pos, plist in positions.items():
            st.markdown(f"**{pos}**")
            cols = st.columns(4)
            for i, player in enumerate(plist[:12]):
                with cols[i % 4]:
                    photo = player.get('strThumb') or player.get('strCutout') or 'https://via.placeholder.com/100'
                    st.image(photo, width=100)
                    st.markdown(f"**{player.get('strPlayer')}**")
                    nat = player.get('strNationality', '')
                    age = ''
                    if player.get('dateBorn'):
                        try:
                            birth_year = int(player['dateBorn'][:4])
                            age = datetime.now().year - birth_year
                        except:
                            age = player['dateBorn'][:4]
                    st.caption(f"{player.get('strPosition', '')} | {nat} | {age} سنة".strip(' |'))
                    # Link to player page if you have one
                    # st.markdown(f"[تفاصيل](/player?player_id={player.get('idPlayer')})")
    else:
        st.info("لا توجد معلومات عن اللاعبين حالياً")

with tab3:
    st.subheader("إحصائيات الفريق")
    if recent_events:
        total_goals_for = 0
        total_goals_against = 0
        matches_played = 0
        for ev in recent_events:
            if ev['intHomeScore'] is not None and ev['intAwayScore'] is not None:
                matches_played += 1
                if ev['idHomeTeam'] == tsdb_team_id:
                    total_goals_for += ev['intHomeScore']
                    total_goals_against += ev['intAwayScore']
                else:
                    total_goals_for += ev['intAwayScore']
                    total_goals_against += ev['intHomeScore']
        if matches_played > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("إجمالي الأهداف المسجلة", total_goals_for)
            with col2:
                st.metric("إجمالي الأهداف المستقبلة", total_goals_against)
            with col3:
                st.metric("معدل الأهداف لكل مباراة", round(total_goals_for / matches_played, 2))

        # Top scorers from TheSportsDB? Not directly available, but we could parse events.

    # Alternative: show top scorers from TheSportsDB if available (need to parse events)
    # For now, just a placeholder.

with tab4:
    st.subheader("السجل الكامل")
    if honors:
        st.markdown("**البطولات**")
        for h in honors:
            st.write(f"- {h.get('strHonour')} ({h.get('strSeason')})")

    # Historical matches (could be added later)
