# Kamux Ultimate Backend

Backend y Proxy de Streaming de alto rendimiento para el reproductor musical Kamux Ultimate. Diseñado para evadir restricciones de red, gestionar metadatos de YouTube Music y entregar audio en calidad óptima sin cortes.

## Arquitectura del Sistema

El backend está compuesto por dos microservicios que operan en conjunto:

1. **Kamux Ultimate API (Python / FastAPI):** Se encarga de toda la lógica de metadatos, gestión de sesiones, extracción de colas de reproducción, búsquedas en el catálogo y sincronización de letras a través de LRCLIB.
2. **Kamux Stream Proxy (Node.js / Express):** Un motor de streaming basado en la arquitectura de "Descarga de Carrete Local" (Local Disk Spooling). Utiliza `yt-dlp` a través de un túnel SOCKS5 para descargar el medio físicamente al servidor y servirlo al cliente, evadiendo el estrangulamiento (throttling) de red y permitiendo saltos de tiempo instantáneos.

## Características Principales

* **Local Disk Spooling:** Descarga temporal de medios en el almacenamiento local (`/tmp`) para un streaming fluido, lectura de rangos (HTTP 206) inmediata y soporte nativo para ExoPlayer.
* **Garbage Collector Integrado:** El proxy de Node.js limpia automáticamente los archivos de audio en caché que superan los 30 minutos de antigüedad, previniendo la saturación del almacenamiento.
* **Evasión de Bloqueos (Throttling):** Uso de túneles SOCKS5 y `yt-dlp` para evitar baneos de IP en centros de datos y evadir los límites de velocidad de 12 KB/s de YouTube.
* **Pipeline de Letras Inteligente:** Búsqueda y formato automático de letras sincronizadas y planas utilizando LRCLIB, con múltiples capas de contingencia (búsqueda exacta, difusa e invertida).
* **Candados de Descarga (Promise Locking):** Prevención de descargas duplicadas simultáneas para la misma pista, optimizando el uso del procesador y el ancho de banda.

## Requisitos Previos

Para ejecutar este entorno de producción, el servidor debe contar con:
* Python 3.9 o superior.
* Node.js 18 o superior.
* `yt-dlp` instalado globalmente y actualizado.
* Un túnel SOCKS5 activo (ej. en el puerto 40000).
* Archivos de autenticación válidos: `browser.json` (para ytmusicapi) y `cookies.txt` (para yt-dlp).

## Instalación y Configuración

**1. Clonar el repositorio**
git clone https://github.com/TuUsuario/kamux-ultimate-backend.git
cd kamux-ultimate-backend

**2. Configurar la API (Python)**
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn ytmusicapi httpx unidecode

**3. Configurar el Proxy de Streaming (Node.js)**
npm install express axios socks-proxy-agent

**4. Autenticación (No rastreada en Git)**
* Genera tu archivo `browser.json` siguiendo la documentación oficial de `ytmusicapi`.
* Exporta tus cookies de YouTube a un archivo llamado `cookies.txt` en formato Netscape.
* Asegúrate de ubicar ambos archivos en la raíz del proyecto.

## Uso y Ejecución

Se recomienda el uso de un gestor de procesos como `pm2` para mantener los servicios activos en segundo plano en entornos de producción.

**Iniciar la API de Metadatos (Puerto por defecto: 8000)**
uvicorn main:app --host 0.0.0.0 --port 8000

**Iniciar el Proxy de Streaming (Puerto por defecto: 5002)**
node stream-proxy.js

## Estructura de Endpoints Principales

* `GET /api/home`: Obtiene las secciones personalizadas del inicio.
* `GET /api/queue`: Genera una cola de reproducción a partir de un `videoId` o `playlistId`.
* `GET /api/search`: Búsqueda global de canciones, artistas y álbumes.
* `GET /api/lyrics`: Retorna letras sincronizadas procesadas.
* `GET /api/stream`: Proxy de descarga y transmisión de audio (Requiere `video_id`).

## Seguridad

Este repositorio está configurado para excluir estrictamente las credenciales de sesión (`browser.json`, `cookies.txt`) y entornos virtuales. Nunca expongas estos archivos públicamente, ya que otorgan acceso directo a la cuenta de Google asociada.