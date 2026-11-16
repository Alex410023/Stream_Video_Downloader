from collections import deque

from PyQt6.QtCore import QPointF, QRectF, QThreadPool, QTime, QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextTable
from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSpinBox, QStyle, QStyleOptionComboBox, QTextBrowser, QTextEdit, QToolButton,
                             QVBoxLayout, QWidget)
from src.name_generator import generate_movie_name, generate_series_name
from src.resolution_parser import ResolutionParser, is_hls_url


class ActivityLog(QTextEdit):
    def __init__(self):
        super().__init__(objectName="ActivityLog", readOnly=True)
        self.setMinimumHeight(42)
        self.setPlaceholderText("Загрузок пока нет")
        self.entries = deque(maxlen=500)
        self.document().setMaximumBlockCount(self.entries.maxlen)

    def set_colors(self, colors):
        self.colors = colors
        scroll = self.verticalScrollBar()
        position = scroll.value()
        following = position == scroll.maximum()
        self.clear()
        cursor = QTextCursor(self.document())
        for entry in self.entries:
            self._render_entry(cursor, entry)
        scroll.setValue(scroll.maximum() if following else position)

    def add_entry(self, message, level):
        entry = (QTime.currentTime().toString("HH:mm:ss"), message, level)
        self.entries.append(entry)
        scroll = self.verticalScrollBar()
        following = scroll.value() == scroll.maximum()
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._render_entry(cursor, entry)
        if following:
            scroll.setValue(scroll.maximum())

    def _render_entry(self, cursor, entry):
        timestamp, message, level = entry
        block = QTextBlockFormat()
        block.setBottomMargin(6)
        if cursor.position():
            cursor.insertBlock(block)
        else:
            cursor.setBlockFormat(block)

        style = QTextCharFormat()
        style.setForeground(QColor(self.colors["secondary"]))
        cursor.insertText(f"{timestamp}    ", style)
        labels = {"error": ("Ошибка", "danger"), "warning": ("Внимание", "danger"),
                  "success": ("Готово", "success"), "start": ("Очередь", "focus")}
        if level in labels:
            label, color = labels[level]
            style.setForeground(QColor(self.colors[color]))
            style.setFontWeight(600)
            cursor.insertText(f"{label}    ", style)
        style.setForeground(QColor(self.colors["text"]))
        style.setFontWeight(400)
        cursor.insertText(message.replace("\n", "\u2028"), style)


class GuideBrowser(QTextBrowser):
    def __init__(self):
        super().__init__(objectName="Guide")

    def paintEvent(self, event):
        super().paintEvent(event)
        document = self.document()
        layout = document.documentLayout()
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(-self.horizontalScrollBar().value(), -self.verticalScrollBar().value())
        for frame in document.rootFrame().childFrames():
            if not isinstance(frame, QTextTable) or frame.rows() != 1 or frame.columns() != 1:
                continue
            bounds = layout.frameBoundingRect(frame)
            table_format = frame.format()
            # The layout reports the cell origin after padding and includes the table's vertical margins.
            padding = table_format.cellPadding()
            bounds.translate(-padding, -padding)
            bounds.setHeight(bounds.height() - table_format.topMargin() - table_format.bottomMargin())
            bounds = QRectF(bounds.toAlignedRect())
            corners = QPainterPath()
            corners.addRect(bounds)
            rounded = QPainterPath()
            rounded.addRoundedRect(bounds, 12, 12)
            painter.fillPath(corners.subtracted(rounded), self.viewport().palette().base())
        painter.end()


def _paint_chevron(painter, center, direction, color):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, 1.4, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    x, y = center.x(), center.y()
    offset = 1.75 * direction
    painter.drawPolyline(QPolygonF([
        QPointF(x - 3.5, y + offset), QPointF(x, y - offset), QPointF(x + 3.5, y + offset),
    ]))


class _QualityComboBox(QComboBox):
    def __init__(self):
        super().__init__(objectName="QualityCombo")

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                            QStyle.SubControl.SC_ComboBoxArrow, self)
        palette = self.palette()
        color = palette.placeholderText() if self.isEnabled() else palette.buttonText()
        _paint_chevron(QPainter(self), QRectF(arrow).center(), -1, color.color())


class _StepperArrow(QToolButton):
    def __init__(self, direction, label):
        super().__init__(objectName="StepperArrow", autoRepeat=True)
        self.direction = direction
        self.setFixedSize(24, 13)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(label)
        self.setToolTip(label)

    def paintEvent(self, event):
        super().paintEvent(event)
        center = QRectF(self.rect()).center()
        _paint_chevron(QPainter(self), center, self.direction, self.palette().buttonText().color())


class _EpisodeStepper(QSpinBox):
    def __init__(self, field_name):
        super().__init__(objectName="EpisodeStepper", minimum=1, maximum=99, value=1)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.setAccessibleName(field_name)
        self.up_button = _StepperArrow(1, f"Увеличить номер в поле «{field_name}»")
        self.down_button = _StepperArrow(-1, f"Уменьшить номер в поле «{field_name}»")
        self.up_button.clicked.connect(self.stepUp)
        self.down_button.clicked.connect(self.stepDown)
        arrows = QVBoxLayout(self)
        arrows.setContentsMargins(0, 2, 3, 2)
        arrows.setSpacing(1)
        arrows.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        arrows.addWidget(self.up_button)
        arrows.addWidget(self.down_button)
        self.valueChanged.connect(self.update_steps)
        self.update_steps()

    def update_steps(self):
        self.up_button.setEnabled(self.value() < self.maximum())
        self.down_button.setEnabled(self.value() > self.minimum())


class _DownloadRowWidget(QFrame):
    VIDEO_URL_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, remove_callback, kind):
        super().__init__(objectName="Card")
        self.kind = kind
        self._quality_url = ''
        self._quality_task = None
        self._quality_timer = QTimer(self)
        self._quality_timer.setSingleShot(True)
        self._quality_timer.setInterval(250)
        self._quality_timer.timeout.connect(self._start_quality_search)

        self.form = QVBoxLayout(self)
        self.form.setContentsMargins(18, 12, 18, 16)
        self.form.setSpacing(10)
        header = QHBoxLayout()
        self.title = QLabel(kind, objectName="CardTitle")
        header.addWidget(self.title, 1)
        self.status = QLabel(objectName="QueueStatus")
        self.status.hide()
        header.addWidget(self.status)
        self.delete_btn = QPushButton("Удалить", objectName="Danger")
        self.delete_btn.clicked.connect(lambda: remove_callback(self))
        header.addWidget(self.delete_btn)
        self.form.addLayout(header)

        self.video_url = QLineEdit(placeholderText="Вставьте ссылку .m3u8 или .mp4")
        self.sub_url = QLineEdit(placeholderText="Вставьте ссылку .vtt или .srt")
        self.filename = QLineEdit(placeholderText="Автоматически")
        self.video_url.textChanged.connect(self.on_inputs_changed)
        self.sub_url.textChanged.connect(self.on_inputs_changed)
        self._add_field(self.form, "Ссылка на видео", self.video_url)

        self.quality_field = QWidget()
        quality_layout = QHBoxLayout(self.quality_field)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_label = QLabel("Качество видео", objectName="FieldLabel")
        self.quality_combo = _QualityComboBox()
        self.quality_combo.addItem("Авто (Максимальное)", "best")
        quality_label.setBuddy(self.quality_combo)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo, 1)
        self.refresh_quality_btn = QPushButton("Обновить")
        self.refresh_quality_btn.setToolTip("Повторить поиск качества видео")
        self.refresh_quality_btn.clicked.connect(self._start_quality_search)
        quality_layout.addWidget(self.refresh_quality_btn)
        self.quality_field.hide()
        self.form.addWidget(self.quality_field)

        subtitles = QHBoxLayout()
        self._add_field(subtitles, "Субтитры (необязательно)", self.sub_url, stretch=1)
        self.offset_field = QWidget()
        offset_layout = QVBoxLayout(self.offset_field)
        offset_layout.setContentsMargins(0, 0, 0, 0)
        self.subtitle_offset = QDoubleSpinBox(minimum=-3600, maximum=3600, decimals=1, suffix=" с")
        self.subtitle_offset.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.subtitle_offset.setToolTip("Положительное число задерживает субтитры. Отрицательное сдвигает их раньше.")
        self._add_field(offset_layout, "Сдвиг субтитров", self.subtitle_offset)
        subtitles.addWidget(self.offset_field)
        self.offset_field.hide()
        self.video_url.textChanged.connect(self._update_offset_field)
        self.sub_url.textChanged.connect(self._update_offset_field)
        self.form.addLayout(subtitles)

    def _update_offset_field(self):
        self.offset_field.setVisible(bool(self.video_url.text().strip() and self.sub_url.text().strip()))

    def set_download_status(self, status):
        self.status.setText(status)
        self.status.setVisible(bool(status))

    def download_options(self):
        return {
            'video_url': self.selected_video_url(),
            'sub_url': self.sub_url.text().strip(),
            'output_name': self.filename.text().strip(),
            'selected_height': self.quality_combo.currentData(),
            'subtitle_offset': self.subtitle_offset.value(),
        }

    def set_position(self, position, can_remove):
        self.title.setText(f"{self.kind} {position}")
        self.delete_btn.setVisible(can_remove)

    @staticmethod
    def _add_field(layout, title, control, stretch=0):
        field = QVBoxLayout()
        field.setSpacing(4)
        label = QLabel(title, objectName="FieldLabel")
        label.setBuddy(control)
        field.addWidget(label)
        field.addWidget(control)
        layout.addLayout(field, stretch)

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
        self.quality_field.setVisible(is_hls)
        if is_hls:
            self.refresh_quality_btn.setEnabled(False)
            self._quality_timer.start()

    def _start_quality_search(self):
        self.refresh_quality_btn.setEnabled(False)
        self._quality_task = ResolutionParser(self._quality_url)
        self._quality_task.signals.completed.connect(self._show_resolutions, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(self._quality_task)

    def _show_resolutions(self, task, options):
        if task is not self._quality_task:
            return
        self._quality_task = None
        self.refresh_quality_btn.setEnabled(True)
        previous_height = self.quality_combo.currentData()
        if not options and previous_height not in (None, "best"):
            return
        self.quality_combo.clear()
        if not options:
            self.quality_combo.addItem("Авто (Максимальное)", "best")
            return

        for index, (height, direct_url) in enumerate(options):
            self.quality_combo.addItem(f"{height}p", str(height))
            self.quality_combo.setItemData(index, direct_url, self.VIDEO_URL_ROLE)
        original = next((index for index, (_, url) in enumerate(options)
                         if url is None or url == self._quality_url), 0)
        previous = self.quality_combo.findData(previous_height)
        self.quality_combo.setCurrentIndex(previous if previous >= 0 else original)

    def selected_video_url(self):
        return self.quality_combo.currentData(self.VIDEO_URL_ROLE) or self.video_url.text().strip()


class MovieRowWidget(_DownloadRowWidget):
    def __init__(self, remove_callback):
        super().__init__(remove_callback, "Фильм")
        self._add_field(self.form, "Имя файла", self.filename)

    def on_inputs_changed(self):
        url = self.video_url.text().strip()
        suggested_name = generate_movie_name(url or self.sub_url.text().strip())
        if suggested_name:
            self.filename.setText(suggested_name)
        self._update_quality_url(url)


class EpisodeRowWidget(_DownloadRowWidget):
    def __init__(self, remove_callback):
        super().__init__(remove_callback, "Серия")
        details = QHBoxLayout()
        details.setSpacing(12)
        self.season = _EpisodeStepper("Сезон")
        self.episode = _EpisodeStepper("Серия")
        for title, control in (("Сезон", self.season), ("Серия", self.episode)):
            control.setMinimumWidth(84)
            control.valueChanged.connect(self.on_inputs_changed)
            self._add_field(details, title, control)
        self._add_field(details, "Имя файла", self.filename, stretch=1)
        self.form.addLayout(details)

    def on_inputs_changed(self):
        url = self.video_url.text().strip()
        suggested_name = generate_series_name(
            url or self.sub_url.text().strip(), self.season.value(), self.episode.value())
        if suggested_name:
            self.filename.setText(suggested_name)
        self._update_quality_url(url)
