import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import hashlib
import re
import pandas as pd
import altair as alt

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

# -------------------- Logo resolver (multiple sources) --------------------
def get_team_logo(team_name, team_website=None):
    # Check local cache
    res = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # TheSportsDB
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

    # Clearbit (from website)
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

# -------------------- Get local team from Supabase --------------------
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

# -------------------- Fetch match data from Supabase (as fallback) --------------------
home_matches = supabase.table("matches").select("*").eq("home_team_id", team_id).execute().data
away_matches = supabase.table("matches").select("*").eq("away_team_id", team_id).execute().data
all_matches = home_matches + away_matches
all_matches.sort(key=lambda x: x['match_time'], reverse=True)

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

# -------------------- Modern CSS --------------------
st.markdown("""
<style>
    .team-header {
        background: linear-gradient(135deg, #0b0b1a, #1a1a2e);
        border-radius: 25px;
        padding: 2rem;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .team-logo {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 4px solid #1976d2;
        background: white;
        object-fit: contain;
    }
    .team-name {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
    }
    .team-meta {
        color: #ccc;
        font-size: 1rem;
        margin-top: 0.5rem;
        display: flex;
        gap: 2rem;
        flex-wrap: wrap;
    }
    .stat-card {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 1rem;
        text-align: center;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .section-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin: 1.5rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #1976d2;
    }
    .match-item {
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border: 1px solid #333;
        transition: all 0.2s;
    }
    .match-item:hover {
        background: rgba(255,255,255,0.07);
        transform: translateX(5px);
    }
    .player-card {
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #333;
        transition: transform 0.2s;
    }
    .player-card:hover {
        transform: translateY(-5px);
        border-color: #1976d2;
    }
    .player-card img {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        object-fit: cover;
        margin-bottom: 0.5rem;
    }
    .badge-group {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .badge-item {
        background: rgba(255,255,255,0.05);
        border-radius: 20px;
        padding: 0.25rem 1rem;
        font-size: 0.9rem;
        border: 1px solid #333;
    }
    .h2h-grid {
        display: flex;
        gap: 1rem;
        justify-content: center;
        margin: 1rem 0;
    }
    .h2h-item {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 1rem;
        text-align: center;
        flex: 1;
    }
    .h2h-number {
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .h2h-label {
        font-size: 0.9rem;
        color: #aaa;
    }
    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    .info-item {
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #333;
    }
    .info-label {
        color: #aaa;
        font-size: 0.9rem;
    }
    .info-value {
        font-size: 1.2rem;
        font-weight: 600;
    }
    .missing-data {
        color: #888;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Header --------------------
logo = get_team_logo(team['name'], tsdb_team.get('strWebsite') if tsdb_team else None)

st.markdown(f"""
<div class="team-header">
    <img src="{logo}" class="team-logo">
    <div>
        <h1 class="team-name">{team['name']}</h1>
        <div class="team-meta">
            <span>🏆 {tsdb_team.get('strLeague', 'الدوري') if tsdb_team else 'الدوري'}</span>
            <span>🌍 {tsdb_team.get('strCountry', 'البلد') if tsdb_team else 'البلد'}</span>
            <span>🏟️ {tsdb_team.get('strStadium', 'الملعب') if tsdb_team else 'الملعب'}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------- Stats Row --------------------
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

cols = st.columns(4)
with cols[0]:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.metric("إجمالي المباريات", len(all_matches))
    st.markdown('</div>', unsafe_allow_html=True)
with cols[1]:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    wins = form_list.count("فوز") if form_list else 0
    st.metric("الفوز", wins)
    st.markdown('</div>', unsafe_allow_html=True)
with cols[2]:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    draws = form_list.count("تعادل") if form_list else 0
    st.metric("تعادل", draws)
    st.markdown('</div>', unsafe_allow_html=True)
with cols[3]:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    losses = form_list.count("خسارة") if form_list else 0
    st.metric("خسارة", losses)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Tabs --------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 نظرة عامة", "👥 التشكيلة", "📅 المباريات", "🏆 الإنجازات", "💬 التعليقات"])

# ==================== TAB 1: Overview ====================
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-title">⚽ معلومات الفريق</div>', unsafe_allow_html=True)
        if tsdb_team:
            # Build info grid
            info_items = [
                ("المدرب", tsdb_team.get('strManager', 'غير معروف')),
                ("الملعب", tsdb_team.get('strStadium', 'غير معروف')),
                ("السعة", tsdb_team.get('intStadiumCapacity', 'غير معروف')),
                ("التأسيس", tsdb_team.get('intFormedYear', 'غير معروف')),
                ("الدوري", tsdb_team.get('strLeague', 'غير معروف')),
                ("البلد", tsdb_team.get('strCountry', 'غير معروف')),
            ]
            if tsdb_team.get('strWebsite'):
                info_items.append(("الموقع", f"[رابط]({tsdb_team['strWebsite']})"))
            html = '<div class="info-grid">'
            for label, value in info_items:
                html += f'<div class="info-item"><div class="info-label">{label}</div><div class="info-value">{value}</div></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

            if tsdb_team.get('strDescriptionEN'):
                with st.expander("📝 نبذة عن الفريق"):
                    st.write(tsdb_team['strDescriptionEN'][:800] + "…")
        else:
            st.info("لا توجد معلومات إضافية من TheSportsDB")

        # Transfermarkt link (manual, not scraped)
        transfermarkt_url = f"https://www.transfermarkt.com/-/startseite/verein/{(team_id)}"  # This ID may not match
        st.markdown(f"🔗 [عرض على Transfermarkt]({transfermarkt_url}) – قد لا يكون المعرف صحيحاً")

    with col2:
        st.markdown('<div class="section-title">📊 آخر 5 مباريات</div>', unsafe_allow_html=True)
        if form_list:
            cols = st.columns(5)
            for i, res in enumerate(form_list):
                icon = form_icon(res)
                color = form_color(res)
                cols[i].markdown(f"<div style='background:{color}; border-radius:8px; padding:10px; text-align:center; color:white; font-weight:bold;'>{icon}</div>", unsafe_allow_html=True)
        else:
            st.info("لا توجد مباريات حديثة")

        st.markdown('<div class="section-title">🔜 المباراة القادمة</div>', unsafe_allow_html=True)
        if next_events:
            nxt = next_events[0]
            date_str = format_date(nxt.get('dateEvent', ''))
            home = nxt['strHomeTeam']
            away = nxt['strAwayTeam']
            st.info(f"**{home} vs {away}** – {date_str}")
        else:
            st.info("لا توجد مباريات قادمة (حسب TheSportsDB)")

# ==================== TAB 2: Squad ====================
with tab2:
    st.markdown('<div class="section-title">👥 التشكيلة الحالية</div>', unsafe_allow_html=True)
    if not players:
        st.info("لا توجد معلومات عن اللاعبين من TheSportsDB")
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
                    name = player.get('strPlayer', '')
                    st.markdown(f"**{name}**")
                    st.caption(f"{player.get('strNumber', '')} | {player.get('strNationality', '')[:3]}")
                    if player.get('strValue'):
                        st.caption(f"💰 {player['strValue']}")
                    if player.get('idPlayer'):
                        st.markdown(f"[🔗 الملف الشخصي](/player?player_id={player['idPlayer']})")
                    st.markdown('</div>', unsafe_allow_html=True)

# ==================== TAB 3: Matches ====================
with tab3:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-title">🗓️ المباريات القادمة</div>', unsafe_allow_html=True)
        if next_events:
            for ev in next_events[:5]:
                date_str = format_date(ev.get('dateEvent', ''))
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
                st.markdown(f'<div class="match-item"><span><strong>{home}</strong> vs <strong>{away}</strong></span> <span>{date_str}</span></div>', unsafe_allow_html=True)
        else:
            # Fallback to Supabase
            upcoming = [m for m in all_matches if m['status'] == 'UPCOMING']
            upcoming.sort(key=lambda x: x['match_time'])
            if upcoming:
                for f in upcoming[:5]:
                    try:
                        dt = datetime.fromisoformat(f["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                        time_str = dt.strftime("%Y/%m/%d %H:%M")
                    except:
                        time_str = f["match_time"][:16]
                    st.markdown(f'<div class="match-item"><span><strong>{f["home_team"]}</strong> vs <strong>{f["away_team"]}</strong></span> <span>{time_str}</span></div>', unsafe_allow_html=True)
            else:
                st.info("لا توجد مباريات قادمة")

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
                    result = f"{hs} - {as_}"
                except:
                    result = "غير متوفرة"
                st.markdown(f'<div class="match-item"><span><strong>{home}</strong> {result} <strong>{away}</strong></span> <span>{date_str}</span></div>', unsafe_allow_html=True)
        else:
            # Fallback to Supabase
            finished = [m for m in all_matches if m['status'] == 'FINISHED']
            finished.sort(key=lambda x: x['match_time'], reverse=True)
            if finished:
                for r in finished[:5]:
                    try:
                        dt = datetime.fromisoformat(r["match_time"].replace('Z', '+00:00')).astimezone(tz_tunis)
                        date_str = dt.strftime("%Y/%m/%d")
                    except:
                        date_str = r["match_time"][:10]
                    score = f"{r['home_score']} - {r['away_score']}"
                    st.markdown(f'<div class="match-item"><span><strong>{r["home_team"]}</strong> {score} <strong>{r["away_team"]}</strong></span> <span>{date_str}</span></div>', unsafe_allow_html=True)
            else:
                st.info("لا توجد نتائج")

    # Head‑to‑Head vs all opponents
    st.markdown('<div class="section-title">⚔️ سجل المواجهات مع جميع الفرق</div>', unsafe_allow_html=True)
    if all_matches:
        # Group by opponent
        opponents = {}
        for m in all_matches:
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

        # Display as a table
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
        st.info("لا توجد مباريات مسجلة")

# ==================== TAB 4: Honours ====================
with tab4:
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
        st.info("لا توجد معلومات عن البطولات من TheSportsDB")

# ==================== TAB 5: Fan Chat ====================
with tab5:
    st.markdown('<div class="section-title">💬 تعليقات الجماهير</div>', unsafe_allow_html=True)
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
        st.info("سجل الدخول للمشاركة في التعليقات")

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
