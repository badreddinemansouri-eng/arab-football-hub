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

# -------------------------------------------------------------------
# Environment variables
# -------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# -------------------------------------------------------------------
# football-data.org API configuration
# -------------------------------------------------------------------
FD_API_BASE = "https://api.football-data.org/v4"
FD_HEADERS = { "X-Auth-Token": FOOTBALL_DATA_TOKEN }

ALLOWED_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "EC", "WC", "QCAF",
]

# -------------------------------------------------------------------
# API-Football (direct) for African leagues
# -------------------------------------------------------------------
API_FOOTBALL_HOST = "v3.football.api-sports.io"
API_FOOTBALL_BASE = f"https://{API_FOOTBALL_HOST}"

AFRICAN_LEAGUES = {
    "Tunisian Ligue 1": 202,
    "Egyptian Premier League": 233,
    "CAF Champions League": 203,
}

def get_current_season():
    now = datetime.now()
    year = now.year
    if now.month < 8:
        return str(year - 1)
    else:
        return str(year)

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
        "International - Champions League", "International - World Cup","CAF-Champions League"
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

# -------------------------------------------------------------------
# Country flags using pycountry + flagcdn
# -------------------------------------------------------------------
def get_country_flag(country_name):
    if not country_name:
        return None
    try:
        import pycountry
        country = pycountry.countries.get(name=country_name)
        if country:
            code = country.alpha_2.lower()
            return f"https://flagcdn.com/w320/{code}.png"
    except ImportError:
        print("pycountry not installed. Install it for automatic country flags: pip install pycountry")
    except:
        pass
    return None

# -------------------------------------------------------------------
# Helper: upsert team
# -------------------------------------------------------------------
def upsert_team(team_id, team_name):
    if not team_id or not team_name:
        return
    try:
        supabase.table("teams").upsert({
            "id": team_id,
            "name": team_name
        }, on_conflict="id").execute()
        print(f"Upserted team {team_id}: {team_name}")
    except Exception as e:
        print(f"Error upserting team {team_id}: {e}")

# -------------------------------------------------------------------
# football-data.org match fetching
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
        resp = requests.get(url, headers=FD_HEADERS, params=params, timeout=20)
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
        "source": "football-data",
        "fixture_id": match["id"],
        "league": competition.get("name", "Unknown"),
        "league_id": competition.get("id"),
        "league_logo": league_logo,
        "home_team": home_team.get("name", "Unknown"),
        "away_team": away_team.get("name", "Unknown"),
        "home_team_id": home_team.get("id"),
        "away_team_id": away_team.get("id"),
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

# -------------------------------------------------------------------
# API-Football functions for African leagues
# -------------------------------------------------------------------

def fetch_african_matches(league_id, season):
    url = f"{API_FOOTBALL_BASE}/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": season}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", [])
        else:
            print(f"API-Football fixtures error {resp.status_code}: {resp.text}")
            return []
    except Exception as e:
        print(f"Exception fetching API-Football fixtures: {e}")
        return []

def parse_african_fixture(fixture, league_name, league_id):
    f = fixture["fixture"]
    teams = fixture["teams"]
    goals = fixture["goals"]
    status_short = f["status"]["short"]

    fixture_id = f["id"]
    home_team = teams["home"]["name"]
    away_team = teams["away"]["name"]
    home_team_id = teams["home"]["id"]
    away_team_id = teams["away"]["id"]
    match_time = f["date"]

    if status_short in ["FT", "AET", "PEN"]:
        status_cat = "FINISHED"
    elif status_short in ["LIVE", "1H", "2H", "HT", "ET", "P"]:
        status_cat = "LIVE"
    else:
        status_cat = "UPCOMING"

    home_score = goals["home"] or 0
    away_score = goals["away"] or 0

    home_logo = get_team_logo_from_db(home_team)
    away_logo = get_team_logo_from_db(away_team)
    league_logo = get_league_logo_from_db(league_name)

    if "Tunisian" in league_name:
        country = "Tunisia"
    elif "Egyptian" in league_name:
        country = "Egypt"
    else:
        country = "Africa"
    country_flag = get_country_flag(country)

    upsert_team(home_team_id, home_team)
    upsert_team(away_team_id, away_team)

    match_data = {
        "source": "api-football",
        "fixture_id": fixture_id,
        "league": league_name,
        "league_id": league_id,
        "league_logo": league_logo,
        "home_team": home_team,
        "away_team": away_team,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_logo": home_logo,
        "away_logo": away_logo,
        "country": country,
        "country_logo": country_flag,
        "match_time": match_time,
        "status": status_cat,
        "home_score": home_score,
        "away_score": away_score,
        "streams": [],
        "broadcasters": [],
    }
    return match_data

def fetch_and_store_african_team_logos(league_id, league_name, season):
    print(f"Fetching team logos for {league_name}...")
    url = f"{API_FOOTBALL_BASE}/teams"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": season}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            teams = data.get("response", [])
            print(f"Received {len(teams)} teams from API.")
            if teams:
                for item in teams:
                    team = item["team"]
                    team_name = team["name"]
                    logo_url = team["logo"]
                    if team_name and logo_url:
                        supabase.table("team_logos").upsert(
                            {"team_name": team_name, "logo_url": logo_url},
                            on_conflict="team_name"
                        ).execute()
                        print(f"  Stored logo for {team_name}")
                print(f"Team logos updated for {league_name}")
            else:
                print("No teams received from API – check season or API limits.")
        else:
            print(f"API-Football teams error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Exception fetching teams for {league_name}: {e}")

def fetch_and_store_african_standings(league_id, league_name, season):
    print(f"Fetching standings for {league_name}...")
    url = f"{API_FOOTBALL_BASE}/standings"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": season}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            standings = data.get("response", [])
            if standings:
                supabase.table("african_standings").upsert({
                    "competition_code": str(league_id),
                    "competition_name": league_name,
                    "data": data,
                    "source": "api-football"
                }, on_conflict="source,competition_code").execute()
                print(f"Standings stored for {league_name}")
        else:
            print(f"API-Football standings error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Exception fetching standings for {league_name}: {e}")

# -------------------------------------------------------------------
# Upsert match (manual, uses composite key)
# -------------------------------------------------------------------
def upsert_match(match_data):
    try:
        supabase.table("matches").upsert(
            match_data,
            on_conflict="source,fixture_id"
        ).execute()
        print(f"Upserted match {match_data['fixture_id']} from {match_data['source']}")
    except Exception as e:
        print(f"Error upserting match {match_data['fixture_id']} from {match_data['source']}: {e}")

# -------------------------------------------------------------------
# Standings for football-data.org
# -------------------------------------------------------------------
def update_standings():
    for code in ALLOWED_COMPETITIONS:
        url = f"{FD_API_BASE}/competitions/{code}/standings"
        try:
            resp = requests.get(url, headers=FD_HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                supabase.table("standings").upsert({
                    "competition_code": code,
                    "competition_name": data["competition"]["name"],
                    "data": data
                }, on_conflict="competition_code").execute()
                print(f"Standings updated for {code}")
            else:
                print(f"Standings fetch failed for {code}: {resp.status_code}")
        except Exception as e:
            print(f"Error fetching standings for {code}: {e}")

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
# TheSportsDB Team ID fetching
# -------------------------------------------------------------------
def fetch_and_store_team_id(team_name, team_id_in_db):
    """Search TheSportsDB for a team and store its ID in the teams table."""
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(team_name)}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("teams"):
                tsdb_team = data["teams"][0]
                tsdb_team_id = tsdb_team.get("idTeam")
                if tsdb_team_id:
                    supabase.table("teams").update({"tsdb_team_id": tsdb_team_id}).eq("id", team_id_in_db).execute()
                    print(f"Stored TheSportsDB ID {tsdb_team_id} for {team_name}")
                    return tsdb_team_id
    except Exception as e:
        print(f"Error fetching team ID for {team_name}: {e}")
    return None

def fetch_all_team_ids():
    """Fetch TheSportsDB IDs for all teams in the database."""
    teams = supabase.table("teams").select("id, name").execute().data
    for team in teams:
        if not team.get("tsdb_team_id"):
            fetch_and_store_team_id(team["name"], team["id"])
            time.sleep(1)

# -------------------------------------------------------------------
# Improved match search using team IDs
# -------------------------------------------------------------------
def find_match_by_team_and_date(team_id, date, opponent_name):
    """Search for a match using team ID and date, then verify opponent."""
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventslast.php?id={team_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            events = data.get("results", [])
            for ev in events:
                ev_date = ev.get("dateEvent")
                if ev_date == date:
                    # Check if opponent matches (home or away)
                    if (ev.get("idHomeTeam") == team_id and ev.get("strAwayTeam") == opponent_name) or \
                       (ev.get("idAwayTeam") == team_id and ev.get("strHomeTeam") == opponent_name):
                        return ev.get("idEvent")
    except Exception as e:
        print(f"Error searching match by team: {e}")
    return None

def process_finished_matches(limit=10):
    """Fetch details for finished matches using team IDs for better accuracy."""
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    res = supabase.table("matches")\
        .select("fixture_id, home_team, away_team, match_time, home_team_id, away_team_id")\
        .eq("status", "FINISHED")\
        .is_("tsdb_event_id", "null")\
        .gte("match_time", recent_cutoff)\
        .limit(limit)\
        .execute()
    matches = res.data
    if not matches:
        print("No matches to process.")
        return

    for m in matches:
        print(f"\nProcessing: {m['home_team']} vs {m['away_team']} on {m['match_time']}")
        date_str = m['match_time'][:10]
        # Get team IDs from teams table
        home_team_info = supabase.table("teams").select("tsdb_team_id").eq("id", m['home_team_id']).execute().data
        away_team_info = supabase.table("teams").select("tsdb_team_id").eq("id", m['away_team_id']).execute().data
        home_tsdb_id = home_team_info[0]["tsdb_team_id"] if home_team_info else None
        away_tsdb_id = away_team_info[0]["tsdb_team_id"] if away_team_info else None

        event_id = None
        # Try home team first
        if home_tsdb_id:
            event_id = find_match_by_team_and_date(home_tsdb_id, date_str, m['away_team'])
        # If not found, try away team
        if not event_id and away_tsdb_id:
            event_id = find_match_by_team_and_date(away_tsdb_id, date_str, m['home_team'])

        if event_id:
            print(f"✅ Found event ID: {event_id}")
            supabase.table("matches").update({"tsdb_event_id": event_id}).eq("fixture_id", m['fixture_id']).execute()
            # Optionally fetch lineups/events here (reuse existing functions)
        else:
            print("❌ No event found after all attempts")
        time.sleep(1)

# -------------------------------------------------------------------
# Highlights fetching (unchanged)
# -------------------------------------------------------------------
def fetch_thesportsdb_highlights(event_id):
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventshighlights.php?id={event_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tvhighlights", [])
    except Exception as e:
        print(f"Error fetching highlights: {e}")
    return []

def update_match_highlights(limit=30):
    """For matches with tsdb_event_id, fetch highlights and add to streams."""
    print(f"[{datetime.now()}] Running highlights update...")
    res = supabase.table("matches")\
        .select("fixture_id, tsdb_event_id, streams")\
        .not_.is_("tsdb_event_id", "null")\
        .limit(limit)\
        .execute()
    matches = res.data
    if not matches:
        print("No matches to process.")
        return

    for m in matches:
        if not m.get("tsdb_event_id"):
            continue
        highlights = fetch_thesportsdb_highlights(m["tsdb_event_id"])
        if highlights:
            streams = m.get("streams", [])
            if isinstance(streams, str):
                try:
                    streams = json.loads(streams)
                except:
                    streams = []
            added = 0
            for h in highlights:
                video_url = h.get("strVideo")
                if not video_url:
                    continue
                if not any(s.get("url") == video_url for s in streams):
                    streams.append({
                        "title": f"ملخص: {h.get('strEvent', '')}",
                        "url": video_url,
                        "source": "thesportsdb_highlight",
                        "verified": True
                    })
                    added += 1
            if added > 0:
                supabase.table("matches").update({"streams": json.dumps(streams)}).eq("fixture_id", m["fixture_id"]).execute()
                print(f"Added {added} highlight(s) for match {m['fixture_id']}")
        time.sleep(1)
    print("Highlights update complete.")

# -------------------------------------------------------------------
# Main update functions
# -------------------------------------------------------------------
def update_live():
    print(f"[{datetime.now()}] Running live update...")
    live_matches = fetch_fd_matches(status="IN_PLAY,PAUSED")
    for match in live_matches:
        data = parse_fd_match(match)
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
                print(f"Error parsing time: {e}")

    # Process recently finished matches for details
    process_finished_matches(limit=5)

    print(f"Processed {len(upcoming_matches)} matches from {today} to {tomorrow}.")

def update_all_matches():
    print(f"[{datetime.now()}] Running global match update...")
    competitions = fetch_fd_competitions()
    if competitions:
        today = datetime.now().strftime("%Y-%m-%d")
        next_7_days = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        for comp in competitions:
            code = comp["code"]
            name = comp["name"]
            print(f"Fetching FD matches for {name} ({code})...")
            matches = fetch_fd_matches(competition_code=code, date_from=today, date_to=next_7_days)
            for match in matches:
                match_data = parse_fd_match(match)
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
                print(f"Updated FD: {match_data['home_team']} vs {match_data['away_team']}")
                time.sleep(0.5)
            time.sleep(1)

    season = get_current_season()
    for league_name, league_id in AFRICAN_LEAGUES.items():
        print(f"Processing {league_name}...")
        fixtures = fetch_african_matches(league_id, season)
        for fix in fixtures:
            match_data = parse_african_fixture(fix, league_name, league_id)
            upsert_match(match_data)
            print(f"Updated API-Football: {match_data['home_team']} vs {match_data['away_team']} ({match_data['status']})")
            time.sleep(0.5)
        fetch_and_store_african_team_logos(league_id, league_name, season)
        fetch_and_store_african_standings(league_id, league_name, season)

    now = datetime.now().isoformat()
    supabase.table("admin_streams")\
        .update({"is_active": False})\
        .lt("expires_at", now)\
        .execute()

    update_standings()
    update_news()
    print("Global update complete!")

# -------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_all_matches()
    elif mode == "details":
        process_finished_matches(limit=20)
    elif mode == "highlights":
        update_match_highlights()
    elif mode == "fetch_team_ids":
        fetch_all_team_ids()
    else:
        print("Unknown mode. Use 'live', 'full', 'details', 'highlights', or 'fetch_team_ids'.")
