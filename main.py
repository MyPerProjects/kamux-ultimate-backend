import os
from fastapi import FastAPI, HTTPException, Query
from ytmusicapi import YTMusic

# 1. Inicializamos FastAPI
app = FastAPI(
    title="Kamux Ultimate API",
    description="Backend Proxy personalizado para el reproductor Kamux Ultimate",
    version="1.0.0"
)

# 2. Definimos la ruta del archivo de autenticación seguro
AUTH_FILE = "browser.json"

if not os.path.exists(AUTH_FILE):
    print(f"[ERROR] No se encontró el archivo {AUTH_FILE} necesario para la autenticación.")
    yt = None
else:
    try:
        yt = YTMusic(AUTH_FILE)
        print("[ÉXITO] Sesión de YouTube Music inicializada correctamente.")
    except Exception as e:
        print(f"[ERROR] Falló la inicialización de YTMusic: {e}")
        yt = None


# 3. Endpoint: Obtener el Home Personalizado limpio
@app.get("/api/home", summary="Obtener secciones personalizadas del Home")
def get_custom_home():
    """
    Filtra el Home masivo de YouTube Music y devuelve únicamente las filas 
    críticas para el usuario: 'Listen again' y 'Quick picks'.
    """
    if not yt:
        raise HTTPException(status_code=500, detail="La sesión no está inicializada.")
    
    try:
        full_home = yt.get_home(limit=5)
        secciones_interesantes = ["Listen again", "Quick picks", "Volver a escuchar", "Selección rápida"]
        home_filtrado = []
        
        for fila in full_home:
            title = fila.get("title", "")
            if any(x.lower() in title.lower() for x in secciones_interesantes):
                home_filtrado.append(fila)
                
        return {"status": "success", "count": len(home_filtrado), "data": home_filtrado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en servidores de Google: {str(e)}")


# 4. Endpoint: Obtener la Cola de Reproducción Inteligente (Radio)
@app.get("/api/queue", summary="Generar cola de reproducción automática")
def get_playlist_queue(video_id: str = Query(..., alias="videoId", description="ID de la canción base")):
    """
    Recibe el videoId de una canción y le pide a YouTube Music que genere la 
    lista de reproducción automática infinita (Radio) combinando algoritmos.
    Devuelve también el ID para solicitar las letras si están disponibles.
    """
    if not yt:
        raise HTTPException(status_code=500, detail="La sesión no está inicializada.")
    
    try:
        # Generamos la lista automática con un límite inicial estándar de 25 tracks
        watch_playlist = yt.get_watch_playlist(videoId=video_id, limit=25)
        
        return {
            "status": "success",
            "playlistId": watch_playlist.get("playlistId"),
            "lyricsId": watch_playlist.get("lyrics"), # ID para consumir en /api/lyrics
            "tracks": watch_playlist.get("tracks", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar la radio: {str(e)}")


# 5. Endpoint: Obtener las Letras en Texto Plano
@app.get("/api/lyrics", summary="Obtener la letra de un track")
def get_track_lyrics(lyrics_id: str = Query(..., alias="lyricsId", description="ID de letras obtenido de la cola")):
    """
    Recibe el lyricsId (que inicia con MPLYt...) devuelto por la cola de 
    reproducción y extrae la letra limpia en texto plano para la UI móvil.
    """
    if not yt:
        raise HTTPException(status_code=500, detail="La sesión no está inicializada.")
    
    try:
        lyrics_data = yt.get_lyrics(browseId=lyrics_id)
        
        if not lyrics_data:
            return {"status": "success", "source": None, "lyrics": "Este tema no tiene letras disponibles."}
            
        return {
            "status": "success",
            "source": lyrics_data.get("source"),
            "lyrics": lyrics_data.get("lyrics", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al extraer letras: {str(e)}")
