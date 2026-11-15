"""Sonido y música con la menor latencia posible.

Archivos esperados en assets/sound/ (para cada efecto vale .wav o .mp3):

    shot      al disparar
    flight    mientras vuela el misil (se corta al impactar)
    burst     explosión del impacto
    gameover  al perder la partida
    song.mp3  música de fondo (en bucle)

Cómo se reproducen los efectos:

* ``.wav``  -> QSoundEffect: se carga en memoria y arranca al instante.
* ``.mp3``  -> QMediaPlayer tiene un retraso propio al arrancar (a veces cerca
  de un segundo) que no se puede evitar. Por eso, la primera vez que se
  arranca el juego cada mp3 se decodifica con QAudioDecoder a un WAV guardado
  en assets/sound/.cache/ y, desde ese momento, se reproduce con
  QSoundEffect. Mientras se convierte (menos de un segundo) se usa el
  QMediaPlayer. Las siguientes ejecuciones leen el WAV ya convertido.
  Si existe un .wav propio con el mismo nombre, se usa ese.

Si falta un archivo, ese sonido no suena y se avisa una vez por consola.
Los reproductores se guardan en esta clase para que no los elimine el
recolector de basura.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import (QAudioDecoder, QAudioFormat, QAudioOutput,
                                  QMediaPlayer, QSoundEffect)

from .settings import SOUND_DIR
from .wavtools import pcm_to_wav

CACHE_DIR = SOUND_DIR / ".cache"
CONVERT_TIMEOUT_MS = 10000

EFFECTS = {
    "shot": "shot",
    "flight": "flight",
    "burst": "burst",
    "gameover": "gameover",
}
MUSIC_FILE = "song.mp3"
MUSIC_GAIN = 0.6     # la música suena algo más baja que los efectos
PRIME_MS = 250       # duración del precalentamiento silencioso


class _MediaChannel:
    """QMediaPlayer que se mantiene 'caliente' (en pausa al inicio)."""

    def __init__(self, owner: QObject, path: Path, loop: bool = False) -> None:
        self.name = path.name
        self.loop = loop
        self._ready = False
        self._priming = False
        self.player = QMediaPlayer(owner)
        self.output = QAudioOutput(owner)
        self.player.setAudioOutput(self.output)
        if loop:
            self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.errorOccurred.connect(self._on_error)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.setSource(QUrl.fromLocalFile(str(path)))

    def _on_error(self, error, message: str) -> None:
        print(f"[audio] {self.name}: {message}")

    def _on_status(self, status) -> None:
        statuses = QMediaPlayer.MediaStatus
        if self.loop:
            return
        if status == statuses.LoadedMedia and not self._ready:
            self._ready = True
            self._prime()
        elif status == statuses.EndOfMedia:
            self._rewind()

    def _prime(self) -> None:
        self._priming = True
        self.output.setMuted(True)
        self.player.play()
        QTimer.singleShot(PRIME_MS, self._end_prime)

    def _end_prime(self) -> None:
        if self._priming:
            self._priming = False
            self._rewind()
            self.output.setMuted(False)

    def _rewind(self) -> None:
        self.player.pause()
        self.player.setPosition(0)

    # -- interfaz común --
    def play(self) -> None:
        if self._priming:
            self._priming = False
        self.output.setMuted(False)
        self.player.setPosition(0)
        self.player.play()

    def stop(self) -> None:
        if self.loop:
            self.player.stop()
        else:
            self._rewind()

    def pause(self) -> None:
        self.player.pause()

    def resume(self) -> None:
        self.player.play()

    def set_volume(self, volume: float) -> None:
        self.output.setVolume(max(0.0, min(1.0, volume)))


class _SfxChannel:
    """QSoundEffect (solo WAV): latencia mínima."""

    def __init__(self, owner: QObject, path: Path) -> None:
        self.name = path.name
        self.effect = QSoundEffect(owner)
        self.effect.statusChanged.connect(self._on_status)
        self.effect.setSource(QUrl.fromLocalFile(str(path)))

    def _on_status(self) -> None:
        if self.effect.status() == QSoundEffect.Status.Error:
            print(f"[audio] {self.name}: no se pudo cargar el WAV")

    def play(self) -> None:
        self.effect.stop()
        self.effect.play()

    def stop(self) -> None:
        self.effect.stop()

    def pause(self) -> None:
        self.effect.stop()

    def resume(self) -> None:
        self.effect.play()

    def set_volume(self, volume: float) -> None:
        self.effect.setVolume(max(0.0, min(1.0, volume)))


def _cache_dir() -> Path:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        probe = CACHE_DIR / ".probe"
        probe.write_bytes(b"")
        probe.unlink()
        return CACHE_DIR
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "tanque_parabolico_cache"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _buffer_bytes(buf) -> bytes | None:
    """Extrae los bytes de un QAudioBuffer (la API varía entre versiones de PySide6).

    Cada intento se valida comparando la longitud con byteCount().
    """
    size = buf.byteCount()
    attempts = (
        lambda: bytes(buf.constData().asarray(size)),
        lambda: bytes(memoryview(buf.constData()))[:size],
        lambda: bytes(buf.data()),
        lambda: bytes(buf.constData()),
    )
    for attempt in attempts:
        try:
            data = attempt()
        except Exception:
            continue
        if len(data) == size:
            return data
    return None


def _sample_format_name(fmt) -> str | None:
    sf = QAudioFormat.SampleFormat
    return {sf.UInt8: "u8", sf.Int16: "s16", sf.Int32: "s32", sf.Float: "f32"}.get(fmt.sampleFormat())


class _Mp3Converter(QObject):
    """Decodifica un mp3 a WAV (asíncrono) para poder usar QSoundEffect."""

    done = Signal(str, str)    # clave, ruta del wav
    failed = Signal(str)       # clave

    def __init__(self, key: str, mp3: Path, wav: Path, parent: QObject) -> None:
        super().__init__(parent)
        self.key, self.mp3, self.wav = key, mp3, wav
        self._chunks: list[bytes] = []
        self._fmt = None
        self._closed = False

        self.decoder = QAudioDecoder(self)
        try:   # pedimos PCM de 16 bits; si el sistema no lo respeta, se convierte después
            wanted = QAudioFormat()
            wanted.setSampleRate(44100)
            wanted.setChannelCount(2)
            wanted.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self.decoder.setAudioFormat(wanted)
        except Exception:
            pass
        self.decoder.setSource(QUrl.fromLocalFile(str(mp3)))
        self.decoder.bufferReady.connect(self._on_buffer)
        self.decoder.finished.connect(self._on_finished)
        for name in ("errorOccurred", "error"):
            signal = getattr(self.decoder, name, None)
            if signal is not None and hasattr(signal, "connect"):
                try:
                    signal.connect(self._on_error)
                    break
                except Exception:
                    continue

    def start(self) -> None:
        """Se llama después de conectar las señales done/failed."""
        QTimer.singleShot(CONVERT_TIMEOUT_MS, self._on_timeout)
        self.decoder.start()

    def _fail(self, reason: str) -> None:
        if self._closed:
            return
        self._closed = True
        print(f"[audio] No se pudo convertir {self.mp3.name} a WAV ({reason}). "
              f"Se usará el reproductor de mp3, con más retraso. "
              f"Solución: guarda {self.mp3.stem}.wav junto al mp3 en assets/sound/.")
        try:
            self.decoder.stop()
        except Exception:
            pass
        self.failed.emit(self.key)

    def _on_error(self, *args) -> None:
        self._fail(self.decoder.errorString() or "error del decodificador")

    def _on_timeout(self) -> None:
        if not self._closed:
            self._fail("tiempo agotado")

    def _on_buffer(self) -> None:
        if self._closed:
            return
        while self.decoder.bufferAvailable():
            buf = self.decoder.read()
            if not buf.isValid():
                break
            if self._fmt is None:
                self._fmt = buf.format()
            data = _buffer_bytes(buf)
            if data is None:
                self._fail("no se pudieron leer los datos del búfer")
                return
            self._chunks.append(data)

    def _on_finished(self) -> None:
        if self._closed:
            return
        self._on_buffer()
        if self._closed:
            return
        if self._fmt is None or not self._chunks:
            self._fail("no se obtuvo audio")
            return
        name = _sample_format_name(self._fmt)
        if name is None:
            self._fail("formato de muestra desconocido")
            return
        try:
            pcm_to_wav(self.wav, b"".join(self._chunks), self._fmt.channelCount(),
                       self._fmt.sampleRate(), name)
        except Exception as exc:   # noqa: BLE001 - cualquier fallo => reproductor de respaldo
            self._fail(str(exc))
            return
        self._closed = True
        print(f"[audio] {self.mp3.name} convertido a WAV: ahora se reproduce sin retraso.")
        self.done.emit(self.key, str(self.wav))


class AudioManager(QObject):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.effects: dict[str, object] = {}
        self.music: _MediaChannel | None = None
        self._converters: list[_Mp3Converter] = []

        for key, stem in EFFECTS.items():
            channel = self._make_effect(key, stem)
            if channel is not None:
                self.effects.setdefault(key, channel)
            else:
                print(f"[audio] Falta assets/sound/{stem}.wav (o .mp3): ese sonido no se reproducirá.")
        if (SOUND_DIR / MUSIC_FILE).exists():
            self.music = _MediaChannel(self, SOUND_DIR / MUSIC_FILE, loop=True)
        else:
            print(f"[audio] Falta assets/sound/{MUSIC_FILE}: no habrá música.")
        self.apply_settings()

    # ------------------------------------------------------------------
    def _make_effect(self, key: str, stem: str):
        wav, mp3 = SOUND_DIR / f"{stem}.wav", SOUND_DIR / f"{stem}.mp3"
        if wav.exists():
            return _SfxChannel(self, wav)
        if not mp3.exists():
            return None
        cached = _cache_dir() / f"{stem}.wav"
        try:
            fresh = cached.stat().st_mtime >= mp3.stat().st_mtime and cached.stat().st_size > 44
        except OSError:
            fresh = False
        if fresh:
            return _SfxChannel(self, cached)
        conv = _Mp3Converter(key, mp3, cached, self)
        conv.done.connect(self._on_converted)
        self._converters.append(conv)
        channel = _MediaChannel(self, mp3)   # provisional hasta que termine la conversión
        self.effects[key] = channel
        conv.start()
        return self.effects[key]

    def _on_converted(self, key: str, wav_path: str) -> None:
        old = self.effects.get(key)
        new = _SfxChannel(self, Path(wav_path))
        new.set_volume(self.settings["audio"]["volume"])
        self.effects[key] = new
        if old is not None:
            old.stop()

    def apply_settings(self) -> None:
        a = self.settings["audio"]
        for ch in self.effects.values():
            ch.set_volume(a["volume"])
        if self.music:
            self.music.set_volume(a["volume"] * MUSIC_GAIN)
            if not a["music"]:
                self.music.stop()

    def play(self, name: str) -> None:
        if not self.settings["audio"]["sound"]:
            return
        ch = self.effects.get(name)
        if ch:
            ch.play()

    def stop(self, name: str) -> None:
        ch = self.effects.get(name)
        if ch:
            ch.stop()

    def start_music(self) -> None:
        if self.music and self.settings["audio"]["music"]:
            self.music.play()

    def stop_music(self) -> None:
        if self.music:
            self.music.stop()

    def pause_music(self) -> None:
        if self.music:
            self.music.pause()

    def resume_music(self) -> None:
        if self.music and self.settings["audio"]["music"]:
            self.music.resume()

    def stop_all(self) -> None:
        for ch in self.effects.values():
            ch.stop()
        self.stop_music()
