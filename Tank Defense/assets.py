"""Sprites PNG (se generan si faltan, para que puedas sustituirlos) y sonido/música en mp3."""
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF, QUrl
from PySide6.QtGui import QImage, QPainter, QColor, QPixmap

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
except ImportError:  # sin QtMultimedia el juego funciona sin sonido
    QMediaPlayer = QAudioOutput = None

from engine import DIRS

BASE = Path(__file__).resolve().parent
SPRITE_DIR = BASE / "assets" / "sprites"
SOUND_DIR = BASE / "assets" / "sound"
SIZE = 128


def _new_image(size=SIZE):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    return img


def _tank_base(body, dark, light):
    """Tanque mirando hacia arriba (N)."""
    img = _new_image()
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(dark))
    p.drawRoundedRect(QRectF(26, 20, 18, 88), 5, 5)   # oruga izquierda
    p.drawRoundedRect(QRectF(84, 20, 18, 88), 5, 5)   # oruga derecha
    p.setBrush(QColor(body))
    p.drawRoundedRect(QRectF(40, 26, 48, 76), 8, 8)   # casco
    p.setBrush(QColor(dark))
    p.drawRect(QRectF(60, 4, 8, 56))                  # cañón
    p.setBrush(QColor(light))
    p.drawEllipse(QPointF(64, 66), 17, 17)            # torreta
    p.end()
    return img


def _rotated(img, angle):
    out = _new_image(img.width())
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    c = img.width() / 2
    p.translate(c, c)
    p.rotate(angle)
    p.translate(-c, -c)
    p.drawImage(0, 0, img)
    p.end()
    return out


def _bullet():
    img = _new_image(32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#e8962a"))
    p.drawEllipse(QPointF(16, 16), 14, 14)
    p.setBrush(QColor("#ffe27a"))
    p.drawEllipse(QPointF(16, 16), 8, 8)
    p.end()
    return img


def ensure_sprites():
    """Crea los PNG que falten. tank_<dir>.png, enemy_<dir>.png (dir = hacia dónde mira)."""
    SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    sets = {
        "tank": _tank_base("#5f8f3a", "#2f4a1c", "#86b85a"),
        "enemy": _tank_base("#b03a2e", "#5a1d17", "#d9574a"),
    }
    for prefix, base in sets.items():
        for i, d in enumerate(DIRS):
            f = SPRITE_DIR / f"{prefix}_{d}.png"
            if not f.exists():
                _rotated(base, 45 * i).save(str(f))
    f = SPRITE_DIR / "bullet.png"
    if not f.exists():
        _bullet().save(str(f))


class Sprites:
    def __init__(self):
        self.originals = {}
        for prefix in ("tank", "enemy"):
            for d in DIRS:
                name = f"{prefix}_{d}"
                self.originals[name] = QPixmap(str(SPRITE_DIR / f"{name}.png"))
        self.originals["bullet"] = QPixmap(str(SPRITE_DIR / "bullet.png"))

    def scaled(self, tank_px, bullet_px):
        out = {}
        for name, pm in self.originals.items():
            px = bullet_px if name == "bullet" else tank_px
            out[name] = pm.scaled(px, px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return out


class Sounds:
    """assets/sound/shot.mp3, burst.mp3, gameover.mp3 (efectos) y song.mp3 (música, en bucle)."""
    EFFECTS = {"shot": "shot.mp3", "burst": "burst.mp3", "gameover": "gameover.mp3"}
    POOL = 6  # reproductores por efecto, para que varios disparos se solapen

    def __init__(self, cfg):
        self.cfg = cfg
        self.pools = {}
        self.idx = {}
        self.music = None
        if QMediaPlayer is None:
            print("[sonido] QtMultimedia no disponible: el juego irá sin sonido")
            return
        for name, fn in self.EFFECTS.items():
            f = SOUND_DIR / fn
            if f.exists():
                self.pools[name] = [self._player(f, 0.7) for _ in range(self.POOL)]
                self.idx[name] = 0
            else:
                print(f"[sonido] no encuentro {f}")
        f = SOUND_DIR / "song.mp3"
        if f.exists():
            self.music = self._player(f, 0.35)
            self.music.setLoops(QMediaPlayer.Loops.Infinite)
        else:
            print(f"[sonido] no encuentro {f}")

    @staticmethod
    def _player(path, volume):
        player = QMediaPlayer()
        out = QAudioOutput()
        out.setVolume(volume)
        player.setAudioOutput(out)
        player.setSource(QUrl.fromLocalFile(str(path)))
        player.errorOccurred.connect(lambda err, msg, n=path.name: print(f"[sonido] {n}: {msg}"))
        player._out = out  # mantener viva la salida de audio
        return player

    # ---- efectos ----
    def play(self, name):
        pool = self.pools.get(name)
        if not self.cfg.sound or not pool:
            return
        i = self.idx[name]
        self.idx[name] = (i + 1) % len(pool)
        p = pool[i]
        p.setPosition(0)
        p.play()

    # ---- música ----
    def sync_music(self):
        """Arranca o detiene la música según la opción 'Música de fondo'."""
        if not self.music:
            return
        if self.cfg.music:
            if self.music.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.music.play()
        else:
            self.music.pause()

    def pause_music(self):
        if self.music:
            self.music.pause()
