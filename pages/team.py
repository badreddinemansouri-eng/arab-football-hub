import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import hashlib
import re
import pandas as pd
import altair as alt
import time

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

# -------------------- Ultra logo resolver --------------------
def get_team_logo(team_name, team_website=None):
    # 1. Local cache
    res = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # 2. TheSportsDB
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(team_name)}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("teams"):
                logo = data["teams"][0].get("strTeamBadge")
                if logo:
                    supabase.table("team_logos").upsert({"team_name": team_name, "logo_url": logo}, on_conflict="team_name").execute()
                    return logo
    except:
        pass

    # 3. Clearbit
    if team_website:
        try:
            domain = team_website.replace("https://", "").replace("http://", "").split("/")[0]
            clearbit_url = f"https://logo.clearbit.com/{domain}"
            if requests.head(clearbit_url, timeout=2).status_code == 200:
                supabase.table("team_logos").upsert({"team_name": team_name, "logo_url": clearbit_url}, on_conflict="team_name").execute()
                return clearbit_url
        except:
            pass

    # 4. Wikipedia
    try:
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(team_name + ' football club')}&format=json"
        search_resp = requests.get(search_url, timeout=3)
        if search_resp.status_code == 200:
            search_data = search_resp.json()
            if search_data.get("query", {}).get("search"):
                page_title = search_data["query"]["search"][0]["title"]
                page_url = f"https://en.wikipedia.org/w/api.php?action=parse&page={requests.utils.quote(page_title)}&format=json&prop=text"
                page_resp = requests.get(page_url, timeout=3)
                if page_resp.status_code == 200:
                    page_data = page_resp.json()
                    html = page_data.get("parse", {}).get("text", {}).get("*", "")
                    match = re.search(r'<td[^>]*class="logo"[^>]*><img[^>]*src="([^"]+)"', html, re.IGNORECASE)
                    if match:
                        img_src = match.group(1)
                        if img_src.startswith("//"):
                            img_src = "https:" + img_src
                        supabase.table("team_logos").upsert({"team_name": team_name, "logo_url": img_src}, on_conflict="team_name").execute()
                        return img_src
    except:
        pass

    # 5. Fallback initials
    words = team_name.split()
    initials = (words[0][:2].upper()) if len(words)==1 else (words[0][0] + words[-1][0]).upper()
    color = hashlib.md5(team_name.encode()).hexdigest()[:6]
    return f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=200&bold=true&length=2"

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

# -------------------- Get local team --------------------
@st.cache_data(ttl=3600)
def get_local_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_local_team(team_id)
if not team:
    st.error("الفريق غير موجود في قاعدة البيانات المحلية")
    st.stop()

# -------------------- Fetch external data --------------------
tsdb_team = search_team_by_name(team['name'])
tsdb_id = tsdb_team.get('idTeam') if tsdb_team else None

players = get_players(tsdb_id) if tsdb_id else []
recent_events = get_recent_events(tsdb_id) if tsdb_id else []
next_events = get_next_events(tsdb_id) if tsdb_id else []
honours = get_honours(tsdb_id) if tsdb_id else []

# -------------------- Helper functions --------------------
def format_date(tsdb_date_str):
    try:
        return datetime.strptime(tsdb_date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
    except:
        return tsdb_date_str

def form_icon(result):
    return "✅" if result == "فوز" else "🤝" if result == "تعادل" else "❌"

def form_color(result):
    return "#28a745" if result == "فوز" else "#ffc107" if result == "تعادل" else "#dc3545"

# -------------------- Modern CSS (glass‑morphism) --------------------
st.markdown("""
<style>
    .hero-section {
        background: linear-gradient(135deg, #0b0b1a, #1a1a2e);
        border-radius: 30px;
        padding: 30px;
        margin-bottom: 30px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        position: relative;
        overflow: hidden;
    }
    .hero-section::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: url('https://images.unsplash.com/photo-1489944448-9e5f1b9b8b8e?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80') center/cover;
        opacity: 0.2;
        z-index: 0;
    }
    .hero-content {
        position: relative;
        z-index: 1;
        display: flex;
        align-items: center;
        gap: 30px;
    }
    .team-logo {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 4px solid #1976d2;
        background: white;
        box-shadow: 0 8px 20px rgba(0,0,0,0.5);
    }
    .team-name {
        font-size: 3rem;
        font-weight: 800;
        color: white;
        text-shadow: 2px 2px 8px black;
        margin: 0;
    }
    .team-tags {
        display: flex;
        gap: 20px;
        margin-top: 10px;
        color: #ccc;
    }
    .glass-card {
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(12px);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.2);
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        transition: transform 0.3s;
    }
    .glass-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 48px rgba(0,0,0,0.2);
    }
    .metric-card {
        background: rgba(255,255,255,0.05);
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        backdrop-filter: blur(8px);
    }
    .match-card {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #333;
        transition: all 0.3s;
    }
    .match-card:hover {
        background: rgba(255,255,255,0.1);
        transform: translateX(5px);
    }
    .player-card {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        border: 1px solid #333;
        transition: transform 0.3s;
        height: 100%;
    }
    .player-card:hover {
        transform: scale(1.05);
        background: rgba(255,255,255,0.1);
        border-color: #1976d2;
    }
    .player-card img {
        border-radius: 50%;
        margin-bottom: 10px;
        width: 100px;
        height: 100px;
        object-fit: cover;
    }
    .badge-icon {
        width: 24px;
        height: 24px;
        margin-right: 5px;
    }
    .honour-item {
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
        padding: 8px 12px;
        margin: 5px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Hero Section --------------------
logo = get_team_logo(team['name'], tsdb_team.get('strWebsite') if tsdb_team else None)

if tsdb_team and tsdb_team.get('strStadiumThumb'):
    stadium_bg = tsdb_team['strStadiumThumb']
else:
    stadium_bg = "https://images.unsplash.com/photo-1489944448-9e5f1b9b8b8e?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80"

st.markdown(f"""
<div class="hero-section" style="background: linear-gradient(135deg, #0b0b1a, #1a1a2e), url('{stadium_bg}'); background-size: cover; background-blend-mode: overlay;">
    <div class="hero-content">
        <img src="{logo}" class="team-logo">
        <div>
            <h1 class="team-name">{team['name']}</h1>
            <div class="team-tags">
                <span>🏆 {tsdb_team.get('strLeague', 'الدوري') if tsdb_team else 'الدوري'}</span>
                <span>🌍 {tsdb_team.get('strCountry', 'البلد') if tsdb_team else 'البلد'}</span>
                <span>🏟️ {tsdb_team.get('strStadium', 'الملعب') if tsdb_team else 'الملعب'}</span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------- Key Metrics --------------------
if recent_events:
    form_list = []
    for ev in recent_events[:5]:
        try:
            hs = int(ev['intHomeScore'])
            as_ = int(ev['intAwayScore'])
            if ev['idHomeTeam'] == tsdb_id:
                result = "فوز" if hs > as_ else "تعادل" if hs == as_ else "خسارة"
            else:
                result = "فوز" if as_ > hs else "تعادل" if as_ == hs else "خسارة"
        except:
            result = "غير معروف"
        form_list.append(result)
else:
    form_list = []

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("إجمالي المباريات", len(recent_events))
    st.markdown('</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    wins = form_list.count("فوز") if form_list else 0
    st.metric("الفوز", wins)
    st.markdown('</div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    draws = form_list.count("تعادل") if form_list else 0
    st.metric("تعادل", draws)
    st.markdown('</div>', unsafe_allow_html=True)
with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    losses = form_list.count("خسارة") if form_list else 0
    st.metric("خسارة", losses)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Tabs --------------------
tabs = st.tabs(["📊 نظرة عامة", "👥 التشكيلة", "📅 المباريات", "🏆 البطولات", "💬 ركن الجماهير"])

# ==================== TAB 1: Overview ====================
with tabs[0]:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚽ معلومات الفريق")
        if tsdb_team:
            st.write(f"**المدرب:** {tsdb_team.get('strManager', 'غير معروف')}")
            st.write(f"**الملعب:** {tsdb_team.get('strStadium', 'غير معروف')} (السعة: {tsdb_team.get('intStadiumCapacity', 'غير معروف')})")
            st.write(f"**التأسيس:** {tsdb_team.get('intFormedYear', 'غير معروف')}")
            if tsdb_team.get('strWebsite'):
                st.write(f"**الموقع:** [{tsdb_team['strWebsite']}]({tsdb_team['strWebsite']})")
            if tsdb_team.get('strDescriptionEN'):
                with st.expander("📝 نبذة"):
                    st.write(tsdb_team['strDescriptionEN'][:500] + "…")
        else:
            st.info("لا توجد معلومات إضافية")

    with col2:
        st.subheader("📊 آخر 5 مباريات")
        if form_list:
            cols = st.columns(5)
            for i, res in enumerate(form_list):
                icon = form_icon(res)
                color = form_color(res)
                cols[i].markdown(f"<div style='background:{color}; border-radius:8px; padding:10px; text-align:center; color:white; font-weight:bold;'>{icon}</div>", unsafe_allow_html=True)
        else:
            st.info("لا توجد مباريات حديثة")

        st.subheader("🔜 المباراة القادمة")
        if next_events:
            nxt = next_events[0]
            date_str = format_date(nxt.get('dateEvent', ''))
            home = nxt['strHomeTeam']
            away = nxt['strAwayTeam']
            st.info(f"**{home} vs {away}** – {date_str}")
        else:
            st.info("لا توجد مباريات قادمة")

# ==================== TAB 2: Squad ====================
with tabs[1]:
    st.subheader("التشكيلة الحالية")
    if not players:
        st.info("لا توجد معلومات عن اللاعبين")
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
                    st.markdown('<div class="player-card">', unsafe_allow_html=True)
                    photo = player.get('strThumb') or player.get('strCutout') or 'https://via.placeholder.com/100'
                    st.image(photo, width=100)
                    st.markdown(f"**{player.get('strPlayer', '')}**")
                    st.caption(f"{player.get('strNumber', '')} | {player.get('strNationality', '')[:3]}")
                    if player.get('strValue'):
                        st.caption(f"💰 {player['strValue']}")
                    if player.get('idPlayer'):
                        st.markdown(f"[🔗 الملف الشخصي](/player?player_id={player['idPlayer']})")
                    st.markdown('</div>', unsafe_allow_html=True)

# ==================== TAB 3: Matches ====================
with tabs[2]:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🗓️ المباريات القادمة")
        if next_events:
            for ev in next_events[:5]:
                date_str = format_date(ev.get('dateEvent', ''))
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
                st.markdown(f'<div class="match-card">**{home} vs {away}** – {date_str}</div>', unsafe_allow_html=True)
        else:
            # Fallback to Supabase
            home_f = supabase.table("matches").select("*").eq("home_team_id", team_id).eq("status", "UPCOMING").order("match_time").execute()
            away_f = supabase.table("matches").select("*").eq("away_team_id", team_id).eq("status", "UPCOMING").order("match_time").execute()
            fixtures = home_f.data + away_f.data
            fixtures.sort(key=lambda x: x['match_time'])
            if fixtures:
                for f in fixtures[:5]:
                    try:
                        dt = datetime.fromisoformat(f["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                        time_str = dt.strftime("%H:%M %Y-%m-%d")
                    except:
                        time_str = f["match_time"][:16]
                    st.markdown(f'<div class="match-card">**{f["home_team"]} vs {f["away_team"]}** – {time_str}</div>', unsafe_allow_html=True)
            else:
                st.info("لا توجد مباريات قادمة")

    with col2:
        st.subheader("📋 آخر النتائج")
        if recent_events:
            for ev in recent_events[:5]:
                date_str = format_date(ev.get('dateEvent', ''))
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
                try:
                    hs = int(ev['intHomeScore'])
                    as_ = int(ev['intAwayScore'])
                    result = f"{hs} - {as_}"
                except:
                    result = "غير متوفرة"
                st.markdown(f'<div class="match-card">**{home} {result} {away}** – {date_str}</div>', unsafe_allow_html=True)
        else:
            # Fallback to Supabase
            home_r = supabase.table("matches").select("*").eq("home_team_id", team_id).eq("status", "FINISHED").order("match_time", desc=True).limit(5).execute()
            away_r = supabase.table("matches").select("*").eq("away_team_id", team_id).eq("status", "FINISHED").order("match_time", desc=True).limit(5).execute()
            results = home_r.data + away_r.data
            results.sort(key=lambda x: x['match_time'], reverse=True)
            if results:
                for r in results[:5]:
                    try:
                        dt = datetime.fromisoformat(r["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                        date_str = dt.strftime("%Y-%m-%d")
                    except:
                        date_str = r["match_time"][:10]
                    score = f"{r['home_score']} - {r['away_score']}"
                    st.markdown(f'<div class="match-card">**{r["home_team"]} {score} {r["away_team"]}** – {date_str}</div>', unsafe_allow_html=True)
            else:
                st.info("لا توجد نتائج")

    # Head‑to‑Head vs main rival (if identifiable)
    st.subheader("⚔️ سجل المواجهات مع الغريم التقليدي")
    # For demo, use a fixed rival; you could compute most frequent opponent
    rival_id = 61 if team_id == 57 else None  # Arsenal vs Chelsea
    if rival_id:
        h2h_home = supabase.table("matches").select("*").eq("home_team_id", team_id).eq("away_team_id", rival_id).execute()
        h2h_away = supabase.table("matches").select("*").eq("home_team_id", rival_id).eq("away_team_id", team_id).execute()
        h2h = h2h_home.data + h2h_away.data
        if h2h:
            wins = draws = losses = 0
            for m in h2h:
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
            colw, cold, coll = st.columns(3)
            colw.metric("فوز", wins)
            cold.metric("تعادل", draws)
            coll.metric("خسارة", losses)
        else:
            st.info("لا توجد مواجهات مسجلة")

# ==================== TAB 4: Honours ====================
with tabs[3]:
    st.subheader("🏆 البطولات والألقاب")
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

# ==================== TAB 5: Fan Chat ====================
with tabs[4]:
    st.subheader("💬 تعليقات الجماهير")
    if "user" in st.session_state and st.session_state.user:
        new_msg = st.text_input("اكتب تعليقاً...")
        if st.button("إرسال") and new_msg:
            supabase.table("comments").insert({
                "match_id": team_id,
                "user_id": st.session_state.user.id,
                "content": new_msg
            }).execute()
            st.success("تم الإرسال")
            st.rerun()
    else:
        st.info("سجل الدخول للمشاركة")
    comments = supabase.table("comments").select("*").eq("match_id", team_id).order("created_at", desc=True).limit(20).execute()
    if comments.data:
        for c in comments.data:
            user_short = c['user_id'][:8] if c.get('user_id') else 'مستخدم'
            st.markdown(f"**{user_short}**: {c['content']}")
    else:
        st.write("لا توجد تعليقات بعد")

# -------------------- Footer --------------------
if tsdb_id:
    st.markdown("---")
    st.markdown(f"🔍 [عرض كامل على TheSportsDB](https://www.thesportsdb.com/team/{tsdb_id})")
