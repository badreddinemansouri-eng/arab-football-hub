import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import html

st.set_page_config(page_title="الدوري", page_icon="🏆", layout="wide")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

league_id = st.query_params.get("league_id")
if not league_id:
    st.error("لم يتم تحديد الدوري")
    st.stop()

@st.cache_data(ttl=3600)
def get_league_name(lid):
    res = supabase.table("standings").select("competition_name").eq("competition_code", lid).execute()
    return res.data[0]["competition_name"] if res.data else lid

league_name = get_league_name(league_id)

st.title(f"🏆 {league_name}")

tab1, tab2, tab3, tab4 = st.tabs(["جدول الترتيب", "المباريات", "جدول الدور", "الهدافون"])

with tab1:
    comp_data = supabase.table("standings").select("*").eq("competition_code", league_id).execute()
    if comp_data.data:
        standings = comp_data.data[0]["data"]["standings"][0]["table"]
        df = []
        for row in standings:
            df.append({
                "المركز": row["position"],
                "الفريق": row["team"]["name"],
                "لعب": row["playedGames"],
                "فوز": row["won"],
                "تعادل": row["draw"],
                "خسارة": row["lost"],
                "له": row["goalsFor"],
                "عليه": row["goalsAgainst"],
                "فارق": row["goalDifference"],
                "نقاط": row["points"]
            })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد معلومات ترتيب")

with tab2:
    matches = supabase.table("matches")\
        .select("*")\
        .eq("league_id", league_id)\
        .order("match_time", desc=True)\
        .limit(100)\
        .execute()
    if matches.data:
        for m in matches.data:
            try:
                utc_time = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00'))
                local_time = utc_time.astimezone(tz_tunis)
                date_str = local_time.strftime("%Y-%m-%d")
            except:
                date_str = m["match_time"][:10]
            st.write(f"{m['home_team']} {m['home_score']}-{m['away_score']} {m['away_team']} - {date_str}")
    else:
        st.info("لا توجد مباريات")

with tab3:
    rounds = supabase.table("league_rounds").select("*").eq("league_id", league_id).order("round_number").execute()
    if rounds.data:
        for r in rounds.data:
            with st.expander(f"الجولة {r['round']}"):
                for fid in r['fixture_ids']:
                    st.markdown(f"[مباراة {fid}](/match_details?match_id={fid})")
    else:
        st.info("لا يوجد جدول دور")

with tab4:
    scorers = supabase.table("top_scorers")\
        .select("players(name), goals, assists")\
        .eq("league_id", league_id)\
        .order("goals", desc=True)\
        .limit(20)\
        .execute()
    if scorers.data:
        for s in scorers.data:
            name = s.get('players', {}).get('name', 'لاعب')
            st.write(f"{name} - {s['goals']} هدف ({s.get('assists', 0)} أسيست)")
    else:
        st.info("لا توجد قائمة هدافين")
