import streamlit as st
from supabase import create_client

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("تم إنشاء الحساب! تحقق من بريدك الإلكتروني.")
        else:
            st.error("حدث خطأ")
    except Exception as e:
        st.error(str(e))

def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            st.session_state.user = res.user
            load_favorites()
            load_profile()
            st.rerun()
        else:
            st.error("بيانات الدخول غير صحيحة")
    except Exception as e:
        st.error(str(e))

def sign_out():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.favorites = []
    st.session_state.profile = None
    st.rerun()

def load_favorites():
    if st.session_state.user:
        res = supabase.table("favorites").select("team_name").eq("user_id", st.session_state.user.id).execute()
        st.session_state.favorites = [row["team_name"] for row in res.data]

def load_profile():
    if st.session_state.user:
        res = supabase.table("user_profiles").select("*").eq("user_id", st.session_state.user.id).execute()
        if res.data:
            st.session_state.profile = res.data[0]

def toggle_favorite(team_name):
    if not st.session_state.user:
        st.warning("يجب تسجيل الدخول أولاً")
        return False
    if team_name in st.session_state.favorites:
        supabase.table("favorites").delete().eq("user_id", st.session_state.user.id).eq("team_name", team_name).execute()
        st.session_state.favorites.remove(team_name)
    else:
        supabase.table("favorites").insert({"user_id": st.session_state.user.id, "team_name": team_name}).execute()
        st.session_state.favorites.append(team_name)
    return True
