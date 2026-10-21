"""Configuración del usuario (settings.json) y récord (record.json)."""
import json
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path

from inputs import default_keys, ACTIONS

BASE = Path(__file__).resolve().parent
SETTINGS_FILE = BASE / "settings.json"
RECORD_FILE = BASE / "record.json"


@dataclass
class Settings:
    fullscreen: bool = False
    window_w: int = 1000
    window_h: int = 720
    mode: int = 1                    # 1 = 4 direcciones, 2 = 8 direcciones
    lives: int = 3                   # 1..3
    kills_per_level: int = 10        # tanques eliminados para subir de nivel
    start_enemies: int = 2           # tanques a la vez al empezar
    enemies_every: int = 2           # +1 tanque a la vez cada N niveles (0 = nunca)
    max_enemies: int = 8             # tope de tanques a la vez
    start_speed: int = 3             # 1..10
    speed_pct: int = 10              # % de incremento de velocidad por nivel
    spawn_mode: str = "progressive"  # random | waves | progressive
    max_bullets: int = 0             # 0 = sin límite de proyectiles en pantalla
    fire_cooldown_ms: int = 250      # 0 = sin tiempo entre disparos
    sound: bool = True               # efectos (disparo, explosión)
    music: bool = True               # música de fondo
    keys: dict = field(default_factory=default_keys)

    @classmethod
    def load(cls):
        s = cls()
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return s
        for f in fields(cls):
            if f.name == "keys" or f.name not in data:
                continue
            if isinstance(data[f.name], type(getattr(s, f.name))):
                setattr(s, f.name, data[f.name])
        keys = data.get("keys")
        if isinstance(keys, dict):
            for a in ACTIONS:
                v = keys.get(a)
                if isinstance(v, list) and v and all(isinstance(k, str) and ":" in k for k in v):
                    s.keys[a] = v
        s.lives = max(1, min(3, s.lives))
        return s

    def save(self):
        try:
            SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass


class Record:
    def __init__(self):
        self.value = 0
        try:
            self.value = int(json.loads(RECORD_FILE.read_text(encoding="utf-8")).get("record", 0))
        except (OSError, ValueError, TypeError):
            pass

    def update(self, score):
        """Guarda el récord si se supera. Devuelve True si hay nuevo récord."""
        if score > self.value:
            self.value = score
            try:
                RECORD_FILE.write_text(json.dumps({"record": score}), encoding="utf-8")
            except OSError:
                pass
            return True
        return False
