import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QTextEdit, QScrollArea,
                             QProgressBar, QLabel, QTabWidget, QFrame, QSplitter,
                             QMessageBox, QProgressDialog, QFileDialog, QTextBrowser)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont

from src.config import DEFAULT_DOWNLOAD_DIR, CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO
from src.updater import UpdateChecker, UpdateDownloader, apply_update_and_restart
from src.logic import DownloaderLogic
from src.gui_widgets import MovieRowWidget, EpisodeRowWidget


def get_asset_path(filename, as_url=True):
    """Возвращает путь к файлу картинки (as_url=True для HTML, as_url=False для системы)."""
    import sys
    import os
    from PyQt6.QtCore import QUrl

    if getattr(sys, 'frozen', False):
        path = os.path.join(sys._MEIPASS, 'assets', filename)
    else:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', filename)

    if as_url:
        return QUrl.fromLocalFile(path).toString()
    return path

class GUISignals(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    done_signal = pyqtSignal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stream Video Downloader (β)")
        self.resize(850, 750)

        # Интерактивная таблица стилей с поддержкой hover/pressed эффектов
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e1e; color: #ffffff; font-family: Arial; }
            QLineEdit, QSpinBox { background-color: #2d2d2d; border: 1px solid #3d3d3d; padding: 10px; border-radius: 4px; color: white; }
            QTabWidget::pane { border: 1px solid #3d3d3d; background-color: #202020; border-radius: 4px; }
            QTabBar::tab { background: #2d2d2d; padding: 10px 25px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #202020; border-bottom: 2px solid #0078d7; font-weight: bold; }
            QScrollArea { border: none; background-color: transparent; }
            QSplitter::handle { background-color: #3d3d3d; height: 6px; border-radius: 3px; }
            QSplitter::handle:hover { background-color: #0078d7; }

            /* Базовый стиль кнопок */
            QPushButton { color: white; border: none; padding: 10px; border-radius: 4px; font-weight: bold; background-color: #2d2d2d; border: 1px solid #3d3d3d;}
            QPushButton:hover { background-color: #3d3d3d; border-color: #4d4d4d; }
            QPushButton:pressed { background-color: #1e1e1e; }
            QPushButton:disabled { background-color: #444444; color: #888888; border-color: #444444; }

            /* Синие кнопки управления (Добавление серий/фильмов) */
            QPushButton#blueBtn { background-color: #0078d7; border: none; }
            QPushButton#blueBtn:hover { background-color: #005a9e; }
            QPushButton#blueBtn:pressed { background-color: #004578; }

            /* Зеленая кнопка Запуска скачивания */
            QPushButton#greenBtn { background-color: #107c10; border: none; }
            QPushButton#greenBtn:hover { background-color: #0d630d; }
            QPushButton#greenBtn:pressed { background-color: #084008; }

            /* Красные кнопки удаления/отмены */
            QPushButton#redBtn { background-color: #d83b01; border: none; }
            QPushButton#redBtn:hover { background-color: #b52e01; }
            QPushButton#redBtn:pressed { background-color: #8c2000; }
        """)

        self.signals = GUISignals()
        self.signals.log_signal.connect(self.append_log)
        self.signals.progress_signal.connect(self.update_progress)
        self.signals.done_signal.connect(self.handle_download_done)

        self.logic = DownloaderLogic(
            on_log=lambda msg: self.signals.log_signal.emit(msg),
            on_progress=lambda percent, text="": self.signals.progress_signal.emit(percent, text),
            on_done=lambda: self.signals.done_signal.emit()
        )

        self.movie_rows = []
        self.episode_rows = []

        self.init_ui()
        self.check_for_updates()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Создаем вертикальный разделитель (QSplitter)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.splitter)

        # ================= ВЕРХНИЙ БЛОК (ТОЛЬКО ВКЛАДКИ) =================
        self.top_container = QWidget()
        top_layout = QVBoxLayout(self.top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        self.tabs = QTabWidget()
        top_layout.addWidget(self.tabs)

        # Вкладка 1: Фильмы
        self.tab_movie = QWidget()
        movie_tab_layout = QVBoxLayout(self.tab_movie)
        movie_tab_layout.setSpacing(10)
        movie_tab_layout.setContentsMargins(10, 10, 10, 10)

        self.add_movie_btn = QPushButton("➕ Добавить еще один фильм")
        self.add_movie_btn.setObjectName("blueBtn")
        self.add_movie_btn.clicked.connect(self.add_movie_row)
        movie_tab_layout.addWidget(self.add_movie_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.scroll_area_movie = QScrollArea()
        self.scroll_area_movie.setWidgetResizable(True)
        self.scroll_area_movie_content = QWidget()
        self.scroll_area_movie_layout = QVBoxLayout(self.scroll_area_movie_content)
        self.scroll_area_movie_layout.setSpacing(10)
        self.scroll_area_movie_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area_movie.setWidget(self.scroll_area_movie_content)
        movie_tab_layout.addWidget(self.scroll_area_movie)

        self.tabs.addTab(self.tab_movie, "🎬 Скачивание фильма")

        # Вкладка 2: Сериалы
        self.tab_series = QWidget()
        series_tab_layout = QVBoxLayout(self.tab_series)
        series_tab_layout.setSpacing(10)
        series_tab_layout.setContentsMargins(10, 10, 10, 10)

        self.add_ep_btn = QPushButton("➕ Добавить еще одну серию")
        self.add_ep_btn.setObjectName("blueBtn")
        self.add_ep_btn.clicked.connect(self.add_episode_row)
        series_tab_layout.addWidget(self.add_ep_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.scroll_area_series = QScrollArea()
        self.scroll_area_series.setWidgetResizable(True)
        self.scroll_area_series_content = QWidget()
        self.scroll_area_series_layout = QVBoxLayout(self.scroll_area_series_content)
        self.scroll_area_series_layout.setSpacing(10)
        self.scroll_area_series_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area_series.setWidget(self.scroll_area_series_content)
        series_tab_layout.addWidget(self.scroll_area_series)

        self.tabs.addTab(self.tab_series, "📺 Скачивание серии сериала")

        # ================= Вкладка 3: Инструкция =================
        self.tab_instructions = QWidget()
        inst_main_layout = QVBoxLayout(self.tab_instructions)
        inst_main_layout.setContentsMargins(10, 10, 10, 10)

        # Используем QTextBrowser вместо QLabel + QScrollArea.
        # Он идеально поддерживает прокрутку, выделение, копирование (в т.ч. через правую кнопку мыши) и клики по картинкам.
        self.inst_browser = QTextBrowser()
        self.inst_browser.setOpenExternalLinks(False)
        self.inst_browser.setOpenLinks(False)
        self.inst_browser.setReadOnly(True)
        self.inst_browser.setStyleSheet("""
                    QTextBrowser {
                        border: none;
                        background-color: transparent;
                        font-size: 13px;
                        color: #dddddd;
                    }
                """)

        # Получаем пути к скриншотам
        safari_img = get_asset_path("safari_dev.png", as_url=True)
        filter_img = get_asset_path("filter_devtools.png", as_url=True)
        master_img = get_asset_path("master_example.png", as_url=True)
        sub_example_img = get_asset_path("sub_example.png", as_url=True)

        inst_html = (
            "<h2>📖 Как пользоваться программой</h2><br>"
            "<h3>🍏 Важно для пользователей браузера Safari</h3>"
            "Если вы пользуетесь браузером Safari, панель разработчика по умолчанию скрыта. Чтобы её включить:<br>"
            "1. Откройте меню <b>Safari -> Настройки</b> (или нажмите сочетание клавиш <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-family: monospace;'>Cmd + ,</code>).<br>"
            "2. Перейдите во вкладку <b>Дополнения</b> (Advanced).<br>"
            "3. В самом низу поставьте галочку <b>«Показывать функции для веб-разработчиков»</b> (или <i>«Показывать меню Разработка в строке меню»</i>).<br>"
            f"<br><a href='safari_dev.png'><img src='{safari_img}' width='600'></a><br><br>"
            "После этого открыть консоль разработчика можно будет сочетанием клавиш <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-family: monospace;'>Option + Cmd + I</code>.<br><br>"

            "<h3>Шаг 1. Откройте нужный сайт в браузере</h3>"
            "Зайдите на сайт с фильмом или сериалом и перейдите на страницу с видеоплеером.<br><br>"

            "<h3>Шаг 2. Откройте панель разработчика (DevTools)</h3>"
            "Нажмите сочетание клавиш на клавиатуре:<br>"
            "• На Mac: <code style='background-color: #3d3d3d; color: #ffffff; padding: 3px 6px; border-radius: 4px; font-family: monospace;'>Option + Cmd + I</code><br>"
            "• На Windows/Linux: <code style='background-color: #3d3d3d; color: #ffffff; padding: 3px 6px; border-radius: 4px; font-family: monospace;'>F12</code> или <code style='background-color: #3d3d3d; color: #ffffff; padding: 3px 6px; border-radius: 4px; font-family: monospace;'>Ctrl + Shift + I</code><br><br>"

            "<h3>Шаг 3. Перейдите во вкладку Network (Сеть) и настройте фильтр</h3>"
            "В открывшейся панели выберите вкладку <b>Network</b> (Сеть).<br>"
            "Чтобы не путаться в тысячах запросов, воспользуйтесь полем фильтра поиска (<b>Filter</b>) в верхнем левом углу панели разработчика:<br>"
            f"<br><a href='filter_devtools.png'><img src='{filter_img}' width='600'></a><br><br>"
            "Введите в это поле фразу поиска: <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>.m3u8</code>.<br>"
            "<i>(Сделайте это строго до запуска видео, чтобы браузер не пропустил самый первый, самый важный запрос плеера. Если вы открыли вкладку Network позже и файлы не появились — просто обновите страницу кнопкой в браузере или сочетанием клавиш <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>Cmd+R</code> / <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>Ctrl+F5</code>).</i><br><br>"

            "<h3>Шаг 4. Запустите воспроизведение видео</h3>"
            "Включите плеер на сайте. Браузер сразу начнет запрашивать у сервера плейлисты видеопотоков, и в вашем списке Network начнут появляться ссылки.<br><br>"

            "<h3>Шаг 5. Найдите ссылки на видео</h3>"
            "В отфильтрованном списке Network вы увидите один или несколько файлов с расширением <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>.m3u8</code>.<br><br>"

            "<h3>💡 Как определить, какая именно ссылка вам нужна?</h3>"
            "Сайты могут отправлять множество запросов, но нам нужен главный файл — <b>Мастер-плейлист</b>. Определить его можно по следующим характерным признакам:<br>"
            "1. <b>Самый первый по времени:</b> Нужный плейлист всегда загружается в первую же секунду при открытии плеера (он окажется на самом верху списка).<br>"
            "2. <b>Ориентируйтесь по типу данных:</b> В любом браузере (Chrome, Safari, Firefox) эти файлы обычно классифицируются как <b>XHR</b>, <b>Fetch</b>, <b>Document</b> или просто <b>Другое (Other)</b>.<br>"
            "3. <b>Файл, в предпросмотре которого описаны несколько разрешений:</b> Кликните по файлу в списке и откройте вкладку <b>Preview</b> (Предпросмотр) или <b>Response</b> (Ответ) на панели справа. В нём должны быть описаны разрешения по типу 480p, 720p, 1080p:<br><br>"
            
            "• <b>Важно:</b> Если нужный файл субтитров или видео долгое время не появляется в списке — просто перезагрузите страницу сайта кнопкой в браузере или нажмите сочетание клавиш <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>Cmd+R</code> (или <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>Ctrl+F5</code> на Windows), чтобы плеер отправил запросы заново.<br><br>"

            
            f"<br><a href='master_example.png'><img src='{master_img}' width='600'></a><br><br>"
            "<b>Пример структуры мастер-файла в предпросмотре:</b><br>"
            "<pre style='background-color: #252525; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 11px; color: #0078d7;'>"
            "#EXTM3U\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=2892000,RESOLUTION=1280x720\n"
            "./720.mp4:hls:manifest.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=5592000,RESOLUTION=1920x1080\n"
            "./1080.mp4:hls:manifest.m3u8"
            "</pre><br>"
            "Если вы нашли такой файл, скопируйте на него ссылку: кликните правой кнопкой мыши -> <b>Copy -> Copy link address</b>.<br><br>"

            "<h3>ℹ️ Замечание: Как скачать другую озвучку или субтитры?</h3>"
            "Обычно плеер сразу подгружает видеофайл и файлы субтитров по умолчанию. Если вам нужна оригинальная звуковая дорожка или другие субтитры (например, английские):<br>"
            "1. Измените настройки языка, озвучки или субтитров в самом плеере на сайте.<br>"
            "2. В этот момент в список Network сразу же подгрузится новый файл плейлиста. Скопируйте ссылку на него (для поиска субтитров можно настроить фильтр на <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>.vtt</code> или <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>.srt</code>).<br><br>"
            "• Чтобы проверить, правильный ли это файл субтитров, откройте вкладку <b>Preview</b> (Предпросмотр). Текст внутри должен выглядеть осмысленно — содержать временные метки (таймкоды) и реплики диалогов, как показано на скриншоте ниже:<br>"
            f"<br><a href='sub_example.png'><img src='{sub_example_img}' width='600'></a><br><br>"

            "<h3>Шаг 6. Перенесите ссылки в программу и выберите качество</h3>"
            "Вставьте скопированную ссылку в поле <b>Видео URL</b> в приложении.<br>"
            "• Программа в фоновом режиме автоматически проанализирует поток и выведет удобный выпадающий список <b>Качество видео</b>. Выберите нужное разрешение (1080p, 720p, 480p и т.д.).<br>"
            "• При необходимости вставьте скопированную ссылку на субтитры в поле <b>Субтитры URL</b> (если они вам нужны). Имя файла сгенерируется автоматически.<br><br>"

            "<h3>Шаг 7. Запустите скачивание</h3>"
            "Выберите папку для сохранения на вашем компьютере и нажмите кнопку <b>🚀 Начать загрузку</b>.<br>"
            "<i>Программа сама скачает все фрагменты, склеит видео с субтитрами и упакует их в готовый файл без потери качества!</i><br><br>"

            "<h3>🎬 Как запустить скачанное видео и включить субтитры?</h3>"
            "Поскольку приложение склеивает видео и субтитры в контейнер высокого разрешения <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 4px; border-radius: 3px;'>.mkv</code>, стандартный плеер Mac (QuickTime Player) не сможет его воспроизвести.<br>"
            "• <b>Используйте VLC Player:</b> Мы настоятельно рекомендуем скачать и использовать бесплатный плеер <b>VLC Player</b> для воспроизведения ваших фильмов.<br>"
            "• <b>Как включить субтитры в VLC:</b> Откройте видео в VLC, в верхнем меню Mac выберите: <b>Субтитры -> Дорожка субтитров</b> и выберите нужный язык (например, «Русский» или «Дорожка 1»).<br>"
            "• <b>Что делать, если субтитры отстают или спешат:</b> Вы можете легко синхронизировать их прямо во время просмотра с помощью горячих клавиш на клавиатуре:<br>"
            "  - Клавиша <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-family: monospace;'>H</code> — задерживает субтитры (сдвигает их назад на 50 мс за каждое нажатие).<br>"
            "  - Клавиша <code style='background-color: #3d3d3d; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-family: monospace;'>J</code> — ускоряет субтитры (сдвигает их вперед на 50 мс за каждое нажатие).<br>"
            "  - С помощью этих клавиш можно идеально выровнять тайминг за пару секунд, если на сайте была заложена нестандартная задержка.<br>"
        )

        self.inst_browser.setHtml(inst_html)
        self.inst_browser.anchorClicked.connect(self.on_instruction_image_clicked)
        inst_main_layout.addWidget(self.inst_browser)

        self.tabs.addTab(self.tab_instructions, "📖 Инструкция")

        # Добавляем стартовые карточки по умолчанию
        self.add_movie_row()
        self.add_episode_row()

        self.splitter.addWidget(self.top_container)

        # ================= НИЖНИЙ БЛОК (ПАПКА + КНОПКИ + ЛОГИ) =================
        self.bottom_container = QWidget()
        bottom_layout = QVBoxLayout(self.bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)

        # Выбор папки
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setReadOnly(True)
        self.dir_input.setText(DEFAULT_DOWNLOAD_DIR)

        self.browse_btn = QPushButton("📁 Папка сохранения...")
        self.browse_btn.clicked.connect(self.on_browse_clicked)

        dir_layout.addWidget(self.dir_input, stretch=1)
        dir_layout.addWidget(self.browse_btn)
        bottom_layout.addLayout(dir_layout)

        # Текстовый статус скачивания (скорость, объем)
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("font-size: 11px; color: #0078d7; margin-bottom: 2px;")
        self.progress_label.hide()
        bottom_layout.addWidget(self.progress_label)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        bottom_layout.addWidget(self.progress_bar)

        # Кнопки Старт / Отмена
        self.btn_layout = QHBoxLayout()

        self.download_btn = QPushButton("🚀 Начать загрузку")
        self.download_btn.setObjectName("greenBtn")
        self.download_btn.setFixedHeight(45)
        self.download_btn.clicked.connect(self.on_download_clicked)
        self.btn_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("❌ Отменить загрузку")
        self.cancel_btn.setObjectName("redBtn")
        self.cancel_btn.setFixedHeight(45)
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        self.btn_layout.addWidget(self.cancel_btn)

        bottom_layout.addLayout(self.btn_layout)

        # Текстовое поле для логов
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 11))
        bottom_layout.addWidget(self.log_output)

        self.splitter.addWidget(self.bottom_container)

        self.splitter.setSizes([450, 300])

        self.append_log(
            "Система готова. Настройте файлы и нажмите 'Начать загрузку'. Размеры окон логов и настроек можно менять перетаскиванием разделителя.")

        # ================= Вкладка 4: О программе =================
        self.tab_about = QWidget()
        about_layout = QVBoxLayout(self.tab_about)
        about_layout.setSpacing(15)
        about_layout.setContentsMargins(30, 40, 30, 40)
        about_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel("Stream Video Downloader (β)")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d7; margin-bottom: 5px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(title_label)

        version_label = QLabel(f"Версия: {CURRENT_VERSION}")
        version_label.setStyleSheet("font-size: 14px; color: #aaaaaa; font-weight: bold;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(version_label)

        self.manual_update_btn = QPushButton("🔄 Проверить обновления")
        self.manual_update_btn.setFixedWidth(220)
        self.manual_update_btn.setStyleSheet("""
                    QPushButton { background-color: #2d2d2d; border: 1px solid #3d3d3d; padding: 10px; border-radius: 4px; font-weight: bold; margin-top: 15px;}
                    QPushButton:hover { background-color: #3d3d3d; border-color: #0078d7; }
                    QPushButton:pressed { background-color: #1e1e1e; }
                """)
        self.manual_update_btn.clicked.connect(self.manual_check_for_updates)
        about_layout.addWidget(self.manual_update_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.tabs.addTab(self.tab_about, "ℹ️ О программе")

    def add_movie_row(self):
        """Добавляет карточку фильма."""
        row = MovieRowWidget(self.remove_movie_row)
        self.scroll_area_movie_layout.addWidget(row)
        self.movie_rows.append(row)

    def remove_movie_row(self, row_widget):
        """Удаляет карточку фильма."""
        if len(self.movie_rows) <= 1:
            self.append_log("⚠️ Должна остаться хотя бы одна карточка для скачивания.")
            return
        self.scroll_area_movie_layout.removeWidget(row_widget)
        self.movie_rows.remove(row_widget)
        row_widget.deleteLater()

    def add_episode_row(self):
        """Добавляет карточку серии."""
        row = EpisodeRowWidget(self.remove_episode_row)
        self.scroll_area_series_layout.addWidget(row)
        self.episode_rows.append(row)

    def remove_episode_row(self, row_widget):
        """Удаляет карточку серии."""
        if len(self.episode_rows) <= 1:
            self.append_log("⚠️ Должна остаться хотя бы одна карточка для скачивания.")
            return
        self.scroll_area_series_layout.removeWidget(row_widget)
        self.episode_rows.remove(row_widget)
        row_widget.deleteLater()

    def append_log(self, message):
        self.log_output.append(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def update_progress(self, percent, status_text):
        if not self.progress_bar.isVisible():
            self.progress_bar.show()
            self.progress_label.show()
        self.progress_bar.setValue(percent)
        self.progress_label.setText(status_text)

    def on_browse_clicked(self):
        selected_directory = QFileDialog.getExistingDirectory(
            self, "Выбрать папку для сохранения", self.dir_input.text()
        )
        if selected_directory:
            self.dir_input.setText(selected_directory)

    def on_download_clicked(self):
        active_index = self.tabs.currentIndex()
        queue = []

        if active_index == 0:  # Режим Фильма
            for i, row in enumerate(self.movie_rows):
                video_url = row.video_url.text().strip()
                sub_url = row.sub_url.text().strip()
                output_name = row.filename.text().strip()

                # Читаем выбранное качество из QComboBox
                selected_height = row.quality_combo.currentData() or "best"

                if not video_url and not sub_url:
                    self.append_log(
                        f"⚠️ Ошибка: В карточке фильма #{i + 1} нужно указать ссылку на видео или субтитры!")
                    return

                queue.append({
                    'video_url': video_url,
                    'sub_url': sub_url,
                    'output_name': output_name,
                    'selected_height': selected_height  # <-- Передаем выбранное качество!
                })
        else:  # Режим Сериала
            for i, row in enumerate(self.episode_rows):
                video_url = row.video_url.text().strip()
                sub_url = row.sub_url.text().strip()
                output_name = row.filename.text().strip()

                # Читаем выбранное качество из QComboBox
                selected_height = row.quality_combo.currentData() or "best"

                if not video_url and not sub_url:
                    self.append_log(f"⚠️ Ошибка: В карточке серии #{i + 1} нужно указать ссылку на видео или субтитры!")
                    return

                queue.append({
                    'video_url': video_url,
                    'sub_url': sub_url,
                    'output_name': output_name,
                    'selected_height': selected_height  # <-- Передаем выбранное качество!
                })

        download_dir = self.dir_input.text().strip()

        self.tabs.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.add_movie_btn.setEnabled(False)
        self.add_ep_btn.setEnabled(False)

        for r in self.movie_rows: r.setEnabled(False)
        for r in self.episode_rows: r.setEnabled(False)

        self.download_btn.hide()
        self.cancel_btn.show()

        self.progress_bar.setValue(0)
        self.progress_bar.show()

        self.progress_label.setText("Запуск загрузки...")  # Сбрасываем текст
        self.progress_label.show()

        self.logic.start_download(queue, download_dir)

    def check_for_updates(self):
        """Запускает фоновую проверку обновлений на GitHub."""
        self.updater_thread = UpdateChecker(CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO)
        self.updater_thread.update_available.connect(self.on_update_available)
        self.updater_thread.error.connect(lambda err: self.append_log(f"⚠️ {err}"))
        self.updater_thread.start()

    def on_update_available(self, version, changelog, download_url):
        """Вызывает диалоговое окно с предложением обновиться."""
        reply = QMessageBox.question(
            self, "Доступно обновление",
            f"Вышла новая версия: {version}!\n\nЧто нового:\n{changelog}\n\nХотите обновить приложение сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.start_downloading_update(download_url)

    def start_downloading_update(self, download_url):
        """Запускает скачивание и показывает прогресс-бар."""
        self.upd_progress_dialog = QProgressDialog("Скачивание обновления...", "Отмена", 0, 100, self)
        self.upd_progress_dialog.setWindowTitle("Обновление")
        self.upd_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.upd_progress_dialog.setAutoClose(False)
        self.upd_progress_dialog.setAutoReset(False)
        self.upd_progress_dialog.show()

        self.download_thread = UpdateDownloader(download_url)
        self.download_thread.progress.connect(self.upd_progress_dialog.setValue)
        self.download_thread.finished.connect(self.on_update_downloaded)
        self.download_thread.error.connect(self.on_update_error)

        self.upd_progress_dialog.canceled.connect(self.download_thread.cancel)

        self.download_thread.start()

    def on_update_downloaded(self, extracted_app_path):
        """Закрывает окно прогресса и запускает установку."""
        self.upd_progress_dialog.close()
        self.append_log("🔄 Установка обновления... Приложение сейчас будет перезапущено.")
        apply_update_and_restart(extracted_app_path)

    def on_update_error(self, error_msg):
        """Вызывается в случае ошибки при скачивании архива."""
        if hasattr(self, 'upd_progress_dialog') and self.upd_progress_dialog:
            self.upd_progress_dialog.close()
        QMessageBox.critical(self, "Ошибка обновления", f"Не удалось обновить приложение:\n{error_msg}")

    def on_cancel_clicked(self):
        self.cancel_btn.setEnabled(False)
        self.logic.cancel()

    def handle_download_done(self):
        self.tabs.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.add_movie_btn.setEnabled(True)
        self.add_ep_btn.setEnabled(True)

        for r in self.movie_rows: r.setEnabled(True)
        for r in self.episode_rows: r.setEnabled(True)

        self.download_btn.show()
        self.cancel_btn.hide()
        self.cancel_btn.setEnabled(True)
        self.progress_bar.hide()
        self.progress_label.hide() # <-- Скрываем статус-лейбл при завершении

    def manual_check_for_updates(self):
        """Ручной запуск проверки обновлений по кнопке во вкладке."""
        self.append_log("🔍 Ручная проверка наличия обновлений...")
        self.manual_update_btn.setEnabled(False)
        self.manual_update_btn.setText("⏳ Проверяю...")
        self.manual_update_found = False

        self.manual_updater = UpdateChecker(CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO)
        self.manual_updater.update_available.connect(self.on_manual_update_available)
        self.manual_updater.finished.connect(self.on_manual_check_finished)
        self.manual_updater.error.connect(self.on_manual_check_error)
        self.manual_updater.start()

    def on_manual_update_available(self, version, changelog, download_url):
        """Вызывается, если при ручной проверке найдено обновление."""
        self.manual_update_found = True
        self.on_update_available(version, changelog, download_url)

    def on_manual_check_finished(self):
        """Вызывается, когда поток проверки завершил работу."""
        self.manual_update_btn.setEnabled(True)
        self.manual_update_btn.setText("🔄 Проверить обновления")

        if not self.manual_update_found:
            QMessageBox.information(
                self, "Обновления",
                "У вас установлена самая актуальная версия программы!"
            )
            self.append_log("✅ Проверка завершена: у вас установлена последняя версия программы.")

    def on_manual_check_error(self, err_msg):
        """Вызывается при ошибке сети во время ручной проверки."""
        self.manual_update_btn.setEnabled(True)
        self.manual_update_btn.setText("🔄 Проверить обновления")
        self.on_update_error(err_msg)

    def on_instruction_image_clicked(self, url):
        """Открывает скриншот в красивом модальном окне, масштабируя его под размер экрана."""
        # QTextBrowser передает объект QUrl, преобразуем его в строку имени файла
        filename = url.toString()

        # Получаем чистый системный путь к оригинальной картинке
        local_path = get_asset_path(filename, as_url=False)

        if os.path.exists(local_path):
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
            from PyQt6.QtGui import QPixmap

            dialog = QDialog(self)
            dialog.setWindowTitle("Просмотр изображения")
            dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel()
            pixmap = QPixmap(local_path)

            screen_geometry = self.screen().geometry()
            max_width = int(screen_geometry.width() * 0.85)
            max_height = int(screen_geometry.height() * 0.85)

            scaled_pixmap = pixmap.scaled(
                max_width, max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            label.setPixmap(scaled_pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

            label.mousePressEvent = lambda event: dialog.accept()
            dialog.exec()