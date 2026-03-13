import streamlit as st
from supabase import create_client
from datetime import datetime
import html

st.set_page_config(page_title="الأخبار", page_icon="📰", layout="wide")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

st.title("📰 آخر الأخبار")

@st.cache_data(ttl=3600)
def get_news():
    res = supabase.table("news").select("*").order("published_at", desc=True).limit(50).execute()
    return res.data

news = get_news()

if not news:
    st.info("لا توجد أخبار حالياً")
else:
    for item in news:
        # Format publication date
        try:
            pub_date = datetime.fromisoformat(item["published_at"].replace('Z', '+00:00'))
            date_str = pub_date.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = "تاريخ غير معروف"

        # Language badge
        if item.get("language") == "en":
            lang_badge = '<span style="background: #1e3a8a; padding: 2px 8px; border-radius: 12px; color: white;">🇬🇧 EN</span>'
        else:
            lang_badge = '<span style="background: #166534; padding: 2px 8px; border-radius: 12px; color: white;">🇸🇦 AR</span>'

        # Image HTML
        image_html = f'<img src="{item["image"]}" style="width:100%; max-height:150px; object-fit:cover; border-radius:10px;">' if item.get("image") else ''

        st.markdown(f"""
        <div style="background: #1a1a2e; border-radius: 20px; padding: 16px; margin-bottom: 20px; border: 1px solid #333;">
            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                {image_html}
                <div style="flex:1;">
                    <a href="{item['url']}" target="_blank" style="text-decoration: none; color: inherit;">
                        <h3 style="margin: 0 0 8px 0;">{html.escape(item['title'])}</h3>
                    </a>
                    <p style="color: #aaa; margin: 0 0 8px 0;">{html.escape(item.get('content', ''))[:200]}...</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; color: #888; font-size: 0.85rem; flex-wrap: wrap;">
                        <span>📰 {html.escape(item.get('source', 'مصدر غير معروف'))}</span>
                        <span>🕒 {date_str}</span>
                        {lang_badge}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
