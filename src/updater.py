import os
import sys
import json
import urllib.request
import tempfile
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


class UpdateChecker(QThread):
    """Фоновый поток для проверки новой версии на GitHub."""
    update_available = pyqtSignal(str, str, str)  # версия, описание изменений, ссылка на zip
    error = pyqtSignal(str)

    def __init__(self, current_version, owner, repo):
        super().__init__()
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    def run(self):
        try:
            req = urllib.request.Request(self.api_url, headers={'User-Agent': 'StreamVideoDownloader-App'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get('tag_name')
                changelog = data.get('body', 'Нет описания')

                # Если версия на гитхабе отличается от нашей
                if latest_version and latest_version != self.current_version:
                    download_url = None
                    # Ищем прикрепленный .zip файл в релизе
                    for asset in data.get('assets', []):
                        if asset['name'].endswith('.zip'):
                            download_url = asset['browser_download_url']
                            break

                    if download_url:
                        self.update_available.emit(latest_version, changelog, download_url)
        except Exception as e:
            self.error.emit(f"Ошибка проверки обновлений: {e}")


class UpdateDownloader(QThread):
    """Фоновый поток для скачивания и распаковки обновления."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)  # Передает путь к распакованному .app
    error = pyqtSignal(str)

    def __init__(self, download_url):
        super().__init__()
        self.download_url = download_url
        self.temp_dir = tempfile.mkdtemp()
        self.zip_path = os.path.join(self.temp_dir, 'update.zip')
        self._is_cancelled = False  # Флаг для безопасной отмены

    def cancel(self):
        """Метод для безопасной отмены загрузки из интерфейса."""
        self._is_cancelled = True

    def run(self):
        import socket
        # Устанавливаем глобальный таймаут сокета, чтобы предотвратить вечное зависание read() при обрыве сети
        socket.setdefaulttimeout(15)
        try:
            req = urllib.request.Request(self.download_url, headers={'User-Agent': 'StreamVideoDownloader-App'})
            with urllib.request.urlopen(req, timeout=15) as response:
                total_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                block_size = 8192

                with open(self.zip_path, 'wb') as f:
                    while True:
                        # Если пользователь нажал "Отмена", безопасно прерываем цикл
                        if self._is_cancelled:
                            raise Exception("Загрузка отменена пользователем.")

                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        downloaded += len(buffer)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent)

            # Распаковываем zip с помощью встроенного в macOS системного архиватора 'unzip'
            subprocess.run(["unzip", "-q", self.zip_path, "-d", self.temp_dir], check=True)

            # Ищем распакованный .app файл
            extracted_app_path = None
            for item in os.listdir(self.temp_dir):
                if item.endswith('.app'):
                    extracted_app_path = os.path.join(self.temp_dir, item)
                    break

            if extracted_app_path:
                self.finished.emit(extracted_app_path)
            else:
                self.error.emit("В архиве не найдено приложение (.app).")
        except Exception as e:
            self.error.emit(f"{e}")


def apply_update_and_restart(extracted_app_path):
    """Создает bash-скрипт для подмены старого .app на новый и закрывает программу."""
    # Если мы запустили код из PyCharm, а не скомпилированное приложение, ничего не меняем
    if not getattr(sys, 'frozen', False):
        print("Запущено из IDE. Обновление файлов отменено.")
        return

    # Определяем путь до текущего запущенного приложения .app
    current_exe = sys.executable
    contents_dir = os.path.dirname(os.path.dirname(current_exe))
    current_app_path = os.path.dirname(contents_dir)

    if not current_app_path.endswith('.app'):
        return

    script_path = os.path.join(tempfile.gettempdir(), "update_app.sh")

    # Bash-скрипт, который подождет закрытия программы, удалит её и поставит новую
    script_content = f'''#!/bin/bash
sleep 1.5
rm -rf "{current_app_path}"
mv "{extracted_app_path}" "{current_app_path}"
xattr -cr "{current_app_path}"
open "{current_app_path}"
rm "$0"
'''
    with open(script_path, 'w') as f:
        f.write(script_content)

    os.chmod(script_path, 0o755)

    # Запускаем скрипт как независимый процесс и убиваем текущее приложение
    subprocess.Popen([script_path], start_new_session=True)
    sys.exit(0)