"""Lógica del juego (sin dependencias de Qt)."""
import math
import random

# Direcciones: índice 0..7 en sentido horario empezando por arriba
DIRS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
CARDINAL = (0, 2, 4, 6)
_SIGN = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))


class Enemy:
    __slots__ = ("x", "y", "vx", "vy", "facing")

    def __init__(self, x, y, vx, vy, facing):
        self.x, self.y, self.vx, self.vy, self.facing = x, y, vx, vy, facing


class Bullet:
    __slots__ = ("x", "y", "vx", "vy")

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy


class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.w = self.h = 1
        self.reset()

    # ---------- geometría ----------
    def set_size(self, w, h):
        self.w, self.h = max(1, w), max(1, h)

    @property
    def unit(self):
        return min(self.w, self.h)

    @property
    def cx(self):
        return self.w / 2

    @property
    def cy(self):
        return self.h / 2

    @property
    def r_tank(self):
        return self.unit * 0.04

    @property
    def r_enemy(self):
        return self.unit * 0.04

    @property
    def r_bullet(self):
        return self.unit * 0.012

    def vec(self, d):
        """Vector unitario de la dirección d. Las diagonales apuntan a la esquina
        real de la ventana, así proyectiles y enemigos siempre se encuentran."""
        sx, sy = _SIGN[d]
        if sx and sy:
            n = math.hypot(self.w, self.h)
            return sx * self.w / n, sy * self.h / n
        return float(sx), float(sy)

    def reach(self, d):
        """Distancia del centro a justo fuera de la pantalla en la dirección d."""
        sx, sy = _SIGN[d]
        if sx and sy:
            base = math.hypot(self.w, self.h) / 2
        else:
            base = self.w / 2 if sx else self.h / 2
        return base + self.unit * 0.08

    # ---------- niveles ----------
    @property
    def level(self):
        return self.kills // max(1, self.cfg.kills_per_level) + 1

    @property
    def speed(self):
        c = self.cfg
        s = c.start_speed * 0.04 * (1 + c.speed_pct / 100) ** (self.level - 1)
        return min(s, 0.6) * self.unit  # tope: siempre más lento que el proyectil

    @property
    def max_enemies(self):
        c = self.cfg
        extra = (self.level - 1) // c.enemies_every if c.enemies_every else 0
        return max(1, min(c.max_enemies, c.start_enemies + extra))

    @property
    def dirs(self):
        return CARDINAL if self.cfg.mode == 1 else tuple(range(8))

    @property
    def wave_mode(self):
        m = self.cfg.spawn_mode
        return m == "waves" or (m == "progressive" and self.level >= 3)

    # ---------- partida ----------
    def reset(self):
        self.score = 0
        self.kills = 0
        self.lives = self.cfg.lives
        self.aim = 0
        self.enemies = []
        self.bullets = []
        self.cooldown = 0.0
        self.invuln = 0.0
        self.spawn_timer = 1.0
        self.wave_timer = 1.0
        self.state = "playing"  # "playing" | "gameover"

    def set_aim(self, d):
        if d in self.dirs:
            self.aim = d

    def fire(self):
        c = self.cfg
        if self.state != "playing" or self.cooldown > 0:
            return False
        if c.max_bullets and len(self.bullets) >= c.max_bullets:
            return False
        vx, vy = self.vec(self.aim)
        sp = self.unit * 0.9
        off = self.r_tank * 1.1
        self.bullets.append(Bullet(self.cx + vx * off, self.cy + vy * off, vx * sp, vy * sp))
        self.cooldown = c.fire_cooldown_ms / 1000
        return True

    def _spawn(self, d, extra=0.0):
        vx, vy = self.vec(d)
        dist = self.reach(d) + extra
        sp = self.speed
        self.enemies.append(Enemy(self.cx + vx * dist, self.cy + vy * dist,
                                  -vx * sp, -vy * sp, (d + 4) % 8))

    def _spawn_free(self):
        ds = list(self.dirs)
        random.shuffle(ds)
        for d in ds:
            vx, vy = self.vec(d)
            sx, sy = self.cx + vx * self.reach(d), self.cy + vy * self.reach(d)
            if all(math.hypot(e.x - sx, e.y - sy) > self.unit * 0.25 for e in self.enemies):
                self._spawn(d)
                return

    def _spawn_wave(self):
        ds = list(self.dirs)
        random.shuffle(ds)
        for i in range(self.max_enemies):
            self._spawn(ds[i % len(ds)], extra=(i // len(ds)) * self.unit * 0.3)

    def update(self, dt):
        """Avanza dt segundos. Devuelve lista de eventos: kill, levelup, hit, gameover."""
        ev = []
        if self.state != "playing":
            return ev
        self.cooldown = max(0.0, self.cooldown - dt)
        self.invuln = max(0.0, self.invuln - dt)

        m = self.unit * 0.1
        for b in self.bullets:
            b.x += b.vx * dt
            b.y += b.vy * dt
        self.bullets = [b for b in self.bullets
                        if -m <= b.x <= self.w + m and -m <= b.y <= self.h + m]
        for e in self.enemies:
            e.x += e.vx * dt
            e.y += e.vy * dt

        # proyectil vs enemigo
        reach = self.r_bullet + self.r_enemy
        for b in self.bullets[:]:
            for e in self.enemies:
                if math.hypot(b.x - e.x, b.y - e.y) <= reach:
                    self.bullets.remove(b)
                    self.enemies.remove(e)
                    old = self.level
                    self.kills += 1
                    self.score += 10 * old
                    ev.append("kill")
                    if self.level > old:
                        ev.append("levelup")
                    break

        # enemigo vs tanque central
        reach = self.r_tank + self.r_enemy
        for e in self.enemies[:]:
            if math.hypot(e.x - self.cx, e.y - self.cy) <= reach:
                self.enemies.remove(e)
                if self.invuln <= 0:
                    self.lives -= 1
                    self.invuln = 1.5
                    ev.append("hit")
                    if self.lives <= 0:
                        self.state = "gameover"
                        ev.append("gameover")
                        return ev

        # aparición de enemigos
        if self.wave_mode:
            if self.enemies:
                self.wave_timer = 1.0
            else:
                self.wave_timer -= dt
                if self.wave_timer <= 0:
                    self._spawn_wave()
                    self.wave_timer = 1.0
        else:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0 and len(self.enemies) < self.max_enemies:
                self._spawn_free()
                self.spawn_timer = random.uniform(0.5, 1.2) * max(0.35, 1.4 - 0.08 * self.level)
        return ev
