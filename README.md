# Drift - AI Playlist Generator

A modern web application that generates Spotify playlists based on mood descriptions using AI. Inspired by the sleek designs of GAFFA, Sony Music, and Epidemic Sound.

## Features

- 🎵 **AI-Powered Playlist Generation**: Describe your mood and get a curated playlist
- 🎨 **Modern UI**: Sleek, dark design inspired by music industry leaders
- 📊 **Analytics**: View indie track percentage and genre diversity scores
- 🔐 **Spotify Integration**: Seamless OAuth authentication
- ⚡ **Real-time Generation**: Watch your playlist come to life

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Make sure your `.env` file contains:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5000/callback
OPENAI_API_KEY=your_openai_api_key
```

**Important**: 
- Update your Spotify app's redirect URI in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) to match `http://127.0.0.1:5000/callback`
- Make sure your `.env` file has `SPOTIFY_REDIRECT_URI=http://127.0.0.1:5000/callback` (not port 8000)

### 3. Run the Application

```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`

## Usage

1. Click "Connect Spotify" to authenticate
2. Enter a mood description (e.g., "jämtland mountain electronic female indie")
3. Optionally customize the playlist name
4. Click "Generate Playlist"
5. View your results and open the playlist in Spotify

## Project Structure

```
Drift/
├── app.py                 # Flask backend
├── templates/
│   └── index.html         # Main HTML template
├── static/
│   ├── css/
│   │   └── style.css      # Styling
│   └── js/
│       └── app.js         # Frontend JavaScript
├── requirements.txt       # Python dependencies
└── .env                   # Environment variables (not in git)
```

## Technologies

- **Backend**: Flask, Python
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **APIs**: Spotify Web API, OpenAI GPT-4
- **Design**: Modern, responsive, dark theme

## License

MIT

