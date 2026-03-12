import streamlit as st
from supabase import create_client
import json
import pandas as pd
import plotly.graph_objects as go
import zoneinfo
from datetime import datetime

st.set_page_config(page_title="تفاصيل المباراة", page_icon="⚽", layout="wide")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

match_id = st.query_params.get("match_id")
if not match_id:
    st.error("لم يتم تحديد المباراة")
    st.stop()

@st.cache_data(ttl=30)
def get_match(mid):
    res = supabase.table("matches").select("*, home_team_id, away_team_id").eq("fixture_id", mid).execute()
    return res.data[0] if res.data else None

match = get_match(match_id)
if not match:
    st.error("المباراة غير موجودة")
    st.stop()

st.title(f"{match['home_team']} vs {match['away_team']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.image(match.get('home_logo') or 'https://via.placeholder.com/150', width=150)
    st.subheader(match['home_team'])
with col2:
    if match['status'] == 'LIVE':
        st.markdown(f"<h1 style='color:#d32f2f;'>{match['home_score']} - {match['away_score']}</h1>", unsafe_allow_html=True)
        st.markdown("🔴 مباشر")
    else:
        try:
            utc_time = datetime.fromisoformat(match["date"].replace('Z', '+00:00'))
            local_time = utc_time.astimezone(tz_tunis)
            st.markdown(f"<h1>{local_time.strftime('%H:%M')}</h1>", unsafe_allow_html=True)
            st.markdown(local_time.strftime('%Y-%m-%d'))
        except:
            pass
with col3:
    st.image(match.get('away_logo') or 'https://via.placeholder.com/150', width=150)
    st.subheader(match['away_team'])

st.markdown(f"**{match['league']}**")
st.markdown("---")

tabs = st.tabs(["ملخص", "إحصائيات", "تشكيلة", "أحداث", "وجهاً لوجه", "توقعات"])

with tabs[0]:
    st.write("ملخص المباراة")
    streams = match.get("streams", [])
    if isinstance(streams, str):
        streams = json.loads(streams)
    try:
        admin_streams = supabase.table("admin_streams").select("*").eq("fixture_id", match_id).eq("is_active", True).execute().data
        if admin_streams:
            for a in admin_streams:
                streams.append({"title": a["stream_title"], "url": a["stream_url"]})
    except:
        pass
    if streams:
        st.subheader("روابط البث")
        for s in streams:
            st.markdown(f'<a href="{s["url"]}" target="_blank" style="display:block; background:#1976d2; color:white; padding:10px; margin:5px 0; border-radius:30px; text-align:center; text-decoration:none;">{s["title"]}</a>', unsafe_allow_html=True)
    else:
        st.info("لا توجد روابط بث")

with tabs[1]:
    st.subheader("إحصائيات")
    stats = supabase.table("match_statistics").select("*").eq("fixture_id", match_id).execute()
    if stats.data:
        for s in stats.data:
            st.write(f"{s['type']}: {s['value']}")
    else:
        st.info("لا توجد إحصائيات متاحة")

with tabs[2]:
    st.subheader("التشكيلة")
    lineups = supabase.table("lineups").select("*").eq("fixture_id", match_id).execute()
    if lineups.data:
        for l in lineups.data:
            team = supabase.table("teams").select("name").eq("id", l["team_id"]).execute().data
            team_name = team[0]["name"] if team else "الفريق"
            st.write(f"**{team_name}** - تشكيل {l['formation']}")
            st.write("**التشكيلة الأساسية:**")
            for player in l['starting_xi']:
                st.write(f"{player['player']['number']} {player['player']['name']} ({player['player']['pos']})")
            if l['substitutes']:
                st.write("**البدلاء:**")
                for sub in l['substitutes']:
                    st.write(f"{sub['player']['name']}")
    else:
        st.info("لا توجد تشكيلة متاحة")

with tabs[3]:
    st.subheader("أحداث المباراة")
    events = supabase.table("match_events").select("*").eq("fixture_id", match_id).order("elapsed").execute()
    if events.data:
        for e in events.data:
            icon = "⚽" if e['type'] == 'Goal' else "🟨" if e['detail'] == 'Yellow Card' else "🟥"
            player_name = ""
            if e.get('player_id'):
                player = supabase.table("players").select("name").eq("id", e['player_id']).execute().data
                player_name = player[0]["name"] if player else ""
            st.write(f"{e['elapsed']}' {icon} {player_name}")
    else:
        st.info("لا توجد أحداث")

with tabs[4]:
    st.subheader("وجهاً لوجه")
    if match.get('home_team_id') and match.get('away_team_id'):
        h2h = supabase.table("head2head").select("*").eq("team1_id", match['home_team_id']).eq("team2_id", match['away_team_id']).execute()
        if h2h.data:
            data = h2h.data[0]
            st.write(f"لعبوا {data['played']} مرة: فاز {match['home_team']} {data['team1_wins']} ، فاز {match['away_team']} {data['team2_wins']} ، تعادل {data['draws']}")
            if data.get('last_meetings'):
                st.write("آخر المواجهات:")
                for fid in data['last_meetings']:
                    st.markdown(f"[مباراة {fid}](/match_details?match_id={fid})")
        else:
            st.info("لا توجد بيانات مواجهات سابقة")
    else:
        st.info("معرفات الفرق غير متوفرة")

with tabs[5]:
    st.subheader("التوقعات")
    pred = supabase.table("predictions").select("*").eq("fixture_id", match_id).execute()
    if pred.data:
        p = pred.data[0]
        st.progress(p['home_win_prob'], text=f"فوز {match['home_team']}")
        st.progress(p['draw_prob'], text="تعادل")
        st.progress(p['away_win_prob'], text=f"فوز {match['away_team']}")
    else:
        st.info("لا توجد توقعات لهذه المباراة")
