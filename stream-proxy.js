const express = require("express");
const { exec } = require("child_process");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = 5002;
const PROXY_URL = "socks5://127.0.0.1:40000";
const CACHE_DIR = "/tmp/kamux_cache";

if (!fs.existsSync(CACHE_DIR)) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
}

setInterval(() => {
  const now = Date.now();
  fs.readdir(CACHE_DIR, (err, files) => {
    if (err) return;
    files.forEach(file => {
      const filePath = path.join(CACHE_DIR, file);
      fs.stat(filePath, (err, stats) => {
        if (err) return;
        if (now - stats.mtimeMs > 30 * 60 * 1000) {
          fs.unlink(filePath, () => console.log(`[INFO] Garbage Collector: Removed stale cache file ${file}`));
        }
      });
    });
  });
}, 10 * 60 * 1000);

const downloadLocks = {};

function downloadAudioLocally(videoId) {
  if (downloadLocks[videoId]) {
    return downloadLocks[videoId];
  }

  const promise = new Promise((resolve, reject) => {
    const filePath = path.join(CACHE_DIR, `${videoId}.media`);
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;

    const cleanEnv = Object.assign({}, process.env);
    delete cleanEnv.NODE_CHANNEL_FD;
    delete cleanEnv.PM2_USAGE;

    const cmd = `yt-dlp --no-warnings --no-update --no-cache-dir --proxy "${PROXY_URL}" -f "251/140/250/249/ba" --cookies ./cookies.txt -o "${filePath}" "${videoUrl}"`;

    exec(cmd, { env: cleanEnv }, (error, stdout, stderr) => {
      delete downloadLocks[videoId];

      if (error) {
        console.error(`[ERROR] yt-dlp failed for video ${videoId}: ${stderr}`);
        if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
        return reject(error);
      }

      resolve(filePath);
    });
  });

  downloadLocks[videoId] = promise;
  return promise;
}

app.all("/api/stream", async (req, res) => {
  const videoId = req.query.video_id;
  if (!videoId) return res.status(400).json({ error: "Missing video_id parameter" });

  const filePath = path.join(CACHE_DIR, `${videoId}.media`);

  try {
    if (!fs.existsSync(filePath)) {
      await downloadAudioLocally(videoId);
    }

    res.sendFile(filePath, {
      headers: {
        'Content-Type': 'audio/mp4',
        'Accept-Ranges': 'bytes'
      }
    });

  } catch (err) {
    res.status(500).json({ error: "Internal server error processing media download." });
  }
});

app.listen(PORT, () => {
  console.log(`[INFO] Kamux Stream Proxy (Local Spooling) initialized on port ${PORT}`);
});
