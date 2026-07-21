import re
import urllib.request
from PyQt6.QtCore import QThread, pyqtSignal


class ResolutionParser(QThread):
    """Поток для быстрого фонового парсинга доступных разрешений из .m3u8."""
    finished = pyqtSignal(list)  # Передает список найденных высот (например, ['1080', '720', '480'])

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            # Скачиваем только начало файла, так как мастер-плейлист весит крайне мало (< 5 КБ)
            req = urllib.request.Request(self.url,
                                         headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode('utf-8', errors='ignore')

                # Проверяем, что это действительно плейлист M3U
                if not content.startswith("#EXTM3U"):
                    self.finished.emit([])
                    return

                # Ищем регулярным выражением параметры RESOLUTION=1920x1080 [1]
                resolutions = re.findall(r'RESOLUTION=\d+x(\d+)', content)
                if resolutions:
                    # Убираем дубликаты и сортируем по убыванию (например, ['1080', '720', '480'])
                    unique_heights = sorted(list(set(resolutions)), key=int, reverse=True)
                    self.finished.emit(unique_heights)
                    return
        except Exception as e:
            print(f"Ошибка парсинга разрешений: {e}")
        self.finished.emit([])