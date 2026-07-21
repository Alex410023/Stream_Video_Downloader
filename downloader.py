import os
import re
import urllib.request
import subprocess
import yt_dlp
import sys

def get_ffmpeg_path():
    """Возвращает путь к ffmpeg в зависимости от того, скрипт это или скомпилированное .app"""
    if getattr(sys, 'frozen', False):
        # Если запущено как скомпилированное приложение
        return os.path.join(sys._MEIPASS, 'ffmpeg')
    else:
        # Если запущено из исходников (ищет в папке со скриптом или в системе)
        return 'ffmpeg'

def download_process(queue, download_dir, on_log, on_progress, on_done, check_cancelled):
    """
    Скачивает очередь по прямым ссылкам. Поддерживает скачивание:
    - Только видео
    - Только субтитров
    - Видео + Субтитры (со склейкой)
    """
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
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Referer': 'https://inoriginal.cc',
                'Origin': 'https://inoriginal.cc'
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            on_log("✅ Видео скачано!")
        except Exception as e:
            if "CANCELLED_BY_USER" in str(e):
                on_log("🛑 Процесс загрузки остановлен.")
                _cleanup(video_path, sub_path)
            else:
                on_log(f"❌ Ошибка загрузки видео: {e}")
            continue

        if check_cancelled():
            _cleanup(video_path, sub_path)
            break

        # Сборка через FFmpeg (если есть и видео, и субтитры)
        if sub_path and os.path.exists(video_path):
            on_log("🔗 Склеиваю видео и субтитры в .mkv...")
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-fflags", "+genpts",  # Принудительно восстанавливаем ровную шкалу времени видео
                "-i", video_path,
                "-i", sub_path,
                "-c:v", "copy",  # Видео копируем без пересжатия
                "-c:a", "copy",  # Аудио копируем без пересжатия
                "-c:s", "subrip",  # Субтитры vtt пережимаем в сверхустойчивый srt (subrip)
                final_mkv
            ]
            try:
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                on_log(f"🎉 Готово! Файл сохранен: {final_mkv}")
                _cleanup(video_path, sub_path)
            except subprocess.CalledProcessError:
                on_log("❌ Ошибка FFmpeg при склейке. Файлы сохранены раздельно.")
        else:
            on_log(f"🎉 Готово! Видео сохранено: {video_path}")

    if check_cancelled():
        on_log("🛑 Скачивание всей очереди было прервано.")
    else:
        on_log("🎉 Загрузка всей очереди успешно завершена!")
    on_progress(100)
    on_done()


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