import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import time
import requests
import json

# --- Page config ---
st.set_page_config(
    page_title="مركز الكرة العربية | مشاهدة المباريات مجاناً",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Auto-refresh page every 5 minutes ---
# Auto-refresh page every 5 minutes using meta tag
st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)

# --- Load secrets ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

# --- Connect to Supabase ---
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = init_supabase()

# --- Inject ad scripts into <head> using st.markdown with unsafe_allow_html ---
# PropellerAds push notification script (place in head)
st.markdown("""
<script type="text/javascript" data-cfasync="false" src="https://your-propellerads-script.com"></script>
""", unsafe_allow_html=True)

# Infolinks in-text ads script
st.markdown("""
<script type="text/javascript">
    var infolinks_pid = 1234567;  // Replace with your PID
    var infolinks_wsid = 0;
</script>
<script type="text/javascript" src="//resources.infolinks.com/js/infolinks_main.js"></script>
""", unsafe_allow_html=True)

# --- Professional RTL styling ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * {
        font-family: 'Cairo', sans-serif;
    }
    
    .main, .block-container, [data-testid="stMarkdownContainer"] {
        direction: rtl;
        text-align: right;
    }
    
    .match-card {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a40 100%);
        color: white;
        padding: 25px;
        border-radius: 20px;
        margin: 20px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        border: 1px solid #333;
        transition: transform 0.3s;
    }
    .match-card:hover {
        transform: translateY(-5px);
    }
    
    .live-badge {
        background: linear-gradient(45deg, #ff4444, #ff6b6b);
        color: white;
        padding: 5px 15px;
        border-radius: 25px;
        font-size: 14px;
        font-weight: bold;
        display: inline-block;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .stream-btn {
        background: #ff6b6b;
        color: white;
        padding: 10px 20px;
        border-radius: 30px;
        text-decoration: none;
        font-weight: 600;
        display: inline-block;
        margin: 5px 10px 5px 0;
        border: none;
        cursor: pointer;
        transition: background 0.3s;
    }
    .stream-btn:hover {
        background: #ff5252;
        color: white;
    }
    
    .verified {
        background: #4CAF50;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin-left: 5px;
    }
    
    .countdown {
        color: #ffd700;
        font-weight: bold;
    }
    
    .trust-badge {
        background: #4CAF50;
        color: white;
        padding: 5px 15px;
        border-radius: 5px;
        font-size: 14px;
        text-align: center;
        margin: 10px 0;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #1e1e2f;
    }
    .sidebar-content {
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    st.image("https://img.icons8.com/color/96/000000/football2--v1.png", width=80)
    st.markdown("<h1 style='text-align: center;'>⚽ **مركز الكرة العربية**</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 18px;'>جميع المباريات • روابط بث مجانية موثوقة • تحديثات مباشرة</p>", unsafe_allow_html=True)
    st.markdown("<div class='trust-badge'>✓ روابط رسمية ومجانية فقط • لا إعلانات مزعجة</div>", unsafe_allow_html=True)

st.markdown("---")

# --- Sidebar ---
with st.sidebar:
    st.header("📢 **ادعم الموقع**")
    st.info("الإعلانات تساعدنا في استمرار الخدمة مجاناً للجميع.")
    
    # Affiliate banner (e.g., 1xBet) – replace with your affiliate link and image
    st.markdown("""
    <a href="https://your-affiliate-link.com" target="_blank">
        <img src="https://example.com/banner.jpg" style="width:100%; border-radius:10px;">
    </a>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.header("📲 **تابعنا**")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("[![WhatsApp](https://img.icons8.com/color/48/000000/whatsapp--v1.png)](https://whatsapp.com)")
    with cols[1]:
        st.markdown("[![Telegram](https://img.icons8.com/color/48/000000/telegram-app--v1.png)](https://t.me/your_bot)")
    
    st.markdown("---")
    st.header("⚙️ **الإعدادات**")
    low_bandwidth = st.checkbox("وضع الانترنت الضعيف (نص فقط)")
    
    st.markdown("---")
    st.subheader("🔔 **اشتراك التنبيهات**")
    with st.form("alert_form"):
        chat_id = st.text_input("معرف التليجرام (اختياري)")
        phone = st.text_input("رقم الواتساب (اختياري)")
        fav_teams = st.multiselect("الفرق المفضلة", ["الهلال", "النصر", "الأهلي", "الزمالك", "الوداد", "الترجي"])
        submitted = st.form_submit_button("اشتراك")
        if submitted and (chat_id or phone):
            data = {}
            if chat_id:
                data["chat_id"] = chat_id
            if phone:
                data["phone"] = phone
            if fav_teams:
                data["favorite_teams"] = fav_teams
            supabase.table("subscribers").insert(data).execute()
            st.success("تم الاشتراك بنجاح! ✅")
    
    st.markdown("---")
    st.markdown("### 📍 **أماكن المشاهدة العامة**")
    st.markdown("ساهم في إضافة مقاهي تعرض المباريات [من هنا](https://forms.gle/...)")
    
    # Last update time
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(f"🕒 آخر تحديث للصفحة: {last_update}")

# --- Fetch matches from Supabase ---
@st.cache_data(ttl=60)
def get_matches():
    response = supabase.table("matches").select("*").order("match_time", desc=False).execute()
    return response.data

matches = get_matches()

# --- Helper: time until match ---
def time_until(match_time_str):
    try:
        match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
        now = datetime.now(match_time.tzinfo)
        diff = match_time - now
        if diff.total_seconds() < 0:
            return "انتهت"
        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)
        return f"{hours} س {minutes} د"
    except:
        return "---"

# --- LIVE matches ---
st.header("🔥 **المباريات المباشرة الآن**")
live_matches = [m for m in matches if m["status"] == "LIVE"]

if live_matches:
    for match in live_matches:
        streams = match.get("streams", [])
        if isinstance(streams, str):
            try:
                streams = json.loads(streams)
            except:
                streams = []
        broadcasters = match.get("broadcasters", [])
        with st.container():
            st.markdown(f"""
            <div class="match-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2>{match['home_team']} vs {match['away_team']}</h2>
                    <span class="live-badge">🔴 مباشر</span>
                </div>
                <p style="font-size: 18px;">🏆 {match['league']} | ⚽ {match['home_score']} - {match['away_score']}</p>
                <div style="margin-top: 15px;">
                    {"".join([f'<a class="stream-btn" href="{s["url"]}" target="_blank">📺 {s["title"][:30]}... {"<span class=\"verified\">موثوق</span>" if s.get("verified") else ""}</a>' for s in streams]) if streams else "<p>سيتم إضافة روابط البث قريباً...</p>"}
                </div>
                <div style="margin-top: 10px;">
                    <p><strong>أين تشاهد:</strong> {", ".join([f'<a href="{b["url"]}" target="_blank">{b["name"]}</a>' for b in broadcasters]) if broadcasters else "تابع التحديثات"}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("لا توجد مباريات مباشرة حالياً. تحقق من المباريات القادمة 👇")

# --- UPCOMING matches ---
st.header("📅 **المباريات القادمة**")
upcoming = [m for m in matches if m["status"] == "UPCOMING"][:15]

if upcoming:
    cols = st.columns(2)
    for i, match in enumerate(upcoming):
        with cols[i % 2]:
            streams = match.get("streams", [])
            if isinstance(streams, str):
                try:
                    streams = json.loads(streams)
                except:
                    streams = []
            broadcasters = match.get("broadcasters", [])
            time_left = time_until(match['match_time'])
            with st.container():
                st.markdown(f"""
                <div style="background: #2a2a40; padding: 15px; border-radius: 15px; margin-bottom: 15px;">
                    <h4>{match['home_team']} vs {match['away_team']}</h4>
                    <p>🏆 {match['league']}</p>
                    <p><span class="countdown">⏳ {time_left}</span></p>
                    {"".join([f'<a class="stream-btn" style="padding:5px 10px; font-size:14px;" href="{s["url"]}" target="_blank">▶️ بث</a>' for s in streams]) if streams else "<p style='color:#aaa'>الروابط قبل المباراة بساعة</p>"}
                    <p><small>أين تشاهد: {", ".join([b["name"] for b in broadcasters]) if broadcasters else "غير معروف"}</small></p>
                </div>
                """, unsafe_allow_html=True)
else:
    st.write("لا توجد مباريات قادمة حالياً.")

# --- Low bandwidth mode ---
if low_bandwidth:
    st.markdown("---")
    st.header("📊 **متابعة النص المباشر**")
    st.info("هنا ستظهر أحداث المباريات نصياً (سيتم إضافته قريباً).")

# --- Public viewing map ---
st.markdown("---")
st.header("📍 **أماكن المشاهدة العامة**")
venues = supabase.table("venues").select("*").eq("approved", True).execute().data
if venues:
    df_venues = pd.DataFrame(venues)
    st.map(df_venues[["latitude", "longitude"]])
    for v in venues:
        st.markdown(f"- **{v['name']}** – {v['address']}")
else:
    st.markdown("لا توجد أماكن بعد. كن أول من يضيف مقهى [من هنا](https://forms.gle/...).")

# --- Community stream submission ---
st.markdown("---")
st.header("➕ **اقترح رابط بث مجاني**")
with st.form("suggest_stream"):
    match_name = st.text_input("اسم المباراة")
    stream_url = st.text_input("رابط البث (يوتيوب، فيسبوك، ...)")
    source = st.selectbox("المصدر", ["YouTube", "Facebook", "موقع آخر"])
    submitted = st.form_submit_button("إرسال")
    if submitted and match_name and stream_url:
        data = {
            "match_name": match_name,
            "url": stream_url,
            "source": source,
            "submitted_at": datetime.now().isoformat(),
            "approved": False
        }
        supabase.table("suggested_streams").insert(data).execute()
        st.success("شكراً! سيتم مراجعة الرابط وإضافته قريباً.")

# --- PopAds pop-under script (place at bottom) ---
st.components.v1.html("""
    <script src="//popads.net/pop.js" async></script>
""", height=0)

# --- Footer with donation ---
st.markdown("---")
st.markdown("""
<div style='text-align: center; background: linear-gradient(135deg, #1e1e2f, #2a2a40); padding: 30px; border-radius: 20px;'>
    <h3 style='color: white;'>ادعم استمرارية الموقع</h3>
    <p style='color: #ccc;'>تبرعك يساعد في توفير خدمة أفضل للجميع، خاصة لمن لا يستطيعون الاشتراك.</p>
    <a href='https://www.paypal.com/donate/?hosted_button_id=YOUR_ID' target='_blank'>
        <img src='https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif' alt='Donate'/>
    </a>
    <p style='color: #888; font-size: 12px; margin-top: 20px;'>جميع الروابط مجانية وموثوقة • لا نشارك في القرصنة</p>
</div>
""", unsafe_allow_html=True)

# --- Footer links ---
st.markdown("""
<div style='text-align: center; margin-top: 20px;'>
    <a href="#">من نحن</a> | <a href="#">سياسة الخصوصية</a> | <a href="#">اتصل بنا</a>
</div>
""", unsafe_allow_html=True)
