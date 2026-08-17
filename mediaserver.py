"""Serves local video files and extracted frames to the GUI over HTTP.

The page itself is served from http://localhost by pywebview, and a browser
refuses to load file:// resources from an http:// document - which is why the
video preview stayed black. This little server hands the same files back over
http, with Range support so the player can seek.

Only files explicitly registered by the app are reachable; the handler never
takes a filesystem path from the URL.
"""

import os
import re
import json
import time
import hashlib
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(BASE_DIR, "ffmpeg", "ffmpeg.exe")
FFPROBE = os.path.join(BASE_DIR, "ffmpeg", "ffprobe.exe")
FRAME_CACHE = os.path.join(BASE_DIR, "cache", "frames")

CONTENT_TYPES = {
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".webm": "video/webm", ".avi": "video/x-msvideo",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".ttf": "font/ttf", ".otf": "font/otf", ".ttc": "font/collection",
}

_registry = {}          # token -> absolute path
_registry_lock = threading.Lock()
_info_cache = {}


def _no_window():
    """Keeps ffmpeg/ffprobe from flashing a console window."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return si


def register(path):
    """Makes a local file reachable and returns its opaque token."""
    path = os.path.abspath(path)
    token = hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]
    with _registry_lock:
        _registry[token] = path
    return token


def resolve(token):
    with _registry_lock:
        return _registry.get(token)


def probe(path):
    """Returns {width, height, duration, fps} for a video, cached by mtime."""
    path = os.path.abspath(path)
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return {}
    if key in _info_cache:
        return _info_cache[key]

    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate",
             "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30, startupinfo=_no_window(),
        )
        data = json.loads(out.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        num, _, den = (stream.get("r_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den) if den and float(den) else 0.0
        info = {
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "duration": float((data.get("format") or {}).get("duration") or 0),
            "fps": round(fps, 3),
        }
    except Exception:
        info = {}

    _info_cache[key] = info
    return info


def extract_frame(path, at_seconds=None):
    """Grabs one representative frame, cached on disk. Returns its file path."""
    path = os.path.abspath(path)
    info = probe(path)
    if at_seconds is None:
        duration = info.get("duration") or 0
        at_seconds = round(duration / 3, 2) if duration else 0.0

    os.makedirs(FRAME_CACHE, exist_ok=True)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = 0
    digest = hashlib.sha1(f"{path}|{stamp}|{at_seconds}".encode("utf-8")).hexdigest()[:16]
    out_path = os.path.join(FRAME_CACHE, f"{digest}.jpg")

    if not os.path.exists(out_path):
        subprocess.run(
            [FFMPEG, "-y", "-ss", str(at_seconds), "-i", path,
             "-frames:v", "1", "-q:v", "3", out_path],
            capture_output=True, timeout=60, startupinfo=_no_window(),
        )
    return out_path if os.path.exists(out_path) else None


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep the console clean

    def handle_one_request(self):
        # A player that seeks or a window that closes drops the socket
        # mid-response; that is normal, not something to print a traceback for.
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token = (params.get("id") or [""])[0]
        path = resolve(token)

        if not path or not os.path.exists(path):
            self.send_error(404, "not registered")
            return

        if parsed.path == "/frame":
            at = params.get("t")
            frame = extract_frame(path, float(at[0]) if at else None)
            if not frame:
                self.send_error(500, "frame extraction failed")
                return
            self._send_file(frame)
        elif parsed.path == "/media":
            self._send_file(path)
        else:
            self.send_error(404)

    def _send_file(self, path):
        size = os.path.getsize(path)
        ctype = CONTENT_TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        start, end = 0, size - 1

        # Range support: without it the player cannot seek and some builds
        # refuse to show anything at all.
        range_header = self.headers.get("Range")
        is_partial = False
        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                g1, g2 = match.groups()
                if g1:
                    start = int(g1)
                    if g2:
                        end = int(g2)
                elif g2:  # suffix form: last N bytes
                    start = max(0, size - int(g2))
                start = min(start, size - 1)
                end = min(end, size - 1)
                is_partial = True

        length = end - start + 1
        self.send_response(206 if is_partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        # The page is served from another port, and @font-face is CORS-checked
        # (unlike <video> or <img>) - without this a font silently falls back.
        self.send_header("Access-Control-Allow-Origin", "*")
        if is_partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        if self.command == "HEAD":
            return

        remaining = length
        with open(path, "rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return  # player seeked away or closed the stream
                remaining -= len(chunk)

    do_HEAD = do_GET


_server = None
_base_url = None


def start():
    """Starts the server on a free loopback port; returns its base URL."""
    global _server, _base_url
    if _base_url:
        return _base_url
    _server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    _server.daemon_threads = True
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    _base_url = f"http://127.0.0.1:{_server.server_address[1]}"
    return _base_url


def media_url(path):
    return f"{start()}/media?id={register(path)}&v={int(os.path.getmtime(path))}"


def font_url(path):
    """Serves a font file to the page.

    Chromium only sees machine-wide fonts, so anything installed just for the
    current user (%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts) is invisible to CSS
    by name. Loading the actual file guarantees the preview uses the same
    typeface the renderer will.
    """
    path = os.path.abspath(path.partition("#")[0])
    return f"{start()}/media?id={register(path)}&v={int(os.path.getmtime(path))}"


def frame_url(path, at_seconds=None):
    token = register(path)
    suffix = f"&t={at_seconds}" if at_seconds is not None else ""
    return f"{start()}/frame?id={token}{suffix}&v={int(os.path.getmtime(path))}"
