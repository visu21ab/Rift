# SoundCloud Integration Setup Guide

## Quick Start

### 1. Environment Variables

Add these to your `.env` file:

```bash
SOUNDCLOUD_CLIENT_ID=your_client_id_here
SOUNDCLOUD_CLIENT_SECRET=your_client_secret_here
SOUNDCLOUD_REDIRECT_URI=https://your-domain.com/soundcloud/callback
```

**Note**: SoundCloud has paused issuing new API keys. You'll need existing credentials or apply for partnership access.

### 2. Database Migration

The integration adds new columns to your database. Run these migrations:

```sql
-- Add SoundCloud fields to User table
ALTER TABLE user ADD COLUMN soundcloud_user_id TEXT;
ALTER TABLE user ADD COLUMN soundcloud_username VARCHAR(255);

-- Add SoundCloud playlist ID to PlaylistUsage table
ALTER TABLE playlist_usage ADD COLUMN soundcloud_playlist_id VARCHAR(255);
```

Or if using Flask-Migrate:

```bash
flask db migrate -m "Add SoundCloud integration fields"
flask db upgrade
```

### 3. Test the Integration

1. **Connect SoundCloud**: Visit `/soundcloud/connect` while logged in
2. **Generate Playlist**: Use the API with `service: "soundcloud"`:

```javascript
fetch('/api/generate-playlist', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mood: 'your mood description',
    playlist_name: 'My Playlist',
    track_count: 25,
    service: 'soundcloud'
  })
});
```

## What's Been Implemented

✅ **OAuth 2.1 with PKCE** - Secure authentication flow
✅ **Track Search** - Search SoundCloud tracks by artist and title
✅ **Playlist Creation** - Create private playlists on SoundCloud
✅ **Track Addition** - Add tracks to playlists
✅ **Token Refresh** - Automatic token refresh handling
✅ **Database Schema** - User and playlist fields added
✅ **API Integration** - Full SoundCloud API integration

## Available Metadata

The integration can access:

- **Track Info**: Title, artist, duration, genre, tags, artwork, description
- **User Info**: Username, display name, avatar, follower counts
- **Playlist Info**: Title, description, track count, artwork, privacy settings
- **Search**: Search tracks, users, and playlists

See `SOUNDCLOUD_INTEGRATION.md` for complete metadata details.

## API Endpoints

### User-Facing Routes
- `GET /soundcloud/connect` - Connect SoundCloud account
- `GET /soundcloud/callback` - OAuth callback handler

### API Routes
- `POST /api/generate-playlist` - Generate playlist (supports `service: "soundcloud"`)
- `GET /api/auth-status` - Returns `soundcloud_connected` and `soundcloud_username`

## Frontend Integration

Update your frontend to support SoundCloud:

1. **Add Connect Button**:
```html
<button onclick="window.location.href='/soundcloud/connect'">
  Connect SoundCloud
</button>
```

2. **Service Selector**:
```html
<select id="service">
  <option value="spotify">Spotify</option>
  <option value="soundcloud">SoundCloud</option>
</select>
```

3. **Update API Call**:
```javascript
const service = document.getElementById('service').value;
const response = await fetch('/api/generate-playlist', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mood: moodInput.value,
    playlist_name: playlistNameInput.value,
    track_count: trackCountInput.value,
    service: service  // Add this
  })
});
```

## Troubleshooting

### "SoundCloud account not connected"
- User needs to visit `/soundcloud/connect` first
- Check that OAuth callback URL matches your `SOUNDCLOUD_REDIRECT_URI`

### "Invalid service"
- Ensure `service` parameter is exactly `"soundcloud"` (lowercase)

### "No tracks found on SoundCloud"
- SoundCloud search may return different results than Spotify
- Some tracks may not be available or searchable

### API Credentials Issues
- Verify `SOUNDCLOUD_CLIENT_ID` and `SOUNDCLOUD_CLIENT_SECRET` are set
- Check that SoundCloud API access is enabled for your account

## Next Steps

1. ✅ Backend integration complete
2. ⏳ Update frontend UI to support SoundCloud
3. ⏳ Test with real SoundCloud account
4. ⏳ Handle edge cases (restricted content, missing tracks)

## Documentation

- **Full Integration Guide**: See `SOUNDCLOUD_INTEGRATION.md`
- **API Reference**: [SoundCloud API Docs](https://developers.soundcloud.com/docs/api/introduction)

