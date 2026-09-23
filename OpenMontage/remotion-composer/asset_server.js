const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");

const PORT = 18940;
const ASSETS_ROOT = path.resolve(__dirname, "..", "projects", "evs-lesson-8");

const MIME_TYPES = {
  ".mp4": "video/mp4",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".webm": "video/webm",
  ".ogg": "audio/ogg",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".txt": "text/plain",
  ".css": "text/css",
  ".js": "application/javascript",
};

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url || "");
  let pathname = decodeURIComponent(parsedUrl.pathname || "/");

  // Strip leading slash
  pathname = pathname.replace(/^\//, "");

  // Prevent path traversal
  const safePath = path.normalize(pathname).replace(/^(\.\.[\/\\])/g, "");
  const filePath = path.join(ASSETS_ROOT, safePath);

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      res.writeHead(404, { "Access-Control-Allow-Origin": "*" });
      res.end("Not found: " + filePath + " | ASSETS_ROOT=" + ASSETS_ROOT + " | pathname=" + pathname);
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const mimeType = MIME_TYPES[ext] || "application/octet-stream";

    // Support range requests for video/audio
    const range = req.headers.range;
    if (range && (mimeType.startsWith("video/") || mimeType.startsWith("audio/"))) {
      const parts = range.replace(/bytes=/, "").split("-");
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : stats.size - 1;
      const chunkSize = end - start + 1;
      const file = fs.createReadStream(filePath, { start, end });
      res.writeHead(206, {
        "Content-Range": "bytes " + start + "-" + end + "/" + stats.size,
        "Accept-Ranges": "bytes",
        "Content-Length": chunkSize,
        "Content-Type": mimeType,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "range",
      });
      file.pipe(res);
    } else {
      const file = fs.createReadStream(filePath);
      res.writeHead(200, {
        "Content-Type": mimeType,
        "Access-Control-Allow-Origin": "*",
        "Accept-Ranges": "bytes",
      });
      file.pipe(res);
    }
  });
});

server.listen(PORT, () => {
  console.log(`Asset server running at http://localhost:${PORT} serving from ${ASSETS_ROOT}`);
});
