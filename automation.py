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

# Verified YouTube channels (add more as you discover)
VERIFIED_CHANNELS = [
    "beIN SPORTS", "SSC", "ONTime Sports", "Dubai Sports",
    "Abu Dhabi Sports", "Alkass TV", "KSA SPORT"
]

# Broadcaster mapping (league name -> list of broadcasters with affiliate links)
BROADCASTER_MAP = {
    "Premier League": [
        {"name": "beIN Sports", "url": "https://affiliate-link.com/bein", "paid": True},
        {"name": "SSC", "url": "https://affiliate-link.com/ssc", "paid": True}
    ],
    "La Liga": [
        {"name": "beIN Sports", "url": "https://affiliate-link.com/bein", "paid": True}
    ],
    "Saudi Pro League": [
        {"name": "SSC", "url": "https://affiliate-link.com/ssc", "paid": True},
        {"name": "Shahid", "url": "https://affiliate-link.com/shahid", "paid": True}
    ],
    # Add more leagues...
}

def fetch_live_matches():
    """Fetch all currently live matches (one API call)."""
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {"live": "all"}
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    return data.get("response", [])

def fetch_todays_matches():
    """Fetch all matches for today."""
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    today = datetime.now().strftime("%Y-%m-%d")
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {"date": today}
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    return data.get("response", [])

def parse_match(item):
    """Convert API response item to our match dict."""
    fixture = item["fixture"]
    teams = item["teams"]
    league = item["league"]["name"]
    goals = item["goals"]
    status = fixture["status"]["short"]
    # Map status
    if status in ["FT", "AET", "PEN"]:
        status_cat = "FINISHED"
    elif status in ["LIVE", "1H", "2H", "HT", "ET"]:
        status_cat = "LIVE"
    else:
        status_cat = "UPCOMING"
    return {
        "fixture_id": fixture["id"],
        "league": league,
        "home_team": teams["home"]["name"],
        "away_team": teams["away"]["name"],
        "match_time": fixture["date"],
        "status": status_cat,
        "home_score": goals["home"] if goals["home"] is not None else 0,
        "away_score": goals["away"] if goals["away"] is not None else 0,
        "streams": [],
        "broadcasters": BROADCASTER_MAP.get(league, [])
    }

def search_youtube_streams(match):
    """Find live YouTube streams for a match."""
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
    resp = requests.get(url, params=params)
    data = resp.json()
    streams = []
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
                "verified": verified
            })
    return streams

def update_live():
    """Update only live matches."""
    print(f"[{datetime.now()}] Running live update...")
    items = fetch_live_matches()
    for item in items:
        match = parse_match(item)
        # Update only the live match (status and score)
        supabase.table("matches").upsert(match, on_conflict="fixture_id").execute()
        print(f"Updated live match: {match['home_team']} vs {match['away_team']} - {match['home_score']}:{match['away_score']}")
        time.sleep(0.5)

def update_full():
    """Full daily update: all matches + stream search."""
    print(f"[{datetime.now()}] Running full daily update...")
    items = fetch_todays_matches()
    for item in items:
        match = parse_match(item)
        # Search for streams (for upcoming/live matches)
        if match["status"] in ["LIVE", "UPCOMING"]:
            streams = search_youtube_streams(match)
            match["streams"] = json.dumps(streams)
        # Upsert
        supabase.table("matches").upsert(match, on_conflict="fixture_id").execute()
        print(f"Updated: {match['home_team']} vs {match['away_team']} ({match['status']})")
        time.sleep(1)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "live"
    if mode == "live":
        update_live()
    elif mode == "full":
        update_full()
    else:
        print("Unknown mode. Use 'live' or 'full'.")
