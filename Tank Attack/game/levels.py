"""Qué cambia al subir de nivel. Sin dependencias de Qt."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LevelParams:
    level: int
    distance_frac: float   # fracción del ancho útil entre tanque y objetivo
    wind_max: float        # viento máximo posible en este nivel
    target_scale: float    # tamaño del objetivo (1.0 = normal)
    ruggedness: float      # multiplicador de la altura de las colinas
    hill_height: float     # colina central, como fracción de la altura del mundo
    moving: bool           # ¿objetivo móvil?
    moving_amp: float      # amplitud del movimiento (px)
    moving_speed: float    # rad/s


def level_params(level: int, gameplay: dict) -> LevelParams:
    t = max(0, level - 1)
    wind_max = 0.0
    if gameplay["wind_enabled"]:
        wind_max = min(gameplay["max_wind"], 1.0 + 0.9 * t)
    moving = bool(gameplay["moving_targets"]) and level >= 6
    return LevelParams(
        level=level,
        distance_frac=min(0.50 + 0.05 * t, 0.90),
        wind_max=wind_max,
        target_scale=max(0.5, 1.0 - 0.05 * t),
        ruggedness=min(1.0 + 0.08 * t, 1.8),
        hill_height=min(0.20 + 0.015 * t, 0.34),
        moving=moving,
        moving_amp=min(30.0 + 8.0 * max(0, level - 6), 100.0) if moving else 0.0,
        moving_speed=min(0.8 + 0.1 * max(0, level - 6), 1.6),
    )
