"""Tank Defense — punto de entrada."""
import sys

from PySide6.QtWidgets import QApplication

from assets import ensure_sprites, Sprites, Sounds
from config import Settings, Record
from widgets import MainWindow, STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    cfg = Settings.load()
    record = Record()
    ensure_sprites()                     # crea los PNG que falten en assets/sprites
    sounds = Sounds(cfg)
    win = MainWindow(cfg, Sprites(), sounds, record)
    win.apply_display()
    sounds.sync_music()                  # música de fondo si está activada
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
