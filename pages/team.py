import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import pandas as pd
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

@st.cache_data(ttl=3600)
def get_league_seasons(league_id):
    """Get all seasons for a league (to show historical standings). Not directly used here."""
    # Optional, can be added later.
    return []

# -------------------- Get team from local DB --------------------
@st.cache_data(ttl=3600)
def get_local_team(tid):
    res = supabase.table("teams").select("*").eq("id", tid).execute()
    return res.data[0] if res.data else None

team = get_local_team(team_id)
if not team:
    st.error("الفريق غير موجود في قاعدة البيانات المحلية")
    st.stop()

# -------------------- Fetch extended data from TheSportsDB --------------------
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
    # TheSportsDB uses YYYY-MM-DD
    try:
        return datetime.strptime(tsdb_date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
    except:
        return tsdb_date_str

def form_icon(result):
    if result == "فوز":
        return "✅"
    elif result == "تعادل":
        return "🤝"
    else:
        return "❌"

# -------------------- Build the page --------------------
st.title(f"🏟️ {team['name']}")

# ---- Top section with logo and basic info ----
col1, col2 = st.columns([1, 3])
with col1:
    logo = team.get('logo') or (tsdb_team.get('strTeamBadge') if tsdb_team else None)
    st.image(logo or "https://via.placeholder.com/200", width=200)
    if tsdb_team and tsdb_team.get('strWebsite'):
        st.markdown(f"[🔗 الموقع الرسمي]({tsdb_team['strWebsite']})")

with col2:
    if tsdb_team:
        st.markdown(f"**🏆 الدوري:** {tsdb_team.get('strLeague', 'غير معروف')}")
        st.markdown(f"**🌍 البلد:** {tsdb_team.get('strCountry', 'غير معروف')}")
        st.markdown(f"**📅 التأسيس:** {tsdb_team.get('intFormedYear', 'غير معروف')}")
        st.markdown(f"**🏟️ الملعب:** {tsdb_team.get('strStadium', 'غير معروف')} (السعة: {tsdb_team.get('intStadiumCapacity', 'غير معروف')})")
        if tsdb_team.get('strDescriptionEN'):
            with st.expander("📝 نبذة عن الفريق"):
                st.write(tsdb_team['strDescriptionEN'][:500] + "…")
    else:
        st.markdown(f"**🌍 البلد:** {team.get('country', 'غير معروف')}")
        st.markdown(f"**📅 التأسيس:** {team.get('founded', 'غير معروف')}")
        st.markdown(f"**🏟️ الملعب:** {team.get('venue_name', 'غير معروف')}")

# ---- Tabs ----
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 نظرة عامة", "👥 التشكيلة", "📅 المباريات", "📈 إحصائيات", "🏆 البطولات"
])

# ==================== TAB 1: Overview ====================
with tab1:
    colA, colB = st.columns(2)

    with colA:
        st.subheader("⚽ المدرب")
        if tsdb_team and tsdb_team.get('strManager'):
            st.write(f"**{tsdb_team['strManager']}**")
        else:
            st.info("لا توجد معلومات عن المدرب")

        st.subheader("📊 آخر 5 مباريات (الشكل)")
        if recent_events:
            form_list = []
            for ev in recent_events[:5]:
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
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
            # Show as colored boxes
            cols = st.columns(5)
            for i, res in enumerate(form_list):
                icon = form_icon(res)
                color = "#28a745" if res == "فوز" else "#ffc107" if res == "تعادل" else "#dc3545"
                cols[i].markdown(f"<div style='background:{color}; border-radius:5px; padding:10px; text-align:center; color:white; font-weight:bold;'>{icon}</div>", unsafe_allow_html=True)
        else:
            st.info("لا توجد مباريات حديثة")

    with colB:
        st.subheader("⭐ أفضل الهدافين (آخر موسم)")
        # We could parse from events, but it's complex. For now, show placeholder.
        st.info("قريباً – إحصائيات الهدافين")

        st.subheader("🏅 لاعب الشهر (إن وجد)")
        # TheSportsDB doesn't provide this; we can leave empty.

    # ---- Upcoming match highlight ----
    if next_events:
        st.subheader("🔜 المباراة القادمة")
        nxt = next_events[0]
        date_str = format_date(nxt.get('dateEvent', ''))
        home = nxt['strHomeTeam']
        away = nxt['strAwayTeam']
        st.info(f"**{home} vs {away}** – {date_str}")

# ==================== TAB 2: Squad ====================
with tab2:
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
                    # Photo
                    photo = player.get('strThumb') or player.get('strCutout') or 'https://via.placeholder.com/100'
                    st.image(photo, width=100)
                    # Name and number
                    name = player.get('strPlayer', 'غير معروف')
                    number = player.get('strNumber', '')
                    st.markdown(f"**{name}** {number}")
                    # Nationality and age
                    nat = player.get('strNationality', '')
                    age = ''
                    if player.get('dateBorn'):
                        try:
                            birth = datetime.strptime(player['dateBorn'], "%Y-%m-%d")
                            age = datetime.now().year - birth.year
                        except:
                            age = player['dateBorn'][:4]
                    st.caption(f"{nat} | {age} سنة")
                    # Link to player page (if you implement one)
                    # if player.get('idPlayer'):
                    #     st.markdown(f"[🔗 الملف الشخصي](/player?player_id={player['idPlayer']})")

# ==================== TAB 3: Matches ====================
with tab3:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🗓️ المباريات القادمة")
        if next_events:
            for ev in next_events[:5]:
                date_str = format_date(ev.get('dateEvent', ''))
                home = ev['strHomeTeam']
                away = ev['strAwayTeam']
                st.write(f"**{home} vs {away}** – {date_str}")
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
                    st.write(f"**{f['home_team']} vs {f['away_team']}** – {time_str}")
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
                st.write(f"**{home} {result} {away}** – {date_str}")
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
                    st.write(f"**{r['home_team']} {score} {r['away_team']}** – {date_str}")
            else:
                st.info("لا توجد نتائج")

# ==================== TAB 4: Statistics ====================
with tab4:
    st.subheader("📊 إحصائيات الفريق")

    if recent_events:
        total_goals_for = 0
        total_goals_against = 0
        matches_played = 0
        wins = 0
        draws = 0
        losses = 0

        for ev in recent_events:
            try:
                hs = int(ev['intHomeScore'])
                as_ = int(ev['intAwayScore'])
                matches_played += 1
                if ev['idHomeTeam'] == tsdb_id:
                    total_goals_for += hs
                    total_goals_against += as_
                    if hs > as_:
                        wins += 1
                    elif hs == as_:
                        draws += 1
                    else:
                        losses += 1
                else:
                    total_goals_for += as_
                    total_goals_against += hs
                    if as_ > hs:
                        wins += 1
                    elif as_ == hs:
                        draws += 1
                    else:
                        losses += 1
            except:
                continue

        if matches_played > 0:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("المباريات", matches_played)
            col2.metric("الأهداف المسجلة", total_goals_for)
            col3.metric("الأهداف المستقبلة", total_goals_against)
            col4.metric("الفارق", total_goals_for - total_goals_against)

            col1, col2, col3 = st.columns(3)
            col1.metric("فوز", wins)
            col2.metric("تعادل", draws)
            col3.metric("خسارة", losses)

            # Win percentage
            win_pct = wins / matches_played * 100
            st.progress(win_pct / 100, text=f"نسبة الفوز: {win_pct:.1f}%")
        else:
            st.info("لا توجد إحصائيات كافية")
    else:
        st.info("لا توجد إحصائيات كافية")

    # Top scorers (if we had player stats)
    st.subheader("⭐ الهدافون")
    st.info("قريباً – قائمة الهدافين")

# ==================== TAB 5: Honors ====================
with tab5:
    st.subheader("🏆 البطولات والألقاب")

    if honours:
        # Group by competition
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

    # Also show league history if available from football-data.org (future enhancement)

# -------------------- Footer --------------------
if tsdb_id:
    st.markdown("---")
    st.markdown(f"🔍 [عرض كامل على TheSportsDB](https://www.thesportsdb.com/team/{tsdb_id})")
