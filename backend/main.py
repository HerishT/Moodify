# --- START OF FILE main.py ---
import json
import sys
import os
import asyncio # Keep asyncio for running the tagging coroutine
import time
from datetime import datetime
from collections import defaultdict
import random
import traceback

from sentiment_analysis import analyze_sentiment
from spotify_client import get_spotify_client
from spotify_functions import (
    get_all_user_tracks_simplified,
    get_track_tags_async, # Use async tagging again
    map_emotions_to_tags,
    filter_tracks_by_mood_tag_score, # Use the tag scoring filter
    get_user_top_artists_genres, # Get genres for recommendations
    get_recommendations_spotify_search, # Use search recommendations
    create_mood_playlist,
    TAG_SAMPLE_SIZE,
    RECS_TRACKS_TARGET # Keep needed constants
)

# --- Mood Determination (Unchanged) ---
def get_dominant_mood(emotions):
    mood_categories = {
        'happy': ['joy', 'excitement', 'amusement', 'satisfaction'],
        'sad': ['sadness', 'empathic pain', 'nostalgia'],
        'relaxed': ['calmness', 'relief', 'satisfaction'],
        'energetic': ['excitement', 'surprise', 'entrancement'],
        'angry': ['anger', 'disgust', 'fear'],
        'focused': ['interest', 'entrancement', 'awe'],
        'romantic': ['romance', 'adoration', 'aesthetic appreciation']
    }
    if not emotions: return "neutral"
    mood_max_scores = {mood: 0 for mood in mood_categories}
    for mood, emotion_list in mood_categories.items():
        max_score_for_mood = 0
        for emotion_name in emotion_list:
            score = emotions.get(emotion_name, 0)
            if score > max_score_for_mood: max_score_for_mood = score
        mood_max_scores[mood] = max_score_for_mood
    if all(score < 0.01 for score in mood_max_scores.values()):
        if emotions:
             try: top_emotion = max(emotions.items(), key=lambda item: item[1])[0]
             except ValueError: return "neutral"
             for mood, e_list in mood_categories.items():
                  if top_emotion in e_list: return mood
        return "neutral"
    dominant_mood = max(mood_max_scores.items(), key=lambda item: item[1])[0]
    return dominant_mood

# --- Album Image Helper (Unchanged) ---
def get_album_image(track):
    try:
        if 'album_image' in track and track['album_image']: return track['album_image']
        elif 'album' in track and isinstance(track['album'], dict):
            images = track['album'].get('images', [])
            if images and isinstance(images, list) and len(images) > 0:
                 for img in images:
                      if isinstance(img, dict) and img.get('url'): return img['url']
    except Exception: pass
    return "https://place-hold.it/300x300"

# --- Main Execution Logic (Async Aware for Tagging) ---
async def async_main():
    start_time = time.time()
    result = {}
    try:
        user_text = os.environ.get('USER_TEXT') or (" ".join(sys.argv[1:]) if len(sys.argv) > 1 else None)
        if not user_text: return {"error": "No mood text provided"}

        emotions = analyze_sentiment(user_text)
        if "error" in emotions: return {"error": f"Sentiment analysis failed: {emotions['error']}"}
        dominant_mood = get_dominant_mood(emotions)
        emotion_tags = map_emotions_to_tags(emotions) # Needed for filtering & search query

        # --- Fetch User Library Sample & All IDs ---
        # Get sample for tagging + full list for filtering recs
        user_library_tracks_sample = get_all_user_tracks_simplified() # Gets shuffled list
        if not user_library_tracks_sample: return {"error": "Could not fetch tracks from Spotify library."}
        # Get ALL user track IDs efficiently for filtering recommendations later
        # We might need a slightly different function for just IDs if get_all_user_tracks_simplified is too slow for full library
        # For now, assume simplified is fast enough to get all IDs from that subset
        user_track_ids = {t['id'] for t in user_library_tracks_sample if t.get('id')}

        # --- Async Tagging ---
        tracks_to_tag = user_library_tracks_sample[:TAG_SAMPLE_SIZE]
        tagging_start = time.time()
        tags_by_track_id = await get_track_tags_async(tracks_to_tag)
        tagging_duration = time.time() - tagging_start

        # Add tags to the sample list
        tracks_with_tags_list = []
        for track in tracks_to_tag:
             track_id = track.get('id')
             # Only include tracks where we got tags (or tried and failed - empty list)
             if track_id in tags_by_track_id:
                 track['tags'] = tags_by_track_id[track_id]
                 tracks_with_tags_list.append(track)

        # --- Filter User Tracks (Using New Tag Score) ---
        mood_matched_user_tracks = filter_tracks_by_mood_tag_score(
            tracks_with_tags_list,
            emotion_tags,
            dominant_mood
        )

        # --- Get User Genres for Recs ---
        user_top_genres = get_user_top_artists_genres(limit=20)

        # --- Get Recommendations (Search Only) ---
        recommended_tracks = get_recommendations_spotify_search(
            emotion_tags,
            user_top_genres,
            dominant_mood,
            user_track_ids # Pass the set of user track IDs
        )

        # --- Create Playlist ---
        if not mood_matched_user_tracks and not recommended_tracks:
            return {"error": "Couldn't find enough relevant tracks to create a playlist."}

        playlist_info, final_tracks_added = create_mood_playlist(
            mood_matched_user_tracks, # Pass tag-scored tracks
            recommended_tracks,
            dominant_mood
        )

        if not playlist_info: return {"error": "Failed to create Spotify playlist."}

        # --- Format Output ---
        formatted_tracks = []
        if final_tracks_added:
            for track in final_tracks_added:
                 artist_names = track.get('artists', [])
                 # Ensure artists is list of strings
                 if artist_names and not isinstance(artist_names[0], str):
                      artist_names = [a if isinstance(a, str) else (a.get('name', '?') if isinstance(a, dict) else '?') for a in artist_names]
                 elif not artist_names: artist_names = ['?']

                 formatted_tracks.append({
                    "id": track.get('id'), "name": track.get('name', '?'),
                    "artists": artist_names,
                    "album": track.get('album', {}).get('name', '') if isinstance(track.get('album'), dict) else track.get('album', ''),
                    "albumImageUrl": get_album_image(track)
                 })

        result = {
            "tracks": formatted_tracks,
            "spotify_url": playlist_info['external_urls']['spotify'],
            "dominant_mood": dominant_mood
        }

    except Exception as e:
        print(f"An unexpected error occurred in async_main: {str(e)}\n{traceback.format_exc()}", file=sys.stderr)
        result = {"error": f"An unexpected error occurred: {str(e)}"}

    total_duration = time.time() - start_time
    return result

if __name__ == "__main__":
    final_result = asyncio.run(async_main())
    print(json.dumps(final_result))
