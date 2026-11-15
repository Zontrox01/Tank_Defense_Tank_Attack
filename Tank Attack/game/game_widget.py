"""Widget del juego: bucle, lógica de partida, entrada de teclado y dibujo.

El mundo tiene una altura lógica fija (WORLD_H) y se escala a la ventana; el
ancho lógico se adapta a la proporción de la pantalla, de modo que la física
es idéntica en ventana y en pantalla completa.
"""
from __future__ import annotations

import math
import random
from enum import Enum, auto

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF,
                           QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF, QKeySequence)
from PySide6.QtWidgets import QWidget

from .levels import level_params
from .physics import Missile, ascent_path, launch_velocity, max_speed
from .settings import DIFFICULTY_NAMES, get_record, set_record
from .terrain import Terrain

# ---------------------------------------------------------------- constantes
WORLD_H = 720
MARGIN = 100                 # distancia del tanque al borde
TANK_W = 100                 # ancho lógico del tanque
BARREL_LEN = 64              # largo lógico del cañón
BARREL_ROOT = 8              # parte del cañón que queda oculta bajo la torreta
BARREL_MOUNT = 0.65          # altura del pivote sobre el suelo (fracción del alto del tanque)
TARGET_D = 64                # diámetro lógico del objetivo
CRATER_R = 30
EXPLOSION_R = 34
MIN_POWER = 0.05
SUBSTEP = 1 / 240            # paso de integración del misil
RESULT_PAUSE = 1.7           # pausa tras un impacto
# Velocidad de las nubes con el viento máximo (px lógicos/s). Con 60 fps son ~1,3 px
# por fotograma: se ve fluido. Las nubes van proporcionales al viento: 0 = paradas.
CLOUD_MAX_SPEED = 80.0


def _ik(k) -> int:
    return int(getattr(k, "value", k))


K_ENTER = (_ik(Qt.Key.Key_Return), _ik(Qt.Key.Key_Enter))
K_R = _ik(Qt.Key.Key_R)
K_M = _ik(Qt.Key.Key_M)
K_Q = _ik(Qt.Key.Key_Q)
K_BACKSPACE = _ik(Qt.Key.Key_Backspace)


def key_from_name(name: str, fallback: Qt.Key) -> int:
    seq = QKeySequence(name)
    if seq.count() == 0:
        return _ik(fallback)
    k = seq[0]
    k = k.key() if hasattr(k, "key") else k
    return _ik(k)


class State(Enum):
    AIMING = auto()
    FLYING = auto()
    RESULT = auto()
    GAME_OVER = auto()


class Explosion:
    def __init__(self, x: float, y: float, radius: float, rng: random.Random) -> None:
        self.x, self.y, self.radius = x, y, radius
        self.t = 0.0
        self.duration = 0.7
        self.sparks = []
        for _ in range(18):
            a = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(80, 260)
            self.sparks.append([x, y, math.cos(a) * sp, math.sin(a) * sp - 60])

    def update(self, dt: float, gravity: float) -> None:
        self.t += dt
        for s in self.sparks:
            s[3] += gravity * dt
            s[0] += s[2] * dt
            s[1] += s[3] * dt

    @property
    def alive(self) -> bool:
        return self.t < self.duration


class GameWidget(QWidget):
    back_to_menu = Signal()
    quit_requested = Signal()

    def __init__(self, settings: dict, assets, audio, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.assets = assets
        self.audio = audio
        self.rng = random.Random()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(False)

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.clock = QElapsedTimer()

        # tamaños lógicos derivados de los sprites
        body = assets.tank_body
        barrel = assets.tank_barrel
        self.tank_h = TANK_W * body.height() / max(1, body.width())
        self.barrel_h = BARREL_LEN * barrel.height() / max(1, barrel.width())

        self.terrain: Terrain | None = None
        self.state = State.AIMING
        self.paused = False
        self.keys: set[int] = set()
        self.entry: str | None = None      # campo numérico activo: "angle" | "power"
        self.entry_text = ""
        self._entry_backup: tuple[float, float] | None = None
        self._charge_src: str | None = None  # "key" | "mouse"
        self._anim_t = 0.0
        self.last_power = 0.0              # último disparo (se muestra en modo Fácil)
        self.world_w = 1280
        self._path_cache: tuple[QPainterPath, QPainterPath] | None = None
        self._terrain_dirty = True
        self.apply_settings()

    # ------------------------------------------------------------- ajustes
    def apply_settings(self) -> None:
        self.gp = self.settings["gameplay"]
        k = self.settings["keys"]
        self.k_up = key_from_name(k["angle_up"], Qt.Key.Key_Up)
        self.k_down = key_from_name(k["angle_down"], Qt.Key.Key_Down)
        self.k_fire = key_from_name(k["fire"], Qt.Key.Key_Space)
        self.k_pause = key_from_name(k["pause"], Qt.Key.Key_Escape)
        self.k_edit_angle = key_from_name(k["edit_angle"], Qt.Key.Key_A)
        self.k_edit_power = key_from_name(k["edit_power"], Qt.Key.Key_P)
        self.difficulty = self.gp["difficulty"]
        self.wheel_step = float(self.gp["wheel_step"])

    # ------------------------------------------------------------- partida
    def start_game(self) -> None:
        self.apply_settings()
        self.score = 0
        self.level = 1
        self.hits = 0
        self.failures = 0
        self.record = get_record(self.difficulty)
        self.new_record = False
        self.paused = False
        self.keys.clear()
        self.entry, self.entry_text, self._charge_src = None, "", None
        self.last_power = 0.0
        self.banner: list[str] = []
        self.banner_t = 0.0
        self.angle = 45.0
        self._new_scenario()
        self.clock.start()
        self.timer.start()
        self.audio.start_music()
        self.setFocus()
        self.update()

    def stop_game(self) -> None:
        self.timer.stop()
        self.audio.stop_all()

    def _new_scenario(self) -> None:
        """Nuevo objetivo: lado, relieve, viento y posiciones aleatorios."""
        rng = self.rng
        self.lp = level_params(self.level, self.gp)
        lp = self.lp

        scale = max(self.height(), 1) / WORLD_H
        self.world_w = max(960, int(round(self.width() / scale)))
        W = self.world_w

        self.dir = rng.choice((1, -1))
        self.tank_x = MARGIN if self.dir == 1 else W - MARGIN
        span = W - 2 * MARGIN
        amp = lp.moving_amp
        base = self.tank_x + self.dir * span * lp.distance_frac
        self.target_base_x = max(60 + amp, min(W - 60 - amp, base))
        self.target_x = self.target_base_x
        self.target_t = rng.uniform(0, 2 * math.pi)
        self.target_r = TARGET_D / 2 * lp.target_scale
        self.target_hit_r = self.target_r * 0.92
        self.target_destroyed = False

        self.terrain = Terrain.generate(
            W, WORLD_H, rng, int(self.tank_x), int(self.target_base_x),
            lp.ruggedness, lp.hill_height, 70.0, 70.0 + amp)
        self._terrain_dirty = True

        if lp.wind_max > 0:
            self.wind = round(rng.uniform(-lp.wind_max, lp.wind_max), 1)
        else:
            self.wind = 0.0
        self.gravity = self.gp["gravity"]
        self.v_max = max_speed(W, self.gravity)

        self.power = 0.0
        self.charging = False
        self._charge_src = None
        self.entry, self.entry_text = None, ""
        self.shots_left = self.gp["shots_per_target"]
        self.best_shot = 0
        self.missile: Missile | None = None
        self.current_path: list[tuple[float, float]] = []
        self.prev_path: list[tuple[float, float]] = []
        self.effects: list[Explosion] = []
        self.floats: list[dict] = []
        self.pending = ""
        self.result_t = 0.0
        self.state = State.AIMING
        self.clouds = [[rng.uniform(0, W), rng.uniform(40, 220), rng.uniform(0.7, 1.4)]
                       for _ in range(5)]

    # ------------------------------------------------------------ geometría
    def _target_center(self) -> tuple[float, float]:
        gy = self.terrain.ground_y(self.target_x)
        return self.target_x, gy - self.target_r - 12

    def _barrel_geometry(self) -> tuple[tuple[float, float], tuple[float, float]]:
        gy = self.terrain.ground_y(self.tank_x)
        px = self.tank_x
        py = gy - self.tank_h * BARREL_MOUNT
        a = math.radians(self.angle)
        length = BARREL_LEN - BARREL_ROOT
        tip = (px + self.dir * length * math.cos(a), py - length * math.sin(a))
        return (px, py), tip

    # --------------------------------------------------------------- disparo
    def _fire(self) -> None:
        _, tip = self._barrel_geometry()
        vx, vy = launch_velocity(self.power, self.angle, self.dir, self.v_max)
        self.missile = Missile(tip[0], tip[1], vx, vy, self.wind, self.gravity)
        self._flight_ticks = 0
        self.current_path = [tip]
        self.shots_left -= 1
        self.last_power = self.power
        self.power = 0.0
        self.charging = False
        self._charge_src = None
        self.entry, self.entry_text = None, ""
        self.state = State.FLYING
        self.audio.play("shot")
        self.audio.play("flight")

    def _step_flight(self, dt: float) -> None:
        m = self.missile
        acc = dt
        while acc > 1e-9 and self.state == State.FLYING and m is not None:
            h = min(SUBSTEP, acc)
            acc -= h
            m.step(h)
            self._flight_ticks += 1
            if self._flight_ticks % 4 == 0:
                self.current_path.append((m.x, m.y))

            if not self.target_destroyed:
                cx, cy = self._target_center()
                if math.hypot(m.x - cx, m.y - cy) <= self.target_hit_r:
                    self._impact(m.x, m.y, crater=False)
                    return

            if m.x < -120 or m.x > self.world_w + 120 or m.t > 25:
                self._impact(m.x, m.y, crater=False, offscreen=True)
                return

            if 0 <= m.x < self.world_w:
                gy = self.terrain.ground_y(m.x)
                if m.y >= gy:
                    self._impact(m.x, gy, crater=True)
                    return

    def _impact(self, x: float, y: float, crater: bool, offscreen: bool = False) -> None:
        self.missile = None
        self.current_path.append((x, y))
        self.audio.stop("flight")

        cx, cy = self._target_center()
        d = math.hypot(x - cx, y - cy)

        if not offscreen:
            self.audio.play("burst")
            self.effects.append(Explosion(x, y, EXPLOSION_R, self.rng))
        if crater:
            self.terrain.crater(x, y, CRATER_R)
            self._terrain_dirty = True

        hit = (not offscreen and not self.target_destroyed
               and d <= self.target_hit_r + EXPLOSION_R * 0.6)
        if hit:
            pts = 10
        elif offscreen:
            pts = 0
        else:
            radius = float(self.gp["action_radius"])
            pts = max(0, int(round(9 * (1 - d / radius)))) if d < radius else 0

        self.best_shot = max(self.best_shot, pts)
        label = "Fuera" if offscreen else f"+{pts}"
        self.floats.append({"x": min(max(x, 40), self.world_w - 40), "y": min(y, WORLD_H - 40) - 20,
                            "text": label, "t": 0.0})

        lines: list[str] = []
        if hit:
            self.target_destroyed = True
            self.effects.append(Explosion(cx, cy, 55, self.rng))
            self.hits += 1
            self.score += 10
            lines.append("¡Objetivo destruido!  +10")
            new_level = 1 + self.hits // self.gp["targets_per_level"]
            if new_level > self.level:
                self.level = new_level
                lines.append(f"¡Nivel {self.level}!")
            self.pending = "target"
        elif self.shots_left <= 0:
            self.failures += 1
            self.score += self.best_shot
            lines.append(f"Sin disparos: fallo {self.failures}/{self.gp['max_failures']}")
            if self.best_shot:
                lines.append(f"Mejor disparo: +{self.best_shot}")
            self.pending = "gameover" if self.failures >= self.gp["max_failures"] else "target"
        else:
            self.pending = "shot"

        if lines:
            self.banner = lines
            self.banner_t = RESULT_PAUSE + 0.3

        self.prev_path = self.current_path
        self.current_path = []
        self.state = State.RESULT
        self.result_t = RESULT_PAUSE if self.pending != "shot" else 1.1

    def _finish_result(self) -> None:
        pending, self.pending = self.pending, ""
        if pending == "shot":
            self.state = State.AIMING
        elif pending == "target":
            self._new_scenario()
        elif pending == "gameover":
            self._enter_game_over()

    def _enter_game_over(self) -> None:
        self.state = State.GAME_OVER
        self.charging = False
        self._charge_src = None
        self._cancel_entry()
        if self.score > self.record:
            self.record = self.score
            self.new_record = True
            set_record(self.difficulty, self.score)
        self.audio.stop_music()
        self.audio.play("gameover")

    # --------------------------------------------------------------- entrada
    def _clamp_angle(self, v: float) -> float:
        return max(0.0, min(90.0, v))

    # -- carga de potencia (barra espaciadora o botón izquierdo) --
    def _begin_charge(self, src: str) -> None:
        if self.state != State.AIMING or self.paused or self.charging:
            return
        self._cancel_entry()
        self.charging = True
        self._charge_src = src
        self.power = 0.0

    def _end_charge(self, src: str) -> None:
        if not self.charging or self._charge_src != src:
            return
        self.charging = False
        self._charge_src = None
        if self.state == State.AIMING and not self.paused and self.power >= MIN_POWER:
            self._fire()
        else:
            self.power = 0.0

    # -- entrada numérica: A (ángulo) / P (potencia) + números; Enter dispara --
    def _cancel_entry(self, restore: bool = False) -> None:
        """Sale del modo numérico. Con restore=True (Esc) se recuperan los valores previos."""
        if restore and self.entry and self._entry_backup:
            self.angle, self.power = self._entry_backup
        self.entry, self.entry_text = None, ""
        self._entry_backup = None

    def _entry_apply_live(self) -> None:
        try:
            v = float(self.entry_text)
        except ValueError:
            return
        if self.entry == "angle":
            self.angle = self._clamp_angle(v)
        elif self.entry == "power":
            self.power = max(0.0, min(1.0, v / 100.0))

    def _entry_switch(self, field: str) -> None:
        """Activa un campo (parpadea y admite números). Si ya estaba activo, reinicia."""
        if self.charging or self.state != State.AIMING:
            return
        if self.entry is None:
            self._entry_backup = (self.angle, self.power)
        self.entry, self.entry_text = field, ""

    def _entry_type(self, ch: str) -> None:
        if self.entry is None:
            return
        if ch in ".,":
            if self.entry == "power" or "." in self.entry_text or not self.entry_text:
                return
            ch = "."
        if len(self.entry_text) >= (5 if self.entry == "angle" else 3):
            return
        self.entry_text += ch
        self._entry_apply_live()

    def _entry_backspace(self) -> None:
        if self.entry and self.entry_text:
            self.entry_text = self.entry_text[:-1]
            self._entry_apply_live()

    def _enter_fire(self) -> None:
        """Enter: dispara con los valores que haya en los campos."""
        if self.state != State.AIMING or self.charging or self.paused:
            return
        if self.entry:
            self._entry_apply_live()
        if self.power >= 0.01:
            self._fire()

    # -- eventos --
    def mousePressEvent(self, event) -> None:
        event.accept()   # evita que el clic arrastre la ventana sin barra de título
        if event.button() == Qt.MouseButton.LeftButton:
            self._begin_charge("mouse")

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._end_charge("mouse")
        event.accept()

    def wheelEvent(self, event) -> None:
        event.accept()
        if self.state != State.AIMING or self.paused:
            return
        delta = event.angleDelta().y()
        if delta:
            self._cancel_entry()
            self.angle = self._clamp_angle(self.angle + delta / 120.0 * self.wheel_step)

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        k = event.key()

        if self.state == State.GAME_OVER:
            if k in K_ENTER or k == self.k_pause or k == K_M:
                self._go_menu()
            elif k == K_R:
                self.start_game()
            return

        if k == self.k_pause:
            if self.entry:
                self._cancel_entry(restore=True)
            else:
                self._toggle_pause()
            return
        if self.paused:
            if k == K_M:
                self._go_menu()
            elif k == K_Q:
                self.stop_game()
                self.quit_requested.emit()
            return

        if self.state == State.AIMING:
            text = event.text()
            if k in K_ENTER:
                self._enter_fire()
                return
            if k == self.k_edit_angle:
                self._entry_switch("angle")
                return
            if k == self.k_edit_power:
                self._entry_switch("power")
                return
            if k == K_BACKSPACE:
                self._entry_backspace()
                return
            if len(text) == 1 and text in "0123456789.,":
                self._entry_type(text)
                return
            if k in (self.k_up, self.k_down):
                self._cancel_entry()

        self.keys.add(k)
        if k == self.k_fire:
            self._begin_charge("key")

    def keyReleaseEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        k = event.key()
        self.keys.discard(k)
        if k == self.k_fire:
            self._end_charge("key")

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.audio.pause_music()
        else:
            self.audio.resume_music()
            self.keys.clear()
            self.charging = False
            self._charge_src = None
            self._cancel_entry()
            self.power = 0.0
            self.clock.restart()
        self.update()

    def _go_menu(self) -> None:
        self.stop_game()
        self.back_to_menu.emit()

    # ------------------------------------------------------------ actualizar
    def _tick(self) -> None:
        dt = min(self.clock.restart() / 1000.0, 0.05)
        if self.paused or self.terrain is None:
            return
        self._anim_t += dt

        wind_ratio = max(-1.0, min(1.0, self.wind / max(self.gp["max_wind"], 0.1)))
        cloud_dx = wind_ratio * CLOUD_MAX_SPEED * dt
        for c in self.clouds:
            c[0] += cloud_dx
            if c[0] > self.world_w + 120:
                c[0] = -120
            elif c[0] < -120:
                c[0] = self.world_w + 120

        for e in self.effects:
            e.update(dt, self.gravity)
        self.effects = [e for e in self.effects if e.alive]
        for f in self.floats:
            f["t"] += dt
            f["y"] -= 30 * dt
        self.floats = [f for f in self.floats if f["t"] < 1.4]
        if self.banner_t > 0:
            self.banner_t -= dt

        if self.lp.moving and not self.target_destroyed and self.state != State.GAME_OVER:
            self.target_t += self.lp.moving_speed * dt
            self.target_x = self.target_base_x + self.lp.moving_amp * math.sin(self.target_t)

        if self.state == State.AIMING:
            direction = (1 if self.k_up in self.keys else 0) - (1 if self.k_down in self.keys else 0)
            if direction:
                self.angle = max(0.0, min(90.0, self.angle + direction * self.gp["angle_speed"] * dt))
            if self.charging:
                self.power = min(1.0, self.power + dt / self.gp["charge_time"])
        elif self.state == State.FLYING:
            self._step_flight(dt)
        elif self.state == State.RESULT:
            self.result_t -= dt
            if self.result_t <= 0:
                self._finish_result()

        self.update()

    # ---------------------------------------------------------------- dibujo
    def _text(self, p: QPainter, x: float, y: float, s: str, size: int = 20,
              color: str = "#ffffff", bold: bool = False, align: str = "l",
              alpha: int = 255) -> None:
        f = QFont()
        f.setPixelSize(size)
        f.setBold(bold)
        p.setFont(f)
        w = QFontMetricsF(f).horizontalAdvance(s)
        if align == "c":
            x -= w / 2
        elif align == "r":
            x -= w
        p.setPen(QColor(0, 0, 0, int(150 * alpha / 255)))
        p.drawText(QPointF(x + 1.5, y + 1.5), s)
        c = QColor(color)
        c.setAlpha(alpha)
        p.setPen(c)
        p.drawText(QPointF(x, y), s)

    def _rebuild_terrain_paths(self) -> None:
        h = self.terrain.h
        fill = QPainterPath()
        top = QPainterPath()
        fill.moveTo(0, WORLD_H + 10)
        for x, y in enumerate(h):
            fill.lineTo(x, y)
            if x == 0:
                top.moveTo(x, y)
            else:
                top.lineTo(x, y)
        fill.lineTo(len(h) - 1, WORLD_H + 10)
        fill.closeSubpath()
        self._path_cache = (fill, top)
        self._terrain_dirty = False

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing
                         | QPainter.RenderHint.SmoothPixmapTransform
                         | QPainter.RenderHint.TextAntialiasing)

        sky = QLinearGradient(0, 0, 0, self.height())
        sky.setColorAt(0.0, QColor("#4a9fe0"))
        sky.setColorAt(1.0, QColor("#d4ecff"))
        p.fillRect(self.rect(), QBrush(sky))

        if self.terrain is None:
            p.end()
            return

        s = self.height() / WORLD_H
        ox = (self.width() - self.world_w * s) / 2
        p.translate(ox, 0)
        p.scale(s, s)

        self._draw_clouds(p)
        self._draw_terrain(p)
        self._draw_target(p)
        self._draw_tank(p)
        self._draw_paths(p)
        self._draw_missile(p)
        self._draw_effects(p)
        self._draw_control_panel(p)
        self._draw_hud(p)
        self._draw_banner(p)

        if self.paused:
            self._draw_overlay(p, "PAUSA", ["Esc: continuar", "M: menú principal", "Q: salir"])
        elif self.state == State.GAME_OVER:
            lines = [f"Puntos: {self.score}", f"Récord ({DIFFICULTY_NAMES[self.difficulty]}): {self.record}"]
            if self.new_record:
                lines.insert(1, "¡Nuevo récord!")
            lines += ["", "R: jugar otra vez", "Enter: menú principal"]
            self._draw_overlay(p, "GAME OVER", lines)
        p.end()

    def _draw_clouds(self, p: QPainter) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 170))
        for x, y, k in self.clouds:
            for dx, dy, r in ((0, 0, 26), (28, 6, 20), (-28, 8, 18), (10, -10, 18)):
                p.drawEllipse(QPointF(x + dx * k, y + dy * k), r * k * 1.3, r * k * 0.8)

    def _draw_terrain(self, p: QPainter) -> None:
        if self._terrain_dirty or self._path_cache is None:
            self._rebuild_terrain_paths()
        fill, top = self._path_cache
        grad = QLinearGradient(0, WORLD_H * 0.3, 0, WORLD_H)
        grad.setColorAt(0.0, QColor("#7a5632"))
        grad.setColorAt(1.0, QColor("#3a2814"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#4caf50"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.drawPath(top)

    def _draw_tank(self, p: QPainter) -> None:
        gy = self.terrain.ground_y(self.tank_x)
        body, barrel = self.assets.tank_body, self.assets.tank_barrel
        p.save()
        p.translate(self.tank_x, gy)
        if self.dir < 0:
            p.scale(-1, 1)
        p.save()
        p.translate(0, -self.tank_h * BARREL_MOUNT)
        p.rotate(-self.angle)
        p.drawPixmap(QRectF(-BARREL_ROOT, -self.barrel_h / 2, BARREL_LEN, self.barrel_h),
                     barrel, QRectF(barrel.rect()))
        p.restore()
        p.drawPixmap(QRectF(-TANK_W / 2, -self.tank_h, TANK_W, self.tank_h),
                     body, QRectF(body.rect()))
        p.restore()

    def _draw_target(self, p: QPainter) -> None:
        cx, cy = self._target_center()
        gy = self.terrain.ground_y(self.target_x)
        p.setPen(QPen(QColor("#5b3a1e"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx, gy + 2), QPointF(cx, cy))
        if not self.target_destroyed:
            r = self.target_r
            pm = self.assets.target
            p.drawPixmap(QRectF(cx - r, cy - r, 2 * r, 2 * r), pm, QRectF(pm.rect()))

    def _draw_polyline(self, p: QPainter, pts: list[tuple[float, float]]) -> None:
        if len(pts) > 1:
            p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))

    def _draw_paths(self, p: QPainter) -> None:
        if self.difficulty == "hard":
            return
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(255, 255, 255, 110), 2.5, Qt.PenStyle.DotLine)
        p.setPen(pen)
        self._draw_polyline(p, self.prev_path)
        pen.setColor(QColor(255, 255, 255, 210))
        p.setPen(pen)
        self._draw_polyline(p, self.current_path)

        if self.difficulty == "easy" and self.state == State.AIMING and self.power > 0.02:
            _, tip = self._barrel_geometry()
            vx, vy = launch_velocity(self.power, self.angle, self.dir, self.v_max)
            pts = ascent_path(tip[0], tip[1], vx, vy, self.wind, self.gravity)
            p.setPen(QPen(QColor(255, 235, 120, 230), 3, Qt.PenStyle.DashLine))
            self._draw_polyline(p, pts)

    def _draw_missile(self, p: QPainter) -> None:
        m = self.missile
        if m is None:
            return
        p.setPen(QPen(QColor("#3a1f00"), 2))
        p.setBrush(QColor("#ffb703"))
        p.drawEllipse(QPointF(m.x, m.y), 5, 5)

    def _draw_effects(self, p: QPainter) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for e in self.effects:
            u = e.t / e.duration
            r = e.radius * (0.4 + 1.2 * u)
            p.setBrush(QColor(255, 140, 30, int(200 * (1 - u))))
            p.drawEllipse(QPointF(e.x, e.y), r, r)
            p.setBrush(QColor(255, 235, 120, int(230 * (1 - u))))
            p.drawEllipse(QPointF(e.x, e.y), r * 0.55, r * 0.55)
            p.setBrush(QColor(255, 200, 80, int(255 * (1 - u))))
            for sx, sy, _, _ in e.sparks:
                p.drawEllipse(QPointF(sx, sy), 2.5, 2.5)
        for f in self.floats:
            alpha = max(0.0, min(1.0, 1.6 - f["t"]))
            self._text(p, f["x"], f["y"], f["text"], 30, "#ffe066" if alpha > 0.2 else "#ffffff",
                       True, "c")

    @staticmethod
    def _fmt_angle(v: float) -> str:
        text = f"{v:.1f}"
        return text[:-2] if text.endswith(".0") else text

    def _draw_field(self, p: QPainter, x: float, y: float, w: float, label: str,
                    value: str, active: bool, unit: str) -> None:
        self._text(p, x, y + 12, label, 13, "#cfe3f5")
        p.setBrush(QColor(0, 0, 0, 110))
        p.setPen(QPen(QColor("#ffd166") if active else QColor(255, 255, 255, 120), 2))
        p.drawRoundedRect(QRectF(x, y + 18, w, 44), 6, 6)
        if active:
            # el valor parpadea mientras el campo está activo
            shown = self.entry_text if self.entry_text else value
            alpha = 255 if int(self._anim_t * 2.5) % 2 == 0 else 70
            color = "#ffd166"
        else:
            shown, alpha, color = value, 255, "#ffffff"
        self._text(p, x + w / 2, y + 50, shown + unit, 26, color, True, "c", alpha)

    def _draw_control_panel(self, p: QPainter) -> None:
        """Arriba a la derecha: ángulo, potencia (numéricos) y barra de potencia."""
        W = self.world_w
        px, py, pw, ph = W - 196, 10, 184, 166
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(QRectF(px, py, pw, ph), 8, 8)

        fx, fw = px + 12, 108
        self._draw_field(p, fx, py + 10, fw, "ÁNGULO", self._fmt_angle(self.angle),
                         self.entry == "angle", "º")
        label = "POTENCIA"
        if self.difficulty == "easy" and self.last_power > 0:
            label += f" ({int(round(self.last_power * 100))}%)"   # Fácil: último disparo
        self._draw_field(p, fx, py + 86, fw, label, str(int(round(self.power * 100))),
                         self.entry == "power", "%")

        bw, bh = 26, ph - 28
        bx, by = px + pw - bw - 14, py + 14
        p.setBrush(QColor(0, 0, 0, 80))
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 3, 3)
        if self.power > 0:
            fh = (bh - 4) * self.power
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor.fromHsvF(0.33 * (1 - self.power), 0.9, 0.95))
            p.drawRect(QRectF(bx + 2, by + bh - 2 - fh, bw - 4, fh))

    def _draw_hud(self, p: QPainter) -> None:
        W = self.world_w
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(QRectF(12, 10, 280, 168), 8, 8)
        gp = self.gp
        self._text(p, 24, 40, f"Puntos  {self.score}", 26, "#ffe066", True)
        self._text(p, 24, 64, f"Récord  {self.record}", 18)
        self._text(p, 24, 88, f"Nivel {self.level}  ·  Objetivos {self.hits % gp['targets_per_level']}/{gp['targets_per_level']}", 18)
        shots = "●" * max(0, self.shots_left) + "○" * max(0, gp["shots_per_target"] - self.shots_left)
        self._text(p, 24, 112, f"Disparos  {shots}", 18)
        self._text(p, 24, 136, f"Fallos  {self.failures}/{gp['max_failures']}", 18)
        self._text(p, 24, 162, f"Dificultad  {DIFFICULTY_NAMES[self.difficulty]}", 16, "#cfe3f5")

        # viento
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(QRectF(W / 2 - 110, 10, 220, 66), 8, 8)
        self._text(p, W / 2, 32, "VIENTO", 15, "#cfe3f5", False, "c")
        ax, ay = W / 2 - 30, 56
        if self.wind != 0:
            sign = 1 if self.wind > 0 else -1
            length = 20 + 50 * min(1.0, abs(self.wind) / max(1.0, self.gp["max_wind"]))
            p.setPen(QPen(QColor("#ffffff"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(ax - sign * length / 2, ay), QPointF(ax + sign * length / 2, ay))
            tipx = ax + sign * length / 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawPolygon(QPolygonF([QPointF(tipx + sign * 10, ay), QPointF(tipx - sign * 2, ay - 9),
                                     QPointF(tipx - sign * 2, ay + 9)]))
        self._text(p, W / 2 + 62, 64, f"{self.wind:+.1f}" if self.wind else "0.0", 22, "#ffffff", True, "c")

        # ayuda de controles (abajo, sobre el suelo)
        k = self.settings["keys"]
        hint = (f"{k['angle_up']}/{k['angle_down']} o rueda: ángulo   ·   "
                f"{k['fire']} o clic izq. (mantener y soltar): potencia   ·   "
                f"{k['edit_angle']} / {k['edit_power']} + números, Enter: disparo exacto   ·   "
                f"{k['pause']}: pausa")
        self._text(p, W / 2, WORLD_H - 14, hint, 14, "#f3e9d8", False, "c")

    def _draw_banner(self, p: QPainter) -> None:
        if self.banner_t <= 0 or not self.banner:
            return
        W = self.world_w
        for i, line in enumerate(self.banner):
            self._text(p, W / 2, 170 + i * 44, line, 36 if i == 0 else 30, "#ffe066", True, "c")

    def _draw_overlay(self, p: QPainter, title: str, lines: list[str]) -> None:
        W = self.world_w
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRect(QRectF(0, 0, W, WORLD_H))
        self._text(p, W / 2, 250, title, 72, "#ffd166", True, "c")
        for i, line in enumerate(lines):
            self._text(p, W / 2, 320 + i * 38, line, 26, "#ffffff", False, "c")
