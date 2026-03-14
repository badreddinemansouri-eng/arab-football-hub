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
        # Safely escape all strings
        safe_title = html.escape(item.get('title', ''))
        safe_content = html.escape(item.get('content', ''))[:200] + "..."
        safe_source = html.escape(item.get('source', 'مصدر غير معروف'))
        safe_url = html.escape(item.get('url', ''))
        safe_image = html.escape(item.get('image', '')) if item.get('image') else None

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

        # Build HTML string
        html_content = f"""
        <div style="background: #1a1a2e; border-radius: 20px; padding: 16px; margin-bottom: 20px; border: 1px solid #333;">
            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
        """

        if safe_image:
            html_content += f'<img src="{safe_image}" style="width:100%; max-height:150px; object-fit:cover; border-radius:10px;">'

        html_content += f"""
                <div style="flex:1;">
                    <a href="{safe_url}" target="_blank" style="text-decoration: none; color: inherit;">
                        <h3 style="margin: 0 0 8px 0;">{safe_title}</h3>
                    </a>
                    <p style="color: #aaa; margin: 0 0 8px 0;">{safe_content}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; color: #888; font-size: 0.85rem; flex-wrap: wrap;">
                        <span>📰 {safe_source}</span>
                        <span>🕒 {date_str}</span>
                        {lang_badge}
                    </div>
                </div>
            </div>
        </div>
        """

        # Render safely
        try:
            # Use st.html if available (Streamlit ≥1.34), otherwise fallback to st.markdown
            if hasattr(st, 'html'):
                st.html(html_content)
            else:
                st.markdown(html_content, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"حدث خطأ في عرض الخبر: {e}")
