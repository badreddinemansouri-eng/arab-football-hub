import os
import sys
import requests
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import json
import time
import unicodedata
import re
import feedparser

# Environment variables
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")          # <-- new: for API-Football
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# -------------------------------------------------------------------
# football-data.org API configuration
# -------------------------------------------------------------------
FD_API_BASE = "https://api.football-data.org/v4"
FD_HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

# -------------------------------------------------------------------
# API-Football (RapidAPI) configuration
# -------------------------------------------------------------------
AF_API_HOST = "api-football-v1.p.rapidapi.com"
AF_HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": AF_API_HOST
}

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC",
]

# -------------------------------------------------------------------
# Helper: check if custom match exists
# -------------------------------------------------------------------
def custom_match_exists(home_team, away_team, match_date):
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
# Logo helpers (unchanged)
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
def upsert_team(team_id, team_name):
    """Store a team in the teams table (football-data.org ID)."""
    try:
        supabase.table("teams").upsert({
            "id": team_id,
            "name": team_name
        }, on_conflict="id").execute()
    except Exception as e:
        print(f"Error upserting team {team_id}: {e}")
# -------------------------------------------------------------------
# football-data.org match fetching (unchanged)
# -------------------------------------------------------------------
def fetch_fd_competitions():
    url = f"{FD_API_BASE}/competitions"
    try:
        resp = requests.get(url, headers=FD_HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"Error response: {resp.text}")
            return []
        data = resp.json()
        competitions = data.get("competitions", [])
        filtered = [c for c in competitions if c["code"] in ALLOWED_COMPETITIONS]
        print(f"Found {len(filtered)} allowed competitions")
        return filtered
    except Exception as e:
        print(f"Exception in fetch_fd_competitions: {e}")
        return []

def fetch_fd_matches(competition_code=None, date_from=None, date_to=None, status=None):
    url = f"{FD_API_BASE}/matches"
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
        resp = requests.get(url, headers=FD_HEADERS, params=params, timeout=10)
        data = resp.json()
        matches = data.get("matches", [])
        return matches
    except Exception as e:
        print(f"Error fetching FD matches: {e}")
        return []

def parse_fd_match(match):
    competition = match.get("competition", {})
    home_team = match.get("homeTeam", {})
    away_team = match.get("awayTeam", {})
      # Upsert teams
    upsert_team(home_team.get("id"), home_team.get("name", "Unknown"))
    upsert_team(away_team.get("id"), away_team.get("name", "Unknown"))
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
        "league_id": competition.get("id"),          # <-- store league id
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
    
        "home_team_id": home_team.get("id"),
        "away_team_id": away_team.get("id"),
        # will be filled later by API-Football
    
    }
    return match_data

def upsert_match(match_data):
    try:
        supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
    except Exception as e:
        print(f"Error upserting match {match_data['fixture_id']}: {e}")

# -------------------------------------------------------------------
# API-Football functions (RapidAPI)
# -------------------------------------------------------------------
def af_request(endpoint, params=None):
    """Make a request to API-Football and return response."""
    if not RAPIDAPI_KEY:
        print("RAPIDAPI_KEY not set, skipping API-Football request.")
        return None
    url = f"https://{AF_API_HOST}/{endpoint}"
    try:
        resp = requests.get(url, headers=AF_HEADERS, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"API-Football error {resp.status_code}: {resp.text}")
            return None
        data = resp.json()
        if data.get("errors") and data["errors"]:
            print(f"API-Football errors: {data['errors']}")
            return None
        return data.get("response")
    except Exception as e:
        print(f"API-Football request error: {e}")
        return None

def fetch_teams_by_league(league_id, season):
    """Fetch all teams in a league for a given season."""
    params = {"league": league_id, "season": season}
    return af_request("teams", params)

def fetch_players_by_team(team_id, season):
    """Fetch players of a team for a given season."""
    params = {"team": team_id, "season": season}
    return af_request("players", params)

def fetch_top_scorers(league_id, season):
    """Fetch top scorers for a league/season."""
    params = {"league": league_id, "season": season}
    return af_request("players/topscorers", params)

def fetch_fixture_by_id(fixture_id):
    """Fetch detailed fixture data (lineups, events, statistics)."""
    params = {"fixture": fixture_id}
    return af_request("fixtures", params)

def fetch_fixtures_by_league(league_id, season, status=None):
    """Fetch all fixtures for a league/season (can filter by status)."""
    params = {"league": league_id, "season": season}
    if status:
        params["status"] = status
    return af_request("fixtures", params)

# -------------------------------------------------------------------
# Enrich matches with API-Football IDs
# -------------------------------------------------------------------
def update_match_with_af_ids(match_data, af_fixture_data):
    """
    Given a match_data dict (from FD) and a fixture response from API-Football,
    update match_data with home_team_id, away_team_id, and possibly more details.
    """
    if not af_fixture_data or len(af_fixture_data) == 0:
        return match_data
    fixture = af_fixture_data[0]
    match_data["home_team_id"] = fixture["teams"]["home"]["id"]
    match_data["away_team_id"] = fixture["teams"]["away"]["id"]
    # Also update league_id if needed (API-Football league id might be different)
    # We'll keep the FD league_id for now, but you could map.
    return match_data

def enrich_match_with_af_details(fixture_id):
    """Fetch details (lineups, events, stats) from AF and store in respective tables."""
    data = fetch_fixture_by_id(fixture_id)
    if not data:
        return
    fixture = data[0]   # should be one fixture

    # Update matches table with additional fields (like elapsed, referee, etc.)
    match_update = {
        "elapsed": fixture["fixture"]["status"]["elapsed"],
        "referee": fixture["fixture"]["referee"],
        "home_score": fixture["goals"]["home"],
        "away_score": fixture["goals"]["away"],
        "halftime_home": fixture["score"]["halftime"]["home"],
        "halftime_away": fixture["score"]["halftime"]["away"],
        "fulltime_home": fixture["score"]["fulltime"]["home"],
        "fulltime_away": fixture["score"]["fulltime"]["away"],
        "extratime_home": fixture["score"]["extratime"]["home"],
        "extratime_away": fixture["score"]["extratime"]["away"],
        "penalty_home": fixture["score"]["penalty"]["home"],
        "penalty_away": fixture["score"]["penalty"]["away"],
        "winner": "home" if fixture["teams"]["home"]["winner"] else "away" if fixture["teams"]["away"]["winner"] else "draw"
    }
    supabase.table("matches").update(match_update).eq("fixture_id", fixture_id).execute()

    # Statistics
    stats = fixture.get("statistics", [])
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
    lineups = fixture.get("lineups", [])
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
    events = fixture.get("events", [])
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

# -------------------------------------------------------------------
# Populate teams and players (bulk update)
# -------------------------------------------------------------------
def update_teams_and_players():
    """Fetch teams and top scorers for leagues, respecting rate limits and last fetch times."""
    # Full league map (you can add/remove as needed)
    league_map = {
        "PL": 39, "PD": 140, "BL1": 78, "SA": 135, "FL1": 61,
        "CL": 2, "EL": 3, "EC": 4, "WC": 1,
        "CAF_CL": 207, "CAF_CC": 208, "AFCON": 21,
        "EGY": 233, "TUN": 253, "ALG": 187, "MAR": 242,
        "LBY": 386, "MTN": 322,
        "KSA": 307, "UAE": 344, "QAT": 305, "KUW": 384,
        "IRN": 292, "IRQ": 294, "JOR": 299, "SYR": 379,
        "LIB": 382, "PLE": 383, "OMN": 381, "BHR": 378, "YEM": 380,
    }
    
    season = datetime.now().year
    max_requests_per_run = 40  # Safe limit (half of daily quota)
    requests_made = 0
    interval_days = 7  # Fetch each league once per week

    # Ensure league_fetch_status table has entries for all leagues
    for code, af_id in league_map.items():
        supabase.table("league_fetch_status").upsert({
            "league_code": code,
            "af_league_id": af_id
        }, on_conflict="league_code").execute()

    # Get current statuses
    status_res = supabase.table("league_fetch_status").select("*").execute()
    status_dict = {s["league_code"]: s for s in status_res.data}

    for code, af_id in league_map.items():
        if requests_made >= max_requests_per_run:
            print(f"Reached max requests ({max_requests_per_run}) for this run. Stopping.")
            break

        status = status_dict.get(code, {})
        last_teams = status.get("last_teams_fetch")
        last_ts = status.get("last_topscorers_fetch")

        # Check if we need to fetch teams
        fetch_teams = False
        if not last_teams or (datetime.now() - datetime.fromisoformat(last_teams)) > timedelta(days=interval_days):
            fetch_teams = True

        # Check if we need to fetch top scorers
        fetch_topscorers = False
        if not last_ts or (datetime.now() - datetime.fromisoformat(last_ts)) > timedelta(days=interval_days):
            fetch_topscorers = True

        if not fetch_teams and not fetch_topscorers:
            continue

        print(f"Processing league {code} (AF ID {af_id})...")

        # Fetch teams (if needed)
        if fetch_teams:
            if requests_made >= max_requests_per_run:
                print("Request limit reached, stopping before teams fetch.")
                break
            teams_data = fetch_teams_by_league(af_id, season)
            requests_made += 1
            if teams_data:
                for t in teams_data:
                    team = t["team"]
                    supabase.table("teams").upsert({
                        "id": team["id"],
                        "name": team["name"],
                        "logo": team["logo"],
                        "country": team["country"]
                    }, on_conflict="id").execute()
                # Update last fetch time
                supabase.table("league_fetch_status").update({
                    "last_teams_fetch": datetime.now().isoformat()
                }).eq("league_code", code).execute()
                print(f"  Updated teams for {code}")
            else:
                print(f"  No teams data for {code}")

        # Fetch top scorers (if needed)
        if fetch_topscorers:
            if requests_made >= max_requests_per_run:
                print("Request limit reached, stopping before top scorers fetch.")
                break
            scorers = fetch_top_scorers(af_id, season)
            requests_made += 1
            if scorers:
                for s in scorers:
                    supabase.table("top_scorers").upsert({
                        "league_id": af_id,
                        "league_name": code,
                        "season": str(season),
                        "player_id": s["player"]["id"],
                        "team_id": s["statistics"][0]["team"]["id"],
                        "goals": s["statistics"][0]["goals"]["total"],
                        "assists": s["statistics"][0]["goals"]["assists"],
                        "penalties": s["statistics"][0]["penalty"]["scored"]
                    }, on_conflict=["league_id", "season", "player_id"]).execute()
                supabase.table("league_fetch_status").update({
                    "last_topscorers_fetch": datetime.now().isoformat()
                }).eq("league_code", code).execute()
                print(f"  Updated top scorers for {code}")
            else:
                print(f"  No top scorers data for {code}")

        # Small delay to avoid hitting rate limits too hard
        time.sleep(1)

    print(f"Total requests made this run: {requests_made}")

# -------------------------------------------------------------------
# News fetching (unchanged)
# -------------------------------------------------------------------
def fetch_news_from_feed(feed_url, language="ar"):
    print(f"[{datetime.now()}] Fetching {language} news from {feed_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(feed_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"Feed returned status {resp.status_code}")
            return
        feed = feedparser.parse(resp.text)
        if feed.bozo:
            print(f"Feed parsing error: {feed.bozo_exception}")
            return
        entries = feed.entries
        print(f"Total entries in feed: {len(entries)}")
        if not entries:
            print("No entries found.")
            return
        for i, entry in enumerate(entries[:20]):
            print(f"Processing entry {i+1}: {entry.get('title', 'No title')}")
            image = None
            if hasattr(entry, 'media_content'):
                image = entry.media_content[0]['url']
            elif hasattr(entry, 'links'):
                for link in entry.links:
                    if link.get('type', '').startswith('image'):
                        image = link['href']
                        break
            if not image and hasattr(entry, 'description'):
                match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
                if match:
                    image = match.group(1)
            if not image and hasattr(entry, 'summary'):
                match = re.search(r'<img[^>]+src="([^"]+)"', entry.summary)
                if match:
                    image = match.group(1)

            data = {
                "title": entry.get('title', '')[:255],
                "content": entry.get('summary', entry.get('description', ''))[:1000],
                "image": image,
                "source": feed.feed.get('title', 'Unknown Source'),
                "url": entry.get('link', ''),
                "published_at": entry.get('published', entry.get('updated', datetime.now().isoformat())),
                "language": language
            }
            if not data["url"]:
                print("Skipping entry: no URL")
                continue
            try:
                supabase.table("news").upsert(data, on_conflict="url").execute()
                print(f"Inserted {language} news: {data['title'][:50]}...")
            except Exception as e:
                print(f"Upsert failed for {data['title'][:30]}: {e}")
    except Exception as e:
        print(f"Error fetching news from {feed_url}: {e}")

def cleanup_old_news():
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    try:
        result = supabase.table("news").delete().lt("published_at", cutoff).execute()
        print(f"Deleted {len(result.data)} news items older than 7 days.")
    except Exception as e:
        print(f"Error during news cleanup: {e}")

def update_news():
    arabic_feeds = [
        "https://www.france24.com/ar/%D8%AA%D8%A7%D8%BA/%D8%AF%D9%88%D8%B1%D9%8A-%D8%A3%D8%A8%D8%B7%D8%A7%D9%84-%D8%A3%D9%81%D8%B1%D9%8A%D9%82%D9%8A%D8%A7/rss",
        "https://www.france24.com/ar/sports/rss",
        "http://feeds.bbci.co.uk/arabic/sport/rss.xml",
    ]
    for feed in arabic_feeds:
        fetch_news_from_feed(feed, "ar")
    cleanup_old_news()

# -------------------------------------------------------------------
# Main update functions (modified to use API-Football enrichment)
# -------------------------------------------------------------------
def update_live():
    print(f"[{datetime.now()}] Running live update...")
    live_matches = fetch_fd_matches(status="IN_PLAY,PAUSED")
    for match in live_matches:
        data = parse_fd_match(match)
        # If we have RapidAPI key, try to enrich with team IDs
        if RAPIDAPI_KEY:
            # We need to get AF fixture data for this match. Since FD uses different fixture IDs,
            # we may need to match by date and teams. For simplicity, we'll skip live enrichment for now.
            # Instead, we can rely on the full update to have stored IDs.
            pass
        upsert_match(data)
        print(f"Updated live: {data['home_team']} vs {data['away_team']}")

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    upcoming_matches = fetch_fd_matches(date_from=today, date_to=tomorrow)

    now_utc = datetime.now(timezone.utc)
    soon_threshold = now_utc + timedelta(minutes=15)

    for match in upcoming_matches:
        match_time_str = match.get("utcDate")
        if match_time_str:
            try:
                match_time = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
                if match_time <= soon_threshold:
                    data = parse_fd_match(match)
                    upsert_match(data)
                    print(f"Proactively updated: {data['home_team']} vs {data['away_team']}")
            except Exception as e:
                print(f"Error parsing time for match {match.get('id')}: {e}")

    print(f"Processed {len(upcoming_matches)} matches from {today} to {tomorrow}.")

def update_all_matches():
    print(f"[{datetime.now()}] Running global match update...")
    competitions = fetch_fd_competitions()
    if not competitions:
        print("No competitions found.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    next_3_days = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    for comp in competitions:
        code = comp["code"]
        name = comp["name"]
        print(f"Fetching matches for {name} ({code})...")
        matches = fetch_fd_matches(competition_code=code, date_from=today, date_to=next_3_days)

        for match in matches:
            match_data = parse_fd_match(match)

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

    # Fetch news after matches
    update_news()

    # After matches are updated, enrich them with API-Football data (if key available)
    if RAPIDAPI_KEY:
        print("Enriching matches with API-Football data...")
        # For simplicity, we'll fetch all matches from the last 3 days that need team IDs.
        # But we can also run a separate job. Here we'll do a one‑time bulk update.
        update_teams_and_players()   # populate teams, players, top scorers

        # Now try to add team IDs to matches we just inserted.
        # We need to match FD fixtures with AF fixtures. This is non‑trivial.
        # A simpler approach: fetch fixtures for each league from AF and match by date and teams.
        # For now, we'll skip; you can run a separate script later.
        print("Team ID enrichment not implemented in this version.")

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
