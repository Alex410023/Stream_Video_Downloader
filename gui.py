import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QTextEdit, QScrollArea,
                             QProgressBar, QLabel, QTabWidget, QFormLayout,
                             QSpinBox, QFileDialog, QFrame, QSplitter,
                             QMessageBox, QProgressDialog)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont

from config import DEFAULT_DOWNLOAD_DIR, CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO
from updater import UpdateChecker, UpdateDownloader, apply_update_and_restart
from name_generator import generate_movie_name, generate_series_name
from logic import DownloaderLogic


class GUISignals(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    done_signal = pyqtSignal()


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
            QLineEdit {
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
        self.check_for_updates()

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

        # 2. Поле для субтитров
        row2 = QHBoxLayout()
        self.sub_url = QLineEdit()
        self.sub_url.setPlaceholderText("Вставь ссылку на субтитры фильма .vtt или .srt (необязательно)...")
        # ДОБАВЛЕНО: реагируем на вставку субтитров для автогенерации имени
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
        # ИСправлено: берем видео, а если его нет - ссылку на сабы
        url = self.video_url.text().strip() or self.sub_url.text().strip()
        suggested_name = generate_movie_name(url)
        if suggested_name:
            self.filename.setText(suggested_name)


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
            QLineEdit, QSpinBox {
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

        # 2. Поле для субтитров
        row2 = QHBoxLayout()
        self.sub_url = QLineEdit()
        self.sub_url.setPlaceholderText("Вставь ссылку на субтитры серии .vtt или .srt (необязательно)...")
        # ДОБАВЛЕНО: реагируем на вставку субтитров для автогенерации имени
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
        # ИСПРАВЛЕНО: берем видео, а если его нет - ссылку на сабы
        url = self.video_url.text().strip() or self.sub_url.text().strip()
        season = self.season.value()
        episode = self.episode.value()
        suggested_name = generate_series_name(url, season, episode)
        if suggested_name:
            self.filename.setText(suggested_name)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stream Video Downloader")
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
            on_progress=lambda percent: self.signals.progress_signal.emit(percent),
            on_done=lambda: self.signals.done_signal.emit()
        )

        self.movie_rows = []
        self.episode_rows = []

        self.init_ui()

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
        # Чтобы можно было менять размер карточек отдельно от панели управления
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

        # Добавляем стартовые карточки по умолчанию
        self.add_movie_row()
        self.add_episode_row()

        self.splitter.addWidget(self.top_container)

        # ================= НИЖНИЙ БЛОК (ПАПКА + КНОПКИ + ЛОГИ) =================
        # Теперь весь нижний блок (настройки, кнопки, логи) масштабируется вместе!
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

        # Задаем начальное распределение размеров (верх со скроллом: 450px, нижний блок настроек и логов: 300px)
        self.splitter.setSizes([450, 300])

        self.append_log(
            "Система готова. Настройте файлы и нажмите 'Начать загрузку'. Размеры окон логов и настроек можно менять перетаскиванием разделителя.")

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

    def update_progress(self, percent):
        if not self.progress_bar.isVisible():
            self.progress_bar.show()
        self.progress_bar.setValue(percent)

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

                # ИСПРАВЛЕНО: проверяем, что хотя бы одно из полей заполнено
                if not video_url and not sub_url:
                    self.append_log(f"⚠️ Ошибка: В карточке фильма #{i + 1} нужно указать ссылку на видео или субтитры!")
                    return

                queue.append({
                    'video_url': video_url,
                    'sub_url': sub_url,
                    'output_name': output_name
                })
        else:  # Режим Сериала
            for i, row in enumerate(self.episode_rows):
                video_url = row.video_url.text().strip()
                sub_url = row.sub_url.text().strip()
                output_name = row.filename.text().strip()

                # ИСПРАВЛЕНО: проверяем, что хотя бы одно из полей заполнено
                if not video_url and not sub_url:
                    self.append_log(f"⚠️ Ошибка: В карточке серии #{i + 1} нужно указать ссылку на видео или субтитры!")
                    return

                queue.append({
                    'video_url': video_url,
                    'sub_url': sub_url,
                    'output_name': output_name
                })

        download_dir = self.dir_input.text().strip()

        # Блокировка интерфейса
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

        # Запускаем очередь загрузок
        self.logic.start_download(queue, download_dir)

    def check_for_updates(self):
        """Запускает фоновую проверку обновлений."""
        self.updater_thread = UpdateChecker(CURRENT_VERSION, GITHUB_OWNER, GITHUB_REPO)
        self.updater_thread.update_available.connect(self.on_update_available)
        self.updater_thread.start()

    def on_update_available(self, version, changelog, download_url):
        """Спрашивает пользователя, хочет ли он обновиться."""
        reply = QMessageBox.question(
            self, "Доступно обновление",
            f"Вышла новая версия: {version}!\n\nЧто нового:\n{changelog}\n\nХотите обновить приложение сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.start_downloading_update(download_url)

    def start_downloading_update(self, download_url):
        """Показывает прогресс-бар скачивания новой версии."""
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

        # Если нажали "Отмена" при скачивании
        self.upd_progress_dialog.canceled.connect(self.download_thread.terminate)

        self.download_thread.start()

    def on_update_downloaded(self, extracted_app_path):
        """Закрывает окно прогресса и запускает установку."""
        self.upd_progress_dialog.close()
        self.append_log("🔄 Установка обновления... Приложение сейчас будет перезапущено.")
        apply_update_and_restart(extracted_app_path)

    def on_update_error(self, error_msg):
        if hasattr(self, 'upd_progress_dialog'):
            self.upd_progress_dialog.close()
        QMessageBox.critical(self, "Ошибка обновления", f"Не удалось обновить приложение:\n{error_msg}")

    def on_cancel_clicked(self):
        self.cancel_btn.setEnabled(False)
        self.logic.cancel()

    def handle_download_done(self):
        # Разблокировка интерфейса
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