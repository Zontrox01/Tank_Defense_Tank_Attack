# Tank Defense

Un tanque en el centro que solo rota y dispara; los enemigos llegan desde los bordes
(y las esquinas en la modalidad de 8 direcciones) hacia el centro. Si uno lo toca, pierdes una vida.

## Ejecutar
```
pip install -r requirements.txt
python main.py
```

## Controles
| Acción | Teclas por defecto |
|---|---|
| Apuntar (4 dir.) | Teclado numérico 8 / 6 / 2 / 4, o cursores |
| Apuntar diagonales (modalidad 8 dir.) | Teclado numérico 9 / 3 / 1 / 7 |
| Disparar (mantener = disparo continuo) | Espacio |
| Pausa | Esc o P |
| Game over | Intro / R: reintentar · Esc / M: menú |

Todas las teclas se pueden cambiar en *Configuración*. El teclado numérico funciona con
BloqNum activado o desactivado.

## Niveles
Cada *N* tanques eliminados (configurable) subes de nivel: la velocidad de los enemigos
aumenta el % configurado y, cada cierto número de niveles, aparece un tanque más a la vez
(hasta el máximo). Modos de aparición: aleatoria, oleadas o progresiva (aleatoria en los
niveles 1-2 y oleadas desde el 3). Puntos por tanque: 10 × nivel.

## Archivos
| Archivo | Contenido |
|---|---|
| `main.py` | Punto de entrada |
| `engine.py` | Lógica del juego (sin Qt) |
| `widgets.py` | Juego, menú, configuración y ventana sin barra de título |
| `inputs.py` | Identificación y nombres de teclas |
| `config.py` | `settings.json` (configuración) y `record.json` (récord) |
| `assets.py` | Carga/generación de sprites, efectos y música |

## Personalizar gráficos
Los sprites están en `assets/sprites/` (se generan solos la primera vez; cámbialos por los tuyos):
- `tank_<dir>.png` — tu tanque mirando en cada dirección.
- `enemy_<dir>.png` — enemigos; `<dir>` es hacia dónde miran/avanzan (un enemigo que
  viene de arriba usa `enemy_s`).
- `bullet.png` — proyectil.

`<dir>` ∈ `n, ne, e, se, s, sw, w, nw`. Se recomienda 128×128 con fondo transparente, tanque
mirando a su dirección y centrado. Para regenerar los originales, borra los PNG.

## Sonido y música
Coloca estos archivos mp3 en `assets/sound/` (la carpeta ya existe):

| Archivo | Cuándo suena |
|---|---|
| `shot.mp3` | cada vez que se lanza un proyectil |
| `burst.mp3` | cada vez que se destruye un tanque |
| `gameover.mp3` | al perder la última vida (la música se pausa y vuelve al reintentar o ir al menú) |
| `song.mp3` | música de fondo, en bucle (se pausa con la pausa del juego) |

En *Configuración* hay dos opciones independientes: **Efectos de sonido** y **Música de fondo**.
Si falta algún archivo, el juego funciona igualmente y avisa por la consola. Si un mp3 no suena,
la consola muestra el motivo (normalmente un códec no soportado por el sistema).

## Notas
- Los proyectiles diagonales siguen la línea centro→esquina real de la ventana, por lo que
  aciertan a los enemigos que vienen de esa esquina aunque la ventana no sea cuadrada.
- La ventana no tiene barra de título: se arrastra desde el fondo del menú; sal con *Salir*.
