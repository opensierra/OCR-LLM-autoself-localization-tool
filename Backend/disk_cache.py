# disk_cache.py
# Caché persistente clave-valor sobre el sistema de archivos.
# Vive bajo %APPDATA%/VivoDPI/cache/<namespace>/<key>.json
# En no-Windows cae a ~/.cache/VivoDPI/<namespace>/<key>.json
#
# Diseño:
#   - JSON plano, una entrada por archivo (no SQLite). Atómico por archivo,
#     simple de inspeccionar y borrar manualmente.
#   - Sin TTL: la clave es un hash del contenido de la imagen, así que si la
#     imagen cambia, la clave cambia y la entrada vieja queda huérfana
#     (limpieza manual o por purge()).
#   - Errores de I/O se loguean y se ignoran: el caché es opcional, el
#     pipeline debe poder funcionar aunque el disco falle.

import json
import os
from pathlib import Path
from .logger import get_logger


log = get_logger("CACHE")


def _root_dir() -> Path:
    """Directorio raíz del caché en %APPDATA% (Windows) o ~/.cache (otros)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "VivoDPI" / "cache"
    return Path.home() / ".cache" / "VivoDPI"


def _path_for(namespace: str, key: str) -> Path:
    """Construye la ruta a un archivo de caché y asegura que la carpeta existe."""
    safe_ns = namespace.replace("/", "_").replace("\\", "_")
    safe_key = key.replace("/", "_").replace("\\", "_")
    folder = _root_dir() / safe_ns
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{safe_key}.json"


def load(namespace: str, key: str):
    """Devuelve el valor cacheado o None si no existe / falla la lectura."""
    p = _path_for(namespace, key)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warn("Falló lectura de %s/%s: %s", namespace, key, e)
        return None


def save(namespace: str, key: str, value) -> bool:
    """
    Serializa value a JSON y lo guarda. Retorna True si fue exitoso.
    Escribe a un archivo temporal y renombra: evita archivos corruptos
    si se interrumpe la escritura a la mitad.
    """
    p = _path_for(namespace, key)
    tmp = p.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
        tmp.replace(p)
        log.debug("Guardado %s/%s (%d bytes)", namespace, key, p.stat().st_size)
        return True
    except Exception as e:
        log.warn("Falló escritura de %s/%s: %s", namespace, key, e)
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False


def has(namespace: str, key: str) -> bool:
    return _path_for(namespace, key).exists()


def purge(namespace: str = None):
    """Borra entradas del caché. Sin argumentos: borra todo."""
    root = _root_dir()
    if not root.exists():
        return
    target = root / namespace if namespace else root
    if not target.exists():
        return
    count = 0
    for p in target.rglob("*.json"):
        try:
            p.unlink()
            count += 1
        except Exception:
            pass
    log.info("Purgadas %d entradas de %s", count, namespace or "caché completo")


def purge_keys(namespace: str, keys: list):
    """Borra entradas específicas (por hash). Devuelve cuántas eliminó."""
    count = 0
    for k in keys:
        p = _path_for(namespace, k)
        if p.exists():
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
    log.info("Purgadas %d entradas específicas de %s", count, namespace)
    return count


def stats() -> dict:
    """
    Devuelve resumen de uso del cache: entradas y bytes por namespace.
    Útil para mostrar en la UI cuánto espacio ocupa.
    """
    root = _root_dir()
    out = {"root": str(root), "namespaces": {}}
    if not root.exists():
        return out
    for ns_dir in root.iterdir():
        if not ns_dir.is_dir():
            continue
        files = list(ns_dir.glob("*.json"))
        total_bytes = sum(f.stat().st_size for f in files)
        out["namespaces"][ns_dir.name] = {
            "entries": len(files),
            "bytes": total_bytes,
            "human_size": _human_bytes(total_bytes),
        }
    return out


def list_keys(namespace: str) -> list:
    """Lista los hash-keys disponibles en un namespace."""
    folder = _root_dir() / namespace
    if not folder.exists():
        return []
    return [p.stem for p in folder.glob("*.json")]


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def root_path() -> str:
    """Devuelve la ruta absoluta del directorio raíz (útil para logs)."""
    return str(_root_dir())