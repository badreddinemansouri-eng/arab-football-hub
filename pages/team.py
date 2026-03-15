import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import hashlib
import re
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

# -------------------- Get local team from Supabase --------------------
@st.cache_data(ttl=3600)
def get_local_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_local_team(team_id)
if not team:
    st.warning("الفريق غير موجود في قاعدة البيانات المحلية")
    if st.button("🏠 العودة إلى الرئيسية"):
        st.switch_page("app.py")
    st.stop()

# -------------------- TheSportsDB API helpers --------------------
@st.cache_data(ttl=3600)
def search_team_by_name(name):
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(name)}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data["teams"][0] if data.get("teams") else None
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def get_players(tsdb_id):
    url = f"https://www.thesportsdb.com/api/v1/json/3/lookup_all_players.php?id={tsdb_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("player", [])
    except:
        pass
    return []

@st.cache_data(ttl=3600)
def get_recent_events(tsdb_id):
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventslast.php?id={tsdb_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("results", [])
    except:
        pass
    return []

@st.cache_data(ttl=3600)
def get_next_events(tsdb_id):
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsnext.php?id={tsdb_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("events", [])
    except:
        pass
    return []

@st.cache_data(ttl=3600)
def get_honours(tsdb_id):
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchhonours.php?id={tsdb_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("honours", [])
    except:
        pass
    return []

# -------------------- Wikidata helper (fallback for extra info) --------------------
@st.cache_data(ttl=86400)
def query_wikidata(team_name):
    sparql = f"""
    SELECT DISTINCT ?founded ?capacity ?countryLabel ?coachLabel ?logo WHERE {{
      ?team rdfs:label "{team_name}"@en.
      OPTIONAL {{ ?team wdt:P571 ?founded. }}
      OPTIONAL {{ ?team wdt:P115 ?stadium. ?stadium wdt:P1083 ?capacity. }}
      OPTIONAL {{ ?team wdt:P17 ?country. }}
      OPTIONAL {{ ?team wdt:P286 ?coach. }}
      OPTIONAL {{ ?team wdt:P154 ?logo. }}
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
                    "capacity": b.get("capacity", {}).get("value"),
                    "country": b.get("countryLabel", {}).get("value"),
                    "coach": b.get("coachLabel", {}).get("value"),
                    "logo": b.get("logo", {}).get("value"),
                }
    except:
        pass
    return {}

# -------------------- Fetch external data --------------------
tsdb_team = search_team_by_name(team['name'])
tsdb_id = tsdb_team.get('idTeam') if tsdb_team else None

players = get_players(tsdb_id) if tsdb_id else []
recent_events = get_recent_events(tsdb_id) if tsdb_id else []
next_events = get_next_events(tsdb_id) if tsdb_id else []
honours = get_honours(tsdb_id) if tsdb_id else []

wiki = query_wikidata(team['name'])

# -------------------- Helper functions --------------------
def safe_str(val, default="–"):
    return str(val) if val else default

def format_date(tsdb_date_str):
    try:
        return datetime.strptime(tsdb_date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
    except:
        return tsdb_date_str

def get_flag_url(country_name):
    if not country_name:
        return None
    return f"https://flagpedia.net/data/flags/icon/72x54/{country_name.lower().replace(' ', '-')}.png"

# -------------------- Logo resolver (multi‑source) --------------------
def get_team_logo():
    # 1. TheSportsDB logo
    if tsdb_team and tsdb_team.get('strTeamBadge'):
        return tsdb_team['strTeamBadge']
    # 2. Wikidata logo
    if wiki.get('logo'):
        return wiki['logo']
    # 3. Clearbit from website
    if tsdb_team and tsdb_team.get('strWebsite'):
        domain = tsdb_team['strWebsite'].replace("https://", "").replace("http://", "").split("/")[0]
        clearbit_url = f"https://logo.clearbit.com/{domain}"
        try:
            if requests.head(clearbit_url, timeout=2).status_code == 200:
                return clearbit_url
        except:
            pass
    # 4. Fallback initials
    name = team['name']
    words = name.split()
    if len(words) == 1:
        initials = words[0][:2].upper()
    else:
        initials = (words[0][0] + words[-1][0]).upper()
    color = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=200&bold=true&length=2"

logo = get_team_logo()

# -------------------- Fetch matches from Supabase --------------------
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

# -------------------- Team statistics --------------------
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

# -------------------- Get current league position from standings (if available) --------------------
position = "–"
try:
    league_code = team.get('league_id')  # you'd need to store this; fallback to None
    if league_code:
        standings_res = supabase.table("standings").select("data").eq("competition_code", league_code).execute()
        if standings_res.data:
            data = standings_res.data[0]["data"]
            table = data.get("standings", [])[0].get("table", [])
            for row in table:
                if row["team"]["id"] == team_id:
                    position = row["position"]
                    break
except:
    pass

# -------------------- Beautiful Light CSS --------------------
st.markdown("""
<style>
    /* Main container */
    .main {
        background: #f8f9fa;
        direction: rtl;
    }
    /* Team header */
    .team-header {
        background: white;
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 2rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    .team-logo {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 3px solid #1976d2;
        background: white;
        object-fit: contain;
        padding: 5px;
    }
    .team-name {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        color: #333;
    }
    .team-meta {
        color: #666;
        margin-top: 0.5rem;
        display: flex;
        gap: 2rem;
        flex-wrap: wrap;
    }
    .team-meta-item {
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }
    /* Stat cards */
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #1976d2;
    }
    .stat-label {
        color: #666;
        font-size: 0.9rem;
    }
    /* Section titles */
    .section-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin: 2rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #1976d2;
        color: #333;
    }
    /* Match cards */
    .match-card {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin-bottom: 0.75rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border: 1px solid #eee;
        transition: all 0.2s;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }
    .match-card:hover {
        border-color: #1976d2;
        transform: translateX(5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .match-score {
        font-weight: 700;
        color: #1976d2;
    }
    .empty-message {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        color: #888;
        border: 1px dashed #ddd;
    }
    /* Player cards */
    .player-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin: 1rem 0;
    }
    .player-card {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #eee;
        transition: transform 0.2s;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }
    .player-card:hover {
        transform: translateY(-5px);
        border-color: #1976d2;
        box-shadow: 0 8px 16px rgba(0,0,0,0.05);
    }
    .player-card img {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        object-fit: cover;
        margin-bottom: 0.5rem;
        border: 2px solid #eee;
    }
    .player-name {
        font-weight: 600;
        margin: 0.5rem 0 0.2rem;
        color: #333;
    }
    .player-detail {
        color: #888;
        font-size: 0.85rem;
    }
    /* Info grid */
    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    .info-item {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #eee;
    }
    .info-label {
        color: #888;
        font-size: 0.9rem;
    }
    .info-value {
        font-size: 1.2rem;
        font-weight: 600;
        color: #333;
    }
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background: white;
        padding: 0.5rem;
        border-radius: 30px;
        border: 1px solid #eee;
        margin-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 30px;
        padding: 0.5rem 1.5rem;
        color: #666;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1976d2;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Header --------------------
country_flag = get_flag_url(tsdb_team.get('strCountry') if tsdb_team else team.get('country'))

st.markdown(f"""
<div class="team-header">
    <img src="{logo}" class="team-logo">
    <div>
        <h1 class="team-name">{team['name']}</h1>
        <div class="team-meta">
            <span class="team-meta-item">{country_flag and f'<img src="{country_flag}" width="24">' or ''} {tsdb_team.get('strCountry') or wiki.get('country') or team.get('country') or ''}</span>
            <span class="team-meta-item">🏟️ {tsdb_team.get('strStadium') or team.get('venue_name') or '–'}</span>
            <span class="team-meta-item">📅 {tsdb_team.get('intFormedYear') or wiki.get('founded') or team.get('founded') or '–'}</span>
            <span class="team-meta-item">⚽ {tsdb_team.get('strManager') or wiki.get('coach') or '–'}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------- Stats Row --------------------
st.markdown(f"""
<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-number">{len(matches)}</div>
        <div class="stat-label">إجمالي المباريات</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{wins}</div>
        <div class="stat-label">فوز</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{draws}</div>
        <div class="stat-label">تعادل</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{losses}</div>
        <div class="stat-label">خسارة</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{position}</div>
        <div class="stat-label">الترتيب</div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------- Tabs --------------------
tab1, tab2, tab3, tab4 = st.tabs(["📅 المباريات", "👥 التشكيلة", "🏆 الإنجازات", "ℹ️ معلومات"])

# ==================== TAB 1: Matches ====================
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-title">🔜 المباريات القادمة</div>', unsafe_allow_html=True)
        if next_events:
            for ev in next_events[:5]:
                date_str = format_date(ev.get('dateEvent', ''))
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
                st.markdown(f'<div class="match-card"><span><strong>{home}</strong> vs <strong>{away}</strong></span> <span>{date_str}</span></div>', unsafe_allow_html=True)
        elif upcoming:
            for m in upcoming[:5]:
                try:
                    dt = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                    time_str = dt.strftime("%Y/%m/%d %H:%M")
                except:
                    time_str = m["match_time"][:16]
                st.markdown(f'<div class="match-card"><span><strong>{m["home_team"]}</strong> – <strong>{m["away_team"]}</strong></span> <span>{time_str}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-message">لا توجد مباريات قادمة</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-title">📋 آخر النتائج</div>', unsafe_allow_html=True)
        if recent_events:
            for ev in recent_events[:5]:
                date_str = format_date(ev.get('dateEvent', ''))
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
                try:
                    hs = int(ev['intHomeScore'])
                    as_ = int(ev['intAwayScore'])
                    result = f"{hs} – {as_}"
                except:
                    result = "–"
                st.markdown(f'<div class="match-card"><span><strong>{home}</strong> {result} <strong>{away}</strong></span> <span>{date_str}</span></div>', unsafe_allow_html=True)
        elif finished:
            for m in finished[:5]:
                try:
                    dt = datetime.fromisoformat(m["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                    date_str = dt.strftime("%Y/%m/%d")
                except:
                    date_str = m["match_time"][:10]
                score = f"{m['home_score']} – {m['away_score']}"
                st.markdown(f'<div class="match-card"><span><strong>{m["home_team"]}</strong> {score} <strong>{m["away_team"]}</strong></span> <span>{date_str}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-message">لا توجد نتائج مسجلة</div>', unsafe_allow_html=True)

# ==================== TAB 2: Squad ====================
with tab2:
    st.markdown('<div class="section-title">👥 التشكيلة الحالية</div>', unsafe_allow_html=True)
    if not players:
        st.info("لا توجد معلومات عن اللاعبين (يمكن إضافتها عبر TheSportsDB)")
    else:
        # Group by position
        positions = {}
        for p in players:
            pos = p.get('strPosition', 'أخرى')
            positions.setdefault(pos, []).append(p)

        for pos, plist in positions.items():
            st.markdown(f"### {pos}")
            cols = st.columns(4)
            for i, player in enumerate(plist):
                with cols[i % 4]:
                    photo = player.get('strThumb') or player.get('strCutout') or 'https://via.placeholder.com/100'
                    st.markdown('<div class="player-card">', unsafe_allow_html=True)
                    st.image(photo, width=100)
                    st.markdown(f'<div class="player-name">{player.get("strPlayer", "")}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="player-detail">{player.get("strNumber", "")} | {player.get("strNationality", "")[:3]} | {player.get("strValue", "")}</div>', unsafe_allow_html=True)
                    if player.get('idPlayer'):
                        st.markdown(f"[🔗 الملف الشخصي](/player?player_id={player['idPlayer']})")
                    st.markdown('</div>', unsafe_allow_html=True)

# ==================== TAB 3: Honours ====================
with tab3:
    st.markdown('<div class="section-title">🏆 البطولات والألقاب</div>', unsafe_allow_html=True)
    if honours:
        honour_dict = {}
        for h in honours:
            comp = h.get('strHonour', 'أخرى')
            season = h.get('strSeason', '')
            honour_dict.setdefault(comp, []).append(season)

        for comp, seasons in honour_dict.items():
            with st.expander(f"**{comp}** ({len(seasons)})"):
                st.write("، ".join(seasons))
    else:
        st.info("لا توجد معلومات عن البطولات")

# ==================== TAB 4: Info ====================
with tab4:
    st.markdown('<div class="section-title">ℹ️ معلومات الفريق</div>', unsafe_allow_html=True)
    info = [
        ("الدوري", tsdb_team.get('strLeague') or team.get('league') or '–'),
        ("البلد", tsdb_team.get('strCountry') or wiki.get('country') or team.get('country') or '–'),
        ("التأسيس", tsdb_team.get('intFormedYear') or wiki.get('founded') or team.get('founded') or '–'),
        ("الملعب", tsdb_team.get('strStadium') or team.get('venue_name') or '–'),
        ("السعة", tsdb_team.get('intStadiumCapacity') or wiki.get('capacity') or '–'),
        ("المدرب", tsdb_team.get('strManager') or wiki.get('coach') or '–'),
        ("الموقع", tsdb_team.get('strWebsite') or '–'),
        ("معرف الفريق", team_id),
    ]
    html = '<div class="info-grid">'
    for label, value in info:
        if label == "الموقع" and value != "–":
            value = f'<a href="{value}" target="_blank">{value}</a>'
        html += f'<div class="info-item"><div class="info-label">{label}</div><div class="info-value">{value}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

    # Head‑to‑head against all opponents (optional)
    st.markdown('<div class="section-title">⚔️ سجل المواجهات</div>', unsafe_allow_html=True)
    opponents = {}
    for m in matches:
        if m['home_team_id'] == team_id:
            opp_id = m['away_team_id']
            opp_name = m['away_team']
            if opp_id not in opponents:
                opponents[opp_id] = {'name': opp_name, 'wins': 0, 'draws': 0, 'losses': 0}
            if m['home_score'] > m['away_score']:
                opponents[opp_id]['wins'] += 1
            elif m['home_score'] == m['away_score']:
                opponents[opp_id]['draws'] += 1
            else:
                opponents[opp_id]['losses'] += 1
        else:
            opp_id = m['home_team_id']
            opp_name = m['home_team']
            if opp_id not in opponents:
                opponents[opp_id] = {'name': opp_name, 'wins': 0, 'draws': 0, 'losses': 0}
            if m['away_score'] > m['home_score']:
                opponents[opp_id]['wins'] += 1
            elif m['away_score'] == m['home_score']:
                opponents[opp_id]['draws'] += 1
            else:
                opponents[opp_id]['losses'] += 1

    if opponents:
        data = []
        for opp in opponents.values():
            data.append({
                "الخصم": opp['name'],
                "فوز": opp['wins'],
                "تعادل": opp['draws'],
                "خسارة": opp['losses']
            })
        df = pd.DataFrame(data).sort_values("الخصم")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد مواجهات مسجلة")

# -------------------- Footer --------------------
st.markdown("---")
st.markdown("<div style='text-align:center; color:#888; font-size:0.9rem;'>بيانات من TheSportsDB, Wikidata, وقاعدة البيانات الخاصة بك</div>", unsafe_allow_html=True)
