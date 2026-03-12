import streamlit as st
from supabase import create_client

st.set_page_config(page_title="الأخبار", page_icon="📰")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

st.title("📰 آخر الأخبار")

news = supabase.table("news").select("*").order("published_at", desc=True).limit(50).execute()
if news.data:
    for item in news.data:
        with st.container():
            col1, col2 = st.columns([1,4])
            with col1:
                if item.get("image"):
                    st.image(item["image"], width=100)
            with col2:
                st.subheader(item["title"])
                st.write(item.get("content", "")[:200] + "...")
                st.caption(f"المصدر: {item['source']} | {item['published_at'][:10]}")
            st.markdown("---")
else:
    st.info("لا توجد أخبار حالياً")
