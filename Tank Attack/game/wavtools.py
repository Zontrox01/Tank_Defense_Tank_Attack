"""Escritura de WAV a partir de PCM crudo. Sin dependencias de Qt."""
from __future__ import annotations

import sys
import wave
from array import array

# Formatos de muestra admitidos: u8, s16, s32, f32


def _int_typecode() -> str:
    """Código de array con 4 bytes por elemento."""
    for code in ("i", "l"):
        if array(code).itemsize == 4:
            return code
    raise RuntimeError("No hay tipo entero de 4 bytes")


def to_pcm16(data: bytes, fmt: str) -> tuple[bytes, int]:
    """Convierte a PCM de 16 bits (o 8 bits sin signo si ya lo era).

    Devuelve (datos, bytes por muestra).
    """
    if fmt == "s16":
        return data, 2
    if fmt == "u8":
        return data, 1
    if fmt == "s32":
        src = array(_int_typecode())
        src.frombytes(data[: len(data) // 4 * 4])
        out = array("h", (v >> 16 for v in src))
    elif fmt == "f32":
        src = array("f")
        src.frombytes(data[: len(data) // 4 * 4])
        out = array("h", (max(-32768, min(32767, int(v * 32767))) for v in src))
    else:
        raise ValueError(f"Formato de muestra no soportado: {fmt}")
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes(), 2


def pcm_to_wav(path, data: bytes, channels: int, rate: int, fmt: str) -> None:
    pcm, width = to_pcm16(data, fmt)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)
