import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="لاعب", page_icon="👤")

player_id = st.query_params.get("player_id")
if not player_id:
    st.error("لم يتم تحديد اللاعب")
    st.stop()

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

@st.cache_data(ttl=3600)
def get_player(pid):
    res = supabase.table("players").select("*").eq("id", pid).execute()
    return res.data[0] if res.data else None

player = get_player(player_id)
if not player:
    st.error("اللاعب غير موجود")
    st.stop()

col1, col2 = st.columns([1,3])
with col1:
    st.image(player.get('photo') or 'https://via.placeholder.com/200', width=200)
with col2:
    st.title(player['name'])
    st.write(f"**العمر:** {player.get('age', '')}")
    st.write(f"**الجنسية:** {player.get('nationality', '')}")
    st.write(f"**المركز:** {player.get('position', '')}")
    st.write(f"**الرقم:** {player.get('number', '')}")

st.markdown("---")
st.subheader("إحصائيات الموسم")
stats = supabase.table("top_scorers").select("league_name, goals, assists").eq("player_id", player_id).execute()
if stats.data:
    df = pd.DataFrame(stats.data)
    st.dataframe(df, hide_index=True, use_container_width=True)
else:
    st.info("لا توجد إحصائيات متاحة")
