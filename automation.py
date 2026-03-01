import os
import sys
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import time

# Environment variables
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]   # optional

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------------------------------------------------------
# football-data.org API configuration
# -------------------------------------------------------------------
API_BASE_URL = "https://api.football-data.org/v4"
HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

# TheSportsDB API for logos (free, no key)
THESPORTSDB_URL = "https://www.thesportsdb.com/api/v1/json/3/searchteams.php"

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC",
    # Add Arab league codes here if you know them
]

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
def fetch_all_competitions():
    url = f"{API_BASE_URL}/competitions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"Error response: {resp.text}")
            return []
        data = resp.json()
        competitions = data.get("competitions", [])
        filtered = [c for c in competitions if c["code"] in ALLOWED_COMPETITIONS]
        print(f"Found {len(filtered)} allowed competitions")
        return filtered
    except Exception as e:
        print(f"Exception in fetch_all_competitions: {e}")
        return []

def fetch_matches(competition_code=None, date_from=None, date_to=None, status=None):
    url = f"{API_BASE_URL}/matches"
    params = {}
    if competition_code:
        params["competitions"] = competition_code
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to
    if status:
        params["status"] = status

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = resp.json()
        matches = data.get("matches", [])
        return matches
    except Exception as e:
        print(f"Error fetching matches: {e}")
        return []

def get_team_logo(team_name):
    """Fetch team logo from TheSportsDB, store in team_logos table."""
    existing = supabase.table("team_logos")\
        .select("logo_url")\
        .eq("team_name", team_name)\
        .execute()\
        .data
    if existing and existing[0].get("logo_url"):
        return existing[0]["logo_url"]

    try:
        params = {"t": team_name}
        resp = requests.get(THESPORTSDB_URL, params=params, timeout=5)
        data = resp.json()
        teams = data.get("teams", [])
        if teams:
            logo = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
            if logo:
                supabase.table("team_logos").upsert(
                    {"team_name": team_name, "logo_url": logo},
                    on_conflict="team_name"
                ).execute()
                return logo
    except Exception as e:
        print(f"Error fetching logo for {team_name}: {e}")
    return None

def parse_match(match):
    competition = match.get("competition", {})
    home_team = match.get("homeTeam", {})
    away_team = match.get("awayTeam", {})
    score = match.get("score", {})
    status = match.get("status", "SCHEDULED")

    if status in ["FINISHED"]:
        status_cat = "FINISHED"
    elif status in ["IN_PLAY", "PAUSED"]:
        status_cat = "LIVE"
    else:
        status_cat = "UPCOMING"

    # Get scores
    if status_cat == "LIVE":
        regular = score.get("regularTime", {})
        home_score = regular.get("home", 0)
        away_score = regular.get("away", 0)
    else:
        full = score.get("fullTime", {})
        home_score = full.get("home", 0)
        away_score = full.get("away", 0)

    # Get logos
    home_logo = get_team_logo(home_team.get("name", ""))
    away_logo = get_team_logo(away_team.get("name", ""))

    match_data = {
        "fixture_id": match["id"],
        "league": competition.get("name", "Unknown"),
        "league_logo": None,
        "home_team": home_team.get("name", "Unknown"),
        "away_team": away_team.get("name", "Unknown"),
        "home_logo": home_logo,
        "away_logo": away_logo,
        "match_time": match.get("utcDate"),
        "status": status_cat,
        "home_score": home_score,
        "away_score": away_score,
        "streams": [],
        "broadcasters": []
    }
    return match_data

def search_youtube_streams(match):
    # (keep your existing function if you have it)
    return []

def update_all_matches():
    print(f"[{datetime.now()}] Running global match update...")
    competitions = fetch_all_competitions()
    if not competitions:
        print("No competitions found.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    for comp in competitions:
        code = comp["code"]
        name = comp["name"]
        print(f"Fetching matches for {name} ({code})...")

        matches = fetch_matches(competition_code=code, date_from=today, date_to=next_week)

        for match in matches:
            match_data = parse_match(match)

            if match_data["status"] in ["LIVE", "UPCOMING"]:
                streams = search_youtube_streams(match_data)
                match_data["streams"] = json.dumps(streams)

            # Admin streams check (unchanged)
            admin_streams = supabase.table("admin_streams")\
                .select("*")\
                .eq("fixture_id", match_data["fixture_id"])\
                .eq("is_active", True)\
                .execute()\
                .data
            if admin_streams:
                existing = json.loads(match_data["streams"]) if match_data["streams"] else []
                for admin in admin_streams:
                    existing.append({
                        "title": admin.get("stream_title", "Official Stream"),
                        "url": admin["stream_url"],
                        "source": admin.get("stream_source", "admin"),
                        "verified": True,
                        "admin_added": True
                    })
                match_data["streams"] = json.dumps(existing)

            supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
            print(f"Updated: {match_data['home_team']} vs {match_data['away_team']}")
            time.sleep(0.5)

        time.sleep(1)

    # Clean up expired admin streams
    now = datetime.now().isoformat()
    supabase.table("admin_streams")\
        .update({"is_active": False})\
        .lt("expires_at", now)\
        .execute()

    print("Global update complete!")

def update_live():
    print(f"[{datetime.now()}] Running live update...")
    # 1. Update live matches
    live_matches = fetch_matches(status="LIVE")
    for match in live_matches:
        match_data = parse_match(match)
        # Admin streams check (keep it if you want)
        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
        print(f"Updated live: {match_data['home_team']} vs {match_data['away_team']}")

    # 2. Also update all matches from today (to catch finished matches)
    today = datetime.now().strftime("%Y-%m-%d")
    today_matches = fetch_matches(date_from=today, date_to=today)
    for match in today_matches:
        match_data = parse_match(match)
        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
    print(f"Updated {len(today_matches)} matches from today.")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_all_matches()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
