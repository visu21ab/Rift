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

# Stripe configuration
import stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # Monthly subscription price ID (49 SEK)
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
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
    playlists_remaining = db.Column(db.Integer, default=3)  # Number of playlists remaining this month
    subscription_plan = db.Column(db.String(50), default='trial')  # 'trial' or 'premium'
    stripe_customer_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
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
    
    def has_premium_access(self) -> bool:
        """Check if user has premium access (admins always have premium)"""
        return self.is_admin or getattr(self, 'subscription_plan', 'trial') == 'premium'
    
    def get_monthly_playlist_limit(self) -> int:
        """Get monthly playlist limit based on subscription plan"""
        if self.is_admin:
            return float('inf')  # Admins have unlimited
        if self.subscription_plan == 'premium':
            return 25
        return 3  # trial
    
    def get_playlists_this_month(self) -> int:
        """Count playlists created in the current month"""
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        return PlaylistUsage.query.filter(
            PlaylistUsage.user_id == self.id,
            PlaylistUsage.created_at >= start_of_month
        ).count()
    
    def can_create_playlist(self) -> bool:
        """Check if user can create a playlist this month"""
        if self.is_admin:
            return True  # Admins have unlimited playlists
        return self.get_playlists_this_month() < self.get_monthly_playlist_limit()


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


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self) -> bool:
        if self.used_at:
            return False
        if datetime.utcnow() > self.expires_at:
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
            existing_user = User.query.filter_by(email=DEFAULT_ADMIN_EMAIL).first()
            if not existing_user:
                admin_user = User(
                    email=DEFAULT_ADMIN_EMAIL,
                    is_admin=True,
                    subscription_plan='premium',  # Admins are always premium
                    playlists_remaining=9999
                )
                admin_user.set_password(DEFAULT_ADMIN_PASSWORD)
                db.session.add(admin_user)
                db.session.commit()
            else:
                # Ensure user with admin email is set as admin and premium
                needs_update = False
                if not existing_user.is_admin:
                    existing_user.is_admin = True
                    needs_update = True
                if existing_user.subscription_plan != 'premium':
                    existing_user.subscription_plan = 'premium'
                    needs_update = True
                # Update password if it's the default admin (in case password changed in env)
                if needs_update or not existing_user.check_password(DEFAULT_ADMIN_PASSWORD):
                    existing_user.set_password(DEFAULT_ADMIN_PASSWORD)
                    needs_update = True
                if needs_update:
                    db.session.commit()
        except Exception as e:
            app.logger.error(f"Failed to create/update admin user: {str(e)}")
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


def send_password_reset_email(email: str, reset_link: str) -> None:
    """Send password reset email to user"""
    if not GMAIL_USERNAME or not GMAIL_APP_PASSWORD:
        raise RuntimeError("Email credentials are not configured. Set GMAIL_USERNAME and GMAIL_APP_PASSWORD.")

    subject = "Reset Your Rift Password"
    body = (
        f"Hi,\n\n"
        f"You requested to reset your password for Rift. Click the link below to reset it:\n\n"
        f"Reset link: {reset_link}\n\n"
        f"This link will expire in 24 hours.\n\n"
        f"If you did not request this password reset, you can safely ignore this email.\n\n"
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


def count_sentences(text: str) -> int:
    """Count the number of sentences in a text string"""
    if not text or not text.strip():
        return 0
    # Split by sentence-ending punctuation followed by whitespace or end of string
    # This handles . ! ? followed by space, newline, or end of string
    sentences = re.split(r'[.!?]+(?:\s+|$)', text.strip())
    # Filter out empty strings
    sentences = [s for s in sentences if s.strip()]
    return len(sentences) if sentences else 1  # At least 1 if there's any text


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


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Generate a password reset token for a user and send email"""
    if g.user:
        return redirect(url_for('index'))

    error = None
    success = None
    reset_token = None
    reset_link = None
    email_sent = False

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()

        if not email:
            error = "Email is required."
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                # Invalidate any existing unused tokens for this user
                existing_tokens = PasswordResetToken.query.filter_by(
                    user_id=user.id,
                    used_at=None
                ).all()
                for token in existing_tokens:
                    token.used_at = datetime.utcnow()

                # Generate new reset token
                token = secrets.token_urlsafe(32)
                reset_token_obj = PasswordResetToken(
                    user_id=user.id,
                    token=token,
                    expires_at=datetime.utcnow() + timedelta(hours=24)  # Token valid for 24 hours
                )
                db.session.add(reset_token_obj)
                db.session.commit()

                reset_token = token
                reset_link = f"{APP_BASE_URL.rstrip('/')}/reset-password/{token}"
                
                # Send password reset email
                if INVITE_EMAIL_ENABLED and GMAIL_USERNAME and GMAIL_APP_PASSWORD:
                    try:
                        send_password_reset_email(email, reset_link)
                        email_sent = True
                    except Exception as exc:
                        app.logger.exception("Failed to send password reset email", exc_info=True)
                        # Continue even if email fails - user can still use the link shown on page
                
                success = True
            else:
                # Don't reveal if email exists or not (security best practice)
                success = True
                reset_token = None

    return render_template('forgot_password.html', error=error, success=success, 
                          reset_token=reset_token, reset_link=reset_link, email_sent=email_sent)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using a reset token"""
    if g.user:
        return redirect(url_for('index'))

    reset_token_obj = PasswordResetToken.query.filter_by(token=token).first()
    
    if not reset_token_obj or not reset_token_obj.is_valid():
        return render_template('reset_password.html', error="Invalid or expired reset token.", token=token)

    user = db.session.get(User, reset_token_obj.user_id)
    if not user:
        return render_template('reset_password.html', error="User not found.", token=token)

    error = None
    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''

        if len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            # Update password
            user.set_password(password)
            # Mark token as used
            reset_token_obj.used_at = datetime.utcnow()
            db.session.commit()

            # Auto-login user
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))

    return render_template('reset_password.html', error=error, token=token, email=user.email)


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
                user.playlists_remaining = invite.credits
            else:
                user = User(
                    email=invite.email,
                    playlists_remaining=invite.credits,
                    subscription_plan='trial'  # New users start with trial
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
def index():
    """Main page - shows landing page if not logged in, app if logged in"""
    if g.user is None:
        return render_template('landing.html')
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
    subscription_plan = getattr(user, 'subscription_plan', 'trial') if user else 'trial'
    # Admins are always premium
    if user and user.is_admin:
        subscription_plan = 'premium'
    
    # Get monthly usage info
    playlists_this_month = 0
    monthly_limit = 3
    if user:
        playlists_this_month = user.get_playlists_this_month()
        if user.is_admin:
            monthly_limit = None  # None represents unlimited for JSON
        else:
            monthly_limit = user.get_monthly_playlist_limit()
    
    return jsonify({
        'authenticated': user is not None,
        'email': user.email if user else None,
        'is_admin': bool(user.is_admin) if user else False,
        'playlists_remaining': user.playlists_remaining if user else 0,
        'subscription_plan': subscription_plan,
        'playlists_this_month': playlists_this_month,
        'monthly_limit': monthly_limit,
        'can_create_playlist': user.can_create_playlist() if user else False,
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
            'playlists_remaining': user.playlists_remaining,
            'is_admin': user.is_admin,
            'subscription_plan': getattr(user, 'subscription_plan', 'trial'),
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
    playlists = data.get('playlists_remaining')
    if playlists is not None:
        try:
            playlists = int(playlists)
        except (TypeError, ValueError):
            return jsonify({'error': 'playlists_remaining must be an integer'}), 400
        user.playlists_remaining = max(0, playlists)

    if 'is_admin' in data and g.user.id != user.id:
        is_admin_value = bool(data.get('is_admin'))
        user.is_admin = is_admin_value
        # Automatically set admins to premium
        if is_admin_value:
            user.subscription_plan = 'premium'
    
    if 'subscription_plan' in data:
        subscription_plan = data.get('subscription_plan', 'trial').lower()
        if subscription_plan in ('trial', 'premium'):
            # Don't allow changing subscription_plan for admins (they're always premium)
            if user.is_admin:
                user.subscription_plan = 'premium'
            else:
                user.subscription_plan = subscription_plan
        else:
            return jsonify({'error': 'subscription_plan must be "trial" or "premium"'}), 400

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

    # Validate prompt length (max 5 sentences)
    mood_sentences = count_sentences(mood)
    if mood_sentences > 5:
        return jsonify({'error': 'Mood description must be 5 sentences or less. Please shorten your description.'}), 400

    # Validate playlist name length (max 5 sentences)
    playlist_name_sentences = count_sentences(playlist_name)
    if playlist_name_sentences > 5:
        return jsonify({'error': 'Playlist name must be 5 sentences or less. Please shorten your playlist name.'}), 400

    # Check monthly playlist limit instead of credits
    if not g.user.can_create_playlist():
        playlists_this_month = g.user.get_playlists_this_month()
        monthly_limit = g.user.get_monthly_playlist_limit()
        if g.user.subscription_plan == 'trial':
            return jsonify({
                'error': f'You have reached your monthly limit of {monthly_limit} playlists. Upgrade to premium for 25 playlists per month.',
                'upgrade_required': True
            }), 403
        else:
            return jsonify({
                'error': f'You have reached your monthly limit of {monthly_limit} playlists.',
                'upgrade_required': False
            }), 403
    
    try:
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({'error': 'Not authenticated with Spotify'}), 401
        
        # Determine how many tracks to request from GPT
        gpt_track_request = track_count
        gpt_track_request = min(gpt_track_request, 100)  # GPT can handle up to 100
        
        # Step 1: Get initial tracks from GPT
        results_dict = get_tracks_from_gpt(mood, gpt_track_request)
        tracks_from_gpt = results_dict.get("tracks", [])
        if not isinstance(tracks_from_gpt, list):
            raise ValueError("Unexpected response format from curator model.")
        
        if not tracks_from_gpt:
            return jsonify({'error': 'No tracks returned from curator model'}), 400
        
        # Step 2: Search Spotify for tracks and collect them
        track_uris = []
        artist_ids = []
        found_tracks = []
        not_found = []
        all_searched_tracks = set()  # Track URIs we've already searched to avoid duplicates
        
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
            
            if matches and matches[0]["uri"] not in all_searched_tracks:
                track_uri = matches[0]["uri"]
                all_searched_tracks.add(track_uri)
                track_uris.append(track_uri)
                # Get artist ID from search results
                if "artist_id" in matches[0]:
                    artist_ids.append(matches[0]["artist_id"])
                found_tracks.append({
                    "artist": matches[0]["artist"],
                    "track": matches[0]["name"],
                    "uri": track_uri
                })
            elif track_name and artist_name:
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

        # Record usage & update playlists remaining
        new_playlists = max(0, g.user.playlists_remaining - 1)
        try:
            g.user.playlists_remaining = new_playlists
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
                g.user.playlists_remaining = new_playlists
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
            'playlists_remaining': new_playlists,
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
    diversity_score = 1 - (entropy / max_entropy if max_entropy > 0 else 0.0)    
    return diversity_score, genre_counts


def get_spotify_recommendations(seed_tracks, access_token, limit=20, min_danceability=None, 
                                max_danceability=None, min_tempo=None, max_tempo=None):
    """
    Get track recommendations from Spotify based on seed tracks and audio feature filters.
    
    Args:
        seed_tracks: List of track IDs to use as seeds (1-5 tracks)
        access_token: Spotify access token
        limit: Number of recommendations (1-100)
        min_danceability, max_danceability: Danceability range (0.0-1.0)
        min_tempo, max_tempo: Tempo range (BPM)
    
    Returns:
        List of recommended tracks with their information
    """
    if not seed_tracks:
        return []
    
    # Spotify allows 1-5 seed tracks
    seed_tracks = seed_tracks[:5]
    limit = max(1, min(100, limit))
    
    url = "https://api.spotify.com/v1/recommendations"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "seed_tracks": ",".join(seed_tracks),
        "limit": limit
    }
    
    # Add audio feature filters if provided
    if min_danceability is not None:
        params["min_danceability"] = min_danceability
    if max_danceability is not None:
        params["max_danceability"] = max_danceability
    if min_tempo is not None:
        params["min_tempo"] = min_tempo
    if max_tempo is not None:
        params["max_tempo"] = max_tempo
    
    try:
        r = spotify_session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
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
                r = spotify_session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                raise Exception("Spotify API request timed out. Please try again.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error connecting to Spotify API: {str(e)}")
        else:
            r.raise_for_status()
    
    r.raise_for_status()
    recommendations_data = r.json().get("tracks", [])
    
    # Format recommendations
    recommendations = []
    for track in recommendations_data:
        recommendations.append({
            "artist": track["artists"][0]["name"] if track.get("artists") else "Unknown",
            "track": track["name"],
            "uri": track["uri"],
            "id": track["id"],
            "artist_id": track["artists"][0]["id"] if track.get("artists") else None
        })
    
    return recommendations


@app.route('/api/my-playlists', methods=['GET'])
@login_required
def get_my_playlists():
    """Get all playlists created by the current user"""
    try:
        playlists = PlaylistUsage.query.filter_by(user_id=g.user.id).order_by(PlaylistUsage.created_at.desc()).all()
        
        playlist_data = []
        access_token = get_valid_access_token()
        
        for usage in playlists:
            if usage.spotify_playlist_id and access_token:
                try:
                    # Get playlist details from Spotify
                    url = f"https://api.spotify.com/v1/playlists/{usage.spotify_playlist_id}"
                    headers = {"Authorization": f"Bearer {access_token}"}
                    r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                    
                    if r.status_code == 401:
                        new_token = refresh_spotify_token()
                        if new_token:
                            headers = {"Authorization": f"Bearer {new_token}"}
                            r = spotify_session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                    
                    if r.status_code == 200:
                        playlist_info = r.json()
                        playlist_data.append({
                            'id': usage.id,
                            'spotify_playlist_id': usage.spotify_playlist_id,
                            'name': playlist_info.get('name', 'Untitled Playlist'),
                            'created_at': usage.created_at.isoformat(),
                            'spotify_url': f"https://open.spotify.com/playlist/{usage.spotify_playlist_id}"
                        })
                except Exception as e:
                    # If we can't fetch from Spotify, still include basic info
                    app.logger.warning(f"Error fetching playlist {usage.spotify_playlist_id}: {str(e)}")
                    playlist_data.append({
                        'id': usage.id,
                        'spotify_playlist_id': usage.spotify_playlist_id,
                        'name': 'Untitled Playlist',
                        'created_at': usage.created_at.isoformat(),
                        'spotify_url': f"https://open.spotify.com/playlist/{usage.spotify_playlist_id}"
                    })
        
        return jsonify({'playlists': playlist_data})
    except Exception as e:
        app.logger.error(f"Error fetching playlists: {str(e)}")
        return jsonify({'error': 'Failed to fetch playlists'}), 500


@app.route('/api/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe Checkout session for subscription"""
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return jsonify({'error': 'Stripe is not configured'}), 500
    
    if g.user.subscription_plan == 'premium':
        return jsonify({'error': 'You already have a premium subscription'}), 400
    
    try:
        # Get or create Stripe customer
        customer_id = g.user.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=g.user.email,
                metadata={'user_id': g.user.id}
            )
            customer_id = customer.id
            g.user.stripe_customer_id = customer_id
            db.session.commit()
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=APP_BASE_URL.rstrip('/') + '/subscription-success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=APP_BASE_URL.rstrip('/') + '/subscription-canceled',
            metadata={
                'user_id': g.user.id
            }
        )
        
        return jsonify({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id
        })
    except stripe.error.StripeError as e:
        app.logger.error(f"Stripe error: {str(e)}")
        return jsonify({'error': f'Stripe error: {str(e)}'}), 500
    except Exception as e:
        app.logger.error(f"Error creating checkout session: {str(e)}")
        return jsonify({'error': 'Failed to create checkout session'}), 500


@app.route('/api/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel the user's Stripe subscription and immediately downgrade to trial"""
    if not STRIPE_SECRET_KEY:
        return jsonify({'error': 'Stripe is not configured'}), 500
    
    if g.user.subscription_plan != 'premium' or not g.user.stripe_subscription_id:
        return jsonify({'error': 'No active subscription found'}), 400
    
    try:
        # Cancel the subscription immediately
        stripe.Subscription.delete(g.user.stripe_subscription_id)
        
        # Immediately downgrade user to trial
        g.user.subscription_plan = 'trial'
        g.user.stripe_subscription_id = None
        db.session.commit()
        
        app.logger.info(f"User {g.user.id} subscription canceled and downgraded to trial")
        
        return jsonify({
            'success': True,
            'message': 'Subscription canceled. You have been downgraded to trial plan (3 playlists per month).'
        })
    except stripe.error.StripeError as e:
        app.logger.error(f"Stripe error: {str(e)}")
        # Even if Stripe fails, downgrade the user locally
        try:
            g.user.subscription_plan = 'trial'
            g.user.stripe_subscription_id = None
            db.session.commit()
            app.logger.info(f"User {g.user.id} downgraded to trial despite Stripe error")
        except Exception as db_error:
            app.logger.error(f"Error updating user: {str(db_error)}")
        return jsonify({'error': f'Stripe error: {str(e)}'}), 500
    except Exception as e:
        app.logger.error(f"Error canceling subscription: {str(e)}")
        return jsonify({'error': 'Failed to cancel subscription'}), 500


@app.route('/api/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        return jsonify({'error': 'Stripe webhook not configured'}), 500
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        app.logger.error(f"Invalid payload: {str(e)}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        app.logger.error(f"Invalid signature: {str(e)}")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('metadata', {}).get('user_id')
        if user_id:
            try:
                user_id = int(user_id)
                user = db.session.get(User, user_id)
                if user:
                    # Get subscription from session
                    subscription_id = session.get('subscription')
                    if subscription_id:
                        user.stripe_subscription_id = subscription_id
                        user.subscription_plan = 'premium'
                        db.session.commit()
                        app.logger.info(f"User {user_id} upgraded to premium")
            except Exception as e:
                app.logger.error(f"Error processing checkout.session.completed: {str(e)}")
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        subscription_id = subscription.get('id')
        status = subscription.get('status')
        
        # Find user by subscription ID
        user = User.query.filter_by(stripe_subscription_id=subscription_id).first()
        if user:
            if status in ('canceled', 'unpaid', 'past_due'):
                user.subscription_plan = 'trial'
                db.session.commit()
                app.logger.info(f"User {user.id} subscription canceled or expired")
            elif status == 'active':
                user.subscription_plan = 'premium'
                db.session.commit()
                app.logger.info(f"User {user.id} subscription activated")
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        subscription_id = subscription.get('id')
        
        # Find user by subscription ID
        user = User.query.filter_by(stripe_subscription_id=subscription_id).first()
        if user:
            user.subscription_plan = 'trial'
            user.stripe_subscription_id = None
            db.session.commit()
            app.logger.info(f"User {user.id} subscription deleted")
    
    return jsonify({'status': 'success'})


@app.route('/subscription-success')
@login_required
def subscription_success():
    """Handle successful subscription payment"""
    session_id = request.args.get('session_id')
    if session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            if checkout_session.payment_status == 'paid':
                # Webhook should have already updated the user, but refresh just in case
                db.session.refresh(g.user)
                return render_template('index.html', user=g.user, subscription_success=True)
        except Exception as e:
            app.logger.error(f"Error retrieving checkout session: {str(e)}")
    
    return render_template('index.html', user=g.user)


@app.route('/subscription-canceled')
@login_required
def subscription_canceled():
    """Handle canceled subscription payment"""
    return render_template('index.html', user=g.user, subscription_canceled=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)

