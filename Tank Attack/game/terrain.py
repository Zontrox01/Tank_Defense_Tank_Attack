"""Relieve del suelo: mapa de alturas con colinas suaves y cráteres.

h[x] es la coordenada Y de la superficie en la columna x (y crece hacia abajo).
Sin dependencias de Qt.
"""
from __future__ import annotations

import math
import random


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Terrain:
    def __init__(self, width: int, height: int, heights: list[float]) -> None:
        self.width = width
        self.height = height
        self.h = heights

    # ------------------------------------------------------------------
    def ground_y(self, x: float) -> float:
        if x <= 0:
            return self.h[0]
        if x >= self.width - 1:
            return self.h[-1]
        i = int(x)
        f = x - i
        return self.h[i] * (1 - f) + self.h[i + 1] * f

    def crater(self, cx: float, cy: float, r: float) -> None:
        """Excava un cráter circular centrado en (cx, cy)."""
        floor = self.height - 2
        for x in range(max(0, int(cx - r)), min(self.width, int(cx + r) + 1)):
            dx = x - cx
            d = math.sqrt(max(0.0, r * r - dx * dx))
            bottom = min(cy + d, floor)
            if self.h[x] < bottom:
                self.h[x] = bottom

    # ------------------------------------------------------------------
    @classmethod
    def generate(cls, width: int, height: int, rng: random.Random,
                 tank_x: int, target_x: int, ruggedness: float = 1.0,
                 hill_height: float = 0.2, tank_flat: float = 70.0,
                 target_flat: float = 70.0) -> "Terrain":
        base = height * 0.70
        comps = [(0.7, 1.0), (1.4, 0.55), (2.6, 0.28), (4.5, 0.12)]
        phases = [rng.uniform(0, 2 * math.pi) for _ in comps]
        amp_main = height * 0.07 * ruggedness
        tilt = rng.uniform(-0.05, 0.05) * height

        ys: list[float] = []
        for x in range(width):
            t = x / (width - 1)
            y = base + tilt * (t - 0.5) * 2
            for (cycles, weight), ph in zip(comps, phases):
                y += amp_main * weight * math.sin(2 * math.pi * cycles * t + ph)
            ys.append(max(height * 0.52, min(height * 0.90, y)))

        lo, hi = sorted((int(tank_x), int(target_x)))
        span = hi - lo

        # Colina entre tanque y objetivo
        c = rng.uniform(lo + 0.35 * span, lo + 0.65 * span)
        sigma = rng.uniform(0.05, 0.09) * width
        amp = hill_height * height * rng.uniform(0.85, 1.15)
        for x in range(width):
            ys[x] -= amp * math.exp(-0.5 * ((x - c) / sigma) ** 2)

        ys = [max(height * 0.12, min(height * 0.94, y)) for y in ys]

        platforms = [(int(tank_x), tank_flat, ys[int(tank_x)]),
                     (int(target_x), target_flat, ys[int(target_x)])]

        def flatten() -> None:
            for px, flat, plat_y in platforms:
                fade = flat * 0.8
                for x in range(max(0, int(px - flat - fade)),
                               min(width, int(px + flat + fade) + 1)):
                    dx = abs(x - px)
                    w = 1.0 if dx <= flat else 1.0 - _smoothstep((dx - flat) / fade)
                    ys[x] = ys[x] * (1 - w) + plat_y * w

        flatten()

        # Garantiza un obstáculo claro entre ambos extremos (fuera de las plataformas)
        reach_lo = platforms[0][1] * 1.8 if tank_x <= target_x else platforms[1][1] * 1.8
        reach_hi = platforms[1][1] * 1.8 if tank_x <= target_x else platforms[0][1] * 1.8
        a, b = int(lo + reach_lo), int(hi - reach_hi)
        if b - a < 40:
            a, b = int(lo + span * 0.35), int(lo + span * 0.65)
        inner = range(a, max(a + 1, b))
        plat_y_min = min(platforms[0][2], platforms[1][2])
        for _ in range(5):
            need = plat_y_min - 100
            peak_x = min(inner, key=lambda i: ys[i])
            if ys[peak_x] <= need:
                break
            extra = ys[peak_x] - need
            for x in range(width):
                ys[x] -= extra * math.exp(-0.5 * ((x - peak_x) / sigma) ** 2)
            ys = [max(height * 0.12, min(height * 0.94, y)) for y in ys]
            flatten()

        return cls(width, height, ys)
