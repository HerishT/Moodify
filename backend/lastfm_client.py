import requests
import os
from dotenv import load_dotenv

load_dotenv()

class LastFmClient:
    def __init__(self):
        self.api_key = os.getenv("LASTFM_API_KEY")
        self.base_url = "https://ws.audioscrobbler.com/2.0/"
        
    def get_track_info(self, artist, track):
        """Get track info including tags from Last.fm"""
        params = {
            'method': 'track.getInfo',
            'api_key': self.api_key,
            'artist': artist,
            'track': track,
            'format': 'json',
            'autocorrect': 1
        }
        
        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_artist_tags(self, artist):
        """Get top tags for an artist from Last.fm"""
        params = {
            'method': 'artist.getTopTags',
            'api_key': self.api_key,
            'artist': artist,
            'format': 'json',
            'autocorrect': 1
        }
        
        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_similar_tracks(self, artist, track, limit=50):
        """Get similar tracks based on a seed track"""
        params = {
            'method': 'track.getSimilar',
            'api_key': self.api_key,
            'artist': artist,
            'track': track,
            'limit': limit,
            'format': 'json',
            'autocorrect': 1
        }
        
        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            return response.json()
        return None

    def get_tag_top_tracks(self, tag, limit=50):
        """Get top tracks for a specific tag"""
        params = {
            'method': 'tag.getTopTracks',
            'tag': tag,
            'limit': limit,
            'api_key': self.api_key,
            'format': 'json'
        }
        
        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
