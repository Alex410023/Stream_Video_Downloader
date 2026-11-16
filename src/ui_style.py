from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


LIGHT = dict(
    background="#ffffff", sidebar="#f1f1f1", surface="#fdfcfc", panel="#ffffff", field="#f5f5f5",
    border="#e0e0e0", text="#1c1e20", secondary="#646567", accent="#7948d8", focus="#7948d8",
    pressed="#6435bb", selection="#ece5fa", selected_text="#38225a", hover="#ededed",
    nav_selection="#e5e6e6", danger="#b52629", disabled="#77787a",
    shortcut_background="#d0b6f7", shortcut_text="#2d144d",
    success="#147653",
)
DARK = dict(
    background="#181818", sidebar="#333334", surface="#232222", panel="#363636", field="#2d2d2d",
    border="#3e3e3e", text="#ffffff", secondary="#b7b7b7", accent="#3c66bf", focus="#439cff",
    pressed="#3056aa", selection="#223d72", selected_text="#eef4ff", hover="#3c3c3c",
    nav_selection="#434343", danger="#ff9599", disabled="#999999",
    shortcut_background="#bcd7ff", shortcut_text="#152b50",
    success="#6fd3a6",
)

STYLE = """
QWidget#AppSurface {{ background: {sidebar}; }}
QFrame#Workspace {{ background: {background}; border: 1px solid {border}; border-radius: 14px; }}
QFrame#Card, QFrame#Activity {{
    background: {surface}; border: 1px solid {border}; border-radius: 12px;
}}
QFrame#DownloadControls {{
    background: {panel}; border: 1px solid {border}; border-radius: 20px;
}}
QFrame#Card:disabled {{ background: {field}; }}
QLabel {{ background: transparent; color: {text}; font-size: 13px; }}
QLabel[muted="true"] {{ color: {secondary}; }}
QLabel#Brand {{ font-size: 17px; font-weight: 700; }}
QLabel#NavSection {{ font-size: 11px; font-weight: 650; color: {secondary}; }}
QLabel#PageTitle {{ font-size: 28px; font-weight: 600; }}
QLabel#CardTitle {{ font-size: 16px; font-weight: 650; }}
QLabel#ActivityTitle, QLabel#FieldLabel {{ font-weight: 600; }}
QLabel#ProgressText {{ color: {secondary}; font-size: 12px; }}
QLabel#QueueStatus {{
    color: {selected_text}; background: {selection};
    border-radius: 8px; padding: 4px 8px; font-size: 11px; font-weight: 600;
}}
QPushButton {{
    background: {surface}; color: {text}; border: 1px solid {border};
    border-radius: 9px; padding: 7px 12px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {selection}; }}
QPushButton:focus {{ border-color: {focus}; }}
QPushButton:disabled {{ color: {disabled}; background: {field}; }}
QPushButton#NavButton {{
    text-align: left; background: transparent; border-color: transparent; padding: 9px 12px;
}}
QPushButton#NavButton:hover {{ background: {hover}; }}
QPushButton#NavButton:checked {{ background: {nav_selection}; color: {text}; }}
QPushButton#NavButton:focus {{ border-color: {focus}; }}
QPushButton#NavButton:disabled {{ color: {disabled}; }}
QPushButton#Primary {{
    background: {accent}; color: white; border-color: {accent};
    padding: 9px 16px; border-radius: 18px;
}}
QPushButton#Primary:hover {{ background: {pressed}; border-color: {pressed}; }}
QPushButton#Primary:focus {{ border-color: {focus}; }}
QPushButton#Primary:disabled {{ background: {field}; color: {disabled}; border-color: {border}; }}
QPushButton#Quiet, QPushButton#Danger {{ background: transparent; border-color: transparent; }}
QPushButton#Danger {{ color: {danger}; }}
QPushButton#Quiet:hover, QPushButton#Danger:hover {{ background: {hover}; }}
QPushButton#Quiet:focus, QPushButton#Danger:focus {{ border-color: {focus}; }}
QPushButton#Danger:disabled {{ color: {disabled}; }}
QToolButton#ThemeOption {{
    background: transparent; color: {secondary}; border: 1px solid transparent;
    border-radius: 9px; padding: 3px 0; font-size: 10px; font-weight: 500;
}}
QToolButton#ThemeOption:hover {{ background: {hover}; color: {text}; }}
QToolButton#ThemeOption:checked {{ background: {nav_selection}; border-color: {focus}; color: {text}; }}
QToolButton#ThemeOption:focus {{ border-color: {focus}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {field}; color: {text}; border: 1px solid {border};
    border-radius: 10px; padding: 6px 10px; min-height: 18px; font-size: 13px;
    selection-background-color: {selection}; selection-color: {text};
    placeholder-text-color: {secondary};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {focus}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {disabled}; }}
QSpinBox#EpisodeStepper {{ padding-right: 32px; }}
QToolButton#StepperArrow {{
    background: {panel}; color: {secondary}; border: none; border-radius: 5px; padding: 0;
}}
QToolButton#StepperArrow:hover {{ background: {hover}; color: {text}; }}
QToolButton#StepperArrow:pressed {{ background: {selection}; }}
QToolButton#StepperArrow:disabled {{ background: transparent; color: {disabled}; }}
QComboBox#QualityCombo {{ padding-right: 34px; }}
QComboBox#QualityCombo::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 24px; height: 22px; margin: 0 3px;
    background: {panel}; border: none; border-radius: 5px;
}}
QComboBox#QualityCombo::drop-down:hover {{ background: {hover}; }}
QComboBox#QualityCombo::drop-down:on {{ background: {selection}; }}
QComboBox#QualityCombo::drop-down:disabled {{ background: transparent; }}
QComboBox QAbstractItemView {{
    background: {surface}; color: {text}; border: 1px solid {border};
    selection-background-color: {selection}; selection-color: {selected_text};
}}
QLineEdit#Destination {{ background: transparent; border-color: transparent; padding-left: 0; }}
QLineEdit#Destination:focus {{ border-bottom-color: {focus}; }}
QTabWidget::pane {{ border: none; }}
QScrollArea, QWidget#Queue {{ border: none; background: transparent; }}
QScrollBar:vertical {{ width: 10px; margin: 4px 2px; background: transparent; }}
QScrollBar:horizontal {{ height: 10px; margin: 2px 4px; background: transparent; }}
QScrollBar::handle {{ background: {disabled}; border-radius: 3px; }}
QScrollBar::handle:vertical {{ min-height: 25px; }}
QScrollBar::handle:horizontal {{ min-width: 25px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QSplitter::handle:vertical {{ height: 12px; background: transparent; }}
QSplitter::handle:vertical:hover {{ background: {hover}; }}
QTextEdit#ActivityLog {{
    background: transparent; color: {secondary}; border: none;
    font-size: 12px; selection-background-color: {selection}; selection-color: {text};
    placeholder-text-color: {secondary};
}}
QTextBrowser#Guide {{
    background: {surface}; color: {text}; border: 1px solid {border}; border-radius: 16px;
    font-size: 14px; selection-background-color: {selection}; selection-color: {text};
}}
QProgressBar {{
    background: {field}; border: none; border-radius: 3px;
    min-height: 6px; max-height: 6px;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
"""


GUIDE_STYLE = """
h2 {{
    font-size: 26px; font-weight: 700; margin: 0 0 20px;
}}
h3 {{
    font-size: 18px; font-weight: 600; margin: 26px 0 8px; line-height: 125%;
}}
h3.guide-step {{ color: {focus}; }}
p {{ margin: 0 0 10px; line-height: 150%; }}
p.guide-item {{ margin: 0 0 7px 18px; text-indent: -18px; }}
p.guide-image {{ margin: 8px 0 15px; line-height: 100%; }}
table {{ margin: 2px 0 14px; }}
td p {{ margin: 0; }}
table.guide-note td {{ background-color: {selection}; color: {selected_text}; }}
table.guide-example td {{ background-color: {field}; color: {text}; }}
pre {{ margin: 0; font-family: monospace; font-size: 12px; line-height: 145%; }}
code {{
    background-color: {shortcut_background}; color: {shortcut_text};
    font-family: monospace; font-size: 13px; font-weight: 600;
}}
"""


def appearance_preview(*palettes):
    pixmap = QPixmap(88, 56)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    width = 44 / len(palettes)
    for index, colors in enumerate(palettes):
        painter.setClipRect(QRectF(index * width, 0, width, 28))
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.setBrush(QColor(colors["sidebar"]))
        painter.drawRoundedRect(QRectF(0.5, 0.5, 43, 27), 5, 5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["background"]))
        painter.drawRoundedRect(QRectF(9, 6, 30, 17), 3, 3)
        painter.setBrush(QColor(colors["secondary"]))
        painter.drawRoundedRect(QRectF(14, 9, 16, 1.5), 0.75, 0.75)
        painter.drawRoundedRect(QRectF(14, 12.5, 12, 1.5), 0.75, 0.75)
        painter.setBrush(QColor(colors["accent"]))
        painter.drawRoundedRect(QRectF(25, 17, 10, 3), 1.5, 1.5)
    painter.end()
    return QIcon(pixmap)


def symbol(name, color, tile=None):
    pixmap = QPixmap(80, 80)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if tile:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tile))
        painter.drawRoundedRect(QRectF(0, 0, 40, 40), 11, 11)
    painter.translate(6, 6)
    painter.scale(1.4, 1.4)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(color), 1.55, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    def line(*points):
        for start, end in zip(points, points[1:]):
            painter.drawLine(QPointF(*start), QPointF(*end))

    if name == "movie":
        painter.drawRoundedRect(QRectF(2, 3, 16, 14), 2.4, 2.4)
        line((8, 7), (13, 10), (8, 13), (8, 7))
    elif name == "series":
        painter.drawRoundedRect(QRectF(2, 3, 16, 11), 2, 2)
        line((10, 14), (10, 17))
        line((6.5, 17), (13.5, 17))
    elif name == "guide":
        painter.drawRoundedRect(QRectF(4, 2, 12, 16), 2, 2)
        line((7, 7), (13, 7))
        line((7, 10), (13, 10))
        line((7, 13), (11, 13))
    elif name == "info":
        painter.drawEllipse(QRectF(2, 2, 16, 16))
        line((10, 9.5), (10, 13.7))
        painter.drawPoint(QPointF(10, 6.5))
    elif name == "download":
        line((10, 2.5), (10, 12))
        line((6, 8), (10, 12), (14, 8))
        line((3, 12), (3, 16.5), (17, 16.5), (17, 12))
    elif name == "plus":
        line((10, 4), (10, 16))
        line((4, 10), (16, 10))
    elif name == "folder":
        line((2.5, 16), (2.5, 5), (8, 5), (10, 7), (17.5, 7), (17.5, 16), (2.5, 16))
    painter.end()
    return QIcon(pixmap)
