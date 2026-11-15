"""Identificación de teclas (distingue teclado numérico de la fila superior)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

ACTIONS = ("n", "ne", "e", "se", "s", "sw", "w", "nw", "fire", "pause")
ACTION_LABELS = {
    "n": "Arriba", "ne": "Arriba-derecha", "e": "Derecha", "se": "Abajo-derecha",
    "s": "Abajo", "sw": "Abajo-izquierda", "w": "Izquierda", "nw": "Arriba-izquierda",
    "fire": "Disparar", "pause": "Pausa",
}

# Con BloqNum desactivado el teclado numérico envía teclas de navegación
_NAV_TO_DIGIT = {
    Qt.Key_Home: Qt.Key_7, Qt.Key_Up: Qt.Key_8, Qt.Key_PageUp: Qt.Key_9,
    Qt.Key_Left: Qt.Key_4, Qt.Key_Clear: Qt.Key_5, Qt.Key_Right: Qt.Key_6,
    Qt.Key_End: Qt.Key_1, Qt.Key_Down: Qt.Key_2, Qt.Key_PageDown: Qt.Key_3,
}
IGNORED_KEYS = (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta,
                Qt.Key_AltGr, Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_unknown)


def _kid(key, keypad=False):
    return f"{'kp' if keypad else 'k'}:{int(key)}"


def key_id(event):
    key = int(event.key())
    keypad = bool(event.modifiers() & Qt.KeyboardModifier.KeypadModifier)
    if keypad:
        key = int(_NAV_TO_DIGIT.get(key, key))
    return _kid(key, keypad)


def key_label(kid):
    kind, code = kid.split(":")
    name = QKeySequence(int(code)).toString() or code
    return ("Num " if kind == "kp" else "") + name


def default_keys():
    return {
        "n": [_kid(Qt.Key_8, True), _kid(Qt.Key_Up)],
        "ne": [_kid(Qt.Key_9, True)],
        "e": [_kid(Qt.Key_6, True), _kid(Qt.Key_Right)],
        "se": [_kid(Qt.Key_3, True)],
        "s": [_kid(Qt.Key_2, True), _kid(Qt.Key_Down)],
        "sw": [_kid(Qt.Key_1, True)],
        "w": [_kid(Qt.Key_4, True), _kid(Qt.Key_Left)],
        "nw": [_kid(Qt.Key_7, True)],
        "fire": [_kid(Qt.Key_Space)],
        "pause": [_kid(Qt.Key_Escape), _kid(Qt.Key_P)],
    }
