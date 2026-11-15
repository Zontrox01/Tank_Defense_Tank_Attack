"""Configuración persistente (config.json) y récord (record.json).

Este módulo no depende de Qt. Cualquier clave que falte o tenga un tipo
incorrecto en config.json se sustituye por su valor por defecto, y los
números se limitan a rangos razonables.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
RECORD_PATH = BASE_DIR / "record.json"
IMAGES_DIR = BASE_DIR / "assets" / "images"
SOUND_DIR = BASE_DIR / "assets" / "sound"

DIFFICULTIES = ("easy", "medium", "hard")
DIFFICULTY_NAMES = {"easy": "Fácil", "medium": "Media", "hard": "Difícil"}

DEFAULTS: dict = {
    "display": {
        "fullscreen": False,
        "window_width": 1280,
        "window_height": 720,
    },
    "gameplay": {
        # Ayuda de trayectoria: "easy", "medium" o "hard"
        "difficulty": "medium",
        "targets_per_level": 3,      # objetivos que hay que cumplir para subir de nivel
        "shots_per_target": 3,       # disparos disponibles por objetivo
        "max_failures": 3,           # objetivos fallados para perder la partida
        "wind_enabled": True,
        "max_wind": 10.0,            # viento máximo (se alcanza en niveles altos)
        "gravity": 500.0,            # px/s²
        "charge_time": 1.5,          # segundos que tarda la barra en llenarse
        "angle_speed": 35.0,         # grados por segundo al mantener cursor
        "wheel_step": 2.0,           # grados por "muesca" de la rueda del ratón
        "action_radius": 260,        # px: radio de acción para puntuar 1-9
        "moving_targets": True,      # objetivos móviles a partir del nivel 6
    },
    "audio": {
        "sound": True,
        "music": True,
        "volume": 0.8,               # 0.0 - 1.0
    },
    # Nombres de tecla de Qt: "Up", "Down", "Space", "Escape", "A", "W"...
    "keys": {
        "angle_up": "Up",
        "angle_down": "Down",
        "fire": "Space",
        "pause": "Escape",
        "edit_angle": "A",        # activa el campo de ángulo (se escribe el valor)
        "edit_power": "P",        # activa el campo de potencia (se escribe el valor)
    },
}

LIMITS = {
    ("display", "window_width"): (640, 7680),
    ("display", "window_height"): (360, 4320),
    ("gameplay", "targets_per_level"): (1, 50),
    ("gameplay", "shots_per_target"): (1, 20),
    ("gameplay", "max_failures"): (1, 20),
    ("gameplay", "max_wind"): (0.0, 30.0),
    ("gameplay", "gravity"): (100.0, 2000.0),
    ("gameplay", "charge_time"): (0.3, 10.0),
    ("gameplay", "angle_speed"): (5.0, 200.0),
    ("gameplay", "wheel_step"): (0.5, 15.0),
    ("gameplay", "action_radius"): (50, 1000),
    ("audio", "volume"): (0.0, 1.0),
}


def _coerce(value, default):
    """Devuelve value si tiene el mismo tipo que default; si no, default."""
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return int(round(value))
    if isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)
    if isinstance(default, str):
        return value if isinstance(value, str) and value else default
    return default


def _merge(defaults: dict, loaded: dict) -> dict:
    result: dict = {}
    for key, default in defaults.items():
        if isinstance(default, dict):
            sub = loaded.get(key)
            result[key] = _merge(default, sub if isinstance(sub, dict) else {})
        else:
            result[key] = _coerce(loaded.get(key, default), default)
    return result


def _clamp(cfg: dict) -> dict:
    for (section, key), (lo, hi) in LIMITS.items():
        cfg[section][key] = max(lo, min(hi, cfg[section][key]))
    if cfg["gameplay"]["difficulty"] not in DIFFICULTIES:
        cfg["gameplay"]["difficulty"] = DEFAULTS["gameplay"]["difficulty"]
    return cfg


def load_config() -> dict:
    loaded: dict = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                loaded = data
        except (OSError, ValueError) as exc:
            print(f"[config] No se pudo leer {CONFIG_PATH.name}: {exc}. Se usan valores por defecto.")
    cfg = _clamp(_merge(deepcopy(DEFAULTS), loaded))
    if not CONFIG_PATH.exists():
        save_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        print(f"[config] No se pudo guardar {CONFIG_PATH.name}: {exc}")


# --------------------------------------------------------------------------
# Récord (uno por dificultad)
# --------------------------------------------------------------------------
def _load_records() -> dict:
    records = {d: 0 for d in DIFFICULTIES}
    if RECORD_PATH.exists():
        try:
            data = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for d in DIFFICULTIES:
                    value = data.get(d, 0)
                    if isinstance(value, int) and not isinstance(value, bool):
                        records[d] = max(0, value)
        except (OSError, ValueError):
            pass
    return records


def get_record(difficulty: str) -> int:
    return _load_records().get(difficulty, 0)


def set_record(difficulty: str, score: int) -> None:
    records = _load_records()
    records[difficulty] = int(score)
    try:
        RECORD_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"[record] No se pudo guardar {RECORD_PATH.name}: {exc}")
