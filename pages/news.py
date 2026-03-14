import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import html

st.set_page_config(page_title="الأخبار", page_icon="📰", layout="wide")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

st.title("📰 آخر الأخبار")

# Custom CSS for clean cards (light background, matches your design)
st.markdown("""
<style>
    .news-card {
        background: #ffffff;
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
        transition: transform 0.2s;
        direction: rtl;
    }
    .news-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }
    .news-image {
        width: 100%;
        max-height: 150px;
        object-fit: cover;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    .news-title {
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0 0 8px 0;
        color: #333;
        text-decoration: none;
    }
    .news-title a {
        color: #333;
        text-decoration: none;
    }
    .news-title a:hover {
        color: #1976d2;
    }
    .news-content {
        color: #666;
        margin: 0 0 12px 0;
        line-height: 1.6;
    }
    .news-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #888;
        font-size: 0.9rem;
        flex-wrap: wrap;
    }
    .source-badge {
        background: #1976d2;
        color: white;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
    }
    .lang-badge {
        background: #166534;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
    }
    .lang-badge.en {
        background: #1e3a8a;
    }
    /* Dark mode overrides (optional – remove if you want only light) */
    @media (prefers-color-scheme: dark) {
        .news-card {
            background: #1e1e2e;
            border-color: #333;
        }
        .news-title a {
            color: #f0f0f0;
        }
        .news-content {
            color: #aaa;
        }
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_news():
    # Show news from the last 14 days
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    try:
        res = supabase.table("news")\
            .select("*")\
            .gte("published_at", cutoff)\
            .order("published_at", desc=True)\
            .limit(50)\
            .execute()
        return res.data
    except Exception as e:
        st.error(f"حدث خطأ في جلب الأخبار: {e}")
        return []

news = get_news()

if not news:
    st.info("لا توجد أخبار حالياً")
else:
    for item in news:
        # Safely escape all strings
        safe_title = html.escape(item.get('title', ''))
        safe_content = html.escape(item.get('content', ''))[:200] + "..." if item.get('content') else ''
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
        lang = item.get("language", "ar")
        if lang == "en":
            lang_badge = '<span class="lang-badge en">🇬🇧 EN</span>'
        else:
            lang_badge = '<span class="lang-badge">🇸🇦 AR</span>'

        # Build the card HTML safely using an f-string with escaped variables
        card_html = f"""
        <div class="news-card">
        """

        if safe_image:
            card_html += f'<img src="{safe_image}" class="news-image">'

        card_html += f"""
            <a href="{safe_url}" target="_blank" class="news-title">
                <h3>{safe_title}</h3>
            </a>
            <div class="news-content">{safe_content}</div>
            <div class="news-meta">
                <span class="source-badge">📰 {safe_source}</span>
                <span>🕒 {date_str}</span>
                {lang_badge}
            </div>
        </div>
        """

        # Render using st.html if available (safer), else fallback to st.markdown
        try:
            if hasattr(st, 'html'):
                st.html(card_html)
            else:
                st.markdown(card_html, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"حدث خطأ في عرض الخبر: {e}")
