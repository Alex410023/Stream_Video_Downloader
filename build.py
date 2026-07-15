import os
import shutil
import subprocess

APP_NAME = "Stream Video Downloader"
ICON_NAME = "icon.icns"


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


def build_app():
    """Запускает PyInstaller."""
    print(f"\n🚀 Шаг 2: Сборка приложения {APP_NAME}...")

    command = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        f"--name={APP_NAME}",
        f"--add-binary=ffmpeg:.",
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
        subprocess.run(["zip", "-q", "-r", zip_name, app_path], check=True)
        os.chdir("..")
        print(f"  [+] Архив успешно создан: dist/{zip_name}")
    else:
        print("  ❌ Ошибка: Файл .app не найден в папке dist.")


if __name__ == "__main__":
    print(f"=== Начало процесса релиза: {APP_NAME} ===\n")
    clean_old_builds()
    build_app()
    create_zip_release()
    print("\n🎉 ГОТОВО! Все прошло успешно.")
    print(f"Перейдите в папку 'dist' — там лежит файл .zip для выгрузки на GitHub.")