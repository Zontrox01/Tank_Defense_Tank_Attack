"""Física del proyectil. Sin dependencias de Qt.

Sistema de coordenadas: x hacia la derecha, y hacia ABAJO (como en pantalla).
Un viento positivo empuja hacia la derecha.
"""
from __future__ import annotations

import math

WIND_K = 12.0   # aceleración (px/s²) por cada unidad de viento


class Missile:
    __slots__ = ("x", "y", "vx", "vy", "ax", "g", "t")

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 wind: float, gravity: float) -> None:
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.ax = wind * WIND_K
        self.g = gravity
        self.t = 0.0

    def step(self, dt: float) -> None:
        self.vx += self.ax * dt
        self.vy += self.g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.t += dt


def max_speed(world_w: float, gravity: float, range_factor: float = 1.2) -> float:
    """Velocidad con potencia 100 %: alcance a 45º (sin viento) = range_factor * ancho."""
    return math.sqrt(range_factor * world_w * gravity)


def launch_velocity(power: float, angle_deg: float, direction: int,
                    v_max: float) -> tuple[float, float]:
    v = v_max * power
    a = math.radians(angle_deg)
    return direction * v * math.cos(a), -v * math.sin(a)


def ascent_path(x: float, y: float, vx: float, vy: float, wind: float,
                gravity: float, dt: float = 1 / 60,
                max_points: int = 600) -> list[tuple[float, float]]:
    """Puntos de la trayectoria de ascenso (hasta el punto más alto)."""
    m = Missile(x, y, vx, vy, wind, gravity)
    pts = [(m.x, m.y)]
    while m.vy < 0 and len(pts) < max_points:
        m.step(dt)
        pts.append((m.x, m.y))
    return pts
