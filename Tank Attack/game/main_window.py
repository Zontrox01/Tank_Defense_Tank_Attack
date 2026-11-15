"""Ventana principal: sin barra de título, con menú, opciones y juego integrados."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from .assets import Assets
from .audio import AudioManager
from .game_widget import GameWidget
from .menus import MainMenu, OptionsPage

STYLE = """
QWidget { color: #e8eef7; font-size: 16px; }
#Page { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f2038, stop:1 #24517e); }
QLabel#Title { font-size: 64px; font-weight: 800; color: #ffd166; letter-spacing: 3px; }
QLabel#Title2 { font-size: 40px; font-weight: 700; color: #ffd166; }
QLabel#Sub { color: #9fb3c8; font-size: 18px; }
QPushButton {
    background: #2a4a6f; border: 2px solid #4b79a8; border-radius: 10px;
    padding: 12px 28px; font-size: 22px; min-width: 240px;
}
QPushButton:hover { background: #38618f; }
QPushButton:pressed { background: #1f3a58; }
QCheckBox::indicator { width: 22px; height: 22px; }
QSpinBox, QDoubleSpinBox, QComboBox {
    background: #16283f; border: 1px solid #4b79a8; border-radius: 6px;
    padding: 4px 8px; min-width: 150px;
}
QComboBox QAbstractItemView { background: #16283f; selection-background-color: #38618f; }
"""


class MainWindow(QMainWindow):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Tanque Parabólico")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.assets = Assets()
        self.audio = AudioManager(settings)

        self.menu = MainMenu(settings)
        self.options = OptionsPage(settings)
        self.options.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.game = GameWidget(settings, self.assets, self.audio)

        self.stack = QStackedWidget()
        for page in (self.menu, self.options, self.game):
            self.stack.addWidget(page)
        self.setCentralWidget(self.stack)

        self.menu.play_clicked.connect(self.start_game)
        self.menu.options_clicked.connect(self.show_options)
        self.menu.quit_clicked.connect(QApplication.quit)
        self.options.accepted_.connect(self._options_saved)
        self.options.cancelled.connect(self.show_menu)
        self.game.back_to_menu.connect(self.show_menu)
        self.game.quit_requested.connect(QApplication.quit)

    # ------------------------------------------------------------ pantallas
    def show_initial(self) -> None:
        self.apply_display()
        self.show_menu()

    def show_menu(self) -> None:
        self.menu.refresh()
        self.stack.setCurrentWidget(self.menu)

    def show_options(self) -> None:
        self.options.load()
        self.stack.setCurrentWidget(self.options)
        self.options.setFocus()

    def start_game(self) -> None:
        self.stack.setCurrentWidget(self.game)
        self.game.setFocus()
        # Espera un instante para que el widget tenga ya su tamaño definitivo
        QTimer.singleShot(60, self.game.start_game)

    def _options_saved(self) -> None:
        self.audio.apply_settings()
        self.apply_display()
        self.show_menu()

    # ------------------------------------------------------------- ventana
    def apply_display(self) -> None:
        d = self.settings["display"]
        if d["fullscreen"]:
            self.showFullScreen()
        else:
            if self.isFullScreen():
                self.showNormal()
            self.resize(d["window_width"], d["window_height"])
            self._center()
            self.show()

    def _center(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.center() - self.rect().center())

    def mousePressEvent(self, event) -> None:
        """Sin barra de título: arrastrar el fondo mueve la ventana."""
        if (event.button() == Qt.MouseButton.LeftButton and not self.isFullScreen()
                and self.windowHandle() is not None):
            self.windowHandle().startSystemMove()
        super().mousePressEvent(event)

    def closeEvent(self, event) -> None:
        self.game.stop_game()
        super().closeEvent(event)
