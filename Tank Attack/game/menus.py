"""Páginas de menú: menú principal y opciones (todo integrado, sin diálogos)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QSlider,
                               QSpinBox, QVBoxLayout, QWidget)

from .settings import DIFFICULTIES, DIFFICULTY_NAMES, get_record, save_config


class MainMenu(QWidget):
    play_clicked = Signal()
    options_clicked = Signal()
    quit_clicked = Signal()

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        title = QLabel("TANQUE PARABÓLICO")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info = QLabel()
        self.info.setObjectName("Sub")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_play = QPushButton("Jugar")
        btn_opts = QPushButton("Opciones")
        btn_quit = QPushButton("Salir")
        btn_play.clicked.connect(self.play_clicked)
        btn_opts.clicked.connect(self.options_clicked)
        btn_quit.clicked.connect(self.quit_clicked)
        for b in (btn_play, btn_opts, btn_quit):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.addStretch(2)
        layout.addWidget(title)
        layout.addWidget(self.info)
        layout.addSpacing(36)
        for b in (btn_play, btn_opts, btn_quit):
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(b)
            row.addStretch()
            layout.addLayout(row)
            layout.addSpacing(10)
        layout.addStretch(3)
        self.refresh()

    def refresh(self) -> None:
        diff = self.settings["gameplay"]["difficulty"]
        self.info.setText(f"Dificultad: {DIFFICULTY_NAMES[diff]}   ·   Récord: {get_record(diff)}")


class OptionsPage(QWidget):
    accepted_ = Signal()
    cancelled = Signal()

    RESOLUTIONS = [(1024, 576), (1280, 720), (1366, 768), (1600, 900), (1920, 1080)]

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.fullscreen = QCheckBox()
        self.resolution = QComboBox()
        self.difficulty = QComboBox()
        for d in DIFFICULTIES:
            self.difficulty.addItem(DIFFICULTY_NAMES[d], d)
        self.targets_per_level = self._spin(1, 50)
        self.shots_per_target = self._spin(1, 20)
        self.max_failures = self._spin(1, 20)
        self.wind_enabled = QCheckBox()
        self.max_wind = self._dspin(1.0, 30.0, 0.5)
        self.gravity = self._spin(100, 2000, 25)
        self.charge_time = self._dspin(0.3, 10.0, 0.1)
        self.angle_speed = self._spin(5, 200, 5)
        self.wheel_step = self._dspin(0.5, 15.0, 0.5)
        self.action_radius = self._spin(50, 1000, 10)
        self.moving_targets = QCheckBox()
        self.sound = QCheckBox()
        self.music = QCheckBox()
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)

        rows = [
            ("Pantalla completa", self.fullscreen),
            ("Resolución en ventana", self.resolution),
            ("Dificultad (ayuda de trayectoria)", self.difficulty),
            ("Objetivos por nivel", self.targets_per_level),
            ("Disparos por objetivo", self.shots_per_target),
            ("Fallos máximos", self.max_failures),
            ("Viento", self.wind_enabled),
            ("Viento máximo", self.max_wind),
            ("Gravedad (px/s²)", self.gravity),
            ("Tiempo de carga (s)", self.charge_time),
            ("Velocidad del cañón (º/s)", self.angle_speed),
            ("Rueda del ratón (º por muesca)", self.wheel_step),
            ("Radio de acción (px)", self.action_radius),
            ("Objetivos móviles (nivel 6+)", self.moving_targets),
            ("Sonido", self.sound),
            ("Música", self.music),
            ("Volumen", self.volume),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        half = (len(rows) + 1) // 2
        for i, (text, widget) in enumerate(rows):
            col = 0 if i < half else 3
            r = i % half
            grid.addWidget(QLabel(text), r, col)
            grid.addWidget(widget, r, col + 1)
        grid.setColumnMinimumWidth(2, 40)
        grid.setColumnStretch(2, 1)

        title = QLabel("Opciones")
        title.setObjectName("Title2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = QLabel("Las teclas se pueden cambiar en config.json (sección \"keys\").")
        note.setObjectName("Sub")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ok = QPushButton("Guardar")
        cancel = QPushButton("Cancelar")
        ok.clicked.connect(self._accept)
        cancel.clicked.connect(self.cancelled)
        for b in (ok, cancel):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(ok)
        buttons.addSpacing(20)
        buttons.addWidget(cancel)
        buttons.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 20, 40, 20)
        outer.addWidget(title)
        outer.addStretch(1)
        wrap = QHBoxLayout()
        wrap.addStretch()
        wrap.addLayout(grid)
        wrap.addStretch()
        outer.addLayout(wrap)
        outer.addStretch(1)
        outer.addWidget(note)
        outer.addSpacing(8)
        outer.addLayout(buttons)

    @staticmethod
    def _spin(lo: int, hi: int, step: int = 1) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        return s

    @staticmethod
    def _dspin(lo: float, hi: float, step: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setDecimals(1)
        return s

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Rellena los controles con la configuración actual."""
        d, g, a = self.settings["display"], self.settings["gameplay"], self.settings["audio"]
        self.fullscreen.setChecked(d["fullscreen"])

        res = list(self.RESOLUTIONS)
        current = (d["window_width"], d["window_height"])
        if current not in res:
            res.insert(0, current)
        self.resolution.clear()
        for w, h in res:
            self.resolution.addItem(f"{w} × {h}", f"{w}x{h}")
        self.resolution.setCurrentIndex(res.index(current))

        self.difficulty.setCurrentIndex(DIFFICULTIES.index(g["difficulty"]))
        self.targets_per_level.setValue(g["targets_per_level"])
        self.shots_per_target.setValue(g["shots_per_target"])
        self.max_failures.setValue(g["max_failures"])
        self.wind_enabled.setChecked(g["wind_enabled"])
        self.max_wind.setValue(g["max_wind"])
        self.gravity.setValue(int(g["gravity"]))
        self.charge_time.setValue(g["charge_time"])
        self.angle_speed.setValue(int(g["angle_speed"]))
        self.wheel_step.setValue(g["wheel_step"])
        self.action_radius.setValue(int(g["action_radius"]))
        self.moving_targets.setChecked(g["moving_targets"])
        self.sound.setChecked(a["sound"])
        self.music.setChecked(a["music"])
        self.volume.setValue(int(round(a["volume"] * 100)))

    def _accept(self) -> None:
        d, g, a = self.settings["display"], self.settings["gameplay"], self.settings["audio"]
        d["fullscreen"] = self.fullscreen.isChecked()
        w, h = str(self.resolution.currentData()).split("x")
        d["window_width"], d["window_height"] = int(w), int(h)

        g["difficulty"] = self.difficulty.currentData()
        g["targets_per_level"] = self.targets_per_level.value()
        g["shots_per_target"] = self.shots_per_target.value()
        g["max_failures"] = self.max_failures.value()
        g["wind_enabled"] = self.wind_enabled.isChecked()
        g["max_wind"] = float(self.max_wind.value())
        g["gravity"] = float(self.gravity.value())
        g["charge_time"] = float(self.charge_time.value())
        g["angle_speed"] = float(self.angle_speed.value())
        g["wheel_step"] = float(self.wheel_step.value())
        g["action_radius"] = self.action_radius.value()
        g["moving_targets"] = self.moving_targets.isChecked()
        a["sound"] = self.sound.isChecked()
        a["music"] = self.music.isChecked()
        a["volume"] = self.volume.value() / 100.0

        save_config(self.settings)
        self.accepted_.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)
