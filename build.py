import os
import shutil
import subprocess

from src.config import CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO

APP_NAME = "Stream Video Downloader"
ICON_NAME = os.path.join("assets", "icon.icns")


def check_release_version():
    version = CURRENT_VERSION.removeprefix('v')
    remote = f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git'
    try:
        result = subprocess.run(
            ['git', 'ls-remote', '--tags', '--refs', remote,
             f'refs/tags/v{version}', f'refs/tags/{version}'],
            check=True, capture_output=True, text=True, timeout=15,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
        )
    except (OSError, subprocess.SubprocessError) as error:
        details = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        raise SystemExit(f'Не удалось проверить версию на GitHub. Сборка остановлена.\n{details}') from error

    if result.stdout.strip():
        raise SystemExit(
            f'Версия {CURRENT_VERSION} уже есть на GitHub. '
            'Обновите CURRENT_VERSION в src/config.py и повторите сборку.'
        )


def clean_old_builds():
    """Удаляет старые папки build, dist и файл .spec."""
    print("🧹 Шаг 1: Очистка старых файлов сборки...")
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  [-] Удалена папка {folder}/")

    spec_file = f"{APP_NAME}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"  [-] Удален файл {spec_file}")


def build_app(ffprobe_path):
    """Запускает PyInstaller."""
    print(f"\n🚀 Шаг 2: Сборка приложения {APP_NAME}...")

    command = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        f"--name={APP_NAME}",
        f"--add-binary=ffmpeg:.",
        f"--add-binary={ffprobe_path}:.",
        "--add-data=assets:assets",
        "main.py"
    ]

    # Если иконка есть в папке, добавляем её в сборку
    if os.path.exists(ICON_NAME):
        command.insert(4, f"--icon={ICON_NAME}")
    else:
        print(f"  ⚠️ Иконка {ICON_NAME} не найдена. Сборка будет без неё.")

    # Запускаем команду (в выводе терминала вы увидите процесс работы PyInstaller)
    subprocess.run(command, check=True)


def create_zip_release():
    """Сжимает .app в .zip для загрузки на GitHub."""
    print("\n📦 Шаг 3: Создание ZIP-архива для GitHub...")
    app_path = f"{APP_NAME}.app"
    zip_name = f"{APP_NAME}.zip"

    dist_dir = os.path.abspath("dist")

    if os.path.exists(os.path.join(dist_dir, app_path)):
        # Переходим в папку dist и используем системную команду zip (сохраняет права файлов macOS)
        os.chdir(dist_dir)
        subprocess.run(["zip", "-q", "-ry", zip_name, app_path], check=True)
        os.chdir("..")
        print(f"  [+] Архив успешно создан: dist/{zip_name}")
    else:
        print("  ❌ Ошибка: Файл .app не найден в папке dist.")


if __name__ == "__main__":
    print(f"=== Начало процесса релиза: {APP_NAME} ===\n")
    check_release_version()
    ffprobe_path = shutil.which(os.path.abspath('ffprobe')) or shutil.which('ffprobe')
    if not ffprobe_path:
        raise SystemExit('Для сборки нужен FFprobe рядом с ffmpeg или в PATH.')
    clean_old_builds()
    build_app(ffprobe_path)
    create_zip_release()
    print("\n🎉 ГОТОВО! Все прошло успешно.")
    print(f"Перейдите в папку 'dist' — там лежит файл .zip для выгрузки на GitHub.")
