from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
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
import re
from functools import wraps
from datetime import datetime, timedelta
import secrets
import smtplib
from email.message import EmailMessage

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import NullPool
from passlib.hash import bcrypt
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SESSION_TYPE'] = 'filesystem'
# Prefer DATABASE_URL; otherwise, build from discrete env vars if present
database_url = os.getenv('DATABASE_URL') or ''
if not database_url:
    pg_user = os.getenv('user')
    pg_password = os.getenv('password')
    pg_host = os.getenv('host')
    pg_port = os.getenv('port')
    pg_dbname = os.getenv('dbname')
    if all([pg_user, pg_password, pg_host, pg_port, pg_dbname]):
        # Use psycopg3 driver and enforce SSL (Supabase)
        database_url = f"postgresql+psycopg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_dbname}?sslmode=require"
    else:
        database_url = 'sqlite:///drift.db'

# Convert postgresql:// URLs to use psycopg3 driver for Python 3.13 compatibility
if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
    # Replace postgresql:// or postgres:// with postgresql+psycopg:// to use psycopg3
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure connection pooling for PostgreSQL
# Detect if using Supabase connection pooler or direct connection
if database_url.startswith(('postgresql+psycopg://', 'postgres://', 'postgresql://')):
    # Check if using Supabase transaction pooler (pooler.supabase.com or port 6543)
    # vs direct connection (db.supabase.co or port 5432)
    is_transaction_pooler = 'pooler.supabase.com' in database_url or ':6543' in database_url
    is_direct = 'db.supabase.co' in database_url or ':5432' in database_url
    
    if is_transaction_pooler:
        # Transaction pooler: disable client-side pooling per SQLAlchemy guidance
        # https://docs.sqlalchemy.org/en/20/core/pooling.html#switching-pool-implementations
        connect_args = {
            'connect_timeout': 10,
            'sslmode': 'require'
        }
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'poolclass': NullPool,
            'connect_args': connect_args
        }
    elif is_direct:
        # Direct connection allows more connections - use larger pool for better performance
        pool_size = 5
        max_overflow = 5
        connect_args = {
            'connect_timeout': 10,
            'sslmode': 'require'
        }
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_recycle': 180,  # Recycle connections after 3 minutes (faster cleanup)
            'pool_pre_ping': True,  # Verify connections before using
            'pool_timeout': 5,  # Wait up to 5 seconds for a connection
            'connect_args': connect_args
        }
    else:
        # Default for other PostgreSQL databases
        pool_size = 5
        max_overflow = 5
        connect_args = {
            'connect_timeout': 10,
            'sslmode': 'require'
        }
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_recycle': 180,  # Recycle connections after 3 minutes (faster cleanup)
            'pool_pre_ping': True,  # Verify connections before using
            'pool_timeout': 5,  # Wait up to 5 seconds for a connection
            'connect_args': connect_args
        }

Session(app)

db = SQLAlchemy(app)

# Spotify API credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "https://t-pauz.onrender.com/callback")
SCOPES = "playlist-modify-private playlist-modify-public user-read-private"

# Request timeout for external API calls (in seconds)
# Reduced from 15 to 10 to fail faster and prevent worker timeouts
REQUEST_TIMEOUT = 10

# Create a requests session with connection pooling and retry strategy
# This improves performance and reliability for multiple API calls
retry_strategy = Retry(
    total=2,  # Maximum 2 retries
    backoff_factor=0.3,  # Wait 0.3, 0.6 seconds between retries
    status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
    allowed_methods=["GET", "POST"]  # Only retry safe methods
)

adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=10,  # Number of connection pools to cache
    pool_maxsize=10,  # Maximum number of connections to save in the pool
    pool_block=False  # Don't block if pool is full
)

# Create a session for Spotify API calls
spotify_session = requests.Session()
spotify_session.mount("https://", adapter)

# Create a separate session for other API calls (OpenAI, etc.)
api_session = requests.Session()
api_session.mount("https://", adapter)

# OpenAI setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

GMAIL_USERNAME = os.getenv("GMAIL_USERNAME")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
INVITE_EMAIL_ENABLED = os.getenv("INVITE_EMAIL_ENABLED", "").lower() in ("1", "true", "yes", "on")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
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


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    credits_remaining = db.Column(db.Integer, default=3)
    spotify_user_id = db.Column(db.Text)
    spotify_display_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usages = db.relationship("PlaylistUsage", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hash(password)

    def check_password(self, password: str) -> bool:
        try:
            return bcrypt.verify(password, self.password_hash)
        except ValueError:
            return False


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    credits = db.Column(db.Integer, default=3)
    expires_at = db.Column(db.DateTime, nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self) -> bool:
        if self.accepted_at:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class PlaylistUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spotify_playlist_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PlaylistPrompt(db.Model):
    """Anonymous storage of playlist prompts (no user_id)"""
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        # Log the error but don't fail startup - tables might already exist
        app.logger.warning(f"Database initialization warning: {str(e)}")
        # Try to continue - this might be a transaction pooler limitation
        pass
    
    if DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD:
        try:
            existing_admin = User.query.filter_by(email=DEFAULT_ADMIN_EMAIL).first()
            if not existing_admin:
                admin_user = User(
                    email=DEFAULT_ADMIN_EMAIL,
                    is_admin=True,
                    credits_remaining=9999
                )
                admin_user.set_password(DEFAULT_ADMIN_PASSWORD)
                db.session.add(admin_user)
                db.session.commit()
        except Exception as e:
            app.logger.error(f"Failed to create admin user: {str(e)}")
            # Don't fail startup if admin creation fails


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    try:
        return db.session.get(User, user_id)
    except Exception as e:
        # Handle database connection errors
        db.session.rollback()
        # Try once more with a fresh session
        try:
            return db.session.get(User, user_id)
        except Exception:
            return None


@app.before_request
def load_logged_in_user():
    g.user = get_current_user()


@app.teardown_request
def close_db_session(exception):
    """Close database session after each request to prevent connection leaks."""
    try:
        db.session.remove()
    except Exception:
        pass


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            next_url = request.path if request.method == 'GET' else url_for('index')
            return redirect(url_for('auth_login', next=next_url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None or not g.user.is_admin:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def send_invite_email(email: str, token: str, credits: int) -> None:
    if not GMAIL_USERNAME or not GMAIL_APP_PASSWORD:
        raise RuntimeError("Email credentials are not configured. Set GMAIL_USERNAME and GMAIL_APP_PASSWORD.")

    invite_link = f"{APP_BASE_URL.rstrip('/')}/invite/{token}"
    subject = "You're invited to Rift"
    body = (
        f"Hi,\n\n"
        f"You have been invited to try Rift. Use the link below to create your account.\n\n"
        f"Invitation link: {invite_link}\n"
        f"You will receive {credits} playlist credits to get started.\n\n"
        f"If you did not expect this invite, you can safely ignore this email.\n\n"
        f"— Rift Team"
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = GMAIL_USERNAME
    message["To"] = email
    message.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USERNAME, GMAIL_APP_PASSWORD)
        smtp.send_message(message)


def generate_invite(email: str, credits: int, expires_in_days: int = 7) -> Invite:
    token = secrets.token_urlsafe(24)
    invite = Invite(
        email=email.strip().lower(),
        token=token,
        credits=max(1, credits),
        expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
    )
    db.session.add(invite)
    db.session.commit()
    return invite


def _is_safe_redirect(target: str) -> bool:
    if not target:
        return False
    host_url = urllib.parse.urlparse(request.host_url)
    redirect_url = urllib.parse.urlparse(urllib.parse.urljoin(request.host_url, target))
    return redirect_url.scheme in ('http', 'https') and host_url.netloc == redirect_url.netloc


@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if g.user:
        return redirect(url_for('index'))

    error = None
    next_url_candidate = request.args.get('next') or request.form.get('next') or None
    next_url = next_url_candidate if _is_safe_redirect(next_url_candidate) else url_for('index')

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            return redirect(next_url)
        else:
            error = "Invalid email or password."

    return render_template('auth_login.html', error=error, next=next_url)


@app.route('/invite/<token>', methods=['GET', 'POST'])
def accept_invite(token):
    invite = Invite.query.filter_by(token=token).first()
    if not invite or not invite.is_valid():
        return render_template('invite_invalid.html')

    error = None
    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''

        if len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            user = User.query.filter_by(email=invite.email).first()
            if user:
                user.set_password(password)
                user.credits_remaining = invite.credits
            else:
                user = User(
                    email=invite.email,
                    credits_remaining=invite.credits
                )
                user.set_password(password)
                db.session.add(user)

            invite.accepted_at = datetime.utcnow()
            db.session.commit()

            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))

    return render_template('invite_accept.html', invite=invite, error=error)


def refresh_spotify_token():
    """Refresh Spotify access token using refresh token"""
    refresh_token = session.get('spotify_refresh_token')
    if not refresh_token:
        # Clear invalid session
        session.pop('spotify_access_token', None)
        return None
    
    token_url = "https://accounts.spotify.com/api/token"
    resp = spotify_session.post(token_url, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }, timeout=REQUEST_TIMEOUT)
    
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
        if g.user is None:
            return jsonify({'error': 'Not authenticated'}), 401
        if 'spotify_access_token' not in session:
            return jsonify({'error': 'Spotify account not connected'}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
@login_required
def index():
    """Main page (requires authenticated user)"""
    return render_template('index.html', user=g.user)


@app.route('/privacy')
def privacy():
    """Privacy policy page (public)"""
    from datetime import datetime
    return render_template('privacy.html', current_date=datetime.now().strftime('%B %d, %Y'), user=g.user if hasattr(g, 'user') else None)


@app.route('/spotify/connect')
@login_required
def spotify_connect():
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
@login_required
def callback():
    """Handle Spotify OAuth callback"""
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index', error='access_denied'))
    
    # Exchange code for tokens
    token_url = "https://accounts.spotify.com/api/token"
    resp = spotify_session.post(token_url, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }, timeout=REQUEST_TIMEOUT)
    
    if resp.status_code != 200:
        return redirect(url_for('index', error='token_exchange_failed'))
    
    tokens = resp.json()
    session['spotify_access_token'] = tokens['access_token']
    session['spotify_refresh_token'] = tokens.get('refresh_token')
    
    # Get user info
    headers = {"Authorization": f"Bearer {session['spotify_access_token']}"}
    r = spotify_session.get("https://api.spotify.com/v1/me", headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code == 200:
        me = r.json()
        session['spotify_user_id'] = me.get('id')
        session['spotify_display_name'] = me.get('display_name')
        g.user.spotify_user_id = me.get('id')
        g.user.spotify_display_name = me.get('display_name')
        db.session.commit()
    
    return redirect(url_for('index'))


@app.route('/logout')
@login_required
def logout():
    """Logout user and clear session"""
    session.clear()
    return redirect(url_for('auth_login'))


@app.route('/api/auth-status')
def auth_status():
    """Check if user is authenticated"""
    user = g.user
    return jsonify({
        'authenticated': user is not None,
        'email': user.email if user else None,
        'is_admin': bool(user.is_admin) if user else False,
        'credits_remaining': user.credits_remaining if user else 0,
        'spotify_connected': 'spotify_access_token' in session,
        'spotify_display_name': user.spotify_display_name if user else None
    })


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    results = []
    for user in users:
        results.append({
            'id': user.id,
            'email': user.email,
            'credits_remaining': user.credits_remaining,
            'is_admin': user.is_admin,
            'spotify_display_name': user.spotify_display_name,
            'created_at': user.created_at.isoformat(),
            'last_updated': user.updated_at.isoformat() if user.updated_at else None,
            'usage_count': len(user.usages)
        })
    return jsonify({'users': results})


@app.route('/api/admin/users/<int:user_id>', methods=['PATCH'])
@admin_required
def admin_update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(force=True)
    credits = data.get('credits_remaining')
    if credits is not None:
        try:
            credits = int(credits)
        except (TypeError, ValueError):
            return jsonify({'error': 'credits_remaining must be an integer'}), 400
        user.credits_remaining = max(0, credits)

    if 'is_admin' in data and g.user.id != user.id:
        user.is_admin = bool(data.get('is_admin'))

    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/admin/invite', methods=['POST'])
@admin_required
def admin_send_invite():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    credits = data.get('credits') or 3

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        credits = int(credits)
    except (TypeError, ValueError):
        return jsonify({'error': 'credits must be a number'}), 400

    invite = generate_invite(email, credits)
    invite_link = f"{APP_BASE_URL.rstrip('/')}/invite/{invite.token}"

    email_sent = False
    if INVITE_EMAIL_ENABLED and GMAIL_USERNAME and GMAIL_APP_PASSWORD:
        try:
            send_invite_email(email, invite.token, invite.credits)
            email_sent = True
        except Exception as exc:
            app.logger.exception("Failed to send invite email", exc_info=True)

    if not email_sent:
        return jsonify({
            'success': True,
            'email_sent': False,
            'invite_link': invite_link,
            'message': 'Email not sent; share the invite link manually.'
        })

    return jsonify({
        'success': True,
        'email_sent': True,
        'invite_link': invite_link
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

    if g.user.credits_remaining <= 0:
        return jsonify({'error': 'You have no playlist credits remaining.'}), 403
    
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
            matches = None
            track_name = ""
            artist_name = ""
            try:
                track_name = t.get("track", "")
                artist_name = t.get("artist", "")
                if not track_name or not artist_name:
                    continue
                # Get fresh token in case it was refreshed
                access_token = session.get('spotify_access_token')
                if not access_token:
                    raise Exception("Spotify authentication lost. Please reconnect your account.")
                matches = search_spotify_track(track_name, artist_name, access_token)
            except KeyError as e:
                app.logger.warning(f"Unexpected track format: {t}")
                continue
            except Exception as e:
                # If search fails for one track, log and continue with others
                app.logger.warning(f"Error searching for track {track_name} by {artist_name}: {str(e)}")
                if track_name and artist_name:
                    not_found.append({"artist": artist_name, "track": track_name})
                continue
            
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
            "AI-generated playlist",
            access_token
        )
        
        # Step 4: Add tracks to playlist
        # Get fresh token in case it was refreshed
        access_token = session.get('spotify_access_token')
        add_tracks_to_playlist(playlist_id, track_uris, access_token)
        
        # Step 5: Calculate metrics using efficient batch API calls
        # Get fresh token in case it was refreshed
        access_token = session.get('spotify_access_token')
        indie_pct = 0.0
        diversity_score = 0.0
        genre_counts = {}
        try:
            # Batch API calls: 1-2 calls instead of 25-50 individual calls
            indie_pct = indie_fraction(track_uris, access_token, threshold=50)
            diversity_score, genre_counts = genre_diversity(artist_ids, access_token)
        except Exception as metrics_error:
            # If metrics fail, use defaults but don't fail the request
            # Playlist was already created successfully
            pass

        # Record usage & update credits
        new_credits = max(0, g.user.credits_remaining - 1)
        try:
            g.user.credits_remaining = new_credits
            usage = PlaylistUsage(
                user_id=g.user.id,
                spotify_playlist_id=playlist_id
            )
            db.session.add(usage)
            
            # Store prompt anonymously (no user_id)
            prompt_record = PlaylistPrompt(
                prompt=mood
            )
            db.session.add(prompt_record)
            
            db.session.commit()
        except Exception as db_error:
            # If database commit fails, rollback and try once more
            db.session.rollback()
            try:
                # Refresh user object and retry
                db.session.refresh(g.user)
                g.user.credits_remaining = new_credits
                usage = PlaylistUsage(
                    user_id=g.user.id,
                    spotify_playlist_id=playlist_id
                )
                db.session.add(usage)
                
                # Store prompt anonymously (no user_id)
                prompt_record = PlaylistPrompt(
                    prompt=mood
                )
                db.session.add(prompt_record)
                
                db.session.commit()
            except Exception:
                # If retry also fails, log but don't fail the request
                # The playlist was already created successfully
                # Use the calculated credits value even if DB commit failed
                pass
        
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
            'credits_remaining': new_credits,
            'requested_track_count': track_count,
            'spotify_url': f"https://open.spotify.com/playlist/{playlist_id}"
        })
        
    except Exception as e:
        # Log the full error for debugging
        import traceback
        app.logger.error(f"Error generating playlist: {str(e)}")
        app.logger.error(traceback.format_exc())
        # Return user-friendly error message
        error_message = str(e)
        if "403" in error_message or "Forbidden" in error_message:
            error_message = "Spotify access denied. Please click 'Connect Spotify' to reconnect your account."
        elif "401" in error_message or "Unauthorized" in error_message:
            error_message = "Spotify authentication expired. Please reconnect your account."
        elif "timeout" in error_message.lower():
            error_message = "Request timed out. Please try again."
        return jsonify({'error': error_message}), 500


# Helper functions from notebook
def get_tracks_from_gpt(user_prompt: str, track_count: int):
    """Ask GPT for tracks and return them directly as a Python dictionary."""
    system_prompt = MODEL_PROMPT_TEMPLATE.format(track_count=track_count)
    
    # Calculate max_tokens based on track count (roughly 25-30 tokens per track)
    estimated_tokens = (track_count * 30) + 50
    max_tokens = min(max(estimated_tokens, 800), 2000)  # Between 800 and 2000 tokens
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=max_tokens
    )
    
    text = response.choices[0].message.content.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```"):
        lines = text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    
    # Try parsing as JSON first (most common format from GPT)
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or "tracks" not in data:
            raise ValueError("Response missing 'tracks' key")
        return data
    except json.JSONDecodeError as json_err:
        # If JSON is incomplete, try to extract complete track entries
        app.logger.warning(f"JSON decode error: {str(json_err)}")
        # Pattern to match complete track entries: {"artist": "...", "track": "..."}
        track_pattern = r'\{"artist":\s*"[^"]+",\s*"track":\s*"[^"]+"\}'
        matches = re.findall(track_pattern, text)
        if matches:
            # Reconstruct JSON with found tracks
            tracks_json = ',\n'.join(matches)
            reconstructed = f'{{"tracks": [{tracks_json}]}}'
            try:
                data = json.loads(reconstructed)
                app.logger.info(f"Recovered {len(data['tracks'])} tracks from incomplete JSON")
                return data
            except json.JSONDecodeError:
                pass
    
    # Fallback to Python literal_eval (for Python dict format)
    try:
        data = ast.literal_eval(text)
        if not isinstance(data, dict) or "tracks" not in data:
            raise ValueError("Response missing 'tracks' key")
        return data
    except (ValueError, SyntaxError) as e:
        app.logger.error(f"Could not parse GPT response as JSON or Python dict.")
        app.logger.error(f"Response text (first 1000 chars): {text[:1000]}")
        raise ValueError(f"Could not parse GPT response. The response may have been truncated. Please try again with fewer tracks. Error: {str(e)}")


def search_spotify_track(track_name, artist_name, access_token):
    """Search Spotify for a track by name and artist."""
    q = f"track:{track_name} artist:{artist_name}"
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": q, "type": "track", "limit": 3}
    
    try:
        r = spotify_session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise Exception("Spotify API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to Spotify API: {str(e)}")
    
    # If token expired (401) or forbidden (403), refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                r = spotify_session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                raise Exception("Spotify API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to Spotify API: {str(e)}")
        else:
            raise Exception("Spotify authentication expired. Please reconnect your account.")
    elif r.status_code == 403:
        # 403 Forbidden - token might be invalid or app permissions changed
        # Try refreshing token first
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                r = spotify_session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
                if r.status_code == 403:
                    # Clear Spotify session to force reconnection
                    session.pop('spotify_access_token', None)
                    session.pop('spotify_refresh_token', None)
                    session.pop('spotify_user_id', None)
                    session.pop('spotify_display_name', None)
                    raise Exception("Spotify access denied. Please click 'Connect Spotify' to reconnect your account.")
            except requests.exceptions.Timeout:
                raise Exception("Spotify API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to Spotify API: {str(e)}")
        else:
            # Clear Spotify session to force reconnection
            session.pop('spotify_access_token', None)
            session.pop('spotify_refresh_token', None)
            session.pop('spotify_user_id', None)
            session.pop('spotify_display_name', None)
            raise Exception("Spotify access denied. Please click 'Connect Spotify' to reconnect your account.")
    
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
    try:
        r = spotify_session.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise Exception("Spotify API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to Spotify API: {str(e)}")
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"}
            try:
                r = spotify_session.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                raise Exception("Spotify API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to Spotify API: {str(e)}")
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
        try:
            r = spotify_session.post(url, headers=headers, json={"uris": chunk}, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            raise Exception("Spotify API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Spotify API: {str(e)}")
        
        # If token expired, refresh and retry
        if r.status_code == 401:
            new_token = refresh_spotify_token()
            if new_token:
                headers = {"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"}
                try:
                    r = spotify_session.post(url, headers=headers, json={"uris": chunk}, timeout=REQUEST_TIMEOUT)
                except requests.exceptions.Timeout:
                    raise Exception("Spotify API request timed out. Please try again.")
                except requests.exceptions.RequestException as e:
                    raise Exception(f"Error connecting to Spotify API: {str(e)}")
            else:
                r.raise_for_status()
        
        r.raise_for_status()


def get_spotify_track(track_id, access_token):
    """Fetch track info from Spotify."""
    url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise Exception("Spotify API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to Spotify API: {str(e)}")
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                raise Exception("Spotify API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to Spotify API: {str(e)}")
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    return r.json()


def get_spotify_artist(artist_id, access_token):
    """Fetch artist info from Spotify."""
    url = f"https://api.spotify.com/v1/artists/{artist_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise Exception("Spotify API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to Spotify API: {str(e)}")
    
    # If token expired, refresh and retry
    if r.status_code == 401:
        new_token = refresh_spotify_token()
        if new_token:
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                raise Exception("Spotify API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to Spotify API: {str(e)}")
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    return r.json()


def get_tracks_batch(track_ids, access_token):
    """Fetch multiple tracks in a single API call (max 50 tracks per request)."""
    if not track_ids:
        return []
    
    # Spotify API allows up to 50 IDs per request
    batch_size = 50
    all_tracks = []
    
    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i:i+batch_size]
        ids_param = ','.join(batch)
        url = f"https://api.spotify.com/v1/tracks?ids={ids_param}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            raise Exception("Spotify API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Spotify API: {str(e)}")
        
        # If token expired, refresh and retry
        if r.status_code == 401:
            new_token = refresh_spotify_token()
            if new_token:
                headers = {"Authorization": f"Bearer {new_token}"}
                try:
                    r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                except requests.exceptions.Timeout:
                    raise Exception("Spotify API request timed out. Please try again.")
                except requests.exceptions.RequestException as e:
                    raise Exception(f"Error connecting to Spotify API: {str(e)}")
            else:
                r.raise_for_status()
        
        r.raise_for_status()
        tracks_data = r.json().get("tracks", [])
        all_tracks.extend(tracks_data)
    
    return all_tracks


def get_artists_batch(artist_ids, access_token):
    """Fetch multiple artists in a single API call (max 50 artists per request)."""
    if not artist_ids:
        return []
    
    # Remove duplicates and limit to 50 per batch
    unique_artist_ids = list(dict.fromkeys(artist_ids))  # Preserves order, removes duplicates
    batch_size = 50
    all_artists = []
    
    for i in range(0, len(unique_artist_ids), batch_size):
        batch = unique_artist_ids[i:i+batch_size]
        ids_param = ','.join(batch)
        url = f"https://api.spotify.com/v1/artists?ids={ids_param}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            raise Exception("Spotify API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Spotify API: {str(e)}")
        
        # If token expired, refresh and retry
        if r.status_code == 401:
            new_token = refresh_spotify_token()
            if new_token:
                headers = {"Authorization": f"Bearer {new_token}"}
                try:
                    r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                except requests.exceptions.Timeout:
                    raise Exception("Spotify API request timed out. Please try again.")
                except requests.exceptions.RequestException as e:
                    raise Exception(f"Error connecting to Spotify API: {str(e)}")
            else:
                r.raise_for_status()
        
        r.raise_for_status()
        artists_data = r.json().get("artists", [])
        all_artists.extend(artists_data)
    
    return all_artists


def indie_fraction(track_uris, access_token, threshold=50):
    """Calculate fraction of indie tracks (popularity < threshold) using efficient batch API."""
    if not track_uris:
        return 0.0
    
    # Extract track IDs from URIs
    track_ids = [uri.split(":")[-1] for uri in track_uris]
    
    # Fetch all tracks in batch(es) - 1-2 API calls instead of 25-50
    tracks_data = get_tracks_batch(track_ids, access_token)
    
    if not tracks_data:
        return 0.0
    
    count_indie = 0
    total = len(tracks_data)
    
    for track in tracks_data:
        popularity = track.get("popularity", 0)
        if popularity < threshold:
            count_indie += 1
    
    return count_indie / total if total > 0 else 0.0


def genre_diversity(artist_ids, access_token):
    """Calculate genre diversity score using efficient batch API."""
    if not artist_ids:
        return 0.0, {}
    
    # Fetch all artists in batch(es) - 1 API call instead of 25-50
    artists_data = get_artists_batch(artist_ids, access_token)
    
    if not artists_data:
        return 0.0, {}
    
    all_genres = []
    for artist in artists_data:
        genres = artist.get("genres", [])
        all_genres.extend(genres)
    
    if not all_genres:
        return 0.0, {}
    
    genre_counts = Counter(all_genres)
    
    total_genres = len(all_genres)
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

