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
RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================================
# Global League Configuration
# ============================================
TOP_LEAGUES = {
    # Europe Top 5
    "Premier League": {"country": "England", "importance": 100},
    "La Liga": {"country": "Spain", "importance": 98},
    "Bundesliga": {"country": "Germany", "importance": 97},
    "Serie A": {"country": "Italy", "importance": 96},
    "Ligue 1": {"country": "France", "importance": 95},
    
    # Arab Leagues
    "Saudi Pro League": {"country": "Saudi Arabia", "importance": 90},
    "Egyptian Premier League": {"country": "Egypt", "importance": 88},
    "UAE Pro League": {"country": "UAE", "importance": 85},
    "Qatar Stars League": {"country": "Qatar", "importance": 84},
    "Tunisian Ligue 1": {"country": "Tunisia", "importance": 82},
    "Moroccan Botola": {"country": "Morocco", "importance": 82},
    "Algerian Ligue 1": {"country": "Algeria", "importance": 80},
    
    # International
    "UEFA Champions League": {"country": "Europe", "importance": 100},
    "UEFA Europa League": {"country": "Europe", "importance": 92},
    "CAF Champions League": {"country": "Africa", "importance": 88},
    "AFC Champions League": {"country": "Asia", "importance": 86},
    "Copa Libertadores": {"country": "South America", "importance": 90},
    
    # Other Major Leagues
    "Eredivisie": {"country": "Netherlands", "importance": 85},
    "Primeira Liga": {"country": "Portugal", "importance": 84},
    "Belgian Pro League": {"country": "Belgium", "importance": 80},
    "Turkish Süper Lig": {"country": "Turkey", "importance": 82},
    "Russian Premier League": {"country": "Russia", "importance": 80},
    "Ukrainian Premier League": {"country": "Ukraine", "importance": 78},
    "Austrian Bundesliga": {"country": "Austria", "importance": 75},
    "Swiss Super League": {"country": "Switzerland", "importance": 75},
    "Greek Super League": {"country": "Greece", "importance": 76},
    "Czech First League": {"country": "Czech Republic", "importance": 72},
    "Croatian HNL": {"country": "Croatia", "importance": 72},
    "Danish Superliga": {"country": "Denmark", "importance": 73},
    "Swedish Allsvenskan": {"country": "Sweden", "importance": 72},
    "Norwegian Eliteserien": {"country": "Norway", "importance": 72},
    "Finnish Veikkausliiga": {"country": "Finland", "importance": 68},
    "Polish Ekstraklasa": {"country": "Poland", "importance": 74},
    "Hungarian NB I": {"country": "Hungary", "importance": 68},
    "Romanian Liga I": {"country": "Romania", "importance": 68},
    "Bulgarian First League": {"country": "Bulgaria", "importance": 66},
    "Serbian SuperLiga": {"country": "Serbia", "importance": 68},
    
    # Americas
    "Brazilian Serie A": {"country": "Brazil", "importance": 88},
    "Argentine Primera Division": {"country": "Argentina", "importance": 86},
    "MLS": {"country": "USA", "importance": 82},
    "Mexican Liga MX": {"country": "Mexico", "importance": 84},
    "Chilean Primera Division": {"country": "Chile", "importance": 78},
    "Colombian Primera A": {"country": "Colombia", "importance": 78},
    
    # Asia
    "J-League": {"country": "Japan", "importance": 82},
    "K-League": {"country": "South Korea", "importance": 80},
    "Chinese Super League": {"country": "China", "importance": 78},
    "Indian Super League": {"country": "India", "importance": 72},
    "A-League": {"country": "Australia", "importance": 74},
}

# Verified YouTube channels (global)
VERIFIED_CHANNELS = [
    "beIN SPORTS", "SSC", "ONTime Sports", "Dubai Sports",
    "Abu Dhabi Sports", "Alkass TV", "KSA SPORT", "CBS Sports",
    "Sky Sports", "BT Sport", "ESPN", "Fox Sports", "DAZN",
    "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "MLS",
    "FIFA", "UEFA", "CAF", "AFC", "CONMEBOL"
]

# Global broadcaster mapping
GLOBAL_BROADCASTERS = {
    "beIN Sports": {
        "countries": ["MENA", "France", "USA", "Asia"],
        "url": "https://www.bein.com",
        "paid": True,
        "free_trial": True
    },
    "SSC": {
        "countries": ["Saudi Arabia"],
        "url": "https://ssc.sa",
        "paid": True,
        "free_trial": False
    },
    "DAZN": {
        "countries": ["USA", "Canada", "Germany", "Austria", "Switzerland", "Japan", "Italy", "Spain", "Brazil"],
        "url": "https://www.dazn.com",
        "paid": True,
        "free_trial": True
    },
    "ESPN+": {
        "countries": ["USA"],
        "url": "https://www.espn.com/watch",
        "paid": True,
        "free_trial": False
    },
    "Paramount+": {
        "countries": ["USA", "Canada", "Australia", "Latin America"],
        "url": "https://www.paramountplus.com",
        "paid": True,
        "free_trial": True
    },
    "Peacock": {
        "countries": ["USA"],
        "url": "https://www.peacocktv.com",
        "paid": True,
        "free_trial": True
    },
    "Fubo": {
        "countries": ["USA", "Canada", "Spain"],
        "url": "https://www.fubo.tv",
        "paid": True,
        "free_trial": True
    },
    "BBC iPlayer": {
        "countries": ["UK"],
        "url": "https://www.bbc.co.uk/iplayer",
        "paid": False,
        "free_trial": False,
        "requires_license": True
    },
    "ITVX": {
        "countries": ["UK"],
        "url": "https://www.itv.com/watch",
        "paid": False,
        "free_trial": False,
        "requires_license": True
    },
    "Channel 4": {
        "countries": ["UK"],
        "url": "https://www.channel4.com",
        "paid": False,
        "free_trial": False,
        "requires_license": True
    },
    "TF1": {
        "countries": ["France"],
        "url": "https://www.tf1.fr",
        "paid": False,
        "free_trial": False
    },
    "M6": {
        "countries": ["France"],
        "url": "https://www.6play.fr",
        "paid": False,
        "free_trial": False
    },
    "Rai Play": {
        "countries": ["Italy"],
        "url": "https://www.raiplay.it",
        "paid": False,
        "free_trial": False
    },
    "Mediaset Infinity": {
        "countries": ["Italy"],
        "url": "https://www.mediasetinfinity.mediaset.it",
        "paid": True,
        "free_trial": False
    },
    "ZDF": {
        "countries": ["Germany"],
        "url": "https://www.zdf.de",
        "paid": False,
        "free_trial": False
    },
    "ARD": {
        "countries": ["Germany"],
        "url": "https://www.ardmediathek.de",
        "paid": False,
        "free_trial": False
    },
    "RTVE Play": {
        "countries": ["Spain"],
        "url": "https://www.rtve.es/play",
        "paid": False,
        "free_trial": False
    },
    "TVP": {
        "countries": ["Poland"],
        "url": "https://tvpstream.vod.tvp.pl",
        "paid": False,
        "free_trial": False
    },
    "JioCinema": {
        "countries": ["India"],
        "url": "https://www.jiocinema.com",
        "paid": False,
        "free_trial": False,
        "sports": ["Cricket", "Football", "NBA", "Tennis"]
    },
    "Sony LIV": {
        "countries": ["India"],
        "url": "https://www.sonyliv.com",
        "paid": True,
        "free_trial": True
    },
    "Pluto TV": {
        "countries": ["USA", "UK", "Germany", "Italy", "Spain", "France", "Latin America"],
        "url": "https://pluto.tv",
        "paid": False,
        "free_trial": False
    },
    "Ryz Sports Network": {
        "countries": ["USA", "Global"],
        "url": "https://www.directv.com/insider/ryz-sports-network",
        "paid": False,
        "free_trial": False,
        "note": "Available on DIRECTV MyFree, 24/7 global sports"
    }
}

def fetch_all_leagues():
    """Fetch all available leagues from API-Football."""
    url = "https://api-football-v1.p.rapidapi.com/v3/leagues"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    try:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        return data.get("response", [])
    except Exception as e:
        print(f"Error fetching leagues: {e}")
        return []

def fetch_matches_by_league(league_id, season="2024"):
    """Fetch matches for a specific league."""
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {
        "league": league_id,
        "season": season,
        "status": "NS,LIVE,FT"  # Not Started, Live, Finished
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        return data.get("response", [])
    except Exception as e:
        print(f"Error fetching matches for league {league_id}: {e}")
        return []

def calculate_importance_score(league_name, match_data):
    """Calculate importance score for a match."""
    base_score = TOP_LEAGUES.get(league_name, {}).get("importance", 50)
    
    # Boost for derbies, cup finals, etc.
    match_info = match_data.get("fixture", {})
    league_info = match_data.get("league", {})
    
    # Check if it's a cup final
    if league_info.get("round") and "Final" in league_info.get("round", ""):
        base_score += 20
    
    # Check for derby (simplified - could be enhanced)
    home_team = match_data.get("teams", {}).get("home", {}).get("name", "")
    away_team = match_data.get("teams", {}).get("away", {}).get("name", "")
    
    # Famous derbies
    derbies = [
        ("Barcelona", "Real Madrid"),
        ("Manchester United", "Liverpool"),
        ("Arsenal", "Tottenham"),
        ("Milan", "Inter"),
        ("Roma", "Lazio"),
        ("Celtic", "Rangers"),
        ("Boca Juniors", "River Plate"),
        ("Al Ahly", "Zamalek"),
        ("Al Hilal", "Al Nassr"),
    ]
    
    for derby_home, derby_away in derbies:
        if (home_team == derby_home and away_team == derby_away) or \
           (home_team == derby_away and away_team == derby_home):
            base_score += 25
            break
    
    return min(base_score, 100)  # Cap at 100

def parse_match_with_enriched_data(item):
    """Enhanced parse function with all new fields."""
    fixture = item["fixture"]
    teams = item["teams"]
    league = item["league"]
    goals = item["goals"]
    status = fixture["status"]["short"]
    
    # Map status
    if status in ["FT", "AET", "PEN"]:
        status_cat = "FINISHED"
    elif status in ["LIVE", "1H", "2H", "HT", "ET"]:
        status_cat = "LIVE"
    else:
        status_cat = "UPCOMING"
    
    # Get minute for live matches
    minute = fixture.get("status", {}).get("elapsed")
    elapsed = minute
    
    # Calculate importance
    importance = calculate_importance_score(league["name"], item)
    
    # Determine if featured (top importance or custom rules)
    is_featured = importance >= 85
    
    # Get country from league info
    country = league.get("country", "")
    country_logo = league.get("flag", "")
    
    # Get broadcasters for this league
    broadcasters = []
    for broadcaster_name, broadcaster_info in GLOBAL_BROADCASTERS.items():
        # Check if broadcaster covers this league or country
        if league["name"] in broadcaster_info.get("leagues", []) or \
           country in broadcaster_info.get("countries", []):
            broadcasters.append({
                "name": broadcaster_name,
                "url": broadcaster_info["url"],
                "paid": broadcaster_info.get("paid", True),
                "free_trial": broadcaster_info.get("free_trial", False)
            })
    
    return {
        "fixture_id": fixture["id"],
        "league": league["name"],
        "league_id": league["id"],
        "league_logo": league.get("logo"),
        "country": country,
        "country_logo": country_logo,
        "home_team": teams["home"]["name"],
        "away_team": teams["away"]["name"],
        "home_logo": teams["home"].get("logo"),
        "away_logo": teams["away"].get("logo"),
        "match_time": fixture["date"],
        "status": status_cat,
        "minute": minute,
        "elapsed": elapsed,
        "home_score": goals["home"] if goals["home"] is not None else 0,
        "away_score": goals["away"] if goals["away"] is not None else 0,
        "streams": [],
        "broadcasters": broadcasters,
        "importance_score": importance,
        "is_featured": is_featured
    }

def search_global_streams(match):
    """Enhanced stream search across multiple sources."""
    streams = []
    
    # Search YouTube
    query = f"{match['home_team']} vs {match['away_team']} live stream"
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "eventType": "live",
        "maxResults": 5,
        "key": YOUTUBE_API_KEY
    }
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get("items"):
            for item in data["items"]:
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                channel = item["snippet"]["channelTitle"]
                verified = channel in VERIFIED_CHANNELS
                streams.append({
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel": channel,
                    "source": "youtube",
                    "verified": verified,
                    "auto_discovered": True
                })
    except Exception as e:
        print(f"YouTube search error: {e}")
    
    # Search for official broadcasters
    for broadcaster in match.get("broadcasters", []):
        if not broadcaster.get("paid", True) or broadcaster.get("free_trial", False):
            streams.append({
                "title": f"Watch on {broadcaster['name']}",
                "url": broadcaster['url'],
                "source": "broadcaster",
                "verified": True,
                "free": not broadcaster.get("paid", True),
                "free_trial": broadcaster.get("free_trial", False)
            })
    
    return streams

def update_all_matches():
    """Main function to update all matches from all leagues."""
    print(f"[{datetime.now()}] Running global match update...")
    
    # First, get all leagues
    leagues = fetch_all_leagues()
    print(f"Found {len(leagues)} leagues")
    
    # Process each league
    for league in leagues[:50]:  # Limit to 50 leagues per run to avoid rate limits
        league_id = league["league"]["id"]
        league_name = league["league"]["name"]
        
        print(f"Fetching matches for {league_name}...")
        matches = fetch_matches_by_league(league_id)
        
        for match in matches:
            match_data = parse_match_with_enriched_data(match)
            
            # Search for streams
            if match_data["status"] in ["LIVE", "UPCOMING"]:
                streams = search_global_streams(match_data)
                match_data["streams"] = json.dumps(streams)
            
            # Check for admin streams
            admin_streams = supabase.table("admin_streams")\
                .select("*")\
                .eq("fixture_id", match_data["fixture_id"])\
                .eq("is_active", True)\
                .execute()\
                .data
            
            if admin_streams:
                # Merge admin streams with auto-discovered ones
                existing_streams = json.loads(match_data["streams"]) if match_data["streams"] else []
                for admin in admin_streams:
                    existing_streams.append({
                        "title": admin.get("stream_title", "Official Stream"),
                        "url": admin["stream_url"],
                        "source": admin.get("stream_source", "admin"),
                        "verified": True,
                        "admin_added": True
                    })
                match_data["streams"] = json.dumps(existing_streams)
            
            # Update database
            supabase.table("matches").upsert(match_data, on_conflict="fixture_id").execute()
            print(f"Updated: {match_data['home_team']} vs {match_data['away_team']} ({match_data['status']})")
            time.sleep(0.5)  # Be gentle with API
        
        time.sleep(2)  # Pause between leagues
    
    # Clean up expired admin streams
    now = datetime.now().isoformat()
    supabase.table("admin_streams")\
        .update({"is_active": False})\
        .lt("expires_at", now)\
        .execute()
    
    print("Global update complete!")

def update_live():
    """Update only live matches (faster for real-time)."""
    print(f"[{datetime.now()}] Running live update...")
    
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {"live": "all"}
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        items = data.get("response", [])
        
        for item in items:
            match_data = parse_match_with_enriched_data(item)
            
            # Check for admin streams
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
            print(f"Updated live: {match_data['home_team']} vs {match_data['away_team']} - {match_data['home_score']}:{match_data['away_score']}")
            time.sleep(0.5)
            
    except Exception as e:
        print(f"Live update error: {e}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_all_matches()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
