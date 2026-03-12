import requests
from supabase import create_client
import streamlit as st
import hashlib

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

def get_initials(name):
    words = name.split()
    if len(words) == 1:
        return words[0][:2].upper()
    else:
        return (words[0][0] + words[-1][0]).upper()

def get_team_logo(team_name):
    # 1. Check database
    res = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # 2. Try TheSportsDB API
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

    # 3. Fallback: UI Avatars
    initials = get_initials(team_name)
    color = hashlib.md5(team_name.encode()).hexdigest()[:6]
    return f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=128&bold=true&length=2"

def get_league_logo(league_name):
    # 1. Check database
    res = supabase.table("league_logos").select("logo_url").eq("league_name", league_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # 2. Try TheSportsDB API
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchleagues.php?l={requests.utils.quote(league_name)}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("leagues"):
                logo = data["leagues"][0].get("strBadge")
                if logo:
                    supabase.table("league_logos").upsert({"league_name": league_name, "logo_url": logo}, on_conflict="league_name").execute()
                    return logo
    except:
        pass

    # 3. Fallback: UI Avatars
    initials = get_initials(league_name)
    color = hashlib.md5(league_name.encode()).hexdigest()[:6]
    return f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=128&bold=true&length=2"
