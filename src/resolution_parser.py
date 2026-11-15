import re
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from threading import Event
from urllib.parse import urljoin, urlsplit

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from src.config import VIDEO_HTTP_HEADERS


COMMON_HEIGHTS = (144, 240, 360, 480, 540, 576, 720, 1080, 1440, 2160, 4320)
PATH_HEIGHT = re.compile(r'(?<=/)([1-9]\d{2,3})(?=p/|p?\.mp4(?:/|:hls:)|p\.m3u8$)', re.IGNORECASE)
STREAM_HEIGHT = re.compile(r'(?:^|,)RESOLUTION=\d+x(\d+)(?=,|$)', re.IGNORECASE)


def is_hls_url(url):
    try:
        parts = urlsplit(url)
        return parts.scheme in ('http', 'https') and bool(parts.hostname) and '.m3u8' in url.lower()
    except ValueError:
        return False


def _read_playlist(url):
    request = urllib.request.Request(url, headers=VIDEO_HTTP_HEADERS)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                text = response.read(128 * 1024).decode('utf-8-sig', errors='replace')
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                return response.geturl(), lines if lines and lines[0] == '#EXTM3U' else []
        except (OSError, HTTPException, ValueError) as error:
            if attempt or not isinstance(getattr(error, 'reason', error), (TimeoutError, socket.timeout)):
                break
    return url, []


def _path_height(path):
    matches = list(PATH_HEIGHT.finditer(path))
    return matches[-1] if matches else None


def _is_media_playlist(lines):
    return (any(line.startswith('#EXTINF:') for line in lines)
            and any(not line.startswith('#') for line in lines))


def _master_variants(url, lines):
    for tag, uri in zip(lines, lines[1:]):
        if not tag.startswith('#EXT-X-STREAM-INF:') or uri.startswith('#'):
            continue
        try:
            variant = urljoin(url, uri)
            parts = urlsplit(variant)
        except ValueError:
            continue
        if parts.scheme not in ('http', 'https') or not parts.hostname:
            continue
        height = STREAM_HEIGHT.search(tag.partition(':')[2]) or _path_height(parts.path)
        if height:
            yield int(height[1]), variant


def find_resolutions(url, cancelled=lambda: False):
    """Return (height, direct URL) pairs. None keeps the original master URL."""
    if not is_hls_url(url) or cancelled():
        return []

    resolved_url, lines = _read_playlist(url)
    variants = list(_master_variants(resolved_url, lines))
    options = dict.fromkeys(height for height, _ in variants)
    template = next((variant for _, variant in variants if _path_height(urlsplit(variant).path)),
                    resolved_url)
    parts = urlsplit(template)
    match = _path_height(parts.path)

    if not variants and match and _is_media_playlist(lines):
        options[int(match[1])] = url

    def probe(height):
        if cancelled():
            return height, None
        path = parts.path[:match.start()] + str(height) + parts.path[match.end():]
        candidate = parts._replace(path=path).geturl()
        target, playlist = _read_playlist(candidate)
        target_height = _path_height(urlsplit(target).path)
        if _is_media_playlist(playlist) and (target_height is None or int(target_height[1]) == height):
            return height, candidate
        return height, None

    if match and not cancelled():
        missing = (height for height in COMMON_HEIGHTS if height not in options)
        with ThreadPoolExecutor(max_workers=4) as pool:
            options.update((height, candidate) for height, candidate in pool.map(probe, missing) if candidate)

    return sorted(options.items(), reverse=True)


class _ResolutionSignals(QObject):
    completed = pyqtSignal(object, list)


class ResolutionParser(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = _ResolutionSignals()
        self.cancelled = Event()

    def run(self):
        options = find_resolutions(self.url, self.cancelled.is_set)
        if not self.cancelled.is_set():
            self.signals.completed.emit(self, options)
