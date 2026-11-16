import os

# Дефолтная папка загрузок на Mac
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

VIDEO_HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Referer': 'https://inoriginal.cc',
    'Origin': 'https://inoriginal.cc',
}

# Настройки обновления (для связи с GitHub)
CURRENT_VERSION = "v1.2.0"
GITHUB_OWNER = "Alex410023"
GITHUB_REPO = "Stream_Video_Downloader"
