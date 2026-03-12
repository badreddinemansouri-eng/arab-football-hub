import streamlit as st
from supabase import create_client

st.set_page_config(page_title="بحث", page_icon="🔍")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

st.title("🔍 بحث عن فرق ولاعبين")

query = st.text_input("اكتب اسم الفريق أو اللاعب")
if query:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("الفرق")
        teams = supabase.table("teams").select("id, name, logo").ilike("name", f"%{query}%").execute()
        if teams.data:
            for t in teams.data:
                st.image(t.get('logo', ''), width=30)
                st.markdown(f"[{t['name']}](/team?team_id={t['id']})")
        else:
            st.info("لا توجد فرق مطابقة")
    with col2:
        st.subheader("اللاعبين")
        players = supabase.table("players").select("id, name, photo").ilike("name", f"%{query}%").execute()
        if players.data:
            for p in players.data:
                st.image(p.get('photo', ''), width=30)
                st.markdown(f"[{p['name']}](/player?player_id={p['id']})")
        else:
            st.info("لا يوجد لاعبين مطابقين")
