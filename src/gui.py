import os
import sys

from PyQt6.QtWidgets import (QApplication, QButtonGroup, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea,
                             QProgressBar, QLabel, QTabWidget, QFrame, QSplitter,
                             QMessageBox, QProgressDialog, QFileDialog, QSizePolicy,
                             QToolButton)
from PyQt6.QtCore import Qt, QObject, QSettings, QSize, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QPalette

from src.config import DEFAULT_DOWNLOAD_DIR, CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO
from src.updater import UpdateChecker, UpdateDownloader, apply_update_and_restart
from src.logic import DownloaderLogic
from src.gui_widgets import ActivityLog, EpisodeRowWidget, GuideBrowser, MovieRowWidget
from src.ui_style import DARK, GUIDE_STYLE, LIGHT, STYLE, appearance_preview, symbol


def get_asset_path(filename, as_url=True):
    """Возвращает путь к файлу картинки (as_url=True для HTML, as_url=False для системы)."""
    if getattr(sys, 'frozen', False):
        path = os.path.join(sys._MEIPASS, 'assets', filename)
    else:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', filename)

    if as_url:
        return QUrl.fromLocalFile(path).toString()
    return path

class GUISignals(QObject):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int, str)
    done_signal = pyqtSignal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stream Video Downloader")
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
        self.resize(1000, 720)
        self.setMinimumSize(800, 570)
        self.setUnifiedTitleAndToolBarOnMac(True)

        self.signals = GUISignals()
        self.signals.log_signal.connect(self.append_log)
        self.signals.progress_signal.connect(self.update_progress)
        self.signals.done_signal.connect(self.handle_download_done)

        self.logic = DownloaderLogic(
            on_log=self.signals.log_signal.emit,
            on_progress=lambda percent, text="": self.signals.progress_signal.emit(percent, text),
            on_done=self.signals.done_signal.emit
        )

        self.movie_rows = []
        self.episode_rows = []
        self.queue_rows = None
        self.pending_rows = []
        self.active_row = None
        self.close_after_queue = False
        self.settings = QSettings(GITHUB_OWNER, "StreamVideoDownloader")

        self.init_ui()
        self.change_appearance()
        QApplication.styleHints().colorSchemeChanged.connect(self.apply_appearance)
        self.check_for_updates()

    def closeEvent(self, event):
        if self.queue_rows is None:
            super().closeEvent(event)
            return
        event.ignore()
        self.close_after_queue = True
        if not self.logic.control.cancelled:
            self.on_cancel_clicked()

    def init_ui(self):
        central_widget = QWidget(objectName="AppSurface")
        self.setCentralWidget(central_widget)
        root = QHBoxLayout(central_widget)
        root.setContentsMargins(0, 6, 6, 6)
        root.setSpacing(0)
        root.addWidget(self.build_navigation())

        workspace = QFrame(objectName="Workspace")
        root.addWidget(workspace, 1)
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(24, 20, 24, 20)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        workspace_layout.addWidget(self.splitter)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 1)

        self.add_movie_btn, self.scroll_area_movie_layout = self.add_download_page(
            "Фильмы", "Добавить фильм", self.add_movie_row)
        self.add_ep_btn, self.scroll_area_series_layout = self.add_download_page(
            "Сериалы", "Добавить серию", self.add_episode_row)

        self.tab_instructions = QWidget()
        inst_main_layout = QVBoxLayout(self.tab_instructions)
        inst_main_layout.setContentsMargins(0, 0, 0, 0)
        self.inst_browser = GuideBrowser()
        self.inst_browser.setOpenExternalLinks(False)
        self.inst_browser.setOpenLinks(False)
        self.inst_browser.document().setDocumentMargin(20)

        # Получаем пути к скриншотам
        safari_img = get_asset_path("safari_dev.png", as_url=True)
        filter_img = get_asset_path("filter_devtools.png", as_url=True)
        master_img = get_asset_path("master_example.png", as_url=True)
        sub_example_img = get_asset_path("sub_example.png", as_url=True)

        inst_html = (
            "<h2>Как пользоваться программой</h2>"
            "<h3>Настройки Safari</h3>"
            "<p>Если вы пользуетесь браузером Safari, панель разработчика по умолчанию скрыта. Чтобы её включить:</p>"
            "<p class='guide-item'>1. Откройте меню <b>Safari -> Настройки</b> (или нажмите сочетание клавиш <code>Cmd + ,</code>).</p>"
            "<p class='guide-item'>2. Перейдите во вкладку <b>Дополнения</b> (Advanced).</p>"
            "<p class='guide-item'>3. В самом низу поставьте галочку <b>«Показывать функции для веб-разработчиков»</b> (или <i>«Показывать меню Разработка в строке меню»</i>).</p>"
            f"<p class='guide-image'><a href='safari_dev.png'><img src='{safari_img}' width='480'></a></p>"
            "<p>После этого открыть консоль разработчика можно будет сочетанием клавиш <code>Option + Cmd + I</code>.</p>"

            "<h3 class='guide-step'>Шаг 1. Откройте нужный сайт в браузере</h3>"
            "<p>Зайдите на сайт с фильмом или сериалом и перейдите на страницу с видеоплеером.</p>"

            "<h3 class='guide-step'>Шаг 2. Откройте панель разработчика (DevTools)</h3>"
            "<p>Нажмите сочетание клавиш на клавиатуре:</p>"
            "<p class='guide-item'>• На Mac: <code>Option + Cmd + I</code></p>"
            "<p class='guide-item'>• На Windows/Linux: <code>F12</code> или <code>Ctrl + Shift + I</code></p>"

            "<h3 class='guide-step'>Шаг 3. Перейдите во вкладку Network (Сеть) и настройте фильтр</h3>"
            "<p>В открывшейся панели выберите вкладку <b>Network</b> (Сеть).</p>"
            "<p>Чтобы не путаться в тысячах запросов, воспользуйтесь полем фильтра поиска (<b>Filter</b>) в верхнем левом углу панели разработчика:</p>"
            f"<p class='guide-image'><a href='filter_devtools.png'><img src='{filter_img}' width='480'></a></p>"
            "<p>Введите в это поле фразу поиска: <code>.m3u8</code>.</p>"
            "<table class='guide-note' width='100%' cellspacing='0' cellpadding='13'><tr><td><p><i>(Сделайте это строго до запуска видео, чтобы браузер не пропустил самый первый, самый важный запрос плеера. Если вы открыли вкладку Network позже и файлы не появились — просто обновите страницу кнопкой в браузере или сочетанием клавиш <code>Cmd+R</code> / <code>Ctrl+F5</code>).</i></p></td></tr></table>"

            "<h3 class='guide-step'>Шаг 4. Запустите воспроизведение видео</h3>"
            "<p>Включите плеер на сайте. Браузер сразу начнет запрашивать у сервера плейлисты видеопотоков, и в вашем списке Network начнут появляться ссылки.</p>"

            "<h3 class='guide-step'>Шаг 5. Найдите ссылки на видео</h3>"
            "<p>В отфильтрованном списке Network вы увидите один или несколько файлов с расширением <code>.m3u8</code>.</p>"

            "<h3>💡 Как определить, какая именно ссылка вам нужна?</h3>"
            "<p>Сайты могут отправлять множество запросов, но нам нужен главный файл — <b>Мастер-плейлист</b>. Определить его можно по следующим характерным признакам:</p>"
            "<p class='guide-item'>1. <b>Самый первый по времени:</b> Нужный плейлист всегда загружается в первую же секунду при открытии плеера (он окажется на самом верху списка).</p>"
            "<p class='guide-item'>2. <b>Ориентируйтесь по типу данных:</b> В любом браузере (Chrome, Safari, Firefox) эти файлы обычно классифицируются как <b>XHR</b>, <b>Fetch</b>, <b>Document</b> или просто <b>Другое (Other)</b>.</p>"
            "<p class='guide-item'>3. <b>Файл, в предпросмотре которого описаны несколько разрешений:</b> Кликните по файлу в списке и откройте вкладку <b>Preview</b> (Предпросмотр) или <b>Response</b> (Ответ) на панели справа. В нём должны быть описаны разрешения по типу 480p, 720p, 1080p:</p>"

            "<table class='guide-note' width='100%' cellspacing='0' cellpadding='13'><tr><td><p>• <b>Важно:</b> Если нужный файл субтитров или видео долгое время не появляется в списке — просто перезагрузите страницу сайта кнопкой в браузере или нажмите сочетание клавиш <code>Cmd+R</code> (или <code>Ctrl+F5</code> на Windows), чтобы плеер отправил запросы заново.</p></td></tr></table>"

            f"<p class='guide-image'><a href='master_example.png'><img src='{master_img}' width='480'></a></p>"
            "<p><b>Пример структуры мастер-файла в предпросмотре:</b></p>"
            "<table class='guide-example' width='100%' cellspacing='0' cellpadding='13'><tr><td><pre>"
            "#EXTM3U\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=2892000,RESOLUTION=1280x720\n"
            "./720.mp4:hls:manifest.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=5592000,RESOLUTION=1920x1080\n"
            "./1080.mp4:hls:manifest.m3u8"
            "</pre></td></tr></table>"
            "<p>Если вы нашли такой файл, скопируйте на него ссылку: кликните правой кнопкой мыши -> <b>Copy -> Copy link address</b>.</p>"

            "<h3>ℹ️ Замечание: Как скачать другую озвучку или субтитры?</h3>"
            "<p>Обычно плеер сразу подгружает видеофайл и файлы субтитров по умолчанию. Если вам нужна оригинальная звуковая дорожка или другие субтитры (например, английские):</p>"
            "<p class='guide-item'>1. Измените настройки языка, озвучки или субтитров в самом плеере на сайте.</p>"
            "<p class='guide-item'>2. В этот момент в список Network сразу же подгрузится новый файл плейлиста. Скопируйте ссылку на него (для поиска субтитров можно настроить фильтр на <code>.vtt</code> или <code>.srt</code>).</p>"
            "<p class='guide-item'>• Чтобы проверить, правильный ли это файл субтитров, откройте вкладку <b>Preview</b> (Предпросмотр). Текст внутри должен выглядеть осмысленно — содержать временные метки (таймкоды) и реплики диалогов, как показано на скриншоте ниже:</p>"
            f"<p class='guide-image'><a href='sub_example.png'><img src='{sub_example_img}' width='480'></a></p>"

            "<h3 class='guide-step'>Шаг 6. Перенесите ссылки в программу и выберите качество</h3>"
            "<p>Вставьте скопированную ссылку в поле <b>Видео URL</b> в приложении.</p>"
            "<p class='guide-item'>• Программа в фоновом режиме автоматически проанализирует поток и выведет удобный выпадающий список <b>Качество видео</b>. Выберите нужное разрешение (1080p, 720p, 480p и т.д.).</p>"
            "<p class='guide-item'>• При необходимости вставьте скопированную ссылку на субтитры в поле <b>Субтитры URL</b> (если они вам нужны). Имя файла сгенерируется автоматически.</p>"

            "<h3 class='guide-step'>Шаг 7. Запустите скачивание</h3>"
            "<p>Выберите папку для сохранения на вашем компьютере и нажмите кнопку <b>🚀 Начать загрузку</b>.</p>"
            "<table class='guide-note' width='100%' cellspacing='0' cellpadding='13'><tr><td><p><i>Программа сама скачает все фрагменты, склеит видео с субтитрами и упакует их в готовый файл без потери качества!</i></p></td></tr></table>"

            "<h3>🎬 Как запустить скачанное видео и включить субтитры?</h3>"
            "<p>Поскольку приложение склеивает видео и субтитры в контейнер высокого разрешения <code>.mkv</code>, стандартный плеер Mac (QuickTime Player) не сможет его воспроизвести.</p>"
            "<p class='guide-item'>• <b>Используйте VLC Player:</b> Мы настоятельно рекомендуем скачать и использовать бесплатный плеер <b>VLC Player</b> для воспроизведения ваших фильмов.</p>"
            "<p class='guide-item'>• <b>Как включить субтитры в VLC:</b> Откройте видео в VLC, в верхнем меню Mac выберите: <b>Субтитры -> Дорожка субтитров</b> и выберите нужный язык (например, «Русский» или «Дорожка 1»).</p>"
            "<p class='guide-item'>• <b>Что делать, если субтитры отстают или спешат:</b> Вы можете легко синхронизировать их прямо во время просмотра с помощью горячих клавиш на клавиатуре:</p>"
            "<p class='guide-item'>  - Клавиша <code>H</code> — задерживает субтитры (сдвигает их назад на 50 мс за каждое нажатие).</p>"
            "<p class='guide-item'>  - Клавиша <code>J</code> — ускоряет субтитры (сдвигает их вперед на 50 мс за каждое нажатие).</p>"
            "<p class='guide-item'>  - С помощью этих клавиш можно идеально выровнять тайминг за пару секунд, если на сайте была заложена нестандартная задержка.</p>"
        )

        self.guide_html = inst_html.replace("🚀 Начать загрузку", "Начать загрузку")
        self.inst_browser.anchorClicked.connect(self.on_instruction_image_clicked)
        inst_main_layout.addWidget(self.inst_browser)
        self.tabs.addTab(self.tab_instructions, "Инструкция")
        self.tabs.addTab(self.build_about_page(), "О программе")

        self.add_movie_row()
        self.add_episode_row()
        self.splitter.addWidget(self.build_download_footer())
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([480, 165])
        self.tabs.currentChanged.connect(self.show_page)
        self.show_page(0)
        self.movie_rows[0].video_url.setFocus()

    def build_navigation(self):
        sidebar = QFrame(objectName="Sidebar")
        sidebar.setFixedWidth(204)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        self.brand_icon = QLabel()
        self.brand_icon.setFixedSize(38, 38)
        brand.addWidget(self.brand_icon)
        brand.addWidget(QLabel("Stream Video\nDownloader", objectName="Brand"), 1)
        layout.addLayout(brand)
        layout.addSpacing(28)

        self.navigation = QWidget()
        nav_layout = QVBoxLayout(self.navigation)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)
        self.nav_group = QButtonGroup(self.navigation)
        self.nav_buttons = []
        for section, entries in (
            ("ЗАГРУЗКИ", (("Фильмы", "movie"), ("Сериалы", "series"))),
            ("ПРИЛОЖЕНИЕ", (("Инструкция", "guide"), ("О программе", "info"))),
        ):
            if self.nav_buttons:
                nav_layout.addSpacing(20)
            nav_layout.addWidget(QLabel(section, objectName="NavSection"))
            for title, glyph in entries:
                button = QPushButton(title, objectName="NavButton", checkable=True)
                button.setIconSize(QSize(22, 22))
                self.nav_group.addButton(button, len(self.nav_buttons))
                self.nav_buttons.append((button, glyph))
                nav_layout.addWidget(button)
        self.nav_group.idClicked.connect(lambda index: self.tabs.setCurrentIndex(index))
        layout.addWidget(self.navigation)
        layout.addStretch()

        theme_label = QLabel("ТЕМА", objectName="NavSection")
        theme_selector = QWidget(objectName="ThemeSelector")
        theme_layout = QHBoxLayout(theme_selector)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.setSpacing(4)
        self.theme_group = QButtonGroup(theme_selector)
        for label, scheme, palettes in (
            ("Авто", Qt.ColorScheme.Unknown, (LIGHT, DARK)),
            ("Светлая", Qt.ColorScheme.Light, (LIGHT,)),
            ("Тёмная", Qt.ColorScheme.Dark, (DARK,)),
        ):
            button = QToolButton(text=label, objectName="ThemeOption", checkable=True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setIcon(appearance_preview(*palettes))
            button.setIconSize(QSize(44, 28))
            if scheme == Qt.ColorScheme.Unknown:
                button.setToolTip("Следовать теме macOS")
                button.setAccessibleName("Системная тема")
            self.theme_group.addButton(button, scheme.value)
            theme_layout.addWidget(button, 1)

        saved_theme = self.settings.value("appearance", "Unknown", type=str)
        scheme = Qt.ColorScheme.__members__.get(saved_theme, Qt.ColorScheme.Unknown)
        self.theme_group.button(scheme.value).setChecked(True)
        self.theme_group.idClicked.connect(self.change_appearance)
        theme_label.setBuddy(self.theme_group.button(Qt.ColorScheme.Unknown.value))
        layout.addWidget(theme_label)
        layout.addWidget(theme_selector)
        return sidebar

    def add_download_page(self, title, action, callback):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.addWidget(QLabel(title, objectName="PageTitle"), 1)
        add_button = QPushButton(action)
        add_button.clicked.connect(callback)
        header.addWidget(add_button)
        layout.addLayout(header)

        scroll = QScrollArea(widgetResizable=True)
        content = QWidget(objectName="Queue")
        rows = QVBoxLayout(content)
        rows.setContentsMargins(0, 1, 1, 1)
        rows.setSpacing(12)
        rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.tabs.addTab(page, title)
        return add_button, rows

    def build_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame(objectName="Card")
        card.setMinimumWidth(340)
        contents = QVBoxLayout(card)
        contents.setContentsMargins(32, 32, 32, 32)
        contents.setSpacing(12)
        self.about_icon = QLabel()
        contents.addWidget(self.about_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Stream Video Downloader", objectName="CardTitle")
        contents.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        version = QLabel(f"Версия {CURRENT_VERSION}")
        version.setProperty("muted", True)
        contents.addWidget(version, alignment=Qt.AlignmentFlag.AlignCenter)
        contents.addSpacing(8)
        self.manual_update_btn = QPushButton("Проверить обновления")
        self.manual_update_btn.clicked.connect(self.manual_check_for_updates)
        contents.addWidget(self.manual_update_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(card)
        return page

    def build_download_footer(self):
        footer = QWidget()
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        activity = QFrame(objectName="Activity")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(16, 8, 16, 8)
        activity_layout.setSpacing(2)
        activity_header = QHBoxLayout()
        activity_header.addWidget(QLabel("Журнал загрузок", objectName="ActivityTitle"), 1)
        self.log_toggle = QPushButton("Свернуть", objectName="Quiet", checkable=True, checked=True)
        self.log_toggle.toggled.connect(self.toggle_log)
        activity_header.addWidget(self.log_toggle)
        activity_layout.addLayout(activity_header)
        self.log_output = ActivityLog()
        activity_layout.addWidget(self.log_output, 1)
        layout.addWidget(activity, 1)

        self.download_controls = QFrame(objectName="DownloadControls")
        controls = QVBoxLayout(self.download_controls)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.folder_icon = QLabel()
        action_row.addWidget(self.folder_icon)
        destination = QVBoxLayout()
        destination.setSpacing(0)
        folder_label = QLabel("Папка сохранения", objectName="FieldLabel")
        self.dir_input = QLineEdit(DEFAULT_DOWNLOAD_DIR, objectName="Destination", readOnly=True)
        folder_label.setBuddy(self.dir_input)
        destination.addWidget(folder_label)
        destination.addWidget(self.dir_input)
        action_row.addLayout(destination, 1)
        self.browse_btn = QPushButton("Выбрать…")
        self.browse_btn.clicked.connect(self.on_browse_clicked)
        action_row.addWidget(self.browse_btn)
        self.download_btn = QPushButton("Начать загрузку", objectName="Primary")
        self.download_btn.clicked.connect(self.on_download_clicked)
        action_row.addWidget(self.download_btn)
        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.clicked.connect(self.on_pause_clicked)
        self.pause_btn.hide()
        action_row.addWidget(self.pause_btn)
        self.cancel_btn = QPushButton("Отменить", objectName="Danger")
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        self.cancel_btn.hide()
        action_row.addWidget(self.cancel_btn)
        controls.addLayout(action_row)

        progress_row = QHBoxLayout()
        self.progress_label = QLabel(objectName="ProgressText")
        self.progress_label.setWordWrap(True)
        self.progress_percent = QLabel(objectName="ProgressText")
        progress_row.addWidget(self.progress_label, 1)
        progress_row.addWidget(self.progress_percent)
        self.progress_bar = QProgressBar(textVisible=False)
        controls.addLayout(progress_row)
        controls.addWidget(self.progress_bar)
        for widget in (self.progress_label, self.progress_percent, self.progress_bar):
            widget.hide()
        layout.addWidget(self.download_controls)
        return footer

    def toggle_log(self, expanded):
        self.log_output.setVisible(expanded)
        self.log_toggle.setText("Свернуть" if expanded else "Развернуть")
        footer = self.splitter.widget(1)
        height = 165 if expanded else footer.minimumSizeHint().height()
        self.splitter.setSizes([self.splitter.height() - height, height])

    def show_page(self, index):
        self.nav_group.button(index).setChecked(True)
        self.splitter.widget(1).setVisible(index < 2 or self.queue_rows is not None)

    def change_appearance(self, button_id=None):
        scheme = Qt.ColorScheme(self.theme_group.checkedId())
        if button_id is not None:
            self.settings.setValue("appearance", scheme.name)
        hints = QApplication.styleHints()
        if hasattr(hints, "setColorScheme"):
            hints.setColorScheme(scheme)
        self.apply_appearance()

    def apply_appearance(self, scheme=None):
        selected = Qt.ColorScheme(self.theme_group.checkedId())
        if selected != Qt.ColorScheme.Unknown:
            scheme = selected
        elif scheme is None:
            scheme = QApplication.styleHints().colorScheme()
        dark = scheme == Qt.ColorScheme.Dark
        if scheme == Qt.ColorScheme.Unknown:
            dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        colors = DARK if dark else LIGHT
        self.setStyleSheet(STYLE.format(**colors))
        self.log_output.set_colors(colors)
        logo = symbol("download", "#ffffff", colors["accent"])
        self.brand_icon.setPixmap(logo.pixmap(QSize(38, 38)))
        self.about_icon.setPixmap(logo.pixmap(QSize(48, 48)))
        for button, glyph in self.nav_buttons:
            button.setIcon(symbol(glyph, colors["secondary"]))
        for button in (self.add_movie_btn, self.add_ep_btn):
            button.setIcon(symbol("plus", colors["text"]))
            button.setIconSize(QSize(18, 18))
        self.download_btn.setIcon(symbol("download", "#ffffff"))
        self.download_btn.setIconSize(QSize(18, 18))
        self.folder_icon.setPixmap(symbol("folder", colors["secondary"]).pixmap(QSize(25, 25)))
        scroll = self.inst_browser.verticalScrollBar()
        position = scroll.value()
        guide_style = GUIDE_STYLE.format(**colors)
        self.inst_browser.setHtml(f"<style>{guide_style}</style>{self.guide_html}")
        scroll.setValue(position)

    def add_movie_row(self):
        """Добавляет карточку фильма."""
        row = MovieRowWidget(self.remove_movie_row)
        self.scroll_area_movie_layout.addWidget(row)
        self.movie_rows.append(row)
        if self.queue_rows is self.movie_rows:
            self.enqueue_row(row)
        self.update_row_positions(self.movie_rows)

    def remove_movie_row(self, row_widget):
        """Удаляет карточку фильма."""
        if row_widget is self.active_row:
            return
        if len(self.movie_rows) <= 1:
            self.append_log("Оставьте хотя бы одну карточку.", "warning")
            return
        self.scroll_area_movie_layout.removeWidget(row_widget)
        self.movie_rows.remove(row_widget)
        if row_widget in self.pending_rows:
            self.pending_rows.remove(row_widget)
        row_widget.hide()
        row_widget.cancel_quality_search()
        row_widget.deleteLater()
        self.update_row_positions(self.movie_rows)

    def add_episode_row(self):
        """Добавляет карточку серии."""
        row = EpisodeRowWidget(self.remove_episode_row)
        self.scroll_area_series_layout.addWidget(row)
        self.episode_rows.append(row)
        if self.queue_rows is self.episode_rows:
            self.enqueue_row(row)
        self.update_row_positions(self.episode_rows)

    def remove_episode_row(self, row_widget):
        """Удаляет карточку серии."""
        if row_widget is self.active_row:
            return
        if len(self.episode_rows) <= 1:
            self.append_log("Оставьте хотя бы одну карточку.", "warning")
            return
        self.scroll_area_series_layout.removeWidget(row_widget)
        self.episode_rows.remove(row_widget)
        if row_widget in self.pending_rows:
            self.pending_rows.remove(row_widget)
        row_widget.hide()
        row_widget.cancel_quality_search()
        row_widget.deleteLater()
        self.update_row_positions(self.episode_rows)

    @staticmethod
    def update_row_positions(rows):
        for position, row in enumerate(rows, start=1):
            row.set_position(position, can_remove=len(rows) > 1)

    def append_log(self, message, level="info"):
        self.log_output.add_entry(message, level)

    def update_progress(self, percent, status_text):
        self.progress_bar.setValue(percent)
        self.progress_percent.setText(f"{percent}%")
        if status_text:
            self.progress_text = status_text
        if self.active_row is not None and not self.logic.control.paused and not self.logic.control.cancelled:
            self.progress_label.setText(f"{self.active_row.title.text()} · {self.progress_text}")
        for widget in (self.progress_label, self.progress_percent, self.progress_bar):
            widget.show()

    def on_browse_clicked(self):
        selected_directory = QFileDialog.getExistingDirectory(
            self, "Выбрать папку для сохранения", self.dir_input.text()
        )
        if selected_directory:
            self.dir_input.setText(selected_directory)

    def on_download_clicked(self):
        if self.queue_rows is not None:
            return
        page = self.tabs.currentIndex()
        if page not in (0, 1):
            return
        rows = self.movie_rows if page == 0 else self.episode_rows
        for row in rows:
            item = row.download_options()
            if not (item['video_url'] or item['sub_url']):
                self.append_log(f"Укажите ссылку на видео или субтитры в карточке «{row.title.text()}».", "warning")
                return

        self.queue_rows = rows
        self.pending_rows = []
        for row in rows:
            self.enqueue_row(row)
        self.queue_dir = self.dir_input.text().strip()
        self.queue_position = 0
        self.queue_has_errors = False
        self.logic.start_queue()
        self.browse_btn.setEnabled(False)
        self.download_btn.hide()
        self.pause_btn.show()
        self.cancel_btn.show()
        self.start_next_download()

    def enqueue_row(self, row):
        row.set_download_status("В очереди")
        self.pending_rows.append(row)

    def start_next_download(self):
        if self.logic.control.paused:
            return
        if not self.pending_rows:
            self.finish_queue()
            return

        row = self.pending_rows[0]
        item = row.download_options()
        if not (item['video_url'] or item['sub_url']):
            row.set_download_status("Нужна ссылка")
            self.pause_queue(f"Добавьте ссылку в карточке «{row.title.text()}» и продолжите загрузку.")
            return

        self.pending_rows.pop(0)
        self.active_row = row
        row.cancel_quality_search()
        row.refresh_quality_btn.setEnabled(True)
        if row.quality_combo.currentText() == "Поиск качества…":
            row.quality_combo.setItemText(row.quality_combo.currentIndex(), "Авто (Максимальное)")
        row.setEnabled(False)
        row.set_download_status("Загрузка")
        self.queue_position += 1
        total = self.queue_position + len(self.pending_rows)
        title = item['output_name'] or row.title.text()
        self.append_log(f"{self.queue_position} из {total} · {title}", "start")
        self.update_progress(0, "Подготовка")
        self.logic.start_download(item, self.queue_dir)

    def check_for_updates(self):
        """Запускает фоновую проверку обновлений на GitHub."""
        self.updater_thread = UpdateChecker(CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO)
        self.updater_thread.update_available.connect(self.on_update_available)
        self.updater_thread.error.connect(lambda err: self.append_log(err, "warning"))
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
        self.append_log("Установка обновления. Приложение перезапустится.")
        apply_update_and_restart(extracted_app_path)

    def on_update_error(self, error_msg):
        """Вызывается в случае ошибки при скачивании архива."""
        if hasattr(self, 'upd_progress_dialog') and self.upd_progress_dialog:
            self.upd_progress_dialog.close()
        QMessageBox.critical(self, "Ошибка обновления", f"Не удалось обновить приложение:\n{error_msg}")

    def pause_queue(self, message):
        self.logic.pause()
        self.pause_btn.setText("Продолжить")
        self.progress_text = message
        self.progress_label.setText(message)
        if self.active_row is not None:
            self.active_row.set_download_status("Пауза")
        self.append_log(message)

    def on_pause_clicked(self):
        if self.queue_rows is None or self.logic.control.cancelled:
            return
        if self.logic.control.paused:
            self.logic.resume()
            self.pause_btn.setText("Пауза")
            self.append_log("Загрузка возобновлена")
            if self.active_row is None:
                self.start_next_download()
            else:
                self.active_row.set_download_status("Загрузка")
                self.update_progress(self.progress_bar.value(), "Загрузка возобновлена")
        else:
            message = f"{self.active_row.title.text()} · Пауза" if self.active_row else "Очередь на паузе"
            self.pause_queue(message)

    def on_cancel_clicked(self):
        if self.queue_rows is None:
            return
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.logic.cancel()
        self.progress_label.setText("Остановка загрузки…")
        if self.active_row is None:
            self.finish_queue()

    def handle_download_done(self, status):
        row = self.active_row
        row.setEnabled(True)
        row.set_download_status({"success": "Готово", "error": "Ошибка", "cancelled": "Отменено"}[status])
        self.active_row = None
        self.queue_has_errors |= status == 'error'
        if self.logic.control.cancelled:
            self.finish_queue()
        else:
            self.start_next_download()

    def finish_queue(self):
        if self.logic.control.cancelled:
            self.append_log("Очередь отменена")
        elif self.queue_has_errors:
            self.append_log("Очередь завершена с ошибками", "warning")
        else:
            self.append_log("Загрузка очереди завершена", "success")

        for row in self.pending_rows:
            row.set_download_status("")
        self.pending_rows.clear()
        self.queue_rows = None
        self.browse_btn.setEnabled(True)
        self.download_btn.show()
        self.pause_btn.setText("Пауза")
        for button in (self.pause_btn, self.cancel_btn):
            button.hide()
            button.setEnabled(True)
        for widget in (self.progress_label, self.progress_percent, self.progress_bar):
            widget.hide()
        self.show_page(self.tabs.currentIndex())
        if self.close_after_queue:
            QTimer.singleShot(0, self.close)

    def manual_check_for_updates(self):
        """Ручной запуск проверки обновлений по кнопке во вкладке."""
        self.append_log("Проверка обновлений")
        self.manual_update_btn.setEnabled(False)
        self.manual_update_btn.setText("Проверяю…")
        self.manual_check_reported = False

        self.manual_updater = UpdateChecker(CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO)
        self.manual_updater.update_available.connect(self.on_manual_update_available)
        self.manual_updater.finished.connect(self.on_manual_check_finished)
        self.manual_updater.error.connect(self.on_manual_check_error)
        self.manual_updater.start()

    def on_manual_update_available(self, version, changelog, download_url):
        """Вызывается, если при ручной проверке найдено обновление."""
        self.manual_check_reported = True
        self.on_update_available(version, changelog, download_url)

    def on_manual_check_finished(self):
        """Вызывается, когда поток проверки завершил работу."""
        self.manual_update_btn.setEnabled(True)
        self.manual_update_btn.setText("Проверить обновления")

        if not self.manual_check_reported:
            QMessageBox.information(
                self, "Обновления",
                "У вас установлена самая актуальная версия программы!"
            )
            self.append_log("Установлена последняя версия приложения.", "success")

    def on_manual_check_error(self, err_msg):
        """Вызывается при ошибке сети во время ручной проверки."""
        self.manual_check_reported = True
        QMessageBox.warning(self, "Не удалось проверить обновления", err_msg)

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
