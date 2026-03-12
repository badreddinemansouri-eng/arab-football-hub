import os
import sys
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import time
import unicodedata
import re

# Environment variables
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------------------------------------------------------
# football-data.org API configuration
# -------------------------------------------------------------------
API_BASE_URL = "https://api.football-data.org/v4"
HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC",
]

# -------------------------------------------------------------------
# Helper: check if custom match exists (using match_time)
# -------------------------------------------------------------------
def custom_match_exists(home_team, away_team, match_date):
    """
    Check if there is already a custom match (source = 'custom') on the given date with the same teams.
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
# Helper functions for logo handling (unchanged from your original)
# -------------------------------------------------------------------
def slugify_team_name(name):
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s]', '', name)
    return name.replace(' ', '_')

def find_team_logo_in_storage(team_name):
    folders = [
        "Italy - Serie A", "England - Premier League", "Spain - LaLiga",
        "Germany - Bundesliga", "France - Ligue 1", "Portugal - Liga Portugal",
        "International - Champions League", "International - World Cup"
    ]
    base_url = f"{SUPABASE_URL}/storage/v1/object/public/logos"
    candidates = [
        team_name,
        team_name.replace(' ', '_'),
        slugify_team_name(team_name)
    ]
    for folder in folders:
        for name in candidates:
            encoded_name = requests.utils.quote(name)
            url = f"{base_url}/{folder}/{encoded_name}.png"
            try:
                if requests.head(url, timeout=3).status_code == 200:
                    return url
            except:
                continue
    return None

def get_team_logo_from_db(team_name):
    if not team_name:
        return None
    try:
        result = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
        if result.data and result.data[0].get("logo_url"):
            return result.data[0]["logo_url"]
    except Exception as e:
        print(f"Error looking up logo for {team_name}: {e}")

    url = find_team_logo_in_storage(team_name)
    if url:
        try:
            supabase.table("team_logos").upsert(
                {"team_name": team_name, "logo_url": url},
                on_conflict="team_name"
            ).execute()
        except Exception as e:
            print(f"Error storing logo for {team_name}: {e}")
        return url
    return None

def slugify_league_name(name):
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s]', '', name)
    return name.replace(' ', '_')

def find_league_logo_in_storage(league_name):
    base_url = f"{SUPABASE_URL}/storage/v1/object/public/logos/leagues"
    candidates = [
        league_name,
        league_name.replace(' ', '_'),
        slugify_league_name(league_name)
    ]
    for name in candidates:
        encoded = requests.utils.quote(name)
        url = f"{base_url}/{encoded}.png"
        try:
            if requests.head(url, timeout=3).status_code == 200:
                return url
        except:
            continue
    return None

def get_league_logo_from_db(league_name):
    if not league_name:
        return None
    try:
        result = supabase.table("league_logos").select("logo_url").eq("league_name", league_name).execute()
        if result.data and result.data[0].get("logo_url"):
            return result.data[0]["logo_url"]
    except Exception as e:
        print(f"Error looking up league logo for {league_name}: {e}")

    url = find_league_logo_in_storage(league_name)
    if url:
        try:
            supabase.table("league_logos").upsert(
                {"league_name": league_name, "logo_url": url},
                on_conflict="league_name"
            ).execute()
        except Exception as e:
            print(f"Error storing league logo for {league_name}: {e}")
        return url
    return None

def get_country_flag(country_name):
    if not country_name:
        return None
    code = country_name.lower().replace(" ", "-")
    return f"https://flagpedia.net/data/flags/icon/72x54/{code}.png"

# -------------------------------------------------------------------
# Fetch competitions and matches (unchanged)
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

    if status_cat == "LIVE":
        regular = score.get("regularTime", {})
        home_score = regular.get("home", 0)
        away_score = regular.get("away", 0)
    else:
        full = score.get("fullTime", {})
        home_score = full.get("home", 0)
        away_score = full.get("away", 0)

    home_logo = get_team_logo_from_db(home_team.get("name", ""))
    away_logo = get_team_logo_from_db(away_team.get("name", ""))
    league_logo = get_league_logo_from_db(competition.get("name", "Unknown"))
    country = competition.get("area", {}).get("name")
    country_flag = get_country_flag(country)

    match_data = {
        "fixture_id": match["id"],
        "league": competition.get("name", "Unknown"),
        "league_logo": league_logo,
        "home_team": home_team.get("name", "Unknown"),
        "away_team": away_team.get("name", "Unknown"),
        "home_logo": home_logo,
        "away_logo": away_logo,
        "country": country,
        "country_logo": country_flag,
        "match_time": match.get("utcDate"),
        "status": status_cat,
        "home_score": home_score,
        "away_score": away_score,
        "streams": [],
        "broadcasters": [],
    }
    return match_data

def upsert_match(match_data):
    try:
        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
    except Exception as e:
        print(f"Error upserting match {match_data['fixture_id']}: {e}")

# -------------------------------------------------------------------
# Update functions (with optional custom match skip)
# -------------------------------------------------------------------
def update_live():
    print(f"[{datetime.now()}] Running live update...")

    # 1. Update currently live matches
    live_matches = fetch_matches(status="IN_PLAY,PAUSED")
    for match in live_matches:
        match_data = parse_match(match)
        # Optional: skip if custom match exists
        # match_date = match_data["match_time"][:10]
        # if custom_match_exists(match_data["home_team"], match_data["away_team"], match_date):
        #     print(f"Skipping {match_data['home_team']} vs {match_data['away_team']} – custom match exists")
        #     continue
        upsert_match(match_data)
        print(f"Updated live: {match_data['home_team']} vs {match_data['away_team']}")

    # 2. Fetch today + tomorrow matches
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    upcoming_matches = fetch_matches(date_from=today, date_to=tomorrow)

    # 3. Proactively update matches within next 15 minutes
    now_utc = datetime.now(timezone.utc)
    soon_threshold = now_utc + timedelta(minutes=15)

    for match in upcoming_matches:
        match_time_str = match.get("utcDate")
        if match_time_str:
            try:
                match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
                if match_time <= soon_threshold:
                    match_data = parse_match(match)
                    upsert_match(match_data)
                    print(f"Proactively updated: {match_data['home_team']} vs {match_data['away_team']} (scheduled at {match_time_str})")
            except Exception as e:
                print(f"Error parsing time for match {match.get('id')}: {e}")

    print(f"Processed {len(upcoming_matches)} matches from {today} to {tomorrow}.")

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
                streams = search_youtube_streams(match_data)  # (you can keep or remove this)
                match_data["streams"] = json.dumps(streams)

            # Merge admin streams
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

            upsert_match(match_data)
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

# -------------------------------------------------------------------
# Placeholder for YouTube search (unchanged)
# -------------------------------------------------------------------
def search_youtube_streams(match):
    return []

# -------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_all_matches()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
