import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="فريق", page_icon="🏟️")

team_id = st.query_params.get("team_id")
if not team_id:
    st.error("لم يتم تحديد الفريق")
    st.stop()

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

@st.cache_data(ttl=3600)
def get_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_team(team_id)
if not team:
    st.error("الفريق غير موجود")
    st.stop()

col1, col2 = st.columns([1,3])
with col1:
    st.image(team.get('logo') or 'https://via.placeholder.com/200', width=200)
with col2:
    st.title(team['name'])
    st.write(f"**الدولة:** {team.get('country', '')}")
    st.write(f"**التأسيس:** {team.get('founded', '')}")
    st.write(f"**الملعب:** {team.get('venue_name', '')}")

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["المباريات القادمة", "النتائج", "اللاعبون"])

with tab1:
    fixtures = supabase.table("matches").select("*").eq("home_team_id", team_id).or_(f"away_team_id.eq.{team_id}").eq("status", "UPCOMING").order("date").execute()
    if fixtures.data:
        for f in fixtures.data:
            st.write(f"{f['home_team']} vs {f['away_team']} - {f['date'][:16]}")
    else:
        st.info("لا توجد مباريات قادمة")

with tab2:
    results = supabase.table("matches").select("*").eq("home_team_id", team_id).or_(f"away_team_id.eq.{team_id}").eq("status", "FINISHED").order("date", desc=True).limit(20).execute()
    if results.data:
        for r in results.data:
            st.write(f"{r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']} - {r['date'][:10]}")
    else:
        st.info("لا توجد نتائج")

with tab3:
    # Fetch players by team – you'd need a player_team table; placeholder for now
    st.info("قائمة اللاعبين (قريباً)")
