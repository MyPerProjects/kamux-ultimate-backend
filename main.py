import asyncio
import os
import httpx
import re
import unidecode
from fastapi import FastAPI, Query, HTTPException
from ytmusicapi import YTMusic

app = FastAPI(
    title="Kamux Ultimate API",
    description="Backend Proxy for Kamux Ultimate Player",
    version="1.0.0"
)

AUTH_FILE = "browser.json"

if not os.path.exists(AUTH_FILE):
    print(f"[ERROR] Auth file {AUTH_FILE} not found.")
    yt = None
else:
    try:
        yt = YTMusic(AUTH_FILE)
        print("[INFO] YTMusic session initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize YTMusic: {e}")
        yt = None

@app.get("/api/home")
def get_custom_home():
    if not yt:
        raise HTTPException(status_code=500, detail="Session not initialized.")
    try:
        full_home = yt.get_home(limit=25)
        target_sections = ["Listen again", "Quick picks", "Volver a escuchar", "Selección rápida"]
        filtered_home = [row for row in full_home if any(x.lower() in row.get("title", "").lower() for x in target_sections)]
        return {"status": "success", "count": len(filtered_home), "data": filtered_home}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Server Error: {str(e)}")

@app.get("/api/queue")
def get_playlist_queue(
    video_id: str = Query(None, alias="videoId"),
    playlist_id: str = Query(None, alias="playlistId")
):
    if not yt:
        raise HTTPException(status_code=500, detail="Session not initialized.")
    if not video_id and not playlist_id:
        raise HTTPException(status_code=400, detail="Must provide videoId or playlistId.")
    try:
        watch_playlist = yt.get_watch_playlist(videoId=video_id, playlistId=playlist_id, limit=25)
        return {
            "status": "success",
            "playlistId": watch_playlist.get("playlistId"),
            "lyricsId": watch_playlist.get("lyrics"),
            "tracks": watch_playlist.get("tracks", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue extraction error: {str(e)}")

def sanitize_artist(artist: str) -> str:
    if not artist: return ""
    clean = re.sub(r'\s*-\s*Topic$', '', artist, flags=re.IGNORECASE)
    clean = re.sub(r'\s*-\s*Tema$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+oficial$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+official$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+music$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+vevo$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+band$', '', clean, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', clean).strip()

def sanitize_title(title: str, clean_artist: str) -> str:
    if not title: return ""
    clean = re.sub(r'[\(\[][^]*?(?:official|video|remaster|remastered|remix|hd|4k|lyric|letra|clip|ft|feat|full|audio|hq|bonus track)[^]*?[\)\]]', '', title, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?remastered\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?bonus track\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?official music video\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?official video\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?video oficial\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?audio\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?lyric video\)?', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\(?letra\)?', '', clean, flags=re.IGNORECASE)
    clean = clean.replace("...", " ")

    if ' - ' in clean:
        parts = clean.split(' - ')
        if len(parts) >= 2:
            first_part = parts[0].strip().lower()
            artist_lower = clean_artist.lower()
            if artist_lower in first_part or first_part in artist_lower:
                clean = ' - '.join(parts[1:])
                
    return re.sub(r'\s+', ' ', clean).strip()

def parse_lrclib_format(synced_lyrics: str) -> list:
    formatted_lyrics = []
    for line in synced_lyrics.split('\n'):
        match = re.match(r'\[(\d{2}):(\d{2}\.\d{2,3})\](.*)', line)
        if match:
            m, s, text = match.groups()
            formatted_lyrics.append({
                "text": text.strip() if text.strip() else "...",
                "startTimeMs": int(m) * 60000 + int(float(s) * 1000),
                "endTimeMs": 0 
            })
    return formatted_lyrics

@app.get("/api/lyrics")
async def get_track_lyrics(track_name: str = Query(...), artist_name: str = Query(...)):
    clean_artist = sanitize_artist(artist_name)
    clean_title = sanitize_title(track_name, clean_artist)
    headers = {'User-Agent': 'KamuxUltimate/1.0 (Android; Python/FastAPI)'}

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        def format_success_response(best_match):
            synced = best_match.get("syncedLyrics")
            plain = best_match.get("plainLyrics")
            if synced and synced.strip():
                return {"status": "success", "hasTimestamps": True, "source": "LRCLIB Premium", "lyricsLines": parse_lrclib_format(synced)}
            elif plain and plain.strip():
                return {"status": "success", "hasTimestamps": False, "source": "LRCLIB Plano", "lyrics": plain}
            return None

        def find_best_synced_match(results):
            if not results: return None
            for track in results:
                if track.get("syncedLyrics") and track.get("syncedLyrics").strip():
                    return track
            return results[0]

        # Process 1: Exact structured match
        try:
            response = await client.get(f"https://lrclib.net/api/get?artist_name={clean_artist}&track_name={clean_title}")
            if response.status_code == 200 and response.json():
                return format_success_response(response.json())
        except Exception as e:
            print(f"[ERROR] LRCLIB Fetch exact match failed: {str(e)}")

        await asyncio.sleep(0.6)

        # Process 2: Fuzzy search match
        try:
            raw_query = re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9\s]', ' ', unidecode.unidecode(f"{clean_title} {clean_artist}").upper())).strip()
            response = await client.get(f"https://lrclib.net/api/search?q={raw_query}")
            if response.status_code == 200 and response.json():
                best = find_best_synced_match(response.json())
                if best: return format_success_response(best)
        except Exception as e:
            print(f"[ERROR] LRCLIB Fuzzy search failed: {str(e)}")

        await asyncio.sleep(0.6)

        # Process 3: Inverted fuzzy search match
        try:
            inv_query = re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9\s]', ' ', unidecode.unidecode(f"{clean_artist} {clean_title}").upper())).strip()
            response = await client.get(f"https://lrclib.net/api/search?q={inv_query}")
            if response.status_code == 200 and response.json():
                best = find_best_synced_match(response.json())
                if best: return format_success_response(best)
        except Exception as e:
            print(f"[ERROR] LRCLIB Inverted search failed: {str(e)}")

    return {"status": "success", "hasTimestamps": False, "source": None, "lyrics": "Lyrics not found in LRCLIB."}

@app.get("/api/search/suggestions")
def get_search_suggestions(query: str = Query(..., min_length=1)):
    if not yt: raise HTTPException(status_code=500, detail="Session not initialized.")
    try:
        return {"status": "success", "data": yt.get_search_suggestions(query, detailed_runs=False)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestions error: {str(e)}")

@app.get("/api/search")
def search_catalog(query: str = Query(..., min_length=1)):
    if not yt: raise HTTPException(status_code=500, detail="Session not initialized.")
    try:
        combined_results = []
        for filter_type, limit in [("songs", 15), ("artists", 3), ("albums", 4)]:
            try:
                combined_results.extend(yt.search(query, filter=filter_type, limit=limit))
            except Exception as e:
                print(f"[WARN] Search partial failure ({filter_type}): {e}")

        if not combined_results:
            raise HTTPException(status_code=500, detail="No results found.")
        return {"status": "success", "count": len(combined_results), "data": combined_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Global search error: {str(e)}")

@app.get("/api/album")
def get_album_details(browse_id: str = Query(..., alias="browseId")):
    if not yt: raise HTTPException(status_code=500, detail="Session not initialized.")
    try:
        return {"status": "success", "data": yt.get_album(browse_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Album extraction error: {str(e)}")

@app.get("/api/artist")
def get_artist_details(browse_id: str = Query(..., alias="browseId")):
    if not yt: raise HTTPException(status_code=500, detail="Session not initialized.")
    try:
        return {"status": "success", "data": yt.get_artist(browse_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Artist extraction error: {str(e)}")

@app.get("/api/artist/albums")
def get_all_artist_albums(
    channel_id: str = Query(..., alias="channelId"),
    params: str = Query(...)
):
    if not yt: raise HTTPException(status_code=500, detail="Session not initialized.")
    try:
        return {"status": "success", "data": yt.get_artist_albums(channelId=channel_id, params=params)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Artist albums extraction error: {str(e)}")
