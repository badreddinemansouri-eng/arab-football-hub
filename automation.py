import os
import sys
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta
import json
import time

# Environment variables
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY = os.environ.get("ONESIGNAL_API_KEY", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------------------------------------------------------
# football-data.org API configuration
# -------------------------------------------------------------------
API_BASE_URL = "https://api.football-data.org/v4"
HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC", "BSA"
]

# -------------------------------------------------------------------
# Helper: check if custom match exists (using match_time)
# -------------------------------------------------------------------
def custom_match_exists(home_team, away_team, match_date):
    """
    Check if there is already a custom match on the given date with the same teams.
    match_date should be a string in format 'YYYY-MM-DD'.
    """
    result = supabase.table("matches")\
        .select("fixture_id")\
        .eq("source", "custom")\
        .eq("home_team", home_team)\
        .eq("away_team", away_team)\
        .gte("match_time", match_date + "T00:00:00+00:00")\
        .lt("match_time", match_date + "T23:59:59+00:00")\
        .execute()
    return len(result.data) > 0

# -------------------------------------------------------------------
# Match fetching from football-data.org
# -------------------------------------------------------------------
def fetch_matches_fd(competition_code=None, date_from=None, date_to=None, status=None):
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
        return data.get("matches", [])
    except Exception as e:
        print(f"FD error: {e}")
        return []

def parse_match_fd(match):
    comp = match.get("competition", {})
    home = match.get("homeTeam", {})
    away = match.get("awayTeam", {})
    score = match.get("score", {})
    status = match.get("status", "SCHEDULED")
    if status in ["FINISHED"]:
        status_cat = "FINISHED"
    elif status in ["IN_PLAY", "PAUSED"]:
        status_cat = "LIVE"
    else:
        status_cat = "UPCOMING"
    full = score.get("fullTime", {})
    home_score = full.get("home", 0)
    away_score = full.get("away", 0)
    return {
        "fixture_id": match["id"],
        "league": comp.get("name", "Unknown"),
        "league_id": comp.get("id"),
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "home_score": home_score,
        "away_score": away_score,
        "status": status_cat,
        "match_time": match.get("utcDate"),   # key is match_time
        "home_team_id": None,
        "away_team_id": None,
    }

def upsert_match(match_data):
    try:
        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
        print(f"Upserted match {match_data['fixture_id']}: {match_data['home_team']} vs {match_data['away_team']}")
    except Exception as e:
        print(f"Error upserting match: {e}")

# -------------------------------------------------------------------
# Push notifications (optional)
# -------------------------------------------------------------------
def send_notification(title, content, url):
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        return
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "headings": {"en": title, "ar": title},
        "contents": {"en": content, "ar": content},
        "url": url
    }
    try:
        requests.post("https://onesignal.com/api/v1/notifications", json=payload, headers=headers)
    except Exception as e:
        print(f"Notification error: {e}")

# -------------------------------------------------------------------
# Main update functions
# -------------------------------------------------------------------
def update_live():
    print(f"[{datetime.now()}] Running live update...")
    live = fetch_matches_fd(status="IN_PLAY,PAUSED")
    print(f"Fetched {len(live)} live matches from FD")
    for m in live:
        data = parse_match_fd(m)
        match_date = data["match_time"][:10]   # extract YYYY-MM-DD
        if custom_match_exists(data["home_team"], data["away_team"], match_date):
            print(f"Skipping {data['home_team']} vs {data['away_team']} – custom match exists")
            continue
        upsert_match(data)
        # Optionally fetch detailed data from API-Football if you have key
        # if RAPIDAPI_KEY:
        #     fetch_match_details(data["fixture_id"])

    # Also fetch today's and tomorrow's matches to catch status changes
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    upcoming = fetch_matches_fd(date_from=today, date_to=tomorrow)
    for m in upcoming:
        data = parse_match_fd(m)
        match_date = data["match_time"][:10]
        if custom_match_exists(data["home_team"], data["away_team"], match_date):
            print(f"Skipping {data['home_team']} vs {data['away_team']} – custom match exists")
            continue
        upsert_match(data)
    print("Live update complete.")

def update_all_matches():
    print(f"[{datetime.now()}] Running full update...")
    # This would fetch competitions and next 7 days – similar logic
    # For simplicity, we'll just call update_live (covers today+tomorrow)
    update_live()

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_all_matches()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
