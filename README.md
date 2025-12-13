# Rift - AI Playlist Generator

*An application that transforms mood descriptions into curated Spotify playlists using AI*
</div>
https://rift-pauz.onrender.com/

</div>

## 🎵 About

Rift is an intelligent music curation platform that bridges the gap between your emotional state and personalized playlists. Unlike traditional recommendation algorithms that rely on your listening history, Rift uses natural language descriptions to discover music you've never heard before, prioritizing indie and lesser-known artists to expand your musical horizons.

### How It Works

Simply describe your mood or the type of sound you're looking for — whether it's "late night New York jazz," "jämtland mountain electronic," or "energetic workout beats" — and Rift's AI curator analyzes your description, searches Spotify's catalog, and creates a fully-formed playlist directly in your Spotify account in seconds.

## ✨ Key Features

### 🎨 AI-Powered Curation
- **GPT-4 Powered**: Uses OpenAI's GPT-4 model as a music curator that understands context, emotion, and musical nuance
- **Indie-First Approach**: Prioritizes small, independent artists over mainstream hits
- **Context-Aware**: Doesn't factor in Spotify popularity scores or your listening history, opening up entirely new musical discoveries

### 📊 Analytics
Each generated playlist includes detailed analytics:

- **Indie Track Percentage**: Calculates what percentage of tracks have a popularity score below 50, helping you discover hidden gems
- **Genre Diversity Score**: Uses Shannon entropy to measure how diverse the genres are across the playlist (0 = single genre, 1 = maximum diversity)
- **Genre Breakdown**: Visual representation of genre distribution across all artists in the playlist

These analytics help users understand the musical composition of their playlists and discover new genres.

### 🔐 Seamless Integration
- **Spotify OAuth**: Secure authentication with Spotify
- **Direct Playlist Creation**: Playlists are created directly in your Spotify account — no downloads, no exports
- **Real-time Generation**: Watch your playlist come to life as tracks are searched and added

## 🛠️ Technical Architecture

### Backend
- **Flask**: Lightweight Python web framework
- **OpenAI GPT-4**: AI-powered music curation engine
- **Spotify Web API**: Track search, playlist creation, and artist metadata
- **PostgreSQL/Supabase**: User management, subscription tracking, and usage analytics
- **Stripe**: Subscription billing (unused for now)

### Frontend
- **Vanilla JavaScript**: No frameworks, optimized for performance
- **CSS3**: Modern styling with CSS variables for theming

### Key Technical Features
- **Batch API Optimization**: Efficiently fetches track and artist data in batches to minimize API calls
- **Monthly Usage Tracking**: Tracks playlist creation per calendar month with automatic limits
- **Subscription Management**: Integrated Stripe subscriptions with webhook handling
- **Token Refresh**: Automatic Spotify token refresh for seamless user experience

### Analytics Implementation
The analytics system uses Spotify's track popularity scores (0-100) and artist genre data:
- **Indie Calculation**: Tracks with popularity < 50 are considered "indie"
- **Diversity Scoring**: Shannon entropy formula measures genre distribution entropy
- **Batch Processing**: Fetches up to 50 tracks/artists per API call for efficiency


## 📖 Usage

1. **Admin Setup**: First admin user is created automatically from `ADMIN_EMAIL` / `ADMIN_PASSWORD`
2. **User Invitations**: Admins can send invitations from `/admin` dashboard
3. **Connect Spotify**: Users connect their Spotify account via OAuth
4. **Generate Playlists**: Enter a mood description, customize playlist name and track count (1-50), and generate
5. **View Analytics**: See indie percentage, genre diversity, and genre breakdown for each playlist

### Subscription Tiers
- **Trial**: 3 playlists per month (free)
- **Premium**: 25 playlists per month (49 SEK/month via Stripe, unused for now)

## 📁 Project Structure

```
Drift/
├── app.py                    # Flask backend application
├── requirements.txt          # Python dependencies
├── templates/
│   ├── index.html           # Main application template
│   ├── landing.html         # Landing page
│   ├── auth_login.html      # Login page
│   └── admin_dashboard.html # Admin interface
├── static/
│   ├── css/
│   │   └── style.css        # Stylesheet
│   ├── js/
│   │   └── app.js           # Frontend JavaScript
│   └── videos/
│       └── landing-video.mp4 # Demo video
└── .env                     # Environment variables (not in git)
```

## 🧪 Technologies

- **Backend**: Flask, Python, SQLAlchemy
- **AI**: OpenAI GPT-4
- **APIs**: Spotify Web API, Stripe API
- **Database**: PostgreSQL (via Supabase)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Payment**: Stripe Subscriptions

## 📄 License

MIT License

---
**This is solely an indie project I built for frinds and family <3**
