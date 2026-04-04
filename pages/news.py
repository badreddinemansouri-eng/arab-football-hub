import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import html

# ═══════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════
st.set_page_config(
    page_title="الأخبار | Badr TV",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════
#  SUPABASE
# ═══════════════════════════════════════════════
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

# ═══════════════════════════════════════════════
#  SESSION STATE (theme shared with app.py)
# ═══════════════════════════════════════════════
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

# ═══════════════════════════════════════════════
#  CSS — mirrors app.py design tokens exactly
# ═══════════════════════════════════════════════
is_dark = st.session_state.theme == "dark"

if is_dark:
    bg_primary    = "#0a0e1a"
    bg_secondary  = "#111827"
    bg_card       = "#1a2035"
    bg_card_hover = "#1e2845"
    text_primary  = "#f0f4ff"
    text_secondary= "#8899bb"
    border_color  = "#1e2d50"
else:
    bg_primary    = "#f0f4ff"
    bg_secondary  = "#e4eaf8"
    bg_card       = "#ffffff"
    bg_card_hover = "#f5f8ff"
    text_primary  = "#0a0e1a"
    text_secondary= "#5a6a8a"
    border_color  = "#d0daf0"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap');
*, *::before, *::after {{ font-family: 'Cairo', sans-serif !important; box-sizing: border-box; }}

header[data-testid="stHeader"], footer, #MainMenu, .stDeployButton {{ display: none !important; }}

.stApp {{ background: {bg_primary} !important; }}
.main, .block-container {{
    background: {bg_primary} !important;
    direction: rtl; text-align: right;
    padding-top: 0 !important;
    padding-bottom: 3rem;
    max-width: 100% !important;
}}

/* ── PAGE HEADER ── */
.page-header {{
    background: linear-gradient(135deg, #0d47a1 0%, #1565c0 50%, #1976d2 100%);
    padding: 20px 24px 18px;
    margin-bottom: 24px;
    border-radius: 0 0 20px 20px;
    box-shadow: 0 4px 24px rgba(13,71,161,0.4);
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.page-header-title {{
    font-size: 1.5rem;
    font-weight: 900;
    color: white;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
}}
.page-header-back {{
    background: rgba(255,255,255,.15);
    border: 1px solid rgba(255,255,255,.25);
    color: white;
    text-decoration: none;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: .82rem;
    font-weight: 600;
    transition: background .2s;
}}
.page-header-back:hover {{ background: rgba(255,255,255,.25); color: white; }}

/* ── FILTER BAR ── */
.filter-bar {{
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    padding: 0 4px;
}}
.filter-chip {{
    background: {bg_secondary};
    border: 1.5px solid {border_color};
    border-radius: 20px;
    padding: 5px 16px;
    font-size: .8rem;
    font-weight: 600;
    color: {text_secondary};
    cursor: pointer;
    transition: all .18s;
    text-decoration: none;
}}
.filter-chip.active, .filter-chip:hover {{
    background: linear-gradient(135deg,#1565c0,#1976d2);
    border-color: #1976d2;
    color: white;
}}

/* ── NEWS GRID ── */
.news-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 18px;
    margin-top: 4px;
}}

/* ── NEWS CARD ── */
.news-card {{
    background: {bg_card};
    border-radius: 18px;
    border: 1px solid {border_color};
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,.09);
    transition: transform .2s ease, box-shadow .2s ease;
    display: flex;
    flex-direction: column;
    position: relative;
}}
.news-card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 10px 32px rgba(25,118,210,.18);
    border-color: #1976d2;
}}
.news-card-accent {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #1565c0, #1976d2);
}}
.news-card-img {{
    width: 100%;
    height: 180px;
    object-fit: cover;
    display: block;
}}
.news-card-img-placeholder {{
    width: 100%;
    height: 80px;
    background: linear-gradient(135deg, #0d47a1 0%, #1976d2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: rgba(255,255,255,.4);
}}
.news-card-body {{
    padding: 16px 16px 14px;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
}}
.news-card-title {{
    font-size: .98rem;
    font-weight: 700;
    line-height: 1.55;
    color: {text_primary};
    text-decoration: none;
    display: block;
}}
.news-card-title:hover {{ color: #1976d2; }}
.news-card-excerpt {{
    font-size: .82rem;
    color: {text_secondary};
    line-height: 1.65;
    flex: 1;
}}
.news-card-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
    padding-top: 10px;
    border-top: 1px solid {border_color};
}}
.source-badge {{
    background: linear-gradient(135deg,#1565c0,#1976d2);
    color: white;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: .7rem;
    font-weight: 700;
    white-space: nowrap;
}}
.lang-badge {{
    background: #166534;
    color: white;
    padding: 3px 9px;
    border-radius: 12px;
    font-size: .68rem;
    font-weight: 600;
}}
.lang-badge.en {{ background: #1e3a8a; }}
.news-date {{
    font-size: .72rem;
    color: {text_secondary};
    white-space: nowrap;
}}

/* ── EMPTY STATE ── */
.empty-state {{
    text-align: center;
    padding: 60px 20px;
    color: {text_secondary};
}}
.empty-state-icon {{ font-size: 3rem; display: block; margin-bottom: 12px; }}

/* ── SCROLLBAR ── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: #1976d2; border-radius: 4px; }}

@media (max-width: 640px) {{
    .news-grid {{ grid-template-columns: 1fr; gap: 14px; }}
    .block-container {{ padding-left: 10px !important; padding-right: 10px !important; }}
    .page-header {{ padding: 14px 14px 12px; border-radius: 0 0 14px 14px; }}
    .page-header-title {{ font-size: 1.2rem; }}
}}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  PAGE HEADER
# ═══════════════════════════════════════════════
st.markdown("""
<div class="page-header">
    <div class="page-header-title">📰 آخر الأخبار</div>
    <a href="/" class="page-header-back">← الرئيسية</a>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  DATA FETCHER
# ═══════════════════════════════════════════════
@st.cache_data(ttl=1800)
def get_news(days: int = 14, limit: int = 60):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        return supabase.table("news")\
            .select("*")\
            .gte("published_at", cutoff)\
            .order("published_at", desc=True)\
            .limit(limit)\
            .execute().data or []
    except Exception:
        return []

# ═══════════════════════════════════════════════
#  LANGUAGE FILTER
# ═══════════════════════════════════════════════
lang_filter = st.query_params.get("lang", "all")

st.markdown(f"""
<div class="filter-bar">
    <a href="?lang=all"  class="filter-chip {'active' if lang_filter == 'all' else ''}">🌐 الكل</a>
    <a href="?lang=ar"   class="filter-chip {'active' if lang_filter == 'ar'  else ''}">🇸🇦 عربي</a>
    <a href="?lang=en"   class="filter-chip {'active' if lang_filter == 'en'  else ''}">🇬🇧 English</a>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  RENDER NEWS
# ═══════════════════════════════════════════════
news_items = get_news()

# Apply filter
if lang_filter in ("ar", "en"):
    news_items = [n for n in news_items if n.get("language", "ar") == lang_filter]

if not news_items:
    st.markdown("""
    <div class="empty-state">
        <span class="empty-state-icon">📭</span>
        لا توجد أخبار حالياً. حاول لاحقاً.
    </div>
    """, unsafe_allow_html=True)
else:
    # ── Build all cards as one HTML block ──────────────────────────────
    # FIX: Never use st.html() — it is broken in Streamlit 1.56 and outputs
    # internal protobuf debug text instead of rendering HTML.
    # We build the entire grid as a single st.markdown() call.
    grid_html = '<div class="news-grid">'

    for item in news_items:
        safe_title   = html.escape(item.get('title', ''))
        raw_content  = item.get('content', '') or ''
        safe_excerpt = html.escape(raw_content[:180]) + ("..." if len(raw_content) > 180 else "")
        safe_source  = html.escape(item.get('source', 'مصدر غير معروف'))
        safe_url     = html.escape(item.get('url', '#'))
        safe_image   = html.escape(item.get('image', '') or '')

        try:
            pub_dt   = datetime.fromisoformat(item["published_at"].replace('Z', '+00:00'))
            date_str = pub_dt.strftime("🕒 %Y-%m-%d %H:%M")
        except Exception:
            date_str = ""

        lang       = item.get("language", "ar")
        lang_badge = (
            '<span class="lang-badge en">🇬🇧 EN</span>'
            if lang == "en"
            else '<span class="lang-badge">🇸🇦 AR</span>'
        )

        img_html = (
            f'<img src="{safe_image}" class="news-card-img" loading="lazy">'
            if safe_image
            else '<div class="news-card-img-placeholder">⚽</div>'
        )

        grid_html += f"""
        <div class="news-card">
            <div class="news-card-accent"></div>
            <a href="{safe_url}" target="_blank" style="text-decoration:none;">
                {img_html}
            </a>
            <div class="news-card-body">
                <a href="{safe_url}" target="_blank" class="news-card-title">{safe_title}</a>
                {'<p class="news-card-excerpt">' + safe_excerpt + '</p>' if safe_excerpt else ''}
                <div class="news-card-footer">
                    <span class="source-badge">📰 {safe_source}</span>
                    {lang_badge}
                    <span class="news-date">{date_str}</span>
                </div>
            </div>
        </div>"""

    grid_html += '</div>'
    st.markdown(grid_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════
st.markdown(f"""
<div style="text-align:center; margin-top:40px; padding:20px;
            color:{text_secondary}; font-size:.78rem; border-top:1px solid {border_color};">
    Badr TV © {datetime.now().year} — منصة كرة القدم الشاملة
</div>
""", unsafe_allow_html=True)
