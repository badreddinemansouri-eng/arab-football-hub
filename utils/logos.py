import requests
from supabase import create_client
import streamlit as st
import hashlib
import unicodedata
import re
import functools
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

def normalize_name(name):
    """
    Convert accented characters to ASCII and remove punctuation.
    """
    if not name:
        return ""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s]', '', name)
    return name

def generate_name_variations(name):
    """
    Return a list of possible names to try when searching for a logo.
    """
    variations = set()
    original = name.strip()
    variations.add(original)
    variations.add(original.replace(' ', '_'))
    # Remove common suffixes (case-insensitive)
    suffixes = [" FC", " AFC", " United", " City", " Real", " CF", " AC", " AS", " SS", " SC", " Club", " Deportivo", " Futebol", " Clube"]
    base = original
    for suffix in suffixes:
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            variations.add(base)
            variations.add(base.replace(' ', '_'))
            break
    # Add normalized version
    norm = normalize_name(original)
    variations.add(norm)
    variations.add(norm.replace(' ', '_'))
    # Add slugified version (spaces to underscores, lower case)
    slug = re.sub(r'\s+', '_', original.lower())
    variations.add(slug)
    return list(variations)

def get_initials(name):
    words = name.split()
    if len(words) == 1:
        return words[0][:2].upper()
    else:
        return (words[0][0] + words[-1][0]).upper()
@functools.lru_cache(maxsize=500)
def get_team_logo(team_name):
    """
    Returns a team logo URL. Tries:
      1. Local database (team_logos table)
      2. TheSportsDB API with name variations
      3. Fallback to UI Avatars with team initials
    """
    # 1. Check database
    res = supabase.table("team_logos").select("logo_url").eq("team_name", team_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # 2. Try TheSportsDB API with multiple name variants
    variants = generate_name_variations(team_name)
    for variant in variants:
        try:
            url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={requests.utils.quote(variant)}"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("teams"):
                    logo = data["teams"][0].get("strTeamBadge")
                    if logo:
                        # Save to database
                        supabase.table("team_logos").upsert(
                            {"team_name": team_name, "logo_url": logo},
                            on_conflict="team_name"
                        ).execute()
                        return logo
        except:
            continue

    # 3. Fallback: UI Avatars with initials
    initials = get_initials(team_name)
    color = hashlib.md5(team_name.encode()).hexdigest()[:6]
    placeholder = f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=128&bold=true&length=2"
    # Optionally store fallback to avoid repeated lookups? We can store it, but it's not a real logo.
    # For consistency, we'll just return it.
    return placeholder
@functools.lru_cache(maxsize=500)
def get_league_logo(league_name):
    """
    Returns a league logo URL. Tries:
      1. Local database (league_logos table)
      2. TheSportsDB API (searchleagues.php) with name variations
      3. Fallback to UI Avatars with league initials
    """
    # 1. Check database
    res = supabase.table("league_logos").select("logo_url").eq("league_name", league_name).execute()
    if res.data:
        return res.data[0]["logo_url"]

    # 2. Try TheSportsDB API with name variations
    variants = generate_name_variations(league_name)
    for variant in variants:
        try:
            url = f"https://www.thesportsdb.com/api/v1/json/3/searchleagues.php?l={requests.utils.quote(variant)}"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("leagues"):
                    logo = data["leagues"][0].get("strBadge")
                    if logo:
                        supabase.table("league_logos").upsert(
                            {"league_name": league_name, "logo_url": logo},
                            on_conflict="league_name"
                        ).execute()
                        return logo
        except:
            continue

    # 3. Fallback: UI Avatars with initials
    initials = get_initials(league_name)
    color = hashlib.md5(league_name.encode()).hexdigest()[:6]
    placeholder = f"https://ui-avatars.com/api/?name={initials}&background={color}&color=fff&size=128&bold=true&length=2"
    return placeholder
