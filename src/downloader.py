import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp
from yt_dlp.utils import format_bytes

from src.config import VIDEO_HTTP_HEADERS


class DownloadCancelled(Exception):
    pass


class DownloadControl:
    def __init__(self):
        self._condition = threading.Condition()
        self.paused = False
        self.cancelled = False

    def set_paused(self, paused):
        with self._condition:
            self.paused = paused
            self._condition.notify_all()

    def cancel(self):
        with self._condition:
            self.cancelled = True
            self._condition.notify_all()

    def checkpoint(self, on_pause=None, on_resume=None):
        with self._condition:
            if self.paused and not self.cancelled:
                if on_pause:
                    on_pause()
                self._condition.wait_for(lambda: not self.paused or self.cancelled)
                if on_resume and not self.cancelled:
                    on_resume()
            if self.cancelled:
                raise DownloadCancelled()


class _ControlledYoutubeDL(yt_dlp.YoutubeDL):
    def __init__(self, options, control):
        self.control = control
        super().__init__(options)

    def urlopen(self, request):
        self.control.checkpoint()
        return super().urlopen(request)


def get_ffmpeg_path():
    app_dir = (sys._MEIPASS if getattr(sys, 'frozen', False)
               else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bundled = shutil.which(os.path.join(app_dir, 'ffmpeg'))
    if bundled and shutil.which(os.path.join(app_dir, 'ffprobe')):
        return bundled

    search_path = os.pathsep.join((os.environ.get('PATH', os.defpath), '/opt/homebrew/bin', '/usr/local/bin'))
    return shutil.which('ffmpeg', path=search_path) or bundled


def _available_base(directory, name):
    base = Path(directory, name)
    candidate = base
    number = 1
    while any(Path(f"{candidate}{suffix}").exists() for suffix in (".mp4", ".mkv", ".vtt", ".srt")):
        candidate = base.with_name(f"{base.name} ({number})")
        number += 1
    return candidate


def _download_subtitles(url, destination, control):
    request = urllib.request.Request(url, headers=VIDEO_HTTP_HEADERS)
    control.checkpoint()
    with urllib.request.urlopen(request, timeout=15) as response, destination.open('wb') as output:
        while True:
            control.checkpoint()
            chunk = response.read1(64 * 1024)
            if not chunk:
                break
            output.write(chunk)


def _download_video(url, path, height, ffmpeg_path, control, on_progress):
    last_update = 0.0

    def progress_hook(status):
        nonlocal last_update
        control.checkpoint()
        now = time.monotonic()
        if status['status'] != 'downloading' or now - last_update < 0.15:
            return
        current = status.get('downloaded_bytes') or 0
        total = status.get('total_bytes') or status.get('total_bytes_estimate')
        if not total:
            return
        last_update = now
        speed = re.sub(r'\x1b\[[0-9;]*m', '', status.get('_speed_str') or '').strip()
        volume = f"{format_bytes(current)} из {format_bytes(total)}"
        on_progress(min(100, int(current * 100 / total)), f"{volume} · {speed}" if speed else volume)

    limit = height if height and height != 'best' else 1080
    options = {
        'format': f'bestvideo[height<={limit}]+bestaudio/best[height<={limit}]/best',
        'outtmpl': str(path),
        'merge_output_format': 'mp4',
        'concurrent_fragment_downloads': 10,
        'retries': 10,
        'socket_timeout': 15,
        'nocheckcertificate': True,
        'quiet': True,
        'noprogress': True,
        'no_warnings': True,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [lambda _: control.checkpoint()],
        'http_headers': VIDEO_HTTP_HEADERS.copy(),
    }
    if ffmpeg_path:
        options['ffmpeg_location'] = ffmpeg_path

    control.checkpoint()
    with _ControlledYoutubeDL(options, control) as ydl:
        if ydl.download([url]) or not path.is_file():
            control.checkpoint()
            raise RuntimeError("Не удалось сохранить видео")


def download_item(item, download_dir, on_log, on_progress, control):
    video_url = item['video_url']
    sub_url = item['sub_url']
    url_path = urlsplit(video_url or sub_url).path
    name = item['output_name'] or Path(url_path).stem or ('Видео' if video_url else 'Субтитры')
    control.checkpoint()
    ffmpeg_path = get_ffmpeg_path()
    with tempfile.TemporaryDirectory(prefix='.stream-', dir=download_dir) as temp_dir:
        directory = Path(temp_dir)
        video_path = directory / 'video.mp4'
        sub_extension = '.srt' if '.srt' in sub_url.lower() else '.vtt'
        sub_path = directory / f'subtitles{sub_extension}'
        subtitle_failed = False
        if sub_url:
            on_log("Скачивание субтитров", "info")
            try:
                _download_subtitles(sub_url, sub_path, control)
            except (OSError, HTTPException, ValueError) as error:
                control.checkpoint()
                if not video_url:
                    raise
                subtitle_failed = True
                on_log(f"Субтитры недоступны: {error}", "warning")

        if video_url:
            on_log("Скачивание видео", "info")
            _download_video(video_url, video_path, item.get('selected_height'), ffmpeg_path, control, on_progress)

        control.checkpoint()
        output_base = _available_base(download_dir, name)
        if video_url and sub_url and not subtitle_failed:
            output = Path(f"{output_base}.mkv")
            on_log("Объединение видео и субтитров", "info")
            try:
                _merge_subtitles(ffmpeg_path, video_path, sub_path, output, item.get('subtitle_offset', 0), control)
            except (OSError, subprocess.CalledProcessError) as error:
                control.checkpoint()
                detail = (getattr(error, 'stderr', None) or str(error)).strip()
                on_log(f"Ошибка склейки: {detail}. Видео и субтитры сохранены отдельно.", "error")
                video_path.replace(f"{output_base}.mp4")
                sub_path.replace(f"{output_base}{sub_extension}")
                return False
        elif video_url:
            output = Path(f"{output_base}.mp4")
            video_path.replace(output)
        else:
            output = Path(f"{output_base}{sub_extension}")
            sub_path.replace(output)

        on_progress(100, "")
        on_log(f"Сохранено: {output.name}", "success")
        return not subtitle_failed


def _merge_subtitles(ffmpeg_path, video_path, sub_path, final_mkv, offset=0, control=None):
    if not ffmpeg_path:
        raise FileNotFoundError("FFmpeg не найден")
    if control is None:
        control = DownloadControl()

    with tempfile.TemporaryDirectory(dir=Path(video_path).parent) as temp_dir:
        temp_dir = Path(temp_dir)
        temp_output = temp_dir / 'output.mkv'
        ffmpeg = [ffmpeg_path, '-nostdin', '-hide_banner', '-loglevel', 'error']
        if offset < 0:
            # Trim the subtitle stream separately so FFmpeg keeps the video and audio timestamps.
            shifted = temp_dir / 'shifted.srt'
            _run_ffmpeg([
                *ffmpeg, '-itsoffset', str(offset), '-i', str(sub_path), '-ss', '0',
                '-map', '0:s:0', '-c:s', 'subrip', str(shifted),
            ], control)
            sub_path = shifted
            offset = 0
        _run_ffmpeg([
            *ffmpeg,
            '-abort_on', 'empty_output_stream',
            '-i', str(video_path), '-itsoffset', str(offset), '-i', str(sub_path),
            '-map', '0:v', '-map', '0:a?', '-map', '1:s:0',
            '-c', 'copy', '-c:s', 'subrip', '-avoid_negative_ts', 'disabled', str(temp_output),
        ], control)
        control.checkpoint()
        temp_output.replace(final_mkv)


def _run_ffmpeg(command, control):
    control.checkpoint()
    with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          text=True, errors='replace') as process:
        try:
            while True:
                control.checkpoint(lambda: process.send_signal(signal.SIGSTOP),
                                   lambda: process.send_signal(signal.SIGCONT))
                try:
                    _, stderr = process.communicate(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except DownloadCancelled:
            process.kill()
            process.communicate()
            raise
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, stderr=stderr)
