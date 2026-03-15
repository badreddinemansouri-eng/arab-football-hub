import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import zoneinfo
import requests
import hashlib
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

# -------------------- Ultra logo resolver (with caching) --------------------


def get_team_logo(team_name, team_website=None):
    """
    Ultimate logo resolver: returns a real logo URL if found, else a stylish placeholder.
    Tries: local cache, TheSportsDB (with variations), Clearbit, Wikipedia.
    """
    # 1. Check local cache
    res = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # 2. Try TheSportsDB with multiple name variations
    variations = [
        team_name,
        team_name.replace(" FC", ""),
        team_name.replace(" CF", ""),
        team_name.replace(" United", ""),
        team_name.replace(" City", ""),
        team_name.replace(" Real", ""),
        team_name.replace(" Club", ""),
        re.sub(r'[^\w\s]', '', team_name)  # remove punctuation
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
                        supabase.table("team_logos").upsert(
                            {"team_name": team_name, "logo_url": logo},
                            on_conflict="team_name"
                        ).execute()
                        return logo
        except:
            pass

    # 3. Try Clearbit if we have the team's official website
    if team_website:
        try:
            domain = team_website.replace("https://", "").replace("http://", "").split("/")[0]
            clearbit_url = f"https://logo.clearbit.com/{domain}"
            if requests.head(clearbit_url, timeout=2).status_code == 200:
                supabase.table("team_logos").upsert(
                    {"team_name": team_name, "logo_url": clearbit_url},
                    on_conflict="team_name"
                ).execute()
                return clearbit_url
        except:
            pass

    # 4. Try Wikipedia – fetch the page and extract the logo from the infobox
    try:
        # Search for the team on Wikipedia (English)
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(team_name + ' football club')}&format=json"
        search_resp = requests.get(search_url, timeout=3)
        if search_resp.status_code == 200:
            search_data = search_resp.json()
            if search_data.get("query", {}).get("search"):
                page_title = search_data["query"]["search"][0]["title"]
                # Get the page content
                page_url = f"https://en.wikipedia.org/w/api.php?action=parse&page={requests.utils.quote(page_title)}&format=json&prop=text"
                page_resp = requests.get(page_url, timeout=3)
                if page_resp.status_code == 200:
                    page_data = page_resp.json()
                    html = page_data.get("parse", {}).get("text", {}).get("*", "")
                    # Look for the logo in the infobox – often in a <td> with class "logo"
                    match = re.search(r'<td[^>]*class="logo"[^>]*><img[^>]*src="([^"]+)"', html, re.IGNORECASE)
                    if match:
                        img_src = match.group(1)
                        if img_src.startswith("//"):
                            img_src = "https:" + img_src
                        supabase.table("team_logos").upsert(
                            {"team_name": team_name, "logo_url": img_src},
                            on_conflict="team_name"
                        ).execute()
                        return img_src
    except Exception as e:
        print(f"Wikipedia logo extraction failed: {e}")

    # 5. If all else fails, return a initials‑based placeholder (not real, but better than nothing)
    words = team_name.split()
    if len(words) == 1:
        initials = words[0][:2].upper()
    else:
        initials = (words[0][0] + words[-1][0]).upper()
    color = hashlib.md5(team_name.encode()).hexdigest()[:6]
    placeholder = f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=200&bold=true&length=2"
    return placeholder

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

# -------------------- Header --------------------
logo = get_team_logo(team['name'], tsdb_team.get('strWebsite') if tsdb_team else None)

col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    st.image(logo, width=200)
with col2:
    st.title(team['name'])
    if tsdb_team:
        st.markdown(f"**الدوري:** {tsdb_team.get('strLeague', 'غير معروف')}")
        st.markdown(f"**البلد:** {tsdb_team.get('strCountry', 'غير معروف')} | **التأسيس:** {tsdb_team.get('intFormedYear', 'غير معروف')}")
        st.markdown(f"**الملعب:** {tsdb_team.get('strStadium', 'غير معروف')} (السعة: {tsdb_team.get('intStadiumCapacity', 'غير معروف')})")
        if tsdb_team.get('strWebsite'):
            st.markdown(f"[🔗 الموقع الرسمي]({tsdb_team['strWebsite']})")
with col3:
    if tsdb_id:
        st.image(f"https://www.thesportsdb.com/team/{tsdb_id}/badge", width=80)

# -------------------- Tabs --------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 نظرة عامة",
    "👥 التشكيلة",
    "📅 المباريات",
    "📈 إحصائيات متقدمة",
    "🏆 البطولات",
    "🔄 تاريخ الانتقالات",
    "💬 ركن الجماهير",
    "🔮 توقعات"
])

# ==================== TAB 1: Overview ====================
with tab1:
    colA, colB = st.columns(2)

    with colA:
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
            wins = form_list.count("فوز")
            draws = form_list.count("تعادل")
            losses = form_list.count("خسارة")
            total = len(form_list)
            if total > 0:
                st.progress(wins/total, text=f"نسبة الفوز: {wins*100/total:.1f}%")
        else:
            st.info("لا توجد مباريات حديثة")

    with colB:
        st.subheader("🔜 المباراة القادمة")
        if next_events:
            nxt = next_events[0]
            date_str = format_date(nxt.get('dateEvent', ''))
            home = nxt['strHomeTeam']
            away = nxt['strAwayTeam']
            st.info(f"**{home} vs {away}** – {date_str}")
        else:
            st.info("لا توجد مباريات قادمة")

        st.subheader("⭐ أفضل الهدافين (آخر 10 مباريات)")
        st.info("قريباً – إحصائيات الهدافين")

# ==================== TAB 2: Squad ====================
with tab2:
    st.subheader("التشكيلة الحالية")

    if not players:
        st.info("لا توجد معلومات عن اللاعبين")
    else:
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
                    st.image(photo, width=100)
                    name = player.get('strPlayer', 'غير معروف')
                    number = player.get('strNumber', '')
                    st.markdown(f"**{name}** {number}")
                    nat = player.get('strNationality', '')
                    age = ''
                    if player.get('dateBorn'):
                        try:
                            birth = datetime.strptime(player['dateBorn'], "%Y-%m-%d")
                            age = datetime.now().year - birth.year
                        except:
                            age = player['dateBorn'][:4]
                    st.caption(f"{nat} | {age} سنة")
                    if player.get('strValue'):
                        st.caption(f"القيمة: {player['strValue']}")
                    if player.get('idPlayer'):
                        st.markdown(f"[🔗 الملف الشخصي](/player?player_id={player['idPlayer']})")

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

    # Head‑to‑Head vs Top Rivals (extracted from matches)
    st.subheader("⚔️ سجل المواجهات مع الغريم التقليدي")
    # Determine rivals by frequency of matches? Hardcode or query.
    # For simplicity, we'll pick a random rival – you can replace with logic.
    rival_id = None
    if team_id == 57:  # Arsenal example
        rival_id = 61  # Chelsea
    # Query head‑to‑head from matches
    if rival_id:
        h2h_home = supabase.table("matches").select("*").eq("home_team_id", team_id).eq("away_team_id", rival_id).execute()
        h2h_away = supabase.table("matches").select("*").eq("home_team_id", rival_id).eq("away_team_id", team_id).execute()
        h2h = h2h_home.data + h2h_away.data
        if h2h:
            wins = 0
            draws = 0
            losses = 0
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
            st.write(f"**فوز:** {wins} | **تعادل:** {draws} | **خسارة:** {losses}")
        else:
            st.info("لا توجد مواجهات مع الغريم")

# ==================== TAB 4: Advanced Statistics ====================
with tab4:
    st.subheader("📊 إحصائيات متقدمة")

    if recent_events:
        # Prepare data for trend chart
        match_dates = []
        goals_for = []
        goals_against = []
        for ev in recent_events[:20]:
            try:
                dt = datetime.strptime(ev.get('dateEvent', ''), "%Y-%m-%d")
                hs = int(ev['intHomeScore'])
                as_ = int(ev['intAwayScore'])
                if ev['idHomeTeam'] == tsdb_id:
                    gf = hs
                    ga = as_
                else:
                    gf = as_
                    ga = hs
                match_dates.append(dt)
                goals_for.append(gf)
                goals_against.append(ga)
            except:
                continue
        df = pd.DataFrame({
            "التاريخ": match_dates,
            "أهداف المسجلة": goals_for,
            "أهداف المستقبلة": goals_against
        })
        df = df.sort_values("التاريخ")

        # Line chart
        chart_data = df.melt("التاريخ", var_name="النوع", value_name="الأهداف")
        line_chart = alt.Chart(chart_data).mark_line().encode(
            x="التاريخ:T",
            y="الأهداف:Q",
            color="النوع:N"
        ).properties(height=400)
        st.altair_chart(line_chart, use_container_width=True)

        # Cumulative goals
        df["المسجلة التراكمي"] = df["أهداف المسجلة"].cumsum()
        df["المستقبلة التراكمي"] = df["أهداف المستقبلة"].cumsum()
        cum_df = df[["التاريخ", "المسجلة التراكمي", "المستقبلة التراكمي"]].melt("التاريخ", var_name="النوع", value_name="الأهداف")
        cum_chart = alt.Chart(cum_df).mark_line().encode(
            x="التاريخ:T",
            y="الأهداف:Q",
            color="النوع:N"
        ).properties(height=400)
        st.altair_chart(cum_chart, use_container_width=True)

    else:
        st.info("لا توجد بيانات كافية للإحصائيات المتقدمة")

# ==================== TAB 5: Honours ====================
with tab5:
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

# ==================== TAB 6: Transfer History (mock) ====================
with tab6:
    st.subheader("🔄 تاريخ الانتقالات (آخر 5 صفقات)")
    st.info("قريباً – سيتم إضافة تاريخ الانتقالات")

# ==================== TAB 7: Fan Zone ====================
with tab7:
    st.subheader("💬 تعليقات الجماهير")

    # Simple chat using Supabase (without joining users)
    if "user" in st.session_state and st.session_state.user:
        new_msg = st.text_input("اكتب تعليقاً...")
        if st.button("إرسال") and new_msg:
            supabase.table("comments").insert({
                "match_id": team_id,  # using team_id as context
                "user_id": st.session_state.user.id,
                "content": new_msg
            }).execute()
            st.success("تم الإرسال")
            st.rerun()
    else:
        st.info("سجل الدخول للمشاركة في التعليقات")

    # Display comments – removed the problematic join
    comments = supabase.table("comments").select("*").eq("match_id", team_id).order("created_at", desc=True).limit(20).execute()
    if comments.data:
        for c in comments.data:
            # Show first 8 chars of user_id as identifier
            user_short = c['user_id'][:8] if c.get('user_id') else 'مستخدم'
            st.markdown(f"**{user_short}**: {c['content']}")
    else:
        st.write("لا توجد تعليقات بعد")

# ==================== TAB 8: Predictions ====================
with tab8:
    st.subheader("🔮 توقعات المباراة القادمة")

    if next_events:
        nxt = next_events[0]
        home = nxt['strHomeTeam']
        away = nxt['strAwayTeam']
        st.write(f"**{home} vs {away}**")

        # Simple prediction based on recent form
        if recent_events:
            # Calculate average goals for/against
            gf = []
            ga = []
            for ev in recent_events[:5]:
                try:
                    hs = int(ev['intHomeScore'])
                    as_ = int(ev['intAwayScore'])
                    if ev['idHomeTeam'] == tsdb_id:
                        gf.append(hs)
                        ga.append(as_)
                    else:
                        gf.append(as_)
                        ga.append(hs)
                except:
                    continue
            if gf:
                avg_gf = sum(gf) / len(gf)
                avg_ga = sum(ga) / len(ga)
                st.metric("متوسط الأهداف المسجلة", f"{avg_gf:.2f}")
                st.metric("متوسط الأهداف المستقبلة", f"{avg_ga:.2f}")

                # Crude win probability
                win_prob = avg_gf / (avg_gf + avg_ga) * 100
                st.progress(win_prob / 100, text=f"نسبة الفوز: {win_prob:.1f}%")
        else:
            st.info("لا توجد بيانات كافية للتوقع")
    else:
        st.info("لا توجد مباراة قادمة للتوقع")

# -------------------- Footer --------------------
if tsdb_id:
    st.markdown("---")
    st.markdown(f"🔍 [عرض كامل على TheSportsDB](https://www.thesportsdb.com/team/{tsdb_id})")
