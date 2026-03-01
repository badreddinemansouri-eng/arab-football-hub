import os
import sys
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import time
import re

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
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"
THESPORTSDB_TEAM = f"{THESPORTSDB_BASE}/searchteams.php"
THESPORTSDB_LEAGUE = f"{THESPORTSDB_BASE}/search_all_leagues.php"  # for league lookup

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC",
    # Add Arab league codes here if you know them
]

# -------------------------------------------------------------------
# Cache tables (ensure they exist – run SQL separately)
# -------------------------------------------------------------------
# CREATE TABLE IF NOT EXISTS team_logos (team_name TEXT PRIMARY KEY, logo_url TEXT, updated_at TIMESTAMP DEFAULT NOW());
# CREATE TABLE IF NOT EXISTS league_logos (league_name TEXT PRIMARY KEY, logo_url TEXT, updated_at TIMESTAMP DEFAULT NOW());

# -------------------------------------------------------------------
# Helper functions for name cleaning
# -------------------------------------------------------------------
def clean_team_name(name):
    """Remove common suffixes and normalize for searching."""
    name = re.sub(r"\s+(FC|AFC|United|City|Real|CF|AC|AS|SS|SC|Club|Deportivo|Futebol|Clube)$", "", name, flags=re.IGNORECASE)
    return name.strip()

def clean_league_name(name):
    """Normalize league names for searching (e.g., 'Premier League' -> 'English Premier League')."""
    # Special mappings for common leagues (expand as needed)
    mapping = {
        "Premier League": "English Premier League",
        "La Liga": "Spanish La Liga",
        "Bundesliga": "German Bundesliga",
        "Serie A": "Italian Serie A",
        "Ligue 1": "French Ligue 1",
        "Champions League": "UEFA Champions League",
        "World Cup": "World Cup",
    }
    return mapping.get(name, name)

# -------------------------------------------------------------------
# Logo fetching functions
# -------------------------------------------------------------------
def fetch_team_logo(team_name):
    """Search TheSportsDB for a team logo, store in team_logos table."""
    # Check cache
    cached = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if cached.data and cached.data[0].get("logo_url"):
        return cached.data[0]["logo_url"]

    # Try variations
    variations = [
        team_name,
        clean_team_name(team_name),
        team_name.split()[0],  # first word
    ]
    # Common synonyms
    special = {
        "Manchester United FC": "Manchester United",
        "Liverpool FC": "Liverpool",
        "Arsenal FC": "Arsenal",
        "Chelsea FC": "Chelsea",
        "Real Madrid CF": "Real Madrid",
        "FC Barcelona": "Barcelona",
        "Bayern München": "Bayern Munich",
        "Juventus FC": "Juventus",
        "AC Milan": "AC Milan",
        "Inter Milan": "Inter",
        "Paris Saint-Germain FC": "PSG",
    }
    if team_name in special:
        variations.append(special[team_name])

    for name in set(variations):  # unique
        try:
            resp = requests.get(THESPORTSDB_TEAM, params={"t": name}, timeout=5)
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                logo = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
                if logo:
                    logo = logo.replace("http://", "https://")
                    # Cache it
                    supabase.table("team_logos").upsert(
                        {"team_name": team_name, "logo_url": logo},
                        on_conflict="team_name"
                    ).execute()
                    return logo
        except Exception as e:
            print(f"Error fetching logo for {name}: {e}")
        time.sleep(0.2)
    return None

def fetch_league_logo(league_name):
    """Search TheSportsDB for a league logo, store in league_logos table."""
    # Check cache
    cached = supabase.table("league_logos").select("logo_url").eq("league_name", league_name).execute()
    if cached.data and cached.data[0].get("logo_url"):
        return cached.data[0]["logo_url"]

    cleaned = clean_league_name(league_name)
    try:
        # TheSportsDB has a different endpoint for leagues: search_all_leagues.php
        # It returns a list of leagues; we need to match by name.
        resp = requests.get(THESPORTSDB_LEAGUE, params={"l": cleaned}, timeout=5)
        data = resp.json()
        # The response may have a 'countries' key with array of leagues
        leagues = data.get("countrys", []) or data.get("leagues", [])
        for league in leagues:
            if league_name.lower() in league.get("strLeague", "").lower():
                logo = league.get("strBadge") or league.get("strLogo")
                if logo:
                    logo = logo.replace("http://", "https://")
                    supabase.table("league_logos").upsert(
                        {"league_name": league_name, "logo_url": logo},
                        on_conflict="league_name"
                    ).execute()
                    return logo
    except Exception as e:
        print(f"Error fetching league logo for {league_name}: {e}")
    return None

# -------------------------------------------------------------------
# Existing functions (fetch_all_competitions, fetch_matches, parse_match)
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

    # Fetch logos (cached)
    home_logo = fetch_team_logo(home_team.get("name", ""))
    away_logo = fetch_team_logo(away_team.get("name", ""))
    league_logo = fetch_league_logo(competition.get("name", "Unknown"))

    match_data = {
        "fixture_id": match["id"],
        "league": competition.get("name", "Unknown"),
        "league_logo": league_logo,
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
