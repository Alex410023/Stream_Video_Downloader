import threading
from src.downloader import download_process

class DownloaderLogic:
    def __init__(self, on_log, on_progress, on_done):
        self.on_log = on_log
        self.on_progress = on_progress
        self.on_done = on_done
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        self.on_log("🛑 Запрос на отмену... Прерываю процессы.")

    def check_cancelled(self):
        return self.is_cancelled

    def start_download(self, queue, download_dir):
        self.is_cancelled = False
        threading.Thread(
            target=download_process,
            args=(queue, download_dir, self.on_log, self.on_progress, self.on_done, self.check_cancelled),
            daemon=True
        ).start()