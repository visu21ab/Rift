"""
YouTube Music Integration Code Examples
These functions follow the same pattern as your Spotify integration in app.py
"""

import requests
import os
from flask import session

# YouTube API Configuration (add to app.py)
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "https://your-domain.com/youtube/callback")
YOUTUBE_SCOPES = "https://www.googleapis.com/auth/youtube.force-ssl"

# Use the same session setup as Spotify
# youtube_session = requests.Session()
# youtube_session.mount("https://", adapter)  # Use same adapter as Spotify


def refresh_youtube_token():
    """
    Refresh YouTube access token using refresh token.
    Similar to refresh_spotify_token() in your app.py
    """
    refresh_token = session.get('youtube_refresh_token')
    if not refresh_token:
        # Check if stored in database
        if hasattr(g, 'user') and g.user.youtube_refresh_token:
            refresh_token = g.user.youtube_refresh_token
        else:
            session.pop('youtube_access_token', None)
            return None
    
    token_url = "https://oauth2.googleapis.com/token"
    resp = requests.post(token_url, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET
    }, timeout=10)  # Use REQUEST_TIMEOUT constant
    
    if resp.status_code != 200:
        # Refresh token is invalid, clear session
        session.pop('youtube_access_token', None)
        session.pop('youtube_refresh_token', None)
        if hasattr(g, 'user'):
            g.user.youtube_refresh_token = None
            db.session.commit()
        return None
    
    tokens = resp.json()
    session['youtube_access_token'] = tokens['access_token']
    # YouTube doesn't return a new refresh token on refresh, keep the old one
    
    return tokens['access_token']


def get_valid_youtube_access_token():
    """
    Get a valid YouTube access token, refreshing if necessary.
    Similar to get_valid_access_token() for Spotify
    """
    access_token = session.get('youtube_access_token')
    
    if not access_token:
        # Try to refresh
        access_token = refresh_youtube_token()
        if not access_token:
            return None
    
    # Token is valid (you might want to check expiry, but YouTube tokens last 1 hour)
    return access_token


def get_youtube_channel_id(access_token):
    """
    Get the authenticated user's YouTube channel ID.
    Required before creating playlists.
    """
    url = "https://www.googleapis.com/youtube/v3/channels"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "part": "id,snippet",
        "mine": "true"
    }
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.exceptions.Timeout:
        raise Exception("YouTube API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to YouTube API: {str(e)}")
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_youtube_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
            except requests.exceptions.Timeout:
                raise Exception("YouTube API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to YouTube API: {str(e)}")
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    data = r.json()
    
    items = data.get("items", [])
    if not items:
        raise Exception("User has no YouTube channel. Please create a YouTube channel first.")
    
    channel_info = items[0]
    return channel_info["id"], channel_info["snippet"]["title"]


def search_youtube_music(track_name, artist_name, access_token):
    """
    Search YouTube for a music video by name and artist.
    Similar to search_spotify_track() in your app.py
    
    Returns:
        List of video results with id, title, etc., or None if not found
    """
    # Search query: combine track and artist
    query = f"{track_name} {artist_name}"
    url = "https://www.googleapis.com/youtube/v3/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoCategoryId": "10",  # Music category
        "maxResults": 3,
        "order": "relevance"
    }
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.exceptions.Timeout:
        raise Exception("YouTube API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to YouTube API: {str(e)}")
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_youtube_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
            except requests.exceptions.Timeout:
                raise Exception("YouTube API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to YouTube API: {str(e)}")
        else:
            raise Exception("YouTube authentication expired. Please reconnect your account.")
    
    r.raise_for_status()
    data = r.json()
    
    items = data.get("items", [])
    if not items:
        return None
    
    # Return first result (best match)
    video = items[0]
    return {
        "video_id": video["id"]["videoId"],
        "title": video["snippet"]["title"],
        "channel": video["snippet"]["channelTitle"],
        "thumbnail": video["snippet"]["thumbnails"]["default"]["url"]
    }


def create_youtube_playlist(channel_id, name, description, access_token, privacy_status="private"):
    """
    Create a private playlist on YouTube.
    Similar to create_spotify_playlist() in your app.py
    
    Returns:
        Playlist ID
    """
    url = "https://www.googleapis.com/youtube/v3/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    params = {"part": "snippet,status"}
    body = {
        "snippet": {
            "title": name,
            "description": description
        },
        "status": {
            "privacyStatus": privacy_status  # "private", "public", or "unlisted"
        }
    }
    
    try:
        r = requests.post(url, headers=headers, params=params, json=body, timeout=10)
    except requests.exceptions.Timeout:
        raise Exception("YouTube API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to YouTube API: {str(e)}")
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_youtube_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"}
            try:
                r = requests.post(url, headers=headers, params=params, json=body, timeout=10)
            except requests.exceptions.Timeout:
                raise Exception("YouTube API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to YouTube API: {str(e)}")
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    return r.json()["id"]


def add_videos_to_youtube_playlist(playlist_id, video_ids, access_token):
    """
    Add a list of video IDs to a YouTube playlist.
    Similar to add_tracks_to_playlist() in your app.py
    
    Note: YouTube API allows adding videos one at a time or in batches.
    For simplicity, this adds them one by one.
    """
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    params = {"part": "snippet"}
    
    for video_id in video_ids:
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
        
        try:
            r = requests.post(url, headers=headers, params=params, json=body, timeout=10)
        except requests.exceptions.Timeout:
            raise Exception("YouTube API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to YouTube API: {str(e)}")
        
        # If token expired, refresh and retry
        if r.status_code == 401:
            new_token = refresh_youtube_token()
            if new_token:
                headers = {"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"}
                try:
                    r = requests.post(url, headers=headers, params=params, json=body, timeout=10)
                except requests.exceptions.Timeout:
                    raise Exception("YouTube API request timed out. Please try again.")
                except requests.exceptions.RequestException as e:
                    raise Exception(f"Error connecting to YouTube API: {str(e)}")
            else:
                r.raise_for_status()
        
        r.raise_for_status()


# Example Flask routes (add to app.py):

"""
@app.route('/youtube/connect')
@login_required
def youtube_connect():
    \"\"\"Initiate YouTube OAuth flow\"\"\"
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": YOUTUBE_CLIENT_ID,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPES,
        "access_type": "offline",  # Required to get refresh token
        "prompt": "consent"  # Force consent screen to get refresh token
    })
    return redirect(auth_url)


@app.route('/youtube/callback')
@login_required
def youtube_callback():
    \"\"\"Handle YouTube OAuth callback\"\"\"
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index', error='youtube_access_denied'))
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    resp = requests.post(token_url, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET
    }, timeout=10)
    
    if resp.status_code != 200:
        return redirect(url_for('index', error='youtube_token_exchange_failed'))
    
    tokens = resp.json()
    session['youtube_access_token'] = tokens['access_token']
    session['youtube_refresh_token'] = tokens.get('refresh_token')
    
    # Get user's channel info
    try:
        channel_id, channel_title = get_youtube_channel_id(tokens['access_token'])
        session['youtube_channel_id'] = channel_id
        session['youtube_display_name'] = channel_title
        
        # Store in database
        g.user.youtube_channel_id = channel_id
        g.user.youtube_display_name = channel_title
        g.user.youtube_refresh_token = tokens.get('refresh_token')
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error getting YouTube channel: {str(e)}")
        return redirect(url_for('index', error='youtube_channel_error'))
    
    return redirect(url_for('index'))
"""


# Example usage in generate_playlist endpoint:
"""
# In your /api/generate-playlist route, add YouTube Music support:

service = data.get('service', 'spotify')  # 'spotify' or 'youtube'

if service == 'youtube':
    access_token = get_valid_youtube_access_token()
    if not access_token:
        return jsonify({'error': 'YouTube not connected. Please connect your YouTube account.'}), 401
    
    # Get channel ID
    channel_id = session.get('youtube_channel_id')
    if not channel_id:
        channel_id, _ = get_youtube_channel_id(access_token)
        session['youtube_channel_id'] = channel_id
    
    # Search for videos (similar to Spotify track search)
    video_ids = []
    found_tracks = []
    not_found = []
    
    for track_info in gpt_tracks:
        track_name = track_info['track']
        artist_name = track_info['artist']
        
        video_result = search_youtube_music(track_name, artist_name, access_token)
        if video_result:
            video_ids.append(video_result['video_id'])
            found_tracks.append({
                "artist": artist_name,
                "track": track_name,
                "video_id": video_result['video_id'],
                "title": video_result['title'],
                "url": f"https://www.youtube.com/watch?v={video_result['video_id']}"
            })
        else:
            not_found.append({"artist": artist_name, "track": track_name})
    
    if not video_ids:
        return jsonify({'error': 'No videos found on YouTube'}), 400
    
    # Create playlist
    playlist_id = create_youtube_playlist(
        channel_id,
        playlist_name,
        "AI-generated playlist",
        access_token
    )
    
    # Add videos to playlist
    add_videos_to_youtube_playlist(playlist_id, video_ids, access_token)
    
    return jsonify({
        'success': True,
        'playlist_id': playlist_id,
        'playlist_name': playlist_name,
        'tracks_found': len(found_tracks),
        'tracks_not_found': len(not_found),
        'tracks': found_tracks,
        'not_found': not_found,
        'youtube_url': f"https://www.youtube.com/playlist?list={playlist_id}"
    })
"""

