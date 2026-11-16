import threading

from src.downloader import DownloadCancelled, DownloadControl, download_item


class DownloaderLogic:
    def __init__(self, on_log, on_progress, on_done):
        self.on_log = on_log
        self.on_progress = on_progress
        self.on_done = on_done
        self.control = DownloadControl()

    def start_queue(self):
        self.control = DownloadControl()

    def pause(self):
        self.control.set_paused(True)

    def resume(self):
        self.control.set_paused(False)

    def cancel(self):
        self.control.cancel()

    def start_download(self, item, download_dir):
        threading.Thread(target=self._run, args=(item, download_dir, self.control), daemon=True).start()

    def _run(self, item, download_dir, control):
        status = 'error'
        try:
            if download_item(item, download_dir, self.on_log, self.on_progress, control):
                status = 'success'
        except DownloadCancelled:
            status = 'cancelled'
        except Exception as error:
            if control.cancelled:
                status = 'cancelled'
            else:
                self.on_log(f"Ошибка загрузки: {error}", "error")
        finally:
            self.on_done(status)
