import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from gui import MainWindow
from config import CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO
import urllib.request
import json


def check_developer_version_warning():
    """Проверка для разработчика: если версия в коде не больше версии на GitHub, выдать предупреждение в PyCharm."""
    # Запускаем эту проверку только если код запущен из IDE (не скомпилирован)
    if not getattr(sys, 'frozen', False):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Dev-Check'})
            with urllib.request.urlopen(req, timeout=3) as response:
                latest_version = json.loads(response.read().decode()).get('tag_name')

                # Если версия в config.py совпадает с версией на сайте, значит вы забыли её повысить!
                if latest_version == CURRENT_VERSION:
                    print(f"⚠️ ВНИМАНИЕ РАЗРАБОТЧИКУ: Вы забыли повысить версию в config.py!")
                    print(f"Текущая версия {CURRENT_VERSION} уже опубликована на GitHub.")
                    print(f"Пожалуйста, измените CURRENT_VERSION перед сборкой новой версии!")
        except Exception:
            pass


if __name__ == "__main__":
    check_developer_version_warning()  # Вызываем проверку до старта интерфейса
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())