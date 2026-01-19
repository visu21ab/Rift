# YouTube Music Integration Guide

This guide explains how to integrate YouTube Music into your application, following the same pattern as your existing Spotify integration.

## Overview

**Important Note**: There is no official "YouTube Music API" - you'll use the **YouTube Data API v3**, which works with YouTube videos (including music videos). Music tracks on YouTube Music are typically video-based.

## What Data You Can Get from YouTube Data API v3

### 1. **Search for Music Videos**
- Search by keyword, artist name, track name
- Filter by video category, region, duration
- Get video metadata: title, description, thumbnails, duration, published date
- **API Endpoint**: `GET https://www.googleapis.com/youtube/v3/search`

### 2. **Video Details**
- Get detailed information about specific videos
- Access metadata: title, description, channel info, duration, view count, like count
- **API Endpoint**: `GET https://www.googleapis.com/youtube/v3/videos`

### 3. **Playlist Operations**
- **Create playlists**: `POST https://www.googleapis.com/youtube/v3/playlists`
- **List user's playlists**: `GET https://www.googleapis.com/youtube/v3/playlists`
- **Update playlists**: `PUT https://www.googleapis.com/youtube/v3/playlists`
- **Delete playlists**: `DELETE https://www.googleapis.com/youtube/v3/playlists`

### 4. **Playlist Items (Videos in Playlists)**
- **Add videos to playlist**: `POST https://www.googleapis.com/youtube/v3/playlistItems`
- **List playlist items**: `GET https://www.googleapis.com/youtube/v3/playlistItems`
- **Update playlist items** (reorder): `PUT https://www.googleapis.com/youtube/v3/playlistItems`
- **Delete playlist items**: `DELETE https://www.googleapis.com/youtube/v3/playlistItems`

### 5. **User Channel Information**
- Get user's channel ID (required for playlist creation)
- Get channel metadata: display name, subscriber count, etc.
- **API Endpoint**: `GET https://www.googleapis.com/youtube/v3/channels`

## OAuth 2.0 Setup & User Connection

### Step 1: Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable **YouTube Data API v3**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"

4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - `https://your-domain.com/youtube/callback` (production)
     - `http://127.0.0.1:5000/youtube/callback` (local development)
   - Save the **Client ID** and **Client Secret**

### Step 2: Required OAuth Scopes

You'll need these scopes for playlist creation:
- `https://www.googleapis.com/auth/youtube` (full access)
- OR `https://www.googleapis.com/auth/youtube.force-ssl` (recommended - same permissions but forces SSL)

### Step 3: OAuth Flow Implementation

The flow is similar to Spotify:

1. **Authorization URL** (redirect user here):
```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=YOUR_CLIENT_ID
  &redirect_uri=YOUR_REDIRECT_URI
  &response_type=code
  &scope=https://www.googleapis.com/auth/youtube.force-ssl
  &access_type=offline
  &prompt=consent
```

**Important**: Include `access_type=offline` and `prompt=consent` to get a refresh token.

2. **Exchange Code for Tokens**:
```python
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=AUTHORIZATION_CODE
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
&redirect_uri=YOUR_REDIRECT_URI
```

Response:
```json
{
  "access_token": "ya29.a0AfH6...",
  "expires_in": 3599,
  "refresh_token": "1//0g...",
  "scope": "https://www.googleapis.com/auth/youtube.force-ssl",
  "token_type": "Bearer"
}
```

3. **Refresh Token** (when access token expires):
```python
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=REFRESH_TOKEN
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
```

## Creating Playlists (Same Pattern as Spotify)

### Step 1: Get User's Channel ID

Before creating playlists, you need the user's channel ID:

```python
def get_youtube_channel_id(access_token):
    """Get the authenticated user's YouTube channel ID"""
    url = "https://www.googleapis.com/youtube/v3/channels"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "part": "id",
        "mine": "true"
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    items = response.json().get("items", [])
    if not items:
        raise Exception("User has no YouTube channel. They may need to create one.")
    
    return items[0]["id"]
```

### Step 2: Create a Playlist

```python
def create_youtube_playlist(channel_id, name, description, access_token, privacy_status="private"):
    """
    Create a playlist on YouTube.
    
    Args:
        channel_id: User's YouTube channel ID
        name: Playlist name
        description: Playlist description
        access_token: OAuth access token
        privacy_status: "private", "public", or "unlisted"
    
    Returns:
        Playlist ID
    """
    url = "https://www.googleapis.com/youtube/v3/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "snippet": {
            "title": name,
            "description": description
        },
        "status": {
            "privacyStatus": privacy_status  # "private", "public", or "unlisted"
        }
    }
    
    params = {"part": "snippet,status"}
    
    response = requests.post(url, headers=headers, params=params, json=body)
    response.raise_for_status()
    
    return response.json()["id"]
```

### Step 3: Search for Music Videos

```python
def search_youtube_music(track_name, artist_name, access_token, max_results=3):
    """
    Search YouTube for a music video by track and artist name.
    
    Returns:
        List of video results with id, title, channelTitle, etc.
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Search query: combine track and artist
    query = f"{track_name} {artist_name} music"
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoCategoryId": "10",  # Music category
        "maxResults": max_results,
        "order": "relevance"
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    results = []
    for item in response.json().get("items", []):
        results.append({
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "thumbnail": item["snippet"]["thumbnails"]["default"]["url"]
        })
    
    return results
```

### Step 4: Add Videos to Playlist

```python
def add_videos_to_youtube_playlist(playlist_id, video_ids, access_token):
    """
    Add videos to a YouTube playlist.
    
    Args:
        playlist_id: YouTube playlist ID
        video_ids: List of YouTube video IDs
        access_token: OAuth access token
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
        
        response = requests.post(url, headers=headers, params=params, json=body)
        response.raise_for_status()
```

## Implementation Checklist

To integrate YouTube Music following your Spotify pattern:

### Backend Changes (`app.py`)

1. **Add YouTube API credentials** (similar to Spotify):
   ```python
   YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
   YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
   YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "https://your-domain.com/youtube/callback")
   YOUTUBE_SCOPES = "https://www.googleapis.com/auth/youtube.force-ssl"
   ```

2. **Add YouTube fields to User model**:
   ```python
   youtube_channel_id = db.Column(db.String(255))
   youtube_display_name = db.Column(db.String(255))
   youtube_refresh_token = db.Column(db.Text)  # Store refresh token securely
   ```

3. **Create OAuth routes**:
   - `/youtube/connect` - Initiate OAuth flow
   - `/youtube/callback` - Handle OAuth callback
   - `refresh_youtube_token()` - Refresh access token

4. **Create helper functions**:
   - `get_youtube_channel_id(access_token)`
   - `search_youtube_music(track_name, artist_name, access_token)`
   - `create_youtube_playlist(channel_id, name, description, access_token)`
   - `add_videos_to_youtube_playlist(playlist_id, video_ids, access_token)`

5. **Update `/api/generate-playlist` endpoint**:
   - Add option to choose service (Spotify or YouTube Music)
   - Implement YouTube Music playlist creation flow

### Frontend Changes

1. **Update UI** to allow selecting music service (Spotify or YouTube Music)
2. **Add YouTube Music connect button** (similar to Spotify button)
3. **Update connection status display** to show both services

### Database Migration

You'll need to add the new YouTube columns to your User table:
```python
# Migration script or manual SQL
ALTER TABLE user ADD COLUMN youtube_channel_id VARCHAR(255);
ALTER TABLE user ADD COLUMN youtube_display_name VARCHAR(255);
ALTER TABLE user ADD COLUMN youtube_refresh_token TEXT;
```

## Key Differences from Spotify

1. **Video-based**: YouTube uses video IDs instead of track URIs
2. **Channel Required**: Users must have a YouTube channel (some accounts don't by default)
3. **Search Approach**: Search for videos instead of tracks - may need to filter for music videos
4. **Privacy Settings**: Playlists can be "private", "public", or "unlisted"
5. **Rate Limits**: YouTube API has daily quotas (default 10,000 units/day)

## Rate Limits & Quotas

- **Default Quota**: 10,000 units per day
- **Cost per operation**:
  - Search: 100 units
  - Create playlist: 50 units
  - Add playlist item: 50 units
  - Get channel: 1 unit
- **Quota increase**: Can request increase in Google Cloud Console

## Limitations

1. **No official YouTube Music API**: Using YouTube Data API v3 means working with videos, not pure audio tracks
2. **Search accuracy**: Music video search may not always find exact tracks
3. **Channel requirement**: Users without YouTube channels may need to create one first
4. **Video vs Audio**: Results are videos, not audio-only tracks

## Next Steps

1. Set up Google Cloud project and OAuth credentials
2. Add environment variables for YouTube credentials
3. Implement OAuth flow routes
4. Add YouTube helper functions
5. Update database schema
6. Modify playlist generation to support YouTube Music
7. Update frontend UI

Would you like me to implement any specific part of this integration?

