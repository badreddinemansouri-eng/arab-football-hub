import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import pandas as pd

st.set_page_config(page_title="فريق", page_icon="🏟️", layout="wide")

# -------------------- Init --------------------
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

team_id = st.query_params.get("team_id")
if not team_id:
    st.error("لم يتم تحديد الفريق")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

try:
    team_id = int(team_id)
except ValueError:
    st.error("معرف الفريق غير صالح")
    st.stop()

# -------------------- Get local team --------------------
@st.cache_data(ttl=3600)
def get_local_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_local_team(team_id)
if not team:
    st.warning("الفريق غير موجود في قاعدة البيانات")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# -------------------- Fetch team matches --------------------
@st.cache_data(ttl=30)
def get_team_matches(tid):
    home = supabase.table("matches").select("*").eq("home_team_id", tid).execute().data
    away = supabase.table("matches").select("*").eq("away_team_id", tid).execute().data
    all_m = home + away
    all_m.sort(key=lambda x: x['match_time'], reverse=True)
    return all_m

matches = get_team_matches(team_id)
upcoming = [m for m in matches if m['status'] == 'UPCOMING']
finished = [m for m in matches if m['status'] == 'FINISHED']

# -------------------- Wikidata SPARQL query for team info --------------------
@st.cache_data(ttl=86400)  # cache for a day
def query_wikidata(team_name):
    """
    Query Wikidata for information about a football team.
    Returns a dict with keys: founded, stadium, stadiumCapacity, country, coach, honours, logo
    """
    sparql = f"""
    SELECT DISTINCT ?team ?teamLabel ?founded ?stadium ?stadiumLabel ?capacity ?countryLabel ?coachLabel ?logo ?honours WHERE {{
      ?team rdfs:label "{team_name}"@en.
      OPTIONAL {{ ?team wdt:P571 ?founded. }}
      OPTIONAL {{ ?team wdt:P115 ?stadium. ?stadium wdt:P1083 ?capacity. }}
      OPTIONAL {{ ?team wdt:P17 ?country. }}
      OPTIONAL {{ ?team wdt:P286 ?coach. }}
      OPTIONAL {{ ?team wdt:P154 ?logo. }}
      OPTIONAL {{ ?team wdt:P166 ?honours. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ar,en". }}
    }}
    LIMIT 1
    """
    url = "https://query.wikidata.org/sparql"
    try:
        resp = requests.get(url, params={"query": sparql, "format": "json"}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            bindings = data["results"]["bindings"]
            if bindings:
                b = bindings[0]
                return {
                    "founded": b.get("founded", {}).get("value"),
                    "stadium": b.get("stadiumLabel", {}).get("value"),
                    "capacity": b.get("capacity", {}).get("value"),
                    "country": b.get("countryLabel", {}).get("value"),
                    "coach": b.get("coachLabel", {}).get("value"),
                    "logo": b.get("logo", {}).get("value"),
                    "honours": b.get("honours", {}).get("value")  # may be multiple; we'll just get one
                }
    except Exception as e:
        print(f"Wikidata query error: {e}")
    return {}

# -------------------- Fetch Wikidata info --------------------
wiki = query_wikidata(team['name'])

# -------------------- Fallback logo (initials) --------------------
def get_logo():
    if wiki.get("logo"):
        return wiki["logo"]
    # else use simple initials
    return f"https://ui-avatars.com/api/?name={team['name'][:2].upper()}&background=1976d2&color=fff&size=200&bold=true&length=2"

logo = get_logo()

# -------------------- Statistics --------------------
wins = draws = losses = 0
for m in finished:
    if m['home_team_id'] == team_id:
        if m['home_score'] > m['away_score']:
            wins += 1
        elif m['home_score'] == m['away_score']:
            draws += 1
        else:
            losses += 1
    else:
        if m['away_score'] > m['home_score']:
            wins += 1
        elif m['away_score'] == m['home_score']:
            draws += 1
        else:
            losses += 1

# -------------------- Modern CSS (same as before) --------------------
st.markdown("""
<style>
    .header-card { background: linear-gradient(135deg, #1e1e2f, #2a2a40); border-radius: 20px; padding: 2rem; margin-bottom: 2rem; display: flex; align-items: center; gap: 2rem; color: white; box-shadow: 0 8px 20px rgba(0,0,0,0.3); }
    .logo { width: 100px; height: 100px; border-radius: 50%; border: 3px solid #1976d2; background: white; object-fit: contain; }
    .team-name { font-size: 2.5rem; font-weight: 700; margin: 0; }
    .team-meta { color: #aaa; margin-top: 0.5rem; }
    .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
    .stat-card { background: #1e1e2f; border-radius: 15px; padding: 1.5rem; text-align: center; color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    .stat-number { font-size: 2rem; font-weight: 700; color: #1976d2; }
    .stat-label { color: #aaa; font-size: 0.9rem; }
    .section-title { font-size: 1.5rem; font-weight: 600; margin: 2rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #1976d2; color: white; }
    .match-card { background: #1e1e2f; border-radius: 12px; padding: 1rem 1.5rem; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; color: white; border: 1px solid #333; transition: all 0.2s; }
    .match-card:hover { border-color: #1976d2; transform: translateX(5px); }
    .match-score { font-weight: 700; color: #1976d2; }
    .empty-message { color: #888; text-align: center; padding: 2rem; border: 1px dashed #444; border-radius: 10px; }
    .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }
    .info-item { background: #1e1e2f; border-radius: 10px; padding: 1rem; color: white; }
    .info-label { color: #aaa; font-size: 0.9rem; }
    .info-value { font-size: 1.2rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# -------------------- Header --------------------
st.markdown(f"""
<div class="header-card">
    <img src="{logo}" class="logo">
    <div>
        <h1 class="team-name">{team['name']}</h1>
        <div class="team-meta">
            {wiki.get('country', '')} • {wiki.get('founded', '')} • {wiki.get('stadium', '')}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------- Stats Row --------------------
st.markdown(f"""
<div class="stat-grid">
    <div class="stat-card"><div class="stat-number">{len(matches)}</div><div class="stat-label">إجمالي المباريات</div></div>
    <div class="stat-card"><div class="stat-number">{wins}</div><div class="stat-label">فوز</div></div>
    <div class="stat-card"><div class="stat-number">{draws}</div><div class="stat-label">تعادل</div></div>
    <div class="stat-card"><div class="stat-number">{losses}</div><div class="stat-label">خسارة</div></div>
</div>
""", unsafe_allow_html=True)

# -------------------- Tabs --------------------
tab1, tab2 = st.tabs(["📅 المباريات", "ℹ️ معلومات الفريق"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-title">🔜 المباريات القادمة</div>', unsafe_allow_html=True)
        if upcoming:
            for m in upcoming[:5]:
                try:
                    dt = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                    time_str = dt.strftime("%Y/%m/%d %H:%M")
                except:
                    time_str = m["match_time"][:16]
                st.markdown(f'<div class="match-card"><span>{m["home_team"]} – {m["away_team"]}</span> <span>{time_str}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-message">لا توجد مباريات قادمة</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-title">📋 آخر النتائج</div>', unsafe_allow_html=True)
        if finished:
            for m in finished[:5]:
                try:
                    dt = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                    date_str = dt.strftime("%Y/%m/%d")
                except:
                    date_str = m["match_time"][:10]
                score = f"{m['home_score']} – {m['away_score']}"
                st.markdown(f'<div class="match-card"><span>{m["home_team"]} {score} {m["away_team"]}</span> <span>{date_str}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-message">لا توجد نتائج مسجلة</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="section-title">ℹ️ معلومات الفريق</div>', unsafe_allow_html=True)
    info = [
        ("الدوري", team.get('league', '–')),
        ("البلد", wiki.get('country', '–')),
        ("التأسيس", wiki.get('founded', '–')),
        ("الملعب", wiki.get('stadium', '–')),
        ("السعة", wiki.get('capacity', '–')),
        ("المدرب", wiki.get('coach', '–')),
        ("معرف الفريق", team_id),
    ]
    html = '<div class="info-grid">'
    for label, value in info:
        html += f'<div class="info-item"><div class="info-label">{label}</div><div class="info-value">{value}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

    if wiki.get('honours'):
        st.markdown('<div class="section-title">🏆 الإنجازات</div>', unsafe_allow_html=True)
        st.write(wiki['honours'])

# -------------------- Footer --------------------
st.markdown("---")
st.markdown("<div style='text-align:center; color:#888; font-size:0.9rem;'>بيانات من قاعدة البيانات وويكي بيانات</div>", unsafe_allow_html=True)
