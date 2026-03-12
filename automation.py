import os
import sys
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta
import json
import time

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY = os.environ.get("ONESIGNAL_API_KEY", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

FOOTBALL_DATA_API = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

RAPIDAPI_HOST = "api-football-v1.p.rapidapi.com"
RAPIDAPI_HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST
}

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC", "BSA"
]

# -------------------------------------------------------------------
# Helper: check if custom match exists (to avoid overwriting)
# -------------------------------------------------------------------
def custom_match_exists(home_team, away_team, match_date):
    res = supabase.table("matches")\
        .select("fixture_id")\
        .eq("source", "custom")\
        .eq("home_team", home_team)\
        .eq("away_team", away_team)\
        .gte("date", match_date + "T00:00:00+00:00")\
        .lt("date", match_date + "T23:59:59+00:00")\
        .execute()
    return len(res.data) > 0

# -------------------------------------------------------------------
# API-Football helpers
# -------------------------------------------------------------------
def api_football_request(endpoint, params=None):
    url = f"https://{RAPIDAPI_HOST}/{endpoint}"
    try:
        resp = requests.get(url, headers=RAPIDAPI_HEADERS, params=params, timeout=15)
        data = resp.json()
        if data.get("errors"):
            print(f"API-Football errors: {data['errors']}")
            return None
        return data.get("response")
    except Exception as e:
        print(f"API-Football request error: {e}")
        return None

def fetch_teams_by_league(league_id, season):
    params = {"league": league_id, "season": season}
    return api_football_request("teams", params)

def fetch_players_by_team(team_id):
    params = {"team": team_id}
    return api_football_request("players", params)

def fetch_match_details(fixture_id):
    params = {"fixture": fixture_id}
    response = api_football_request("fixtures", params)
    if not response:
        return
    data = response[0]
    # Update matches table
    match_update = {
        "date": data["fixture"]["date"],
        "status": data["fixture"]["status"]["short"],
        "elapsed": data["fixture"]["status"]["elapsed"],
        "referee": data["fixture"]["referee"],
        "home_score": data["goals"]["home"],
        "away_score": data["goals"]["away"],
        "halftime_home": data["score"]["halftime"]["home"],
        "halftime_away": data["score"]["halftime"]["away"],
        "fulltime_home": data["score"]["fulltime"]["home"],
        "fulltime_away": data["score"]["fulltime"]["away"],
        "extratime_home": data["score"]["extratime"]["home"],
        "extratime_away": data["score"]["extratime"]["away"],
        "penalty_home": data["score"]["penalty"]["home"],
        "penalty_away": data["score"]["penalty"]["away"],
        "winner": "home" if data["teams"]["home"]["winner"] else "away" if data["teams"]["away"]["winner"] else "draw"
    }
    supabase.table("matches").update(match_update).eq("fixture_id", fixture_id).execute()
    # Statistics
    stats = data.get("statistics", [])
    for team_stats in stats:
        team_id = team_stats["team"]["id"]
        for stat in team_stats["statistics"]:
            supabase.table("match_statistics").upsert({
                "fixture_id": fixture_id,
                "team_id": team_id,
                "type": stat["type"],
                "value": stat["value"]
            }, on_conflict=["fixture_id", "team_id", "type"]).execute()
    # Lineups
    lineups = data.get("lineups", [])
    for lineup in lineups:
        supabase.table("lineups").upsert({
            "fixture_id": fixture_id,
            "team_id": lineup["team"]["id"],
            "formation": lineup["formation"],
            "starting_xi": lineup["startXI"],
            "substitutes": lineup["substitutes"],
            "coach_name": lineup["coach"]["name"]
        }, on_conflict=["fixture_id", "team_id"]).execute()
    # Events
    events = data.get("events", [])
    for ev in events:
        supabase.table("match_events").insert({
            "fixture_id": fixture_id,
            "elapsed": ev["time"]["elapsed"],
            "extra_minute": ev["time"]["extra"],
            "team_id": ev["team"]["id"],
            "player_id": ev["player"]["id"] if ev.get("player") else None,
            "assist_player_id": ev["assist"]["id"] if ev.get("assist") else None,
            "type": ev["type"],
            "detail": ev["detail"],
            "comments": ev["comments"]
        }).execute()
    return data

def fetch_head2head(team1, team2):
    params = {"h2h": f"{team1}-{team2}"}
    return api_football_request("fixtures/headtohead", params)

def fetch_top_scorers(league_id, season):
    params = {"league": league_id, "season": season}
    return api_football_request("players/topscorers", params)

def fetch_predictions(fixture_id):
    params = {"fixture": fixture_id}
    return api_football_request("predictions", params)

# -------------------------------------------------------------------
# football-data.org functions (matches, standings)
# -------------------------------------------------------------------
def fetch_matches_fd(competition_code=None, date_from=None, date_to=None, status=None):
    url = f"{FOOTBALL_DATA_API}/matches"
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
        resp = requests.get(url, headers=FOOTBALL_DATA_HEADERS, params=params, timeout=10)
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
        "date": match.get("utcDate"),
        "home_team_id": None,
        "away_team_id": None,
    }

def upsert_match(match_data):
    try:
        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
        print(f"Upserted match {match_data['fixture_id']}: {match_data['home_team']} vs {match_data['away_team']}")
    except Exception as e:
        print(f"Error upserting match: {e}")

def update_standings():
    for code in ALLOWED_COMPETITIONS:
        url = f"{FOOTBALL_DATA_API}/competitions/{code}/standings"
        try:
            resp = requests.get(url, headers=FOOTBALL_DATA_HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                supabase.table("standings").upsert({
                    "competition_code": code,
                    "competition_name": data["competition"]["name"],
                    "data": data
                }, on_conflict="competition_code").execute()
                print(f"Standings updated for {code}")
        except Exception as e:
            print(f"Error updating standings for {code}: {e}")

# -------------------------------------------------------------------
# Main update functions
# -------------------------------------------------------------------
def update_live():
    print(f"[{datetime.now()}] Running live update...")
    live = fetch_matches_fd(status="IN_PLAY,PAUSED")
    print(f"Fetched {len(live)} live matches from FD")
    for m in live:
        data = parse_match_fd(m)
        # Check custom conflict
        match_date = data["date"][:10]
        if custom_match_exists(data["home_team"], data["away_team"], match_date):
            print(f"Skipping {data['home_team']} vs {data['away_team']} – custom match exists")
            continue
        upsert_match(data)
        # Fetch detailed data from API-Football (if available)
        if RAPIDAPI_KEY:
            fetch_match_details(data["fixture_id"])
    # Also fetch today's matches to catch status changes
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    upcoming = fetch_matches_fd(date_from=today, date_to=tomorrow)
    for m in upcoming:
        data = parse_match_fd(m)
        match_date = data["date"][:10]
        if custom_match_exists(data["home_team"], data["away_team"], match_date):
            print(f"Skipping {data['home_team']} vs {data['away_team']} – custom match exists")
            continue
        upsert_match(data)
    print("Live update complete.")

def update_full():
    print(f"[{datetime.now()}] Running full update...")
    update_standings()
    if RAPIDAPI_KEY:
        # Fetch teams, players, top scorers for each league
        leagues = [
            {"id": 39, "season": 2025, "name": "PL"},
            {"id": 140, "season": 2025, "name": "PD"},
            # add more as needed
        ]
        for l in leagues:
            teams = fetch_teams_by_league(l["id"], l["season"])
            if teams:
                for t in teams:
                    team = t["team"]
                    supabase.table("teams").upsert({
                        "id": team["id"],
                        "name": team["name"],
                        "logo": team["logo"],
                        "country": team["country"]
                    }, on_conflict="id").execute()
            scorers = fetch_top_scorers(l["id"], l["season"])
            if scorers:
                for s in scorers:
                    supabase.table("top_scorers").upsert({
                        "league_id": l["id"],
                        "league_name": l["name"],
                        "season": str(l["season"]),
                        "player_id": s["player"]["id"],
                        "team_id": s["statistics"][0]["team"]["id"],
                        "goals": s["statistics"][0]["goals"]["total"],
                        "assists": s["statistics"][0]["goals"]["assists"],
                        "penalties": s["statistics"][0]["penalty"]["scored"]
                    }, on_conflict=["league_id", "season", "player_id"]).execute()
    print("Full update complete.")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_full()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
