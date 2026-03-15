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

# -------------------- Ultra logo resolver (with multiple sources) --------------------
def get_team_logo(team_name, team_website=None):
    # Check local cache
    res = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # TheSportsDB variations
    variations = [
        team_name,
        team_name.replace(" FC", ""),
        team_name.replace(" CF", ""),
        team_name.replace(" United", ""),
        team_name.replace(" City", ""),
        team_name.replace(" Real", ""),
        team_name.replace(" Club", ""),
        re.sub(r'[^\w\s]', '', team_name)
    ]
    for name in set(variations):
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(name)}"
        try:
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

    # Clearbit
    if team_website:
        try:
            domain = team_website.replace("https://", "").replace("http://", "").split("/")[0]
            clearbit_url = f"https://logo.clearbit.com/{domain}"
            if requests.head(clearbit_url, timeout=2).status_code == 200:
                supabase.table("team_logos").upsert({"team_name": team_name, "logo_url": clearbit_url}, on_conflict="team_name").execute()
                return clearbit_url
        except:
            pass

    # Wikipedia
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

    # Fallback initials
    words = team_name.split()
    initials = (words[0][:2].upper()) if len(words)==1 else (words[0][0] + words[-1][0]).upper()
    color = hashlib.md5(team_name.encode()).hexdigest()[:6]
    return f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=200&bold=true&length=2"

# -------------------- TheSportsDB API helpers (cached) --------------------
@st.cache_data(ttl=3600)
def search_team_by_name(name):
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(name)}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data["teams"][0] if data.get("teams") else None
    except:
        return None
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
        return []
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
        return []
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
        return []
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
        return []
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
def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def format_date(tsdb_date_str):
    try:
        return datetime.strptime(tsdb_date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
    except:
        return tsdb_date_str

def form_icon(result):
    return "✅" if result == "فوز" else "🤝" if result == "تعادل" else "❌"

def form_color(result):
    return "#28a745" if result == "فوز" else "#ffc107" if result == "تعادل" else "#dc3545"

# -------------------- Modern CSS --------------------
st.markdown("""
<style>
    /* Glassmorphism card */
    .glass-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
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
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .match-card {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid rgba(255,255,255,0.1);
        transition: background 0.3s;
    }
    .match-card:hover {
        background: rgba(255,255,255,0.1);
    }
    .player-card {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        transition: transform 0.3s;
    }
    .player-card:hover {
        transform: scale(1.05);
    }
    .badge-icon {
        width: 30px;
        height: 30px;
        object-fit: contain;
        margin-right: 5px;
    }
    /* Dark mode adjustments (assuming .stApp has data-theme) */
    .stApp[data-theme="dark"] .glass-card {
        background: rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Hero Section --------------------
logo = get_team_logo(team['name'], tsdb_team.get('strWebsite') if tsdb_team else None)

# Background image (stadium) if available
stadium_img = tsdb_team.get('strStadiumThumb') if tsdb_team else None
if stadium_img:
    st.markdown(f"""
    <div style="position: relative; height: 300px; background-image: url('{stadium_img}'); background-size: cover; background-position: center; border-radius: 30px; margin-bottom: 30px; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(to right, rgba(0,0,0,0.7), rgba(0,0,0,0.3));"></div>
        <div style="position: absolute; bottom: 20px; right: 20px; display: flex; align-items: center; gap: 20px;">
            <h1 style="color: white; font-size: 4rem; text-shadow: 2px 2px 8px black;">{team['name']}</h1>
            <img src="{logo}" style="width: 100px; height: 100px; border-radius: 50%; border: 3px solid white; background: white;">
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image(logo, width=120)
    with col2:
        st.title(team['name'])

# -------------------- Key Metrics --------------------
colA, colB, colC, colD = st.columns(4)
with colA:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("المركز", tsdb_team.get('intStadiumCapacity', '?') if tsdb_team else "?")
    st.markdown('</div>', unsafe_allow_html=True)
with colB:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("النقاط", "72")
    st.markdown('</div>', unsafe_allow_html=True)
with colC:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("الشكل", "W D L W W")
    st.markdown('</div>', unsafe_allow_html=True)
with colD:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    top_scorer = players[0]['strPlayer'] if players else "?"
    st.metric("الهداف", top_scorer)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Tabs --------------------
tabs = st.tabs([
    "📊 نظرة عامة", "👥 التشكيلة", "📅 المباريات", "📈 إحصائيات متقدمة",
    "🏆 البطولات", "🔄 الانتقالات", "💬 ركن الجماهير", "🔮 توقعات"
])

# ==================== TAB 1: Overview ====================
with tabs[0]:
    colX, colY = st.columns(2)

    with colX:
        st.subheader("⚽ الجهاز الفني")
        if tsdb_team and tsdb_team.get('strManager'):
            st.write(f"**المدرب:** {tsdb_team['strManager']}")
        else:
            st.info("لا توجد معلومات")

        st.subheader("📊 آخر 10 مباريات (الشكل)")
        if recent_events:
            form_list = []
            for ev in recent_events[:10]:
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
            cols = st.columns(10)
            for i, res in enumerate(form_list):
                icon = form_icon(res)
                color = form_color(res)
                cols[i].markdown(f"<div style='background:{color}; border-radius:8px; padding:5px; text-align:center; color:white; font-weight:bold;'>{icon}</div>", unsafe_allow_html=True)
        else:
            st.info("لا توجد مباريات حديثة")

    with colY:
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
        cols = st.columns(4)
        for i, player in enumerate(players[:20]):
            with cols[i % 4]:
                st.markdown('<div class="player-card">', unsafe_allow_html=True)
                photo = player.get('strThumb') or player.get('strCutout') or 'https://via.placeholder.com/100'
                st.image(photo, width=100)
                st.markdown(f"**{player.get('strPlayer', '')}**")
                st.caption(f"{player.get('strPosition', '')} | {player.get('strNationality', '')[:3]}")
                if player.get('strValue'):
                    st.caption(f"💰 {player['strValue']}")
                if player.get('idPlayer'):
                    st.markdown(f"[🔗 الملف](/player?player_id={player['idPlayer']})")
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
            st.info("لا توجد نتائج")

    # Head‑to‑Head vs Rival
    st.subheader("⚔️ سجل المواجهات مع الغريم التقليدي")
    # For demo, use a fixed rival; you can compute most frequent opponent
    rival_id = 61 if team_id == 57 else None  # Arsenal vs Chelsea example
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

# ==================== TAB 4: Advanced Statistics ====================
with tabs[3]:
    if recent_events:
        # Prepare data
        dates, gf, ga = [], [], []
        for ev in recent_events[:20]:
            try:
                dt = datetime.strptime(ev.get('dateEvent', ''), "%Y-%m-%d")
                hs = int(ev['intHomeScore'])
                as_ = int(ev['intAwayScore'])
                if ev['idHomeTeam'] == tsdb_id:
                    gf.append(hs)
                    ga.append(as_)
                else:
                    gf.append(as_)
                    ga.append(hs)
                dates.append(dt)
            except:
                continue
        df = pd.DataFrame({"التاريخ": dates, "أهداف لنا": gf, "أهداف عليهم": ga}).sort_values("التاريخ")
        df["المسجلة التراكمي"] = df["أهداف لنا"].cumsum()
        df["المستقبلة التراكمي"] = df["أهداف عليهم"].cumsum()
        # Chart
        chart_data = df.melt("التاريخ", var_name="النوع", value_name="الأهداف")
        line = alt.Chart(chart_data).mark_line().encode(
            x="التاريخ:T", y="الأهداف:Q", color="النوع:N"
        ).properties(height=400)
        st.altair_chart(line, use_container_width=True)
    else:
        st.info("لا توجد بيانات كافية")

# ==================== TAB 5: Honours ====================
with tabs[4]:
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

# ==================== TAB 6: Transfers (mock) ====================
with tabs[5]:
    st.info("قريباً – تاريخ الانتقالات")

# ==================== TAB 7: Fan Chat ====================
with tabs[6]:
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

# ==================== TAB 8: Predictions ====================
with tabs[7]:
    if next_events:
        nxt = next_events[0]
        home = nxt['strHomeTeam']
        away = nxt['strAwayTeam']
        st.write(f"**{home} vs {away}**")
        if recent_events:
            gf_avg = sum([int(ev['intHomeScore'] if ev['idHomeTeam']==tsdb_id else ev['intAwayScore']) for ev in recent_events[:5] if ev.get('intHomeScore')]) / 5
            ga_avg = sum([int(ev['intAwayScore'] if ev['idHomeTeam']==tsdb_id else ev['intHomeScore']) for ev in recent_events[:5] if ev.get('intAwayScore')]) / 5
            st.metric("متوسط أهدافنا", f"{gf_avg:.2f}")
            st.metric("متوسط أهداف الخصم", f"{ga_avg:.2f}")
            prob = gf_avg / (gf_avg + ga_avg) * 100 if gf_avg+ga_avg>0 else 50
            st.progress(prob/100, text=f"نسبة الفوز: {prob:.1f}%")
        else:
            st.info("لا توجد بيانات كافية")
    else:
        st.info("لا توجد مباراة قادمة")

# -------------------- Footer --------------------
if tsdb_id:
    st.markdown("---")
    st.markdown(f"🔍 [عرض كامل على TheSportsDB](https://www.thesportsdb.com/team/{tsdb_id})")
