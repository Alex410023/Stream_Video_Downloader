from PyQt6.QtCore import QThreadPool, QTimer, Qt
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QSpinBox, QComboBox
from src.name_generator import generate_movie_name, generate_series_name
from src.resolution_parser import ResolutionParser, is_hls_url


class _DownloadRowWidget(QFrame):
    VIDEO_URL_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, remove_callback):
        super().__init__()
        self.remove_callback = remove_callback
        self._quality_url = ''
        self._quality_task = None
        self._quality_timer = QTimer(self)
        self._quality_timer.setSingleShot(True)
        self._quality_timer.setInterval(250)
        self._quality_timer.timeout.connect(self._start_quality_search)

    def _add_quality_selector(self, layout):
        quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Качество видео:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Авто (Максимальное)", "best")
        quality_layout.addWidget(self.quality_label)
        quality_layout.addWidget(self.quality_combo, stretch=1)
        layout.addLayout(quality_layout)
        self.quality_label.hide()
        self.quality_combo.hide()

    def cancel_quality_search(self):
        self._quality_timer.stop()
        if self._quality_task is not None:
            self._quality_task.cancelled.set()
            self._quality_task = None

    def _update_quality_url(self, url):
        if url == self._quality_url:
            return
        self.cancel_quality_search()
        self._quality_url = url
        is_hls = is_hls_url(url)
        self.quality_combo.clear()
        self.quality_combo.addItem("Поиск качества…" if is_hls else "Авто (Максимальное)", "best")
        self.quality_combo.setVisible(is_hls)
        self.quality_label.setVisible(is_hls)
        if is_hls:
            self._quality_timer.start()

    def _start_quality_search(self):
        self._quality_task = ResolutionParser(self._quality_url)
        self._quality_task.signals.completed.connect(self._show_resolutions, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(self._quality_task)

    def _show_resolutions(self, task, options):
        if task is not self._quality_task:
            return
        self._quality_task = None
        self.quality_combo.clear()
        if not options:
            self.quality_combo.addItem("Авто (Максимальное)", "best")
            return

        for index, (height, direct_url) in enumerate(options):
            self.quality_combo.addItem(f"{height}p", str(height))
            self.quality_combo.setItemData(index, direct_url, self.VIDEO_URL_ROLE)
        original = next((index for index, (_, url) in enumerate(options)
                         if url is None or url == self._quality_url), 0)
        self.quality_combo.setCurrentIndex(original)

    def selected_video_url(self):
        return self.quality_combo.currentData(self.VIDEO_URL_ROLE) or self.video_url.text().strip()


class MovieRowWidget(_DownloadRowWidget):
    """Компонент (карточка) для ввода данных одного фильма."""

    def __init__(self, remove_callback):
        super().__init__(remove_callback)

        self.setStyleSheet("""
            QFrame {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                background-color: #252525;
                padding: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
                color: white;
            }
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #aaaaaa;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Поле для видео
        row1 = QHBoxLayout()
        self.video_url = QLineEdit()
        self.video_url.setPlaceholderText("Вставь прямую ссылку .m3u8 или .mp4 фильма из Network (DevTools)...")
        self.video_url.textChanged.connect(self.on_inputs_changed)
        row1.addWidget(QLabel("Видео URL:"), stretch=0)
        row1.addWidget(self.video_url, stretch=1)
        layout.addLayout(row1)

        self._add_quality_selector(layout)

        # 2. Поле для субтитров
        row2 = QHBoxLayout()
        self.sub_url = QLineEdit()
        self.sub_url.setPlaceholderText("Вставь ссылку на субтитры фильма .vtt или .srt (необязательно)...")
        self.sub_url.textChanged.connect(self.on_inputs_changed)
        row2.addWidget(QLabel("Субтитры URL:"), stretch=0)
        row2.addWidget(self.sub_url, stretch=1)
        layout.addLayout(row2)

        # 3. Название и кнопка удаления
        row3 = QHBoxLayout()
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("Имя сохраняемого файла...")

        self.delete_btn = QPushButton("🗑 Удалить")
        self.delete_btn.setObjectName("redBtn")
        self.delete_btn.clicked.connect(lambda: self.remove_callback(self))

        row3.addWidget(QLabel("Имя файла:"))
        row3.addWidget(self.filename, stretch=1)
        row3.addWidget(self.delete_btn)

        layout.addLayout(row3)

    def on_inputs_changed(self):
        url = self.video_url.text().strip()
        sub_url = self.sub_url.text().strip()

        # Генерация имени
        suggested_name = generate_movie_name(url or sub_url)
        if suggested_name:
            self.filename.setText(suggested_name)

        self._update_quality_url(url)


class EpisodeRowWidget(_DownloadRowWidget):
    """Компонент (карточка) для ввода данных одной серии."""

    def __init__(self, remove_callback):
        super().__init__(remove_callback)

        self.setStyleSheet("""
            QFrame {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                background-color: #252525;
                padding: 12px;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
                color: white;
            }
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #aaaaaa;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Поле для видео
        row1 = QHBoxLayout()
        self.video_url = QLineEdit()
        self.video_url.setPlaceholderText("Вставь прямую ссылку .m3u8 или .mp4 серии из Network (DevTools)...")
        self.video_url.textChanged.connect(self.on_inputs_changed)
        row1.addWidget(QLabel("Видео URL:"), stretch=0)
        row1.addWidget(self.video_url, stretch=1)
        layout.addLayout(row1)

        self._add_quality_selector(layout)

        # 2. Поле для субтитров
        row2 = QHBoxLayout()
        self.sub_url = QLineEdit()
        self.sub_url.setPlaceholderText("Вставь ссылку на субтитры серии .vtt или .srt (необязательно)...")
        self.sub_url.textChanged.connect(self.on_inputs_changed)
        row2.addWidget(QLabel("Субтитры URL:"), stretch=0)
        row2.addWidget(self.sub_url, stretch=1)
        layout.addLayout(row2)

        # 3. Сезон, Серия, Название и кнопка удаления
        row3 = QHBoxLayout()

        self.season = QSpinBox()
        self.season.setRange(1, 99)
        self.season.setValue(1)
        self.season.valueChanged.connect(self.on_inputs_changed)

        self.episode = QSpinBox()
        self.episode.setRange(1, 99)
        self.episode.setValue(1)
        self.episode.valueChanged.connect(self.on_inputs_changed)

        self.filename = QLineEdit()
        self.filename.setPlaceholderText("Имя сохраняемого файла...")

        self.delete_btn = QPushButton("🗑 Удалить")
        self.delete_btn.setObjectName("redBtn")
        self.delete_btn.clicked.connect(lambda: self.remove_callback(self))

        row3.addWidget(QLabel("Сезон:"))
        row3.addWidget(self.season)
        row3.addWidget(QLabel("Серия:"))
        row3.addWidget(self.episode)
        row3.addWidget(QLabel("Имя файла:"))
        row3.addWidget(self.filename, stretch=1)
        row3.addWidget(self.delete_btn)

        layout.addLayout(row3)

    def on_inputs_changed(self):
        url = self.video_url.text().strip()
        sub_url = self.sub_url.text().strip()
        season = self.season.value()
        episode = self.episode.value()

        # Генерация имени
        suggested_name = generate_series_name(url or sub_url, season, episode)
        if suggested_name:
            self.filename.setText(suggested_name)

        self._update_quality_url(url)
