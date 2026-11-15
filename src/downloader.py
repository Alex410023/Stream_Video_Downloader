import os
import re
import shutil
import tempfile
import urllib.request
import subprocess
import yt_dlp
import sys

from src.config import VIDEO_HTTP_HEADERS

def get_ffmpeg_path():
    app_dir = (sys._MEIPASS if getattr(sys, 'frozen', False)
               else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bundled = shutil.which(os.path.join(app_dir, 'ffmpeg'))
    if bundled and shutil.which(os.path.join(app_dir, 'ffprobe')):
        return bundled

    search_path = os.pathsep.join((os.environ.get('PATH', os.defpath), '/opt/homebrew/bin', '/usr/local/bin'))
    return shutil.which('ffmpeg', path=search_path) or bundled

def download_process(queue, download_dir, on_log, on_progress, on_done, check_cancelled):
    """
    Скачивает очередь по прямым ссылкам. Поддерживает скачивание:
    - Только видео
    - Только субтитров
    - Видео + Субтитры (со склейкой)
    """
    ffmpeg_path = get_ffmpeg_path()
    had_errors = False
    for i, item in enumerate(queue):
        if check_cancelled():
            break

        video_url = item['video_url']
        sub_url = item['sub_url']
        output_name = item['output_name']

        # 1. Определяем базовое имя
        if not output_name:
            url_for_name = video_url if video_url else sub_url
            parsed_name = [p for p in url_for_name.split("/") if p][-1].split("?")[0]
            if "." not in parsed_name:
                parsed_name += ".mp4" if video_url else ".vtt"
            output_base = os.path.splitext(parsed_name)[0]
        else:
            output_base = output_name

        orig_output_base = output_base
        counter = 1
        base_path = os.path.join(download_dir, output_base)
        # Проверяем, существует ли уже файл с таким именем (mp4, mkv, vtt или srt)
        while os.path.exists(f"{base_path}.mp4") or os.path.exists(f"{base_path}.mkv") or os.path.exists(
                f"{base_path}.vtt") or os.path.exists(f"{base_path}.srt"):
            output_base = f"{orig_output_base} ({counter})"
            base_path = os.path.join(download_dir, output_base)
            counter += 1

        title = output_base
        on_log("-" * 40)
        on_log(f"🔄 [{i + 1}/{len(queue)}] Обрабатываю: {title}...")

        base_path = os.path.join(download_dir, output_base)
        video_path = f"{base_path}.mp4"
        final_mkv = f"{base_path}.mkv"
        sub_path = None

        # СЦЕНАРИЙ 1: Скачиваем только субтитры
        if not video_url and sub_url:
            on_log("📝 Скачиваю только субтитры (видео не указано)...")
            ext = ".srt" if ".srt" in sub_url.lower() else ".vtt"
            sub_path = f"{base_path}{ext}"
            try:
                req = urllib.request.Request(sub_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(sub_path, 'wb') as out_file:
                    out_file.write(response.read())
                on_log(f"🎉 Готово! Субтитры сохранены: {sub_path}")
            except Exception as e:
                had_errors = True
                on_log(f"❌ Ошибка скачивания субтитров: {e}")
            on_progress(100)
            continue

        # СЦЕНАРИЙ 2 и 3: Скачивание видео (с субтитрами или без)
        if sub_url and sub_url.strip():
            on_log("📝 Скачиваю субтитры...")
            ext = ".srt" if ".srt" in sub_url.lower() else ".vtt"
            sub_path = f"{base_path}{ext}"
            try:
                req = urllib.request.Request(sub_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(sub_path, 'wb') as out_file:
                    out_file.write(response.read())
                on_log("✅ Субтитры скачаны.")
            except Exception as e:
                had_errors = True
                on_log(f"⚠️ Не удалось скачать субтитры: {e}")
                sub_path = None

        if check_cancelled():
            _cleanup(video_path, sub_path)
            break

        # Скачивание видео фрагментов через yt-dlp
        on_log(f"🎥 Загружаю видео фрагменты...")

        def progress_hook(d):
            if check_cancelled():
                raise Exception("CANCELLED_BY_USER")
            if d['status'] == 'downloading':
                percent_str = d.get('_percent_str', '0%')
                clean_percent = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).replace('%', '').strip()

                speed = d.get('_speed_str', '0 B/s').strip()
                downloaded = d.get('_downloaded_bytes_str', '0 B').strip()

                # Пробуем получить общий размер от yt-dlp
                total = d.get('_total_bytes_str') or d.get('_total_bytes_estimate_str')

                # --- РЕШЕНИЕ: Если размер N/A, рассчитываем его математически ---
                if not total:
                    try:
                        pct = float(clean_percent)
                        downloaded_bytes = d.get('downloaded_bytes')
                        if pct > 0 and downloaded_bytes:
                            # Рассчитываем примерный итоговый вес файла
                            estimated_total_bytes = downloaded_bytes / (pct / 100.0)

                            # Красиво форматируем байты в человекочитаемый вид (KiB, MiB, GiB)
                            def format_bytes(b):
                                for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
                                    if b < 1024.0:
                                        return f"{b:.2f}{unit}"
                                    b /= 1024.0
                                return f"{b:.2f}PiB"

                            total = format_bytes(estimated_total_bytes)
                    except Exception:
                        pass

                # Дефолтный фоллбек, если расчет не удался
                if not total:
                    total = 'N/A'
                else:
                    total = total.strip()

                status_text = f"Скачано: {downloaded} из {total} ({percent_str.strip()}) | Скорость: {speed}"

                try:
                    val = int(float(clean_percent))
                    on_progress(val, status_text)
                except ValueError:
                    pass


        # Читаем выбранное пользователем качество (если его нет, по умолчанию берем 'best')
        selected_height = item.get('selected_height', 'best')

        # Динамически настраиваем формат скачивания под выбранное разрешение
        if selected_height and selected_height != 'best':
            video_format = f'bestvideo[height<={selected_height}]+bestaudio/best[height<={selected_height}]/best'
        else:
            video_format = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'

        ydl_opts = {
            'format': video_format,  # <-- Сюда подставляется наш динамический формат
            'outtmpl': video_path,
            'merge_output_format': 'mp4',
            'concurrent_fragment_downloads': 10,
            'retries': 10,
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            'http_headers': VIDEO_HTTP_HEADERS.copy(),
        }
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if ydl.download([video_url]) or not os.path.isfile(video_path):
                    raise RuntimeError(f"Не удалось сохранить видео в {video_path}")
            on_log("✅ Видео скачано!")
        except Exception as e:
            if "CANCELLED_BY_USER" in str(e):
                on_log("🛑 Процесс загрузки остановлен.")
                _cleanup(video_path, sub_path)
            else:
                had_errors = True
                on_log(f"❌ Ошибка загрузки видео: {e}")
            continue

        if check_cancelled():
            _cleanup(video_path, sub_path)
            break

        # Сборка через FFmpeg (если есть и видео, и субтитры)
        if sub_path:
            on_log("🔗 Склеиваю видео и субтитры в .mkv...")
            try:
                _merge_subtitles(ffmpeg_path, video_path, sub_path, final_mkv)
                on_log(f"🎉 Готово! Файл сохранен: {final_mkv}")
                _cleanup(video_path, sub_path)
            except (OSError, subprocess.CalledProcessError) as e:
                had_errors = True
                details = (getattr(e, 'stderr', None) or str(e)).strip()
                on_log(f"❌ Ошибка склейки: {details}\nВидео и субтитры сохранены раздельно.")
        else:
            on_log(f"🎉 Готово! Видео сохранено: {video_path}")

    if check_cancelled():
        on_log("🛑 Скачивание всей очереди было прервано.")
    elif had_errors:
        on_log("⚠️ Очередь завершена с ошибками.")
    else:
        on_log("🎉 Загрузка всей очереди успешно завершена!")
    on_progress(100)
    on_done()


def _merge_subtitles(ffmpeg_path, video_path, sub_path, final_mkv):
    if not ffmpeg_path:
        raise FileNotFoundError("FFmpeg не найден")

    with tempfile.TemporaryDirectory(dir=os.path.dirname(final_mkv)) as temp_dir:
        temp_mkv = os.path.join(temp_dir, 'output.mkv')
        subprocess.run([
            ffmpeg_path, '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-abort_on', 'empty_output_stream',
            '-i', video_path, '-i', sub_path,
            '-map', '0:v', '-map', '0:a?', '-map', '1:s:0',
            '-c', 'copy', '-c:s', 'subrip', temp_mkv,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors='replace')
        os.replace(temp_mkv, final_mkv)


def _cleanup(video_path, sub_path):
    if video_path and os.path.exists(video_path):
        try:
            os.remove(video_path)
        except:
            pass
    if sub_path and os.path.exists(sub_path):
        try:
            os.remove(sub_path)
        except:
            pass
