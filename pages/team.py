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

# -------------------------------------------------------------------
# Helper: fetch team details from TheSportsDB and cache in Supabase
# -------------------------------------------------------------------
def fetch_and_update_team_details(team_name, team_id):
    """Try to get additional team info from TheSportsDB and update the teams table."""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(team_name)}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("teams"):
                t = data["teams"][0]
                # Prepare update data
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

# If the team is missing details, try to fetch them from TheSportsDB
if not team.get("country") or not team.get("founded") or not team.get("venue_name"):
    fetched = fetch_and_update_team_details(team["name"], team_id)
    team.update(fetched)  # update local dict for display

# Display team info
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
    fixtures = supabase.table("matches")\
        .select("*")\
        .eq("home_team_id", team_id).or_(f"away_team_id.eq.{team_id}")\
        .eq("status", "UPCOMING")\
        .order("match_time")\
        .execute()
    if fixtures.data:
        for f in fixtures.data:
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
    results = supabase.table("matches")\
        .select("*")\
        .eq("home_team_id", team_id).or_(f"away_team_id.eq.{team_id}")\
        .eq("status", "FINISHED")\
        .order("match_time", desc=True)\
        .limit(20)\
        .execute()
    if results.data:
        for r in results.data:
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
    # Try to fetch players for this team from TheSportsDB
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
        for p in players[:20]:  # show max 20
            col1, col2 = st.columns([1, 4])
            with col1:
                st.image(p.get('strThumb') or 'https://via.placeholder.com/50', width=50)
            with col2:
                st.markdown(f"**{p.get('strPlayer')}**")
                st.caption(f"{p.get('strPosition', '')} | {p.get('strNationality', '')} | العمر: {p.get('dateBorn', '')[:4] if p.get('dateBorn') else ''}")
    else:
        st.info("لا توجد معلومات عن اللاعبين حالياً")
