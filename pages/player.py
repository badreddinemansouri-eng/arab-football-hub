import streamlit as st
from supabase import create_client
from datetime import datetime
import requests
import html

st.set_page_config(page_title="لاعب", page_icon="👤", layout="wide")

# We'll use TheSportsDB directly; no need for Supabase here, but we keep it for consistency
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

player_id = st.query_params.get("player_id")
if not player_id:
    st.error("لم يتم تحديد اللاعب")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# Since player_id is likely a TheSportsDB ID, we can fetch directly
def get_player_from_thesportsdb(pid):
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/lookupplayer.php?id={pid}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("players"):
                return data["players"][0]
    except Exception as e:
        print(f"Error fetching player: {e}")
    return None

player = get_player_from_thesportsdb(player_id)
if not player:
    st.warning("اللاعب غير موجود في قاعدة البيانات")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# Display player info
col1, col2 = st.columns([1, 3])
with col1:
    st.image(player.get('strThumb') or 'https://via.placeholder.com/200', width=200)
with col2:
    st.title(player.get('strPlayer', 'لاعب'))
    st.write(f"**الاسم الكامل:** {player.get('strPlayer', '')}")
    st.write(f"**الجنسية:** {player.get('strNationality', 'غير معروف')}")
    st.write(f"**المركز:** {player.get('strPosition', 'غير معروف')}")
    if player.get('dateBorn'):
        try:
            birth_year = player['dateBorn'][:4]
            age = datetime.now().year - int(birth_year)
            st.write(f"**العمر:** {age} سنة")
        except:
            st.write(f"**تاريخ الميلاد:** {player['dateBorn']}")
    st.write(f"**النادي الحالي:** {player.get('strTeam', 'غير معروف')}")

st.markdown("---")
st.markdown(f"[عرض على TheSportsDB](https://www.thesportsdb.com/player/{player_id})")
