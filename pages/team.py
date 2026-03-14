import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import html
from utils.logos import get_team_logo  # if you have this helper

st.set_page_config(page_title="فريق", page_icon="🏟️", layout="wide")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

team_id = st.query_params.get("team_id")
if not team_id:
    st.error("لم يتم تحديد الفريق")
    st.stop()

@st.cache_data(ttl=3600)
def get_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_team(team_id)
if not team:
    st.error("الفريق غير موجود")
    st.stop()

# Logo – use helper if available
team_logo = team.get('logo') or get_team_logo(team['name'])  # fallback to helper

col1, col2 = st.columns([1, 3])
with col1:
    st.image(team_logo or 'https://via.placeholder.com/200', width=200)
with col2:
    st.title(team['name'])
    st.write(f"**الدولة:** {team.get('country', '')}")
    st.write(f"**التأسيس:** {team.get('founded', '')}")
    st.write(f"**الملعب:** {team.get('venue_name', '')}")

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
            # Convert UTC to local time
            try:
                utc_time = datetime.fromisoformat(f["match_time"].replace('Z', '+00:00'))
                local_time = utc_time.astimezone(tz_tunis)  # need tz_tunis imported
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
    # Show players who have scored for this team (from top_scorers)
    players = supabase.table("top_scorers")\
        .select("players(name, position, photo)")\
        .eq("team_id", team_id)\
        .execute()
    if players.data:
        for p in players.data:
            player_info = p.get('players', {})
            name = player_info.get('name', '')
            pos = player_info.get('position', '')
            photo = player_info.get('photo') or 'https://via.placeholder.com/50'
            st.image(photo, width=30)
            st.markdown(f"**{name}** – {pos}")
    else:
        st.info("لا توجد معلومات عن اللاعبين حالياً")
