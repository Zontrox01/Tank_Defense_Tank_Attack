"""Interfaz: juego, menú principal, configuración y ventana sin barra de título."""
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, Signal, QPointF, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics
from PySide6.QtWidgets import (QWidget, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QSpinBox, QComboBox, QCheckBox, QFormLayout,
                               QScrollArea)

from engine import Engine, DIRS
from inputs import (ACTIONS, ACTION_LABELS, IGNORED_KEYS, key_id, key_label, default_keys)

STYLE = """
QWidget { background:#1e2a18; color:#eef0e0; font-size:16px; }
QLabel#title { font-size:60px; font-weight:bold; color:#e0c040; }
QLabel#title2 { font-size:32px; font-weight:bold; color:#e0c040; }
QPushButton { background:#3f5a2c; border:2px solid #6b8f47; border-radius:8px;
              padding:10px 24px; min-width:260px; }
QPushButton:hover { background:#4f7036; }
QPushButton:focus { border-color:#e0c040; }
QSpinBox, QComboBox { background:#2b3a22; border:1px solid #6b8f47; padding:4px; min-width:220px; }
QScrollArea { border:none; }
"""


# ======================================================================
#  Juego
# ======================================================================
class GameWidget(QWidget):
    back_to_menu = Signal()

    def __init__(self, cfg, sprites, sounds, record):
        super().__init__()
        self.cfg, self.sprites, self.sounds, self.record = cfg, sprites, sounds, record
        self.engine = Engine(cfg)
        self.pix = {}
        self.bind = {}
        self.paused = False
        self.fire_held = False
        self.new_record = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    # ---- ciclo de vida ----
    def start(self):
        self.bind = {kid: a for a, kids in self.cfg.keys.items() for kid in kids}
        self.engine.set_size(self.width(), self.height())
        self.engine.reset()
        self.paused = False
        self.sounds.sync_music()
        self.fire_held = False
        self.new_record = False
        self._rebuild_pixmaps()
        self.clock.start()
        self.timer.start()
        self.setFocus()

    def stop(self):
        self.timer.stop()

    def _rebuild_pixmaps(self):
        u = self.engine.unit
        self.pix = self.sprites.scaled(max(16, int(u * 0.10)), max(6, int(u * 0.04)))

    def resizeEvent(self, ev):
        self.engine.set_size(self.width(), self.height())
        self._rebuild_pixmaps()

    def focusOutEvent(self, ev):
        if self.timer.isActive() and self.engine.state == "playing":
            self._set_paused(True)
        self.fire_held = False

    def _set_paused(self, paused):
        self.paused = paused
        if paused:
            self.sounds.pause_music()
        else:
            self.sounds.sync_music()

    # ---- bucle ----
    def tick(self):
        dt = min(self.clock.restart() / 1000, 0.05)
        en = self.engine
        if not self.paused and en.state == "playing":
            if self.fire_held and en.fire():
                self.sounds.play("shot")
            for e in en.update(dt):
                if e == "gameover":
                    self.new_record = self.record.update(en.score)
                    self.sounds.pause_music()          # se oye el sonido de game over
                    self.sounds.play("gameover")
                if e in ("kill", "hit"):      # tanque enemigo destruido
                    self.sounds.play("burst")
        self.update()

    # ---- teclado ----
    def keyPressEvent(self, ev):
        if ev.isAutoRepeat():
            return
        en = self.engine
        k = ev.key()
        if en.state == "gameover":
            if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_R):
                self.start()
            elif k in (Qt.Key_Escape, Qt.Key_M):
                self.back_to_menu.emit()
            return
        action = self.bind.get(key_id(ev))
        if self.paused:
            if action == "pause":
                self._set_paused(False)
                self.clock.restart()
            elif k == Qt.Key_M:
                self.back_to_menu.emit()
            return
        if action in DIRS:
            en.set_aim(DIRS.index(action))
        elif action == "fire":
            self.fire_held = True
            if en.fire():
                self.sounds.play("shot")
        elif action == "pause":
            self._set_paused(True)

    def keyReleaseEvent(self, ev):
        if not ev.isAutoRepeat() and self.bind.get(key_id(ev)) == "fire":
            self.fire_held = False

    # ---- dibujo ----
    def paintEvent(self, ev):
        if not self.pix:
            return
        en, w, h = self.engine, self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#2b3a22"))

        pen = QPen(QColor(255, 255, 255, 30), 2, Qt.DashLine)
        p.setPen(pen)
        for d in en.dirs:
            vx, vy = en.vec(d)
            L = en.reach(d)
            p.drawLine(QPointF(en.cx, en.cy), QPointF(en.cx + vx * L, en.cy + vy * L))

        for e in en.enemies:
            pm = self.pix["enemy_" + DIRS[e.facing]]
            p.drawPixmap(int(e.x - pm.width() / 2), int(e.y - pm.height() / 2), pm)
        pm = self.pix["bullet"]
        for b in en.bullets:
            p.drawPixmap(int(b.x - pm.width() / 2), int(b.y - pm.height() / 2), pm)
        if en.state == "playing" and (en.invuln <= 0 or int(en.invuln * 10) % 2 == 0):
            pm = self.pix["tank_" + DIRS[en.aim]]
            p.drawPixmap(int(en.cx - pm.width() / 2), int(en.cy - pm.height() / 2), pm)

        self._hud(p, w)
        if self.paused:
            self._overlay(p, "PAUSA", ["Pausa / Esc: continuar", "M: volver al menú"])
        elif en.state == "gameover":
            lines = [f"Puntos: {en.score}   ·   Nivel: {en.level}"]
            if self.new_record:
                lines.append("¡Nuevo récord!")
            lines.append("Intro / R: jugar de nuevo   ·   Esc / M: menú")
            self._overlay(p, "GAME OVER", lines)

    def _font(self, factor, bold=True):
        f = QFont()
        f.setPixelSize(max(12, int(self.engine.unit * factor)))
        f.setBold(bold)
        return f

    def _hud(self, p, w):
        en = self.engine
        p.setFont(self._font(0.035))
        p.setPen(QColor("#f2f2e6"))
        fm = QFontMetrics(p.font())
        m = int(en.unit * 0.02)
        r = QRect(m, m, w - 2 * m, fm.height())
        p.drawText(r, Qt.AlignLeft, f"Puntos: {en.score}")
        p.drawText(r, Qt.AlignHCenter, f"Nivel {en.level}")
        p.drawText(r, Qt.AlignRight, f"Récord: {max(self.record.value, en.score)}")
        icon = self.pix["tank_n"]
        small = icon.scaled(int(icon.width() * 0.6), int(icon.height() * 0.6),
                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        for i in range(max(0, en.lives)):
            p.drawPixmap(m + i * (small.width() + 4), m + fm.height() + 6, small)

    def _overlay(self, p, title, lines):
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))
        p.setPen(QColor("#e0c040"))
        p.setFont(self._font(0.12))
        h = self.height()
        p.drawText(QRect(0, int(h * 0.25), self.width(), int(h * 0.2)), Qt.AlignCenter, title)
        p.setPen(QColor("#f2f2e6"))
        p.setFont(self._font(0.035, bold=False))
        p.drawText(QRect(0, int(h * 0.48), self.width(), int(h * 0.3)), Qt.AlignHCenter | Qt.AlignTop,
                   "\n".join(lines))


# ======================================================================
#  Menú principal
# ======================================================================
class MenuPage(QWidget):
    play = Signal()
    settings = Signal()
    quit = Signal()

    def __init__(self, cfg, record):
        super().__init__()
        self.cfg, self.record = cfg, record
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)
        title = QLabel("TANK DEFENSE")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        self.rec = QLabel()
        self.rec.setAlignment(Qt.AlignCenter)
        self.b_mode = QPushButton()
        b_play, b_set, b_quit = QPushButton("Jugar"), QPushButton("Configuración"), QPushButton("Salir")
        hint = QLabel("Teclado numérico o cursores para apuntar  ·  Espacio: disparar  ·  Esc: pausa")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addWidget(self.rec)
        lay.addSpacing(20)
        for b in (b_play, self.b_mode, b_set, b_quit):
            lay.addWidget(b, alignment=Qt.AlignCenter)
        lay.addSpacing(20)
        lay.addWidget(hint)
        b_play.clicked.connect(self.play)
        b_set.clicked.connect(self.settings)
        b_quit.clicked.connect(self.quit)
        self.b_mode.clicked.connect(self._toggle_mode)
        self.b_play = b_play
        self.refresh()

    def _toggle_mode(self):
        self.cfg.mode = 2 if self.cfg.mode == 1 else 1
        self.cfg.save()
        self.refresh()

    def refresh(self):
        self.rec.setText(f"Récord: {self.record.value}")
        self.b_mode.setText(f"Modalidad: {4 if self.cfg.mode == 1 else 8} direcciones")
        self.b_play.setFocus()


# ======================================================================
#  Configuración
# ======================================================================
FIELDS = [
    ("fullscreen", "Pantalla completa", "bool", None),
    ("window_w", "Ancho de la ventana (px)", "int", (640, 7680)),
    ("window_h", "Alto de la ventana (px)", "int", (480, 4320)),
    ("mode", "Modalidad", "choice", [(1, "4 direcciones"), (2, "8 direcciones")]),
    ("lives", "Vidas (máx. 3)", "int", (1, 3)),
    ("kills_per_level", "Tanques eliminados por nivel", "int", (1, 200)),
    ("start_enemies", "Tanques a la vez (al empezar)", "int", (1, 20)),
    ("enemies_every", "+1 tanque a la vez cada N niveles (0 = nunca)", "int", (0, 20)),
    ("max_enemies", "Máximo de tanques a la vez", "int", (1, 30)),
    ("start_speed", "Velocidad inicial de los enemigos (1-10)", "int", (1, 10)),
    ("speed_pct", "Incremento de velocidad por nivel (%)", "int", (0, 100)),
    ("spawn_mode", "Aparición de enemigos", "choice",
     [("random", "Aleatoria"), ("waves", "Oleadas"), ("progressive", "Progresiva (aleatoria → oleadas)")]),
    ("max_bullets", "Proyectiles máx. en pantalla (0 = sin límite)", "int", (0, 30)),
    ("fire_cooldown_ms", "Tiempo entre disparos (ms, 0 = sin límite)", "int", (0, 3000)),
    ("sound", "Efectos de sonido (disparo, explosión)", "bool", None),
    ("music", "Música de fondo", "bool", None),
]


class KeyButton(QPushButton):
    captured = Signal(str, str)  # acción, id de tecla ("" = cancelado)

    def __init__(self, action):
        super().__init__()
        self.action = action
        self.capturing = False
        self.clicked.connect(self._begin)

    def _begin(self):
        self.capturing = True
        self.setText("Pulsa una tecla…  (Esc cancela)")

    def keyPressEvent(self, ev):
        if not self.capturing:
            return super().keyPressEvent(ev)
        if ev.key() in IGNORED_KEYS:
            return
        self.capturing = False
        self.captured.emit(self.action, "" if ev.key() == Qt.Key_Escape else key_id(ev))


class SettingsPage(QWidget):
    done = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.widgets = {}
        self.keys = {}
        self.keybtns = {}
        outer = QVBoxLayout(self)
        t = QLabel("Configuración")
        t.setObjectName("title2")
        t.setAlignment(Qt.AlignCenter)
        outer.addWidget(t)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        for attr, label, kind, arg in FIELDS:
            if kind == "bool":
                w = QCheckBox()
            elif kind == "int":
                w = QSpinBox()
                w.setRange(*arg)
            else:
                w = QComboBox()
                for value, text in arg:
                    w.addItem(text, value)
            self.widgets[attr] = (w, kind)
            form.addRow(label, w)
        form.addRow(QLabel("— Teclas (pulsa el botón y luego la nueva tecla) —"))
        for a in ACTIONS:
            b = KeyButton(a)
            b.captured.connect(self._on_key)
            self.keybtns[a] = b
            form.addRow(ACTION_LABELS[a], b)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        row = QHBoxLayout()
        b_reset, b_cancel, b_save = (QPushButton("Restablecer teclas"), QPushButton("Cancelar"),
                                     QPushButton("Guardar y volver"))
        for b in (b_reset, b_cancel, b_save):
            row.addWidget(b)
        outer.addLayout(row)
        b_reset.clicked.connect(self._reset_keys)
        b_cancel.clicked.connect(self.done)
        b_save.clicked.connect(self._save)

    def load(self):
        for attr, (w, kind) in self.widgets.items():
            v = getattr(self.cfg, attr)
            if kind == "bool":
                w.setChecked(v)
            elif kind == "int":
                w.setValue(v)
            else:
                w.setCurrentIndex(max(0, w.findData(v)))
        self.keys = {a: list(k) for a, k in self.cfg.keys.items()}
        self._refresh_keys()

    def _save(self):
        for attr, (w, kind) in self.widgets.items():
            v = w.isChecked() if kind == "bool" else w.value() if kind == "int" else w.currentData()
            setattr(self.cfg, attr, v)
        self.cfg.keys = self.keys
        self.cfg.save()
        self.done.emit()

    def _refresh_keys(self):
        for a, b in self.keybtns.items():
            b.setText(", ".join(key_label(k) for k in self.keys[a]))

    def _on_key(self, action, kid):
        if kid:
            for a in self.keys:
                if kid in self.keys[a]:
                    self.keys[a].remove(kid)
                    if not self.keys[a]:      # no dejar acciones sin tecla
                        self.keys[a] = list(default_keys()[a])
            self.keys[action] = [kid]
        self._refresh_keys()

    def _reset_keys(self):
        self.keys = default_keys()
        self._refresh_keys()


# ======================================================================
#  Ventana principal (sin barra de título)
# ======================================================================
class MainWindow(QMainWindow):
    def __init__(self, cfg, sprites, sounds, record):
        super().__init__()
        self.cfg = cfg
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.menu = MenuPage(cfg, record)
        self.settings = SettingsPage(cfg)
        self.game = GameWidget(cfg, sprites, sounds, record)
        for w in (self.menu, self.settings, self.game):
            self.stack.addWidget(w)
        self.menu.play.connect(self._play)
        self.menu.settings.connect(self._open_settings)
        self.menu.quit.connect(self.close)
        self.settings.done.connect(self._close_settings)
        self.sounds = sounds
        self.game.back_to_menu.connect(self._to_menu)

    def apply_display(self):
        if self.cfg.fullscreen:
            self.showFullScreen()
            return
        self.showNormal()
        geo = self.screen().availableGeometry()
        w, h = min(self.cfg.window_w, geo.width()), min(self.cfg.window_h, geo.height())
        self.resize(w, h)
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)

    def _play(self):
        self.stack.setCurrentWidget(self.game)
        self.game.start()

    def _to_menu(self):
        self.game.stop()
        self.sounds.sync_music()
        self.menu.refresh()
        self.stack.setCurrentWidget(self.menu)

    def _open_settings(self):
        self.settings.load()
        self.stack.setCurrentWidget(self.settings)

    def _close_settings(self):
        self.sounds.sync_music()
        self.apply_display()
        self.menu.refresh()
        self.stack.setCurrentWidget(self.menu)

    def mousePressEvent(self, ev):
        # Ventana sin barra de título: se arrastra desde el fondo del menú
        if (ev.button() == Qt.LeftButton and not self.isFullScreen()
                and self.stack.currentWidget() is not self.game and self.windowHandle()):
            self.windowHandle().startSystemMove()
