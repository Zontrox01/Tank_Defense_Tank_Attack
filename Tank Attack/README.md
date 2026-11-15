# Tanque Parabólico

Juego de artillería en Python + PySide6. Un tanque dispara misiles en parábola
contra un objetivo situado en el otro extremo de un terreno aleatorio, con
viento y colinas por medio.

## Instalación y ejecución

    pip install -r requirements.txt
    python main.py

Necesita Python 3.10 o superior.

## Cómo se juega

| Control | Acción |
|---|---|
| Cursor arriba / abajo | Sube / baja el cañón (0º a 90º, velocidad uniforme) |
| Rueda del ratón | Sube / baja el cañón (ajustable en Opciones: º por muesca) |
| Espacio **o** botón izquierdo del ratón (mantener) | Carga la potencia (barra vertical arriba a la derecha) |
| Soltar Espacio / botón izquierdo | Dispara |
| `A` / `P` + números | Activan el campo **Ángulo** / **Potencia** (el valor parpadea) para escribir un valor exacto |
| `Enter` | Dispara con los valores que haya en los campos |
| Esc | Pausa (M: menú, Q: salir). En el menú no hay barra de título: se puede arrastrar la ventana desde el fondo |

### Valores numéricos exactos

1. Pulsa `A`: el valor del campo **Ángulo** parpadea. Escribe el ángulo (0 a 90;
   admite decimales con `.` o `,`).
2. Pulsa `P`: el valor del campo **Potencia** parpadea. Escribe de 1 a 100.
3. Pulsa `Enter`: se lanza el misil con los valores de los campos.

Los números sustituyen al valor actual y el cañón y la barra se mueven en vivo
mientras escribes. Puedes cambiar solo un campo (los dos son independientes),
`Retroceso` borra, y `Esc` cancela y recupera los valores anteriores. Mover el
cañón con cursores o rueda, o cargar potencia con Espacio o ratón, también
cierra el campo activo. Sin potencia (0 %) `Enter` no dispara. Las teclas `A` y
`P` se pueden cambiar en `config.json` (`edit_angle`, `edit_power`).

* El tanque aparece en un lado aleatorio en cada objetivo y el objetivo en el opuesto.
* El relieve, el viento (flecha + valor) y las posiciones cambian con cada objetivo.
* Las nubes se mueven con la dirección y la velocidad del viento: con el viento
  máximo van a `CLOUD_MAX_SPEED` (80 px/s, constante en `game/game_widget.py`),
  proporcionalmente más despacio con menos viento, y quedan paradas con viento 0.
* El misil explota al tocar el suelo y deja un cráter.
* **Puntos por objetivo:** 10 si lo destruyes; de 0 a 9 según lo cerca que caiga
  dentro del *radio de acción*. Si hay varios disparos, cuenta el mejor.
* Dispones de *N* disparos por objetivo. Si los gastas sin destruirlo, es un
  **fallo**; al llegar al máximo de fallos, Game Over.
* **Nivel:** sube cada *N* objetivos destruidos. Con cada nivel aumentan la
  distancia, el viento máximo y la altura de las colinas; el objetivo se hace
  más pequeño y, desde el nivel 6, se mueve.

### Dificultad (ayuda de trayectoria)

* **Fácil:** mientras cargas la potencia se dibuja la trayectoria de ascenso, y
  queda dibujada la trayectoria del disparo anterior. Además, la etiqueta del
  campo muestra la potencia del último disparo: `POTENCIA (58%)`.
* **Media:** solo queda dibujada la trayectoria del disparo anterior.
* **Difícil:** no se dibuja ninguna trayectoria.

El récord se guarda por separado para cada dificultad.

## Configuración

Desde **Opciones** o editando `config.json` (se crea en el primer arranque).
Los valores no válidos se sustituyen por los de por defecto.

| Sección | Clave | Significado |
|---|---|---|
| display | fullscreen, window_width, window_height | Pantalla completa / tamaño de ventana |
| gameplay | difficulty | `easy`, `medium` o `hard` |
| gameplay | targets_per_level | Objetivos para subir de nivel |
| gameplay | shots_per_target | Disparos por objetivo |
| gameplay | max_failures | Fallos para perder |
| gameplay | wind_enabled, max_wind | Viento y su máximo |
| gameplay | gravity | Gravedad (px/s²) |
| gameplay | charge_time | Segundos que tarda la barra en llenarse |
| gameplay | angle_speed | Grados por segundo del cañón |
| gameplay | wheel_step | Grados por muesca de la rueda del ratón |
| gameplay | action_radius | Radio (px) para puntuar de 1 a 9 |
| gameplay | moving_targets | Objetivos móviles a partir del nivel 6 |
| audio | sound, music, volume | Efectos, música y volumen (0 a 1) |
| keys | angle_up, angle_down, fire, pause, edit_angle, edit_power | Nombres de tecla de Qt: `Up`, `Down`, `Space`, `Escape`, `W`, `S`... |

## Archivos

    main.py                 Punto de entrada
    requirements.txt
    config.json             Se genera solo
    record.json             Se genera solo
    game/
      settings.py           Configuración JSON y récord
      levels.py             Qué cambia en cada nivel
      terrain.py            Relieve aleatorio y cráteres
      physics.py            Misil, viento y gravedad
      assets.py             Carga de sprites PNG
      audio.py              Sonido y música (mp3)
      game_widget.py        Lógica, entrada y dibujo del juego
      menus.py              Menú principal y opciones
      main_window.py        Ventana sin barra de título y estilos
    assets/
      images/               tank_body.png, tank_barrel.png, target.png
      sound/                shot.mp3, flight.mp3, burst.mp3, gameover.mp3, song.mp3

## Sprites PNG

Sustituye los PNG de `assets/images/` conservando el nombre:

* `tank_body.png`: cuerpo del tanque mirando a la **derecha**, con la base en el borde inferior.
* `tank_barrel.png`: cañón apuntando a la **derecha**; el pivote es el centro de su borde izquierdo.
* `target.png`: objetivo (se dibuja centrado, como un círculo).

Para jugar a la izquierda el juego refleja los sprites automáticamente.
Si falta un PNG, se dibuja uno sencillo en su lugar.

## Sonido

Pon los archivos en `assets/sound/`:

| Sonido | Archivo |
|---|---|
| Disparo | `shot.wav` o `shot.mp3` |
| Vuelo del misil (se corta al impactar) | `flight.wav` o `flight.mp3` |
| Explosión | `burst.wav` o `burst.mp3` |
| Game over | `gameover.wav` o `gameover.mp3` |
| Música en bucle | `song.mp3` |

**Latencia:** el reproductor de mp3 de Qt (`QMediaPlayer`) tarda en arrancar,
a veces cerca de un segundo, y no se puede evitar. Los `.wav` se reproducen con
`QSoundEffect`, que los carga en memoria y los lanza al instante. Por eso, la
**primera vez** que arrancas el juego cada mp3 de efectos se convierte solo a
WAV y se guarda en `assets/sound/.cache/`. Desde ese momento se reproduce sin
retraso (la conversión tarda menos de un segundo; durante ese rato se usa el
reproductor de mp3). Si cambias un mp3, se vuelve a convertir.

Si prefieres hacerlo a mano, pon `shot.wav` (etc.) junto al mp3: el WAV propio
tiene prioridad. Puedes crearlo con Audacity o `ffmpeg -i shot.mp3 shot.wav`.

Si la conversión automática falla, la consola muestra un mensaje `[audio] No se
pudo convertir ...` y el efecto sigue sonando con el reproductor de mp3 (con
retraso): en ese caso usa un WAV propio. La música (`song.mp3`) no se convierte:
suena en bucle y no importa que tarde en arrancar.

Si falta un archivo, ese sonido no suena y se avisa por consola. Si no oyes
nada, revisa los mensajes `[audio]` de la consola.
