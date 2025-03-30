# --- START OF FILE spotify_functions.py ---
import asyncio
import aiohttp
import time
import random
import json
import os
from collections import defaultdict
from datetime import datetime
import math # For scoring bonuses

# Only import client needed
from spotify_client import get_spotify_client
from lastfm_client import LastFmClient # Needed again for tagging

# --- Constants ---
TAG_CACHE_FILE = "tag_cache.json"
RECOMMENDATION_HISTORY_FILE = "recommendation_history.json"
LASTFM_CONCURRENCY = 5 # Limit concurrent Last.fm requests
TAG_SAMPLE_SIZE = 150 # Increase sample size slightly for tagging
USER_TRACKS_TARGET = 15
RECS_TRACKS_TARGET = 20
TOTAL_TARGET = USER_TRACKS_TARGET + RECS_TRACKS_TARGET

# Mood-Genre Map (Used for search query enhancement)
MOOD_GENRE_MAP = {
    'happy': ['pop', 'dance pop', 'happy', 'summer'],
    'sad': ['sad', 'acoustic', 'emo', 'blues', 'singer-songwriter'],
    'relaxed': ['chill', 'ambient', 'lo-fi', 'acoustic', 'instrumental', 'sleep'],
    'energetic': ['dance', 'electronic', 'energy', 'rock', 'pop punk', 'workout'],
    'angry': ['metal', 'hard rock', 'punk', 'industrial', 'rage'],
    'focused': ['ambient', 'instrumental', 'focus', 'classical', 'minimal-techno'],
    'romantic': ['r-n-b', 'soul', 'love', 'slow jam', 'romantic'],
}


# --- Cache and History Handling (Unchanged) ---
def load_json_cache(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f: return json.load(f)
        except Exception: print(f"Warning: Cache file {filepath} corrupted."); return {}
    return {}

def save_json_cache(filepath, data):
    try:
        with open(filepath, "w") as f: json.dump(data, f, indent=2)
    except Exception as e: print(f"Error saving cache file {filepath}: {e}")

tag_cache = load_json_cache(TAG_CACHE_FILE)
recommendation_history = load_json_cache(RECOMMENDATION_HISTORY_FILE)
if "tracks" not in recommendation_history: recommendation_history = {"tracks": [], "last_updated": None}


# --- Async Last.fm Tag Fetching (Reinstated & Robust) ---
async def fetch_tags_for_track(session, semaphore, track_info):
    """Coroutine to fetch tags for a single track using Last.fm."""
    track_id = track_info.get('id')
    artist_name = None
    # Robust artist name extraction
    artists = track_info.get('artists')
    if artists and isinstance(artists, list) and artists[0]:
        if isinstance(artists[0], dict): artist_name = artists[0].get('name')
        elif isinstance(artists[0], str): artist_name = artists[0] # Should not happen from Spotify direct
    track_name = track_info.get('name')

    if not all([track_id, artist_name, track_name]): return track_id, None

    cache_key = f"{artist_name}|||{track_name}".lower()
    if cache_key in tag_cache: return track_id, tag_cache[cache_key]

    tags = set()
    lastfm = LastFmClient() # Create instance inside coroutine if needed, or pass

    async with semaphore:
        # print(f"Fetching tags: {artist_name} - {track_name}") # Debug
        try:
            # Use the client's methods which now handle rate limiting internally (if implemented there)
            # If not, add asyncio.sleep(LastFmClient.DELAY) here
            await asyncio.sleep(0.1) # Small delay anyway
            track_info_resp = await asyncio.to_thread(lastfm.get_track_info, artist_name, track_name)
            await asyncio.sleep(0.1)
            artist_tags_resp = await asyncio.to_thread(lastfm.get_artist_tags, artist_name)

            if track_info_resp and 'track' in track_info_resp and 'toptags' in track_info_resp['track']:
                 if track_info_resp['track']['toptags'].get('tag'):
                     tags.update(tag['name'].lower() for tag in track_info_resp['track']['toptags']['tag'])

            if artist_tags_resp and 'toptags' in artist_tags_resp:
                 if artist_tags_resp['toptags'].get('tag'):
                     tags.update(tag['name'].lower() for tag in artist_tags_resp['toptags']['tag'])

        except Exception as e:
             print(f"Error fetching tags for {artist_name} - {track_name}: {e}")
             return track_id, None

    final_tags = list(set(t for t in tags if t)) # Clean empty strings and deduplicate
    if final_tags: tag_cache[cache_key] = final_tags
    return track_id, final_tags

async def get_track_tags_async(tracks_to_sample):
    """Fetches tags for a list of tracks asynchronously using LastFmClient methods."""
    if not tracks_to_sample: return {}
    # print(f"Starting async tagging for {len(tracks_to_sample)} tracks...") # Debug
    semaphore = asyncio.Semaphore(LASTFM_CONCURRENCY)
    # No aiohttp session needed if using requests internally in LastFmClient
    tasks = [fetch_tags_for_track(None, semaphore, track) for track in tracks_to_sample] # Pass None for session
    results = await asyncio.gather(*tasks, return_exceptions=True)

    tags_by_track_id = {}
    for i, result in enumerate(results):
        # Use track_info from the original list to ensure correct ID mapping
        track_info = tracks_to_sample[i]
        track_id_input = track_info.get('id')
        if not track_id_input: continue # Skip if input track had no ID

        if isinstance(result, Exception):
            print(f"Task for track ID {track_id_input} failed: {result}")
            tags_by_track_id[track_id_input] = [] # Mark as failed (empty list)
        elif result is not None:
            track_id_result, tags = result
            # Ensure the result corresponds to the input track ID
            if track_id_input == track_id_result:
                if tags is not None: # Success or cache hit
                    tags_by_track_id[track_id_input] = tags
                else: # Explicit failure from fetch_tags_for_track
                    tags_by_track_id[track_id_input] = []
            else:
                # This case should ideally not happen if IDs are handled correctly
                print(f"Warning: Mismatched ID in tag results. Input: {track_id_input}, Result: {track_id_result}")
                tags_by_track_id[track_id_input] = [] # Mark as failed due to mismatch
        else: # Result was None, treat as failure
             tags_by_track_id[track_id_input] = []

    save_json_cache(TAG_CACHE_FILE, tag_cache) # Save updated cache
    # print(f"Finished tagging. Got results for {len(tags_by_track_id)} tracks.") # Debug
    return tags_by_track_id

# --- Spotify Library Fetching (Unchanged) ---
def get_all_user_tracks_simplified():
    sp = get_spotify_client()
    user_id = sp.me()['id']
    all_tracks = []
    all_track_ids = set()
    playlist_limit = 20

    try: # Saved Tracks
        results = sp.current_user_saved_tracks(limit=50)
        while results:
            for item in results.get('items', []):
                track = item.get('track')
                if track and track.get('id') and track['id'] not in all_track_ids:
                    all_track_ids.add(track['id']); track['source'] = 'Saved'; all_tracks.append(track)
            results = sp.next(results) if results.get('next') else None
    except Exception as e: print(f"Error fetching saved tracks: {e}")

    try: # Playlists
        playlists = sp.user_playlists(user_id, limit=playlist_limit)
        if playlists and playlists.get('items'):
            for playlist in playlists['items']:
                if playlist and playlist.get('owner') and playlist['owner'].get('id') == user_id:
                    playlist_id = playlist['id']; playlist_name = playlist.get('name', 'Unnamed')
                    try:
                        fields='items(track(id, name, artists(name), album(name, images), popularity)),next'
                        pl_results = sp.playlist_items(playlist_id, fields=fields, limit=100)
                        while pl_results:
                            for item in pl_results.get('items', []):
                                track = item.get('track')
                                if track and track.get('id') and track['id'] not in all_track_ids:
                                    all_track_ids.add(track['id']); track['source'] = playlist_name; all_tracks.append(track)
                            pl_results = sp.next(pl_results) if pl_results.get('next') else None
                    except Exception as e: print(f"Error fetching items for playlist {playlist_name}: {e}")
    except Exception as e: print(f"Error fetching user playlists: {e}")

    random.shuffle(all_tracks)
    return all_tracks

# --- Spotify Top Artists (For Genre Info) ---
def get_user_top_artists_genres(limit=20, time_range='short_term'):
    """Gets genres from user's top artists."""
    sp = get_spotify_client()
    genres = set()
    try:
        results = sp.current_user_top_artists(limit=limit, time_range=time_range)
        if results and results.get('items'):
            for artist in results['items']:
                genres.update(artist.get('genres', []))
        return list(genres)
    except Exception as e:
        print(f"Error fetching user top artists for genres: {e}")
        return []


# --- Mood Tag Mapping (Unchanged) ---
def map_emotions_to_tags(emotions):
    emotion_tag_map = {
        'joy': ['happy', 'upbeat', 'joyful', 'energetic', 'party', 'summer', 'feel-good', 'uplifting', 'celebratory', 'pop', 'dance'],
        'sadness': ['sad', 'melancholy', 'melancholic', 'emotional', 'heartbreak', 'lonely', 'mellow', 'somber', 'reflective', 'ballad', 'blues', 'acoustic'],
        'anger': ['angry', 'rage', 'intense', 'aggressive', 'heavy', 'metal', 'hard rock', 'punk', 'industrial', 'protest'],
        'excitement': ['upbeat', 'energetic', 'party', 'dance', 'happy', 'uplifting', 'driving', 'fast tempo', 'anthem', 'electronic', 'rock'],
        'fear': ['dark', 'scary', 'intense', 'atmospheric', 'suspenseful', 'horror', 'dissonant', 'eerie', 'anxious', 'ambient'],
        'anxiety': ['tense', 'atmospheric', 'dark', 'experimental', 'intense', 'lo-fi', 'uneasy', 'minimal', 'ambient'],
        'empathic pain': ['emotional', 'sad', 'touching', 'heartbreak', 'ballad', 'acoustic', 'soulful', 'moving'],
        'nostalgia': ['nostalgic', '80s', '90s', 'classic rock', 'retro', 'memories', 'vintage', 'oldies', 'synthwave'],
        'calmness': ['calm', 'relaxing', 'mellow', 'chill', 'ambient', 'peaceful', 'sleep', 'lo-fi', 'acoustic', 'instrumental', 'new age'],
        'awe': ['epic', 'atmospheric', 'beautiful', 'orchestral', 'cinematic', 'soundtrack', 'grandiose', 'majestic', 'post-rock'],
        'romantic': ['love', 'romantic', 'sensual', 'sexy', 'smooth', 'ballad', 'r&b', 'soul', 'slow jam', 'intimate'],
        'satisfaction': ['groove', 'feel-good', 'catchy', 'summer', 'pleasant', 'pop', 'funk', 'soul', 'chillwave', 'content']
    }
    if not emotions: return []
    try: dominant_emotion_name = max(emotions.items(), key=lambda item: item[1])[0]; dominant_score = emotions[dominant_emotion_name]
    except ValueError: return []
    relevant_tags = {}
    for emotion, score in emotions.items():
        if score <= 0: continue
        weight_multiplier = 2.0 if emotion == dominant_emotion_name else (1.5 if score > dominant_score * 0.4 else 1.0)
        if emotion in emotion_tag_map:
            for tag in emotion_tag_map[emotion]: relevant_tags[tag] = relevant_tags.get(tag, 0) + (score * weight_multiplier)
    sorted_tags = sorted(relevant_tags.items(), key=lambda x: x[1], reverse=True)
    return [tag for tag, weight in sorted_tags]


# --- Filtering Logic (Refined Tag Scoring) ---
def filter_tracks_by_mood_tag_score(tracks_with_tags_list, mood_tags, dominant_mood_category):
    """Filters tracks based on tags with improved scoring and negative filtering."""
    scored_tracks = []
    negative_tags_map = {
        'happy': {'sad', 'melancholy', 'melancholic', 'depressing', 'heartbreak', 'angry', 'rage', 'somber'},
        'sad': {'happy', 'joyful', 'party', 'upbeat', 'celebratory', 'cheerful'},
        'relaxed': {'angry', 'rage', 'intense', 'aggressive', 'party', 'loud', 'fast tempo', 'chaotic'},
        'energetic': {'calm', 'relaxing', 'mellow', 'sleep', 'slow tempo', 'peaceful', 'somber'},
        'angry': {'happy', 'joyful', 'calm', 'relaxing', 'peaceful', 'cheerful', 'love', 'romantic'},
        'romantic': {'angry', 'rage', 'aggressive', 'hate', 'breakup', 'platonic'},
    }
    negative_tags = negative_tags_map.get(dominant_mood_category, set())
    if not mood_tags: return []
    mood_tags_len = len(mood_tags)
    # Create a reverse index lookup for quick weight calculation based on position
    mood_tag_weights = {tag: (mood_tags_len - i) / mood_tags_len for i, tag in enumerate(mood_tags)}

    for track in tracks_with_tags_list:
        track_id = track.get('id')
        track_tags_list = track.get('tags')
        if not track_id or track_tags_list is None: continue # Skip tracks without ID or fetched tags
        track_tags = set(track_tags_list)
        if not track_tags: continue

        # --- New Scoring ---
        base_score = 0.0
        num_matches = 0
        highest_match_weight = 0.0
        matched_tags = []

        for tag in track_tags:
            if tag in mood_tag_weights:
                weight = mood_tag_weights[tag]
                base_score += weight
                num_matches += 1
                highest_match_weight = max(highest_match_weight, weight)
                matched_tags.append(tag)

        if num_matches == 0: continue # Skip if no mood tags matched

        # Apply bonuses: logarithmic for quantity, linear for relevance of best match
        quantity_bonus_factor = math.log1p(num_matches) # log(1+N), starts at log(2) for 1 match
        relevance_bonus_factor = highest_match_weight

        # Combine scores (Tune the multipliers: 1.0, 0.5, 0.2 ?)
        tag_score = base_score * (1.0 + quantity_bonus_factor * 0.5) + (relevance_bonus_factor * 0.2)

        # Apply negative penalty
        final_score = tag_score
        intersecting_negative = negative_tags.intersection(track_tags)
        if intersecting_negative:
             penalty_factor = 0.85 # Strong penalty
             final_score *= (1.0 - penalty_factor)
             # print(f"Penalizing {track.get('name')} for {intersecting_negative}. Score: {tag_score:.2f} -> {final_score:.2f}") # Debug

        # Filter based on final score
        if final_score > 0.05: # Threshold slightly higher due to bonuses
            track['mood_score'] = final_score
            scored_tracks.append(track)

    scored_tracks.sort(key=lambda x: x.get('mood_score', 0), reverse=True)
    return scored_tracks


# --- Recommendation Logic (Spotify Search Only - Refined Query) ---
def get_recommendations_spotify_search(mood_tags, user_top_genres, dominant_mood, user_track_ids):
    """Gets recommendations using Spotify search with enhanced query."""
    sp = get_spotify_client()
    recommended_tracks = []
    processed_rec_ids = set()
    search_limit = 50 # Max results per search query
    target_recommendations = 40 # Fetch more candidates than needed

    # --- Build Search Query ---
    query_parts = []
    # 1. Add dominant mood word itself? Sometimes helpful.
    # query_parts.append(dominant_mood) # Optional: Test if this helps or hurts

    # 2. Add Top 1-2 specific mood tags (keywords)
    query_parts.extend(mood_tags[:2])

    # 3. Add 1-2 relevant genres derived from user's top genres
    relevant_mood_genres = MOOD_GENRE_MAP.get(dominant_mood, [])
    found_genres = 0
    if relevant_mood_genres and user_top_genres:
        user_top_genres_set = set(user_top_genres) # Faster lookups
        for mood_genre in relevant_mood_genres:
             # Check if mood_genre exists (partially or fully) in user's genres
             if mood_genre in user_top_genres_set or any(mood_genre in top_g for top_g in user_top_genres_set):
                  # Prefer specific genres from user's list if possible
                  matched_user_genre = mood_genre # Default
                  for top_g in user_top_genres_set:
                       if mood_genre in top_g:
                           matched_user_genre = top_g # Use the more specific user genre
                           break
                  if matched_user_genre not in query_parts: # Avoid duplicates
                      query_parts.append(matched_user_genre)
                      found_genres += 1
                      if found_genres >= 2: break # Limit added genres

    search_query = " ".join(filter(None, query_parts)) # Ensure no empty strings

    if not search_query:
        print("Warning: Could not build a search query for recommendations.")
        return []

    previously_recommended = set(recommendation_history.get("tracks", []))

    try:
        results = sp.search(q=search_query, type='track', limit=search_limit, market='from_token')
        time.sleep(0.1)
    except Exception as e:
        print(f"Spotify search failed for query '{search_query}': {e}")
        return []

    if results and results.get('tracks') and results['tracks'].get('items'):
        for track in results['tracks']['items']:
            if len(recommended_tracks) >= target_recommendations: break
            track_id = track.get('id')
            if not track_id: continue

            # Filter against ENTIRE user library + history + current batch
            if track_id in user_track_ids or \
               track_id in previously_recommended or \
               track_id in processed_rec_ids:
                continue

            # Basic popularity filter (optional, adjust threshold 5-15)
            if track.get('popularity', 0) < 7:
                 continue

            # Format track data consistently
            album_data = track.get('album', {})
            album_images = album_data.get('images', [])
            artist_list = track.get('artists', [])
            rec_track_data = {
                "id": track_id,
                "name": track.get('name', 'Unknown Track'),
                "artists": [a.get('name', 'Unknown Artist') for a in artist_list], # List of names
                "album": album_data.get('name', ''),
                "album_image": album_images[0]["url"] if album_images else "",
                "tags": mood_tags[:2] # Store tags used in search
            }
            recommended_tracks.append(rec_track_data)
            processed_rec_ids.add(track_id)

    # Update recommendation history
    recommendation_history["tracks"] = list(previously_recommended.union(processed_rec_ids))
    recommendation_history["last_updated"] = datetime.now().isoformat()
    save_json_cache(RECOMMENDATION_HISTORY_FILE, recommendation_history)

    random.shuffle(recommended_tracks)
    return recommended_tracks


# --- Playlist Creation (Mostly Unchanged logic) ---
def create_mood_playlist(mood_tracks, recommended_tracks, mood_name):
    # (Logic is the same as the previous correct version, ensure safety checks)
    sp = get_spotify_client()
    user_id = sp.me()['id']
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    playlist_name = f"{mood_name.capitalize()} Mood - {date_str}"
    playlist_description = f"Songs matching your {mood_name} mood, created on {date_str}."

    try:
        playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False, description=playlist_description)
        playlist_id = playlist['id']; playlist_url = playlist['external_urls']['spotify']
    except Exception as e: print(f"Error creating Spotify playlist: {e}"); return None, None

    final_tracks_added_objects = []; final_track_ids_added = set()
    artists = defaultdict(int); albums = defaultdict(int)

    # 1. Add User Tracks (Sorted by new tag score)
    user_added = 0
    for track in mood_tracks:
        if user_added >= USER_TRACKS_TARGET: break
        track_id = track.get('id')
        if not track_id or track_id in final_track_ids_added: continue
        artist_list = track.get('artists', [])
        primary_artist_name = artist_list[0].get('name') if artist_list and isinstance(artist_list[0], dict) else (artist_list[0] if artist_list and isinstance(artist_list[0], str) else None)
        album_data = track.get('album', {})
        album_name = album_data.get('name', '') if isinstance(album_data, dict) else album_data

        if not primary_artist_name: continue
        if artists[primary_artist_name] >= 2 or (album_name and albums[album_name] >= 2): continue

        final_tracks_added_objects.append(track); final_track_ids_added.add(track_id); user_added += 1
        artists[primary_artist_name] += 1;
        if album_name: albums[album_name] += 1

    # 2. Add Recommended Tracks
    recs_added = 0
    for track in recommended_tracks: # Assumes list of dicts from search
        if user_added + recs_added >= TOTAL_TARGET: break
        track_id = track.get('id')
        if not track_id or track_id in final_track_ids_added: continue
        # Artist names should be strings already from search processing
        artist_list = track.get('artists', []) # List of strings
        primary_artist_name = artist_list[0] if artist_list else None
        album_name = track.get('album', '') # Simple string

        if not primary_artist_name: continue
        if artists[primary_artist_name] >= 2 or (album_name and albums[album_name] >= 2): continue

        # Track structure should be consistent now
        final_tracks_added_objects.append(track); final_track_ids_added.add(track_id); recs_added += 1
        artists[primary_artist_name] += 1;
        if album_name: albums[album_name] += 1

    random.shuffle(final_tracks_added_objects)
    track_uris_to_add = [f"spotify:track:{t['id']}" for t in final_tracks_added_objects if t.get('id')]

    if track_uris_to_add:
        try:
            for i in range(0, len(track_uris_to_add), 100):
                sp.playlist_add_items(playlist_id, track_uris_to_add[i:i+100]); time.sleep(0.1)
        except Exception as e: print(f"Error adding items to playlist {playlist_id}: {e}"); return playlist, []
    else: print("No tracks selected after filtering.")
    return playlist, final_tracks_added_objects
