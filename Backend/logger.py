# logger.py
# Sistema de logging unificado para todo el backend.
#
# Uso típico:
#   from .logger import get_logger
#   log = get_logger("OCR")
#   log.info("Procesando imagen %s", path)
#   log.warn("Confianza baja en región %d", region_id)
#   log.error("Fallo al cargar modelo: %s", err)
#
# Para el streaming del LLM (token a token, sin newline):
#   from .logger import stream_token, stream_end
#   stream_token(t)   # imprime t sin salto de línea, flush inmediato
#   stream_end()      # cierra con un salto y un mensaje [LLM] hecho
#
# Niveles disponibles (en orden ascendente de severidad):
#   STREAM(5) < DEBUG(10) < INFO(20) < WARN(30) < ERROR(40)
#
# Control por entorno:
#   DPI_LOG_LEVEL=DEBUG|INFO|WARN|ERROR   (default INFO)
#   DPI_LOG_STREAM=1|0                    (1 default, 0 silencia tokens del LLM)
#
# En batch nocturno: export DPI_LOG_STREAM=0 y DPI_LOG_LEVEL=WARN

import logging
import os
import sys
from datetime import datetime


# Nivel custom para el streaming del LLM (por debajo de DEBUG)
STREAM_LEVEL = 5
logging.addLevelName(STREAM_LEVEL, "STREAM")


def _resolve_level(name: str) -> int:
    mapping = {
        "STREAM": STREAM_LEVEL, "DEBUG": logging.DEBUG, "INFO": logging.INFO,
        "WARN": logging.WARNING, "WARNING": logging.WARNING,
        "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL,
    }
    return mapping.get((name or "").upper(), logging.INFO)


class _CompactFormatter(logging.Formatter):
    """Formato: [HH:MM:SS] [MÓDULO] mensaje"""
    def format(self, record):
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        return f"[{ts}] [{record.name}] {record.getMessage()}"


_root_configured = False
_stream_enabled = os.environ.get("DPI_LOG_STREAM", "1") == "1"


def _configure_root_once():
    global _root_configured
    if _root_configured:
        return
    root = logging.getLogger("DPI")
    root.setLevel(_resolve_level(os.environ.get("DPI_LOG_LEVEL", "INFO")))
    # Quitar handlers previos por si el módulo se re-importa (debug Flask)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_CompactFormatter())
    root.addHandler(handler)
    root.propagate = False
    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Devuelve un logger nombrado tipo DPI.<NAME>. El nombre se muestra entre
    corchetes en la salida. Convención: nombres cortos en mayúsculas.
    Ejemplos: OCR, LLM, CACHE, BATCH, HTTP, MAIN, WARMUP.
    """
    _configure_root_once()
    return logging.getLogger(f"DPI.{name.upper()}")


# ── Streaming del LLM ────────────────────────────────────────
# El streaming token-a-token no encaja en el modelo de logging estándar
# (no queremos newline ni prefijo por token). Lo manejamos aparte.

def stream_token(token: str):
    """Imprime un token del LLM sin newline, con flush inmediato."""
    if _stream_enabled:
        sys.stdout.write(token)
        sys.stdout.flush()


def stream_end():
    """Cierra el bloque de streaming con un salto de línea."""
    if _stream_enabled:
        sys.stdout.write("\n")
        sys.stdout.flush()


def stream_enabled() -> bool:
    return _stream_enabled