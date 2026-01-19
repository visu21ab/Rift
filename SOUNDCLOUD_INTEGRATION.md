# SoundCloud Integration Guide

This guide explains how SoundCloud integration works in your application, following the same pattern as your existing Spotify integration.

## Overview

SoundCloud integration allows users to search for tracks, create playlists, and access metadata from SoundCloud's vast catalog of music. The integration uses SoundCloud's REST API with OAuth 2.1 authentication (PKCE required).

## Important Note: API Access

**⚠️ Critical**: SoundCloud has **paused issuing new API keys** for many third-party developers. To use this integration, you'll need:

1. **Existing API credentials** - If you already have SoundCloud API access
2. **Partnership application** - Apply through SoundCloud's developer portal or support
3. **Wait for reopening** - Monitor SoundCloud's developer announcements for when new registrations resume

Check the [SoundCloud API GitHub repository](https://github.com/soundcloud/api) for the latest status on API access.

## What Metadata You Can Get from SoundCloud API

### 1. **Track Metadata**

When searching or fetching tracks, you can access:

**⚠️ Note on BPM**: The `bpm` field is available but **optional and often `null`**. Many tracks, especially user uploads, don't have BPM data. Always check for `null` before using BPM values.

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique track ID | `123456789` |
| `title` | Track title | `"Midnight City"` |
| `duration` | Duration in milliseconds | `245000` |
| `description` | Track description | `"A beautiful ambient track..."` |
| `permalink_url` | Direct link to track | `"https://soundcloud.com/artist/track"` |
| `artwork_url` | Cover art image URL | `"https://i1.sndcdn.com/artworks-..."` |
| `genre` | Track genre | `"Electronic"` |
| `tags` | Array of tags | `["ambient", "electronic", "chill"]` |
| `created_at` | Upload timestamp | `"2023-01-15T10:30:00Z"` |
| `release_date` | Release date | `"2023-01-15"` |
| `isrc` | ISRC code (if available) | `"USRC12345678"` |
| `metadata_artist` | Official artist name | `"M83"` |
| `user` | Uploader/user object | `{id, username, avatar_url, ...}` |
| `playback_count` | Number of plays | `125000` |
| `likes_count` | Number of likes | `5000` |
| `comment_count` | Number of comments | `250` |
| `downloadable` | Whether track can be downloaded | `true/false` |
| `streamable` | Whether track can be streamed | `true/false` |
| `access` | Access level | `"playable"`, `"preview"`, or `"blocked"` |
| `bpm` | **Beats per minute** (optional, often null) | `128` or `null` |
| `key_signature` | Musical key (optional) | `"C major"` or `null` |

### 2. **Artist/User Metadata**

From track objects or user endpoints:

| Field | Description |
|-------|-------------|
| `id` | User/artist ID |
| `username` | SoundCloud username |
| `full_name` | Display name |
| `avatar_url` | Profile picture URL |
| `permalink_url` | Profile URL |
| `followers_count` | Number of followers |
| `followings_count` | Number of users following |
| `track_count` | Number of tracks uploaded |
| `playlist_count` | Number of playlists |

### 3. **Playlist/Set Metadata**

| Field | Description |
|-------|-------------|
| `id` | Playlist ID |
| `title` | Playlist name |
| `description` | Playlist description |
| `artwork_url` | Cover art URL |
| `permalink_url` | Playlist URL |
| `tracks` | Array of track objects |
| `track_count` | Number of tracks |
| `created_at` | Creation timestamp |
| `sharing` | Privacy setting (`"private"`, `"public"`) |

### 4. **Search Capabilities**

SoundCloud supports searching across:
- **Tracks**: By title, artist, genre, tags
- **Users**: By username or display name
- **Playlists**: By title or creator

Search parameters:
- `q`: Search query string
- `limit`: Results per page (default 10, max varies)
- `linked_partitioning`: Enable pagination
- `filter`: Filter by duration, license, etc.

## OAuth 2.1 Setup & Authentication

### Step 1: SoundCloud Developer Portal Setup

1. **Check API Access Status**: Visit [SoundCloud Developers](https://developers.soundcloud.com/)
2. **Apply for Access**: If new registrations are open, create an app
3. **Get Credentials**: Obtain `CLIENT_ID` and `CLIENT_SECRET`
4. **Set Redirect URI**: Configure your callback URL:
   - Production: `https://your-domain.com/soundcloud/callback`
   - Development: `http://127.0.0.1:5000/soundcloud/callback`

### Step 2: OAuth 2.1 with PKCE (Required)

SoundCloud requires **OAuth 2.1** with **PKCE** (Proof Key for Code Exchange) as of April 2024. This is implemented in the integration:

1. **Generate PKCE Pair**: Code verifier and code challenge
2. **Authorization URL**: Redirect user with code challenge
3. **Exchange Code**: Use code verifier to exchange authorization code for tokens
4. **Token Refresh**: Use refresh token to get new access tokens

### Step 3: Required Scopes

- `non-expiring`: Access token doesn't expire (if available)
- Default scopes provide access to user's playlists and tracks

## API Endpoints Used

### Search Tracks
```
GET https://api.soundcloud.com/tracks
Authorization: Bearer {access_token}
Parameters:
  - q: Search query
  - limit: Results per page
  - linked_partitioning: Enable pagination
```

### Get Track Details
```
GET https://api.soundcloud.com/tracks/{track_id}
Authorization: Bearer {access_token}
```

### Create Playlist
```
POST https://api.soundcloud.com/playlists
Authorization: Bearer {access_token}
Content-Type: application/json

Body:
{
  "playlist": {
    "title": "Playlist Name",
    "description": "Description",
    "sharing": "private"
  }
}
```

### Update Playlist (Add Tracks)
```
PUT https://api.soundcloud.com/playlists/{playlist_id}
Authorization: Bearer {access_token}
Content-Type: application/json

Body:
{
  "playlist": {
    "tracks": [
      {"id": 123456},
      {"id": 789012}
    ]
  }
}
```

### Get User Info
```
GET https://api.soundcloud.com/me
Authorization: Bearer {access_token}
```

## Implementation Details

### Backend Functions (`app.py`)

The integration includes these key functions:

1. **`generate_pkce_pair()`**: Generates PKCE code verifier and challenge
2. **`refresh_soundcloud_token()`**: Refreshes expired access tokens
3. **`get_valid_soundcloud_token()`**: Gets valid token, refreshing if needed
4. **`search_soundcloud_track()`**: Searches for tracks by name and artist
5. **`create_soundcloud_playlist()`**: Creates a new playlist
6. **`add_tracks_to_soundcloud_playlist()`**: Adds tracks to playlist
7. **`get_soundcloud_track_metadata()`**: Fetches detailed track info

### Routes

- `/soundcloud/connect`: Initiates OAuth flow
- `/soundcloud/callback`: Handles OAuth callback
- `/api/generate-playlist`: Supports `service: "soundcloud"` parameter

### Database Schema

Added to `User` model:
- `soundcloud_user_id`: SoundCloud user ID
- `soundcloud_username`: SoundCloud username

Added to `PlaylistUsage` model:
- `soundcloud_playlist_id`: SoundCloud playlist ID

## Environment Variables

Add these to your `.env` file:

```bash
# SoundCloud API Credentials
SOUNDCLOUD_CLIENT_ID=your_client_id_here
SOUNDCLOUD_CLIENT_SECRET=your_client_secret_here
SOUNDCLOUD_REDIRECT_URI=https://your-domain.com/soundcloud/callback
```

## Usage Example

### Frontend (JavaScript)

```javascript
// Connect SoundCloud
window.location.href = '/soundcloud/connect';

// Generate playlist with SoundCloud
const response = await fetch('/api/generate-playlist', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mood: 'late night ambient electronic',
    playlist_name: 'Chill Vibes',
    track_count: 25,
    service: 'soundcloud'  // Specify SoundCloud
  })
});
```

### Backend (Python)

```python
# Search for a track
matches = search_soundcloud_track(
    track_name="Midnight City",
    artist_name="M83",
    access_token=access_token
)

# Create playlist
playlist_id = create_soundcloud_playlist(
    user_id=user_id,
    name="My Playlist",
    description="AI-generated playlist",
    access_token=access_token
)

# Add tracks
add_tracks_to_soundcloud_playlist(
    playlist_id=playlist_id,
    track_ids=[123456, 789012],
    access_token=access_token
)
```

## Key Differences from Spotify

1. **OAuth 2.1 with PKCE**: Required, more secure than Spotify's OAuth 2.0
2. **Track IDs vs URIs**: SoundCloud uses numeric IDs, not URIs like Spotify
3. **Playlist Updates**: SoundCloud uses PUT to update entire playlist, not POST to add items
4. **Metadata Structure**: Different field names (`title` vs `name`, `permalink_url` vs `uri`)
5. **Access Levels**: Tracks can be `playable`, `preview`, or `blocked` based on subscription
6. **No Batch Endpoints**: SoundCloud doesn't have batch track/artist endpoints like Spotify

## Limitations & Considerations

1. **API Access**: New API keys may not be available
2. **Rate Limits**: SoundCloud has rate limits (check current limits)
3. **High-Tier Content**: Some tracks may be restricted (`access: "blocked"`)
4. **Search Accuracy**: Search may return different results than Spotify
5. **No Analytics**: SoundCloud doesn't provide popularity scores like Spotify
6. **Playlist Updates**: Must replace entire track list, not append

## High-Tier Content Handling

SoundCloud has "Go+" content that may have restrictions:
- `playable`: Full access (user has subscription or track is free)
- `preview`: 30-second preview only
- `blocked`: No playback available

The integration handles these cases gracefully, showing metadata even if playback is restricted.

## Error Handling

Common errors and handling:

- **401 Unauthorized**: Token expired → Refresh token automatically
- **403 Forbidden**: Invalid permissions → Clear session, require reconnection
- **404 Not Found**: Track/playlist doesn't exist → Skip and continue
- **429 Too Many Requests**: Rate limit exceeded → Retry with backoff

## Testing

1. **Test OAuth Flow**: Connect/disconnect SoundCloud account
2. **Test Search**: Search for various tracks and artists
3. **Test Playlist Creation**: Create playlists with different track counts
4. **Test Error Cases**: Expired tokens, invalid tracks, rate limits

## Next Steps

1. **Obtain API Credentials**: Get SoundCloud API access (if available)
2. **Set Environment Variables**: Add credentials to `.env`
3. **Test OAuth Flow**: Connect a test SoundCloud account
4. **Update Frontend**: Add SoundCloud connection button and service selector
5. **Test Playlist Generation**: Generate playlists via SoundCloud
6. **Handle Edge Cases**: Test with restricted content, missing tracks, etc.

## Resources

- [SoundCloud API Documentation](https://developers.soundcloud.com/docs/api/introduction)
- [SoundCloud API GitHub](https://github.com/soundcloud/api)
- [OAuth 2.1 Migration Guide](https://developers.soundcloud.com/blog/oauth-migration)
- [Artist Metadata Blog](https://developers.soundcloud.com/blog/api-artist-metadata)
- [High-Tier Content Guide](https://developers.soundcloud.com/blog/high-tier-content-in-the-soundcloud-api)

## Support

If you encounter issues:
1. Check SoundCloud API status
2. Verify API credentials are valid
3. Review OAuth flow implementation
4. Check rate limits and quotas
5. Consult SoundCloud developer documentation

