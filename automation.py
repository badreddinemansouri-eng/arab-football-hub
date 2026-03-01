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
FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]   # your new token
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]           # keep this for stream search

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------------------------------------------------------
# football-data.org API configuration
# -------------------------------------------------------------------
API_BASE_URL = "https://api.football-data.org/v4"
HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

# Free tier allows only certain competitions – you can expand this list
ALLOWED_COMPETITIONS = [
    "PL",   # Premier League
    "PD",   # La Liga
    "BL1",  # Bundesliga
    "SA",   # Serie A
    "FL1",  # Ligue 1
    "CL",   # Champions League
    "EC",   # European Championship
    "WC",   # World Cup
    # Add more competition codes as needed: https://www.football-data.org/docs/v4/index.html#competitions
]

def fetch_all_competitions():
    """Fetch list of all competitions (leagues) from football-data.org."""
    url = f"{API_BASE_URL}/competitions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        print(f"Competitions API status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error response: {resp.text}")
            return []
        data = resp.json()
        competitions = data.get("competitions", [])
        # Filter to only allowed competitions (optional)
        filtered = [c for c in competitions if c["code"] in ALLOWED_COMPETITIONS]
        print(f"Found {len(filtered)} allowed competitions")
        return filtered
    except Exception as e:
        print(f"Exception in fetch_all_competitions: {e}")
        return []

def fetch_matches(competition_code=None, date_from=None, date_to=None, status=None):
    """
    Fetch matches – can be filtered by competition, date range, and status.
    For live scores, use status = "LIVE".
    """
    url = f"{API_BASE_URL}/matches"
    params = {}
    if competition_code:
        params["competitions"] = competition_code   # note: plural 'competitions'
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to
    if status:
        params["status"] = status   # e.g., "LIVE", "FINISHED", "SCHEDULED"

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = resp.json()
        matches = data.get("matches", [])
        return matches
    except Exception as e:
        print(f"Error fetching matches: {e}")
        return []

def parse_match(match):
    """
    Convert a football-data.org match object to our database format.
    """
    area = match.get("area", {})
    competition = match.get("competition", {})
    season = match.get("season", {})
    home_team = match.get("homeTeam", {})
    away_team = match.get("awayTeam", {})
    score = match.get("score", {})
    full_time = score.get("fullTime", {})
    status = match.get("status", "SCHEDULED")

    # Map status to our categories
    if status in ["FINISHED"]:
        status_cat = "FINISHED"
    elif status in ["IN_PLAY", "PAUSED"]:
        status_cat = "LIVE"
    else:
        status_cat = "UPCOMING"

    # Get scores (may be null)
    home_score = full_time.get("home") if full_time.get("home") is not None else 0
    away_score = full_time.get("away") if full_time.get("away") is not None else 0

    # Build match data
    match_data = {
        "fixture_id": match["id"],
        "league": competition.get("name", "Unknown"),
        "league_logo": None,   # football-data.org doesn't provide logos
        "home_team": home_team.get("name", "Unknown"),
        "away_team": away_team.get("name", "Unknown"),
        "home_logo": None,
        "away_logo": None,
        "match_time": match.get("utcDate"),
        "status": status_cat,
        "home_score": home_score,
        "away_score": away_score,
        "streams": [],
        "broadcasters": []
    }
    return match_data

def search_youtube_streams(match):
    """Search YouTube for free streams (unchanged)."""
    query = f"{match['home_team']} vs {match['away_team']} live"
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "eventType": "live",
        "maxResults": 3,
        "key": YOUTUBE_API_KEY
    }
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        streams = []
        if data.get("items"):
            for item in data["items"]:
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                channel = item["snippet"]["channelTitle"]
                streams.append({
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel": channel,
                    "source": "youtube",
                    "verified": False
                })
        return streams
    except Exception as e:
        print(f"YouTube search error: {e}")
        return []

def update_all_matches():
    """Main update – fetch today's matches for all allowed competitions."""
    print(f"[{datetime.now()}] Running global match update...")

    competitions = fetch_all_competitions()
    if not competitions:
        print("No competitions found. Check your token and network.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    for comp in competitions:
        code = comp["code"]
        name = comp["name"]
        print(f"Fetching matches for {name} ({code})...")

        # Get matches from today and tomorrow (covers upcoming and live)
        matches = fetch_matches(competition_code=code, date_from=today, date_to=tomorrow)

        for match in matches:
            match_data = parse_match(match)

            # Search for YouTube streams (only for live/upcoming)
            if match_data["status"] in ["LIVE", "UPCOMING"]:
                streams = search_youtube_streams(match_data)
                match_data["streams"] = json.dumps(streams)

            # Check for admin streams (if any)
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

            # Upsert into Supabase
            supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
            print(f"Updated: {match_data['home_team']} vs {match_data['away_team']}")
            time.sleep(0.5)   # be gentle

        time.sleep(1)   # pause between competitions

    # Clean up expired admin streams
    now = datetime.now().isoformat()
    supabase.table("admin_streams")\
        .update({"is_active": False})\
        .lt("expires_at", now)\
        .execute()

    print("Global update complete!")

def update_live():
    """Update only live matches."""
    print(f"[{datetime.now()}] Running live update...")
    # football-data.org supports filtering by status=LIVE
    matches = fetch_matches(status="LIVE")
    for match in matches:
        match_data = parse_match(match)

        # Check for admin streams (same as above)
        admin_streams = supabase.table("admin_streams")\
            .select("*")\
            .eq("fixture_id", match_data["fixture_id"])\
            .eq("is_active", True)\
            .execute()\
            .data
        if admin_streams:
            streams = []
            for admin in admin_streams:
                streams.append({
                    "title": admin.get("stream_title", "Official Stream"),
                    "url": admin["stream_url"],
                    "source": admin.get("stream_source", "admin"),
                    "verified": True,
                    "admin_added": True
                })
            match_data["streams"] = json.dumps(streams)

        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
        print(f"Updated live: {match_data['home_team']} vs {match_data['away_team']}")
        time.sleep(0.5)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_all_matches()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
