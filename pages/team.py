import streamlit as st
from supabase import create_client
from datetime import datetime
import zoneinfo
import requests
import html
import time

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
# Helper: fetch team details from TheSportsDB and cache in Supabase
# -------------------------------------------------------------------
def fetch_and_update_team_details(team_name, team_id):
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(team_name)}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("teams"):
                t = data["teams"][0]
                update_data = {}
                if t.get("strTeamBadge"):
                    update_data["logo"] = t["strTeamBadge"]
                if t.get("strCountry"):
                    update_data["country"] = t["strCountry"]
                if t.get("intFormedYear"):
                    update_data["founded"] = int(t["intFormedYear"])
                if t.get("strStadium"):
                    update_data["venue_name"] = t["strStadium"]
                if update_data:
                    supabase.table("teams").update(update_data).eq("id", team_id).execute()
                    return update_data
    except Exception as e:
        print(f"Error fetching team details from TheSportsDB: {e}")
    return {}

# -------------------------------------------------------------------
# Get team from database
# -------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_team(team_id)
if not team:
    st.warning("الفريق غير موجود في قاعدة البيانات")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# If missing details, fetch from TheSportsDB
if not team.get("country") or not team.get("founded") or not team.get("venue_name"):
    fetched = fetch_and_update_team_details(team["name"], team_id)
    team.update(fetched)

col1, col2 = st.columns([1, 3])
with col1:
    st.image(team.get('logo') or 'https://via.placeholder.com/200', width=200)
with col2:
    st.title(team['name'])
    st.write(f"**الدولة:** {team.get('country', 'غير معروف')}")
    st.write(f"**التأسيس:** {team.get('founded', 'غير معروف')}")
    st.write(f"**الملعب:** {team.get('venue_name', 'غير معروف')}")

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["المباريات القادمة", "النتائج", "اللاعبون"])

with tab1:
    # Two separate queries (since .or_ is not available)
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
    # Sort combined list by match_time
    fixtures.sort(key=lambda x: x['match_time'])
    
    if fixtures:
        for f in fixtures:
            try:
                utc_time = datetime.fromisoformat(f["match_time"].replace('Z', '+00:00'))
                local_time = utc_time.astimezone(tz_tunis)
                time_str = local_time.strftime("%H:%M %Y-%m-%d")
            except:
                time_str = f["match_time"][:16]
            st.write(f"{f['home_team']} vs {f['away_team']} - {time_str}")
    else:
        st.info("لا توجد مباريات قادمة")

with tab2:
    home_results = supabase.table("matches")\
        .select("*")\
        .eq("home_team_id", team_id)\
        .eq("status", "FINISHED")\
        .order("match_time", desc=True)\
        .limit(20)\
        .execute()
    away_results = supabase.table("matches")\
        .select("*")\
        .eq("away_team_id", team_id)\
        .eq("status", "FINISHED")\
        .order("match_time", desc=True)\
        .limit(20)\
        .execute()
    results = home_results.data + away_results.data
    # Sort descending by match_time (already done per query, but combine then sort again to ensure)
    results.sort(key=lambda x: x['match_time'], reverse=True)
    
    if results:
        for r in results[:20]:  # limit combined
            try:
                utc_time = datetime.fromisoformat(r["match_time"].replace('Z', '+00:00'))
                local_time = utc_time.astimezone(tz_tunis)
                date_str = local_time.strftime("%Y-%m-%d")
            except:
                date_str = r["match_time"][:10]
            st.write(f"{r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']} - {date_str}")
    else:
        st.info("لا توجد نتائج")

with tab3:
    st.subheader("اللاعبون")
    players = []
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?t={requests.utils.quote(team['name'])}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("player"):
                players = data["player"]
    except Exception as e:
        print(f"Error fetching players: {e}")

    if players:
        for p in players[:20]:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.image(p.get('strThumb') or 'https://via.placeholder.com/50', width=50)
            with col2:
                st.markdown(f"**{p.get('strPlayer')}**")
                st.caption(f"{p.get('strPosition', '')} | {p.get('strNationality', '')} | العمر: {p.get('dateBorn', '')[:4] if p.get('dateBorn') else ''}")
    else:
        st.info("لا توجد معلومات عن اللاعبين حالياً")
