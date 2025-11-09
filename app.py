from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import requests
import json
import os
import urllib.parse
from dotenv import load_dotenv
from openai import OpenAI
from collections import Counter
import math
import ast
from functools import wraps

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Spotify API credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/callback")
SCOPES = "playlist-modify-private playlist-modify-public user-read-private"

# OpenAI setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL_PROMPT_TEMPLATE = """
You are a music curator whose task is to suggest songs and artists based only on the user's full mood description.

Rules:
1. Prioritize the user's full description.
2. Ignore popularity or mainstream success — small, indie, or lesser-known artists are extremely preferred.
3. Provide a mix of different artists that match the description.
4. Provide exactly {track_count} distinct tracks unless the user explicitly asks for fewer.
5. Return a Python dictionary (not JSON) with this structure:
   {{"tracks": [{{"artist": "Artist Name", "track": "Track Name"}}, ...]}}
"""


def refresh_spotify_token():
    """Refresh Spotify access token using refresh token"""
    refresh_token = session.get('spotify_refresh_token')
    if not refresh_token:
        # Clear invalid session
        session.pop('spotify_access_token', None)
        return None
    
    token_url = "https://accounts.spotify.com/api/token"
    resp = requests.post(token_url, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    
    if resp.status_code != 200:
        # Refresh token is invalid, clear session
        session.pop('spotify_access_token', None)
        session.pop('spotify_refresh_token', None)
        return None
    
    tokens = resp.json()
    session['spotify_access_token'] = tokens['access_token']
    # Spotify may return a new refresh token, or keep the old one
    if 'refresh_token' in tokens:
        session['spotify_refresh_token'] = tokens['refresh_token']
    
    return tokens['access_token']


def get_valid_access_token():
    """Get a valid access token, refreshing if necessary"""
    access_token = session.get('spotify_access_token')
    if not access_token:
        return None
    
    # Try to use the token - if it fails with 401, refresh it
    # For now, we'll refresh on 401 errors in the API calls
    return access_token


def require_spotify_auth(f):
    """Decorator to require Spotify authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'spotify_access_token' not in session:
            return jsonify({'error': 'Not authenticated with Spotify'}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/login')
def login():
    """Initiate Spotify OAuth flow"""
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "show_dialog": "true"
    })
    return redirect(auth_url)


@app.route('/callback')
def callback():
    """Handle Spotify OAuth callback"""
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index', error='access_denied'))
    
    # Exchange code for tokens
    token_url = "https://accounts.spotify.com/api/token"
    resp = requests.post(token_url, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    
    if resp.status_code != 200:
        return redirect(url_for('index', error='token_exchange_failed'))
    
    tokens = resp.json()
    session['spotify_access_token'] = tokens['access_token']
    session['spotify_refresh_token'] = tokens.get('refresh_token')
    
    # Get user info
    headers = {"Authorization": f"Bearer {session['spotify_access_token']}"}
    r = requests.get("https://api.spotify.com/v1/me", headers=headers)
    if r.status_code == 200:
        me = r.json()
        session['spotify_user_id'] = me.get('id')
        session['spotify_display_name'] = me.get('display_name')
    
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    """Logout user and clear session"""
    session.clear()
    return redirect(url_for('index'))


@app.route('/api/auth-status')
def auth_status():
    """Check if user is authenticated"""
    return jsonify({
        'authenticated': 'spotify_access_token' in session,
        'user_id': session.get('spotify_user_id'),
        'display_name': session.get('spotify_display_name')
    })


@app.route('/api/generate-playlist', methods=['POST'])
@require_spotify_auth
def generate_playlist():
    """Generate playlist from mood description"""
    data = request.json
    mood = data.get('mood', '').strip()
    playlist_name = data.get('playlist_name', 'AI Generated Playlist').strip()
    track_count = data.get('track_count', 25)
    
    try:
        track_count = int(track_count)
    except (ValueError, TypeError):
        track_count = 25
    
    track_count = max(1, min(50, track_count))
    
    if not mood:
        return jsonify({'error': 'Mood description is required'}), 400
    
    try:
        # Step 1: Get tracks from GPT
        results_dict = get_tracks_from_gpt(mood, track_count)
        tracks_from_gpt = results_dict.get("tracks", [])
        if not isinstance(tracks_from_gpt, list):
            raise ValueError("Unexpected response format from curator model.")
        tracks_from_gpt = tracks_from_gpt[:track_count]
        
        if not tracks_from_gpt:
            return jsonify({'error': 'No tracks returned from curator model'}), 400
        
        # Step 2: Search Spotify for tracks
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({'error': 'Not authenticated with Spotify'}), 401
        
        track_uris = []
        artist_ids = []
        found_tracks = []
        not_found = []
        
        for t in tracks_from_gpt:
            track_name = t["track"]
            artist_name = t["artist"]
            # Get fresh token in case it was refreshed
            access_token = session.get('spotify_access_token')
            matches = search_spotify_track(track_name, artist_name, access_token)
            
            if matches:
                track_uris.append(matches[0]["uri"])
                # Get artist ID from search results
                if "artist_id" in matches[0]:
                    artist_ids.append(matches[0]["artist_id"])
                found_tracks.append({
                    "artist": matches[0]["artist"],
                    "track": matches[0]["name"],
                    "uri": matches[0]["uri"]
                })
            else:
                not_found.append({"artist": artist_name, "track": track_name})
        
        if not track_uris:
            return jsonify({'error': 'No tracks found on Spotify'}), 400
        
        # Step 3: Create playlist
        user_id = session['spotify_user_id']
        # Get fresh token in case it was refreshed
        access_token = session.get('spotify_access_token')
        playlist_id = create_spotify_playlist(
            user_id, 
            playlist_name, 
            f"Generated from mood: {mood}",
            access_token
        )
        
        # Step 4: Add tracks to playlist
        # Get fresh token in case it was refreshed
        access_token = session.get('spotify_access_token')
        add_tracks_to_playlist(playlist_id, track_uris, access_token)
        
        # Step 5: Calculate metrics
        # Get fresh token in case it was refreshed
        access_token = session.get('spotify_access_token')
        indie_pct = indie_fraction(track_uris, access_token, threshold=50)
        diversity_score, genre_counts = genre_diversity(artist_ids, access_token)
        
        return jsonify({
            'success': True,
            'playlist_id': playlist_id,
            'playlist_name': playlist_name,
            'tracks_found': len(found_tracks),
            'tracks_not_found': len(not_found),
            'tracks': found_tracks,
            'not_found': not_found,
            'metrics': {
                'indie_fraction': round(indie_pct * 100, 1),
                'diversity_score': round(diversity_score, 2),
                'genre_counts': dict(genre_counts)
            },
            'requested_track_count': track_count,
            'spotify_url': f"https://open.spotify.com/playlist/{playlist_id}"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Helper functions from notebook
def get_tracks_from_gpt(user_prompt: str, track_count: int):
    """Ask GPT for tracks and return them directly as a Python dictionary."""
    system_prompt = MODEL_PROMPT_TEMPLATE.format(track_count=track_count)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=600
    )
    
    text = response.choices[0].message.content.strip()
    
    try:
        data = ast.literal_eval(text)
        return data
    except Exception as e:
        print("Could not parse GPT response as Python dict.")
        print(text)
        raise e


def search_spotify_track(track_name, artist_name, access_token):
    """Search Spotify for a track by name and artist."""
    q = f"track:{track_name} artist:{artist_name}"
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": q, "type": "track", "limit": 3}
    
    r = requests.get(url, headers=headers, params=params)
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            r = requests.get(url, headers=headers, params=params)
        else:
            raise Exception("Spotify authentication expired. Please reconnect your account.")
    
    r.raise_for_status()
    
    items = r.json().get("tracks", {}).get("items", [])
    results = []
    
    for item in items:
        results.append({
            "name": item["name"],
            "artist": item["artists"][0]["name"],
            "artist_id": item["artists"][0]["id"],
            "uri": item["uri"],
            "id": item["id"]
        })
    
    return results


def create_spotify_playlist(user_id, name, description, access_token):
    """Create a private playlist on Spotify."""
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "name": name,
        "description": description,
        "public": False
    }
    r = requests.post(url, headers=headers, json=body)
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"}
            r = requests.post(url, headers=headers, json=body)
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    return r.json()["id"]


def add_tracks_to_playlist(playlist_id, track_uris, access_token):
    """Add a list of track URIs to a Spotify playlist."""
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    chunk_size = 100
    for i in range(0, len(track_uris), chunk_size):
        chunk = track_uris[i:i+chunk_size]
        r = requests.post(url, headers=headers, json={"uris": chunk})
        
        # If token expired, refresh and retry
        if r.status_code == 401:
            new_token = refresh_spotify_token()
            if new_token:
                headers = {"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"}
                r = requests.post(url, headers=headers, json={"uris": chunk})
            else:
                r.raise_for_status()
        
        r.raise_for_status()


def get_spotify_track(track_id, access_token):
    """Fetch track info from Spotify."""
    url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers)
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            r = requests.get(url, headers=headers)
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    return r.json()


def get_spotify_artist(artist_id, access_token):
    """Fetch artist info from Spotify."""
    url = f"https://api.spotify.com/v1/artists/{artist_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers)
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            r = requests.get(url, headers=headers)
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    return r.json()


def indie_fraction(track_uris, access_token, threshold=50):
    """Calculate fraction of indie tracks (popularity < threshold)."""
    if not track_uris:
        return 0
    
    count_indie = 0
    total = 0
    
    for uri in track_uris:
        track_id = uri.split(":")[-1]
        track_data = get_spotify_track(track_id, access_token)
        popularity = track_data.get("popularity", 0)
        total += 1
        if popularity < threshold:
            count_indie += 1
    
    return count_indie / total if total > 0 else 0.0


def genre_diversity(artist_ids, access_token):
    """Calculate genre diversity score."""
    if not artist_ids:
        return 0.0, {}
    
    all_genres = []
    
    for artist_id in artist_ids:
        artist_data = get_spotify_artist(artist_id, access_token)
        genres = artist_data.get("genres", [])
        all_genres.extend(genres)
    
    genre_counts = Counter(all_genres)
    
    total_genres = len(all_genres)
    if total_genres == 0:
        return 0.0, genre_counts
    
    entropy = 0.0
    for count in genre_counts.values():
        p = count / total_genres
        if p > 0:
            entropy -= p * math.log(p)
    
    max_entropy = math.log(len(genre_counts)) if len(genre_counts) > 0 else 1
    diversity_score = entropy / max_entropy if max_entropy > 0 else 0.0
    
    return diversity_score, genre_counts


if __name__ == '__main__':
    app.run(debug=True, port=5000)

