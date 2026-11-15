"""Tanque Parabólico — punto de entrada.  Ejecutar:  python main.py"""
import sys

from PySide6.QtWidgets import QApplication

from game.main_window import STYLE, MainWindow
from game.settings import load_config


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    settings = load_config()
    window = MainWindow(settings)
    window.show_initial()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
