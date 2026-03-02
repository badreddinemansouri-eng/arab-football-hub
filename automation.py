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
THESPORTSDB_LEAGUE = f"{THESPORTSDB_BASE}/search_all_leagues.php"

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC",
    # Add Arab league codes here if you know them
]

# -------------------------------------------------------------------
# Manual name mappings (expand as needed)
# -------------------------------------------------------------------
TEAM_NAME_MAP = {
    "Manchester United FC": "Manchester United",
    "Liverpool FC": "Liverpool",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Tottenham Hotspur FC": "Tottenham",
    "Manchester City FC": "Manchester City",
    "Everton FC": "Everton",
    "Newcastle United FC": "Newcastle",
    "Leicester City FC": "Leicester",
    "Aston Villa FC": "Aston Villa",
    "West Ham United FC": "West Ham",
    "Wolverhampton Wanderers FC": "Wolves",
    "Southampton FC": "Southampton",
    "Crystal Palace FC": "Crystal Palace",
    "Brighton & Hove Albion FC": "Brighton",
    "Burnley FC": "Burnley",
    "Watford FC": "Watford",
    "Norwich City FC": "Norwich",
    "Leeds United FC": "Leeds",
    "Brentford FC": "Brentford",
    "Fulham FC": "Fulham",
    "Nottingham Forest FC": "Nottingham Forest",
    "Bournemouth FC": "Bournemouth",
    "Real Madrid CF": "Real Madrid",
    "FC Barcelona": "Barcelona",
    "Atlético Madrid": "Atletico Madrid",
    "Sevilla FC": "Sevilla",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
    "Real Betis Balompié": "Real Betis",
    "Athletic Club": "Athletic Bilbao",
    "Real Sociedad": "Real Sociedad",
    "Celta Vigo": "Celta Vigo",
    "Granada CF": "Granada",
    "CA Osasuna": "Osasuna",
    "Cádiz CF": "Cadiz",
    "RCD Mallorca": "Mallorca",
    "Deportivo Alavés": "Alaves",
    "Rayo Vallecano": "Rayo Vallecano",
    "Elche CF": "Elche",
    "Getafe CF": "Getafe",
    "Espanyol": "Espanyol",
    "Levante UD": "Levante",
    "Almería": "Almeria",
    "Real Valladolid": "Valladolid",
    "Girona FC": "Girona",
    "Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Borussia Dortmund",
    "RB Leipzig": "Leipzig",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Borussia Mönchengladbach": "Monchengladbach",
    "VfL Wolfsburg": "Wolfsburg",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "VfB Stuttgart": "Stuttgart",
    "Hertha BSC": "Hertha Berlin",
    "SC Freiburg": "Freiburg",
    "TSG 1899 Hoffenheim": "Hoffenheim",
    "1. FC Köln": "Koln",
    "FC Augsburg": "Augsburg",
    "1. FSV Mainz 05": "Mainz",
    "FC Schalke 04": "Schalke",
    "Arminia Bielefeld": "Bielefeld",
    "Union Berlin": "Union Berlin",
    "VfL Bochum": "Bochum",
    "SpVgg Greuther Fürth": "Greuther Furth",
    "Juventus FC": "Juventus",
    "AC Milan": "AC Milan",
    "Inter Milan": "Inter",
    "AS Roma": "Roma",
    "SSC Napoli": "Napoli",
    "SS Lazio": "Lazio",
    "Atalanta BC": "Atalanta",
    "ACF Fiorentina": "Fiorentina",
    "Torino FC": "Torino",
    "Bologna FC": "Bologna",
    "Udinese Calcio": "Udinese",
    "Sampdoria": "Sampdoria",
    "Genoa CFC": "Genoa",
    "US Sassuolo Calcio": "Sassuolo",
    "Cagliari Calcio": "Cagliari",
    "Spezia Calcio": "Spezia",
    "Empoli FC": "Empoli",
    "Venezia FC": "Venezia",
    "Salernitana": "Salernitana",
    "Paris Saint-Germain FC": "PSG",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "AS Monaco FC": "Monaco",
    "Stade Rennais FC": "Rennes",
    "Lille OSC": "Lille",
    "OGC Nice": "Nice",
    "RC Strasbourg Alsace": "Strasbourg",
    "FC Nantes": "Nantes",
    "Montpellier HSC": "Montpellier",
    "Stade Brestois 29": "Brest",
    "Stade de Reims": "Reims",
    "FC Metz": "Metz",
    "Angers SCO": "Angers",
    "Clermont Foot": "Clermont",
    "ES Troyes AC": "Troyes",
    "FC Lorient": "Lorient",
    "AJ Auxerre": "Auxerre",
    "AC Ajaccio": "Ajaccio",
    "Toulouse FC": "Toulouse",
}

LEAGUE_NAME_MAP = {
    "Premier League": "English Premier League",
    "La Liga": "Spanish La Liga",
    "Bundesliga": "German Bundesliga",
    "Serie A": "Italian Serie A",
    "Ligue 1": "French Ligue 1",
    "Champions League": "UEFA Champions League",
    "Europa League": "UEFA Europa League",
    "World Cup": "World Cup",
    "European Championship": "European Championships",
}

def clean_team_name(name):
    """Remove common suffixes and normalize."""
    name = re.sub(r"\s+(FC|AFC|United|City|Real|CF|AC|AS|SS|SC|Club|Deportivo|Futebol|Clube)$", "", name, flags=re.IGNORECASE)
    return name.strip()

def fetch_team_logo(team_name):
    """Search TheSportsDB for a team logo, store in team_logos table."""
    print(f"🔍 Searching logo for team: '{team_name}'")
    # Check cache
    try:
        cached = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
        if cached.data and cached.data[0].get("logo_url"):
            print(f"✅ Found cached logo for '{team_name}': {cached.data[0]['logo_url']}")
            return cached.data[0]["logo_url"]
    except Exception as e:
        print(f"⚠️ Error checking cache for '{team_name}': {e}")

    # Try variations
    variations = [
        team_name,
        TEAM_NAME_MAP.get(team_name, team_name),
        clean_team_name(team_name),
        team_name.split()[0],  # first word
    ]
    # Remove duplicates
    variations = list(set(variations))

    for name in variations:
        print(f"  Trying variation: '{name}'")
        try:
            resp = requests.get(THESPORTSDB_TEAM, params={"t": name}, timeout=5)
            data = resp.json()
            teams = data.get("teams", [])
            if teams:
                logo = teams[0].get("strTeamBadge") or teams[0].get("strTeamLogo")
                if logo:
                    logo = logo.replace("http://", "https://")
                    print(f"✅ Found logo for '{team_name}' using variation '{name}': {logo}")
                    # Store in cache
                    try:
                        supabase.table("team_logos").upsert(
                            {"team_name": team_name, "logo_url": logo},
                            on_conflict="team_name"
                        ).execute()
                    except Exception as e:
                        print(f"⚠️ Error caching logo for '{team_name}': {e}")
                    return logo
                else:
                    print(f"  ⚠️ Team found but no logo field for variation '{name}'")
            else:
                print(f"  ❌ No team found for variation '{name}'")
        except Exception as e:
            print(f"  ❌ Error fetching variation '{name}': {e}")
        time.sleep(0.2)
    print(f"❌ No logo found for '{team_name}' after all variations.")
    return None

def fetch_league_logo(league_name):
    """Search TheSportsDB for a league logo, store in league_logos table."""
    print(f"🔍 Searching logo for league: '{league_name}'")
    # Check cache
    try:
        cached = supabase.table("league_logos").select("logo_url").eq("league_name", league_name).execute()
        if cached.data and cached.data[0].get("logo_url"):
            print(f"✅ Found cached logo for '{league_name}': {cached.data[0]['logo_url']}")
            return cached.data[0]["logo_url"]
    except Exception as e:
        print(f"⚠️ Error checking cache for '{league_name}': {e}")

    # Use mapped name if available
    search_name = LEAGUE_NAME_MAP.get(league_name, league_name)
    print(f"  Searching with name: '{search_name}'")
    try:
        resp = requests.get(THESPORTSDB_LEAGUE, params={"l": search_name}, timeout=5)
        data = resp.json()
        # TheSportsDB may return under 'countrys' or 'leagues'
        leagues = data.get("countrys", []) or data.get("leagues", [])
        for league in leagues:
            if league_name.lower() in league.get("strLeague", "").lower():
                logo = league.get("strBadge") or league.get("strLogo")
                if logo:
                    logo = logo.replace("http://", "https://")
                    print(f"✅ Found logo for '{league_name}': {logo}")
                    try:
                        supabase.table("league_logos").upsert(
                            {"league_name": league_name, "logo_url": logo},
                            on_conflict="league_name"
                        ).execute()
                    except Exception as e:
                        print(f"⚠️ Error caching logo for '{league_name}': {e}")
                    return logo
        print(f"❌ No logo found for '{league_name}'.")
    except Exception as e:
        print(f"❌ Error fetching league logo for '{league_name}': {e}")
    return None

# -------------------------------------------------------------------
# football-data.org fetching functions
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

    # Fetch logos (these functions return None if not found)
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
    # If you have a YouTube search function, keep it here.
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

            # Admin streams check
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
