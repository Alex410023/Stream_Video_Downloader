from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QSpinBox, QComboBox
from name_generator import generate_movie_name, generate_series_name
from resolution_parser import ResolutionParser


class MovieRowWidget(QFrame):
    """Компонент (карточка) для ввода данных одного фильма."""

    def __init__(self, remove_callback):
        super().__init__()
        self.remove_callback = remove_callback

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

        # 1.5. Поле выбора качества (скрыто по умолчанию)
        self.quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Качество видео:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Авто (Максимальное)", "best")
        self.quality_layout.addWidget(self.quality_label, stretch=0)
        self.quality_layout.addWidget(self.quality_combo, stretch=1)

        # Прячем элементы при инициализации
        self.quality_label.hide()
        self.quality_combo.hide()
        layout.addLayout(self.quality_layout)

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

        # Если ссылка на m3u8 изменилась — запускаем фоновый анализ разрешений
        if url.startswith("http") and ".m3u8" in url and url != getattr(self, 'last_parsed_url', ''):
            self.last_parsed_url = url

            # Останавливаем предыдущий парсер, если он работал
            if hasattr(self, 'parser') and self.parser.isRunning():
                try:
                    self.parser.finished.disconnect()
                except:
                    pass
                self.parser.terminate()

            # Сбрасываем список и пишем статус ожидания
            self.quality_combo.clear()
            self.quality_combo.addItem("⏳ Анализ потока...", "best")
            self.quality_label.show()
            self.quality_combo.show()

            self.parser = ResolutionParser(url)
            self.parser.finished.connect(self.on_resolutions_parsed)
            self.parser.start()

        elif not ".m3u8" in url:
            # Если это не m3u8 (например, прямая ссылка mp4), то скрываем выбор качества
            self.quality_label.hide()
            self.quality_combo.hide()
            self.quality_combo.clear()
            self.quality_combo.addItem("Авто (Максимальное)", "best")

    def on_resolutions_parsed(self, heights):
        self.quality_combo.clear()
        if heights:
            # Заполняем выпадающий список доступными качествами
            for h in heights:
                self.quality_combo.addItem(f"{h}p", h)
            # По умолчанию ставим максимальное качество (первый элемент)
            self.quality_combo.setCurrentIndex(0)
        else:
            # Если это не мастер-плейлист или произошла ошибка загрузки
            self.quality_combo.addItem("Авто (Максимальное)", "best")
            if not ".m3u8" in self.video_url.text():
                self.quality_label.hide()
                self.quality_combo.hide()


class EpisodeRowWidget(QFrame):
    """Компонент (карточка) для ввода данных одной серии."""

    def __init__(self, remove_callback):
        super().__init__()
        self.remove_callback = remove_callback

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

        # 1.5. Поле выбора качества (скрыто по умолчанию)
        self.quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Качество видео:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Авто (Максимальное)", "best")
        self.quality_layout.addWidget(self.quality_label, stretch=0)
        self.quality_layout.addWidget(self.quality_combo, stretch=1)

        # Прячем элементы при инициализации
        self.quality_label.hide()
        self.quality_combo.hide()
        layout.addLayout(self.quality_layout)

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

        # Если ссылка на m3u8 изменилась — запускаем фоновый анализ разрешений
        if url.startswith("http") and ".m3u8" in url and url != getattr(self, 'last_parsed_url', ''):
            self.last_parsed_url = url

            # Останавливаем предыдущий парсер, если он работал
            if hasattr(self, 'parser') and self.parser.isRunning():
                try:
                    self.parser.finished.disconnect()
                except:
                    pass
                self.parser.terminate()

            # Сбрасываем список и пишем статус ожидания
            self.quality_combo.clear()
            self.quality_combo.addItem("⏳ Анализ потока...", "best")
            self.quality_label.show()
            self.quality_combo.show()

            self.parser = ResolutionParser(url)
            self.parser.finished.connect(self.on_resolutions_parsed)
            self.parser.start()

        elif not ".m3u8" in url:
            # Если это не m3u8 (например, прямая ссылка mp4), то скрываем выбор качества
            self.quality_label.hide()
            self.quality_combo.hide()
            self.quality_combo.clear()
            self.quality_combo.addItem("Авто (Максимальное)", "best")

    def on_resolutions_parsed(self, heights):
        self.quality_combo.clear()
        if heights:
            # Заполняем выпадающий список доступными качествами
            for h in heights:
                self.quality_combo.addItem(f"{h}p", h)
            # По умолчанию ставим максимальное качество (первый элемент)
            self.quality_combo.setCurrentIndex(0)
        else:
            # Если это не мастер-плейлист или произошла ошибка загрузки
            self.quality_combo.addItem("Авто (Максимальное)", "best")
            if not ".m3u8" in self.video_url.text():
                self.quality_label.hide()
                self.quality_combo.hide()