import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_spotify_client():
    """Create and return an authenticated Spotify client"""
    scope = (
        "playlist-read-private playlist-read-collaborative "
        "playlist-modify-public playlist-modify-private "
        "user-library-modify user-library-read "
        "user-top-read "
        "user-read-private"  
    )
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=scope,
        cache_path=".spotify_cache"
    ))
    
    return sp

