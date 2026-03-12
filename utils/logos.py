import requests
from supabase import create_client
import streamlit as st

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

def get_team_logo(team_name):
    """
    Returns a team logo URL. Tries:
      1. Check local database (team_logos table)
      2. Fetch from TheSportsDB API
      3. Fallback to transparent GIF
    """
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
                    # Save to database for future use
                    supabase.table("team_logos").upsert({"team_name": team_name, "logo_url": logo}, on_conflict="team_name").execute()
                    return logo
    except:
        pass

    # 3. Fallback to transparent GIF
    return "https://upload.wikimedia.org/wikipedia/commons/c/ce/Transparent.gif"

def get_league_logo(league_name):
    """
    Similar function for league logos (can be extended).
    For now, returns transparent GIF.
    """
    # You can implement league logo lookup later if needed.
    return "https://upload.wikimedia.org/wikipedia/commons/c/ce/Transparent.gif"
