"""Carga de sprites PNG (assets/images).

Si falta algún PNG se dibuja uno sencillo en su lugar, así el juego siempre
arranca. Para personalizar basta con sustituir los PNG manteniendo el nombre:

* tank_body.png   cuerpo del tanque mirando a la DERECHA, con la base apoyada
                  en el borde inferior de la imagen.
* tank_barrel.png cañón apuntando a la DERECHA; el pivote es el centro de su
                  borde izquierdo.
* target.png      objetivo (se dibuja como un círculo centrado).
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

from .settings import IMAGES_DIR


def _blank(w: int, h: int) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _fallback_body() -> QPixmap:
    pm = _blank(192, 88)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#2b2f33"))
    p.drawRoundedRect(QRectF(6, 56, 180, 32), 14, 14)
    p.setBrush(QColor("#4f7d3b"))
    p.drawRoundedRect(QRectF(18, 34, 156, 28), 8, 8)
    p.setBrush(QColor("#5b8f45"))
    p.drawEllipse(QRectF(60, 12, 72, 38))
    p.end()
    return pm


def _fallback_barrel() -> QPixmap:
    pm = _blank(128, 24)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#6c757d"))
    p.drawRoundedRect(QRectF(0, 4, 128, 16), 5, 5)
    p.end()
    return pm


def _fallback_target() -> QPixmap:
    pm = _blank(128, 128)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for r, c in ((62, "#d62828"), (50, "#ffffff"), (38, "#d62828"),
                 (26, "#ffffff"), (14, "#d62828")):
        p.setBrush(QColor(c))
        p.drawEllipse(QRectF(64 - r, 64 - r, 2 * r, 2 * r))
    p.end()
    return pm


def _load(name: str, fallback) -> QPixmap:
    path = IMAGES_DIR / name
    pm = QPixmap(str(path))
    if pm.isNull():
        print(f"[assets] No se pudo cargar {path}; se usa un dibujo por defecto.")
        return fallback()
    return pm


class Assets:
    """Debe crearse cuando ya existe la QApplication."""

    def __init__(self) -> None:
        self.tank_body = _load("tank_body.png", _fallback_body)
        self.tank_barrel = _load("tank_barrel.png", _fallback_barrel)
        self.target = _load("target.png", _fallback_target)
