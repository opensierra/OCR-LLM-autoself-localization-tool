import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from tkinter import Tk, filedialog
from pathlib import Path
from .env import IMG_EXTS
from .screenshot_ocr import process_image, RawTextResult
from .localQ import analyze_text
from .logger import get_logger
from . import disk_cache

# Para volver a Gemini (en caso de prueba o comparación):
# from .gemini_qa import analyze_text


log = get_logger("DPI")


# Namespaces del caché en disco
_NS_OCR = "ocr"
_NS_QA = "qa"

# Cuántas imágenes pre-procesar adelante del índice actual.
PREFETCH_LOOKAHEAD = 3


def getTree(folder: str) -> list[str]:
    return [str(p) for p in Path(folder).resolve().rglob('*')
            if p.is_file() and p.suffix.lower() in IMG_EXTS]


def selectFolder() -> str:
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(title="Seleccione un directorio de imagenes")
    root.destroy()
    return folder or None


def hash_image(image_path: str) -> str:
    """
    Hash rápido del contenido de una imagen, usado como clave de caché.

    Lee los primeros 64 KB + el tamaño del archivo y los pasa por MD5.
    Esto es lo bastante único para distinguir imágenes y es virtualmente
    instantáneo (no leemos el archivo completo). Si dos imágenes coinciden
    en los primeros 64 KB y el tamaño, las tratamos como iguales — para
    screenshots de Android es virtualmente imposible que choquen.

    El hash incluye el tamaño total para que dos imágenes con el mismo
    prefijo pero distinto tamaño no se mezclen.
    """
    p = Path(image_path)
    size = p.stat().st_size
    h = hashlib.md5()
    h.update(str(size).encode())
    with open(p, 'rb') as f:
        h.update(f.read(64 * 1024))
    return h.hexdigest()


class DPI:
    def __init__(self, folder: str = None):
        self.folder = folder or selectFolder()
        self.tree = getTree(self.folder)
        # Caches indexados por HASH de contenido, no por path.
        # Así sobreviven a movimientos/renombrados de carpetas y
        # se preparan para persistencia en disco (paso C).
        self._ocr_cache = {}   # hash -> resultado de process_image
        self._qa_cache = {}    # hash -> resultado de analyze_text
        # Mapping auxiliar path->hash para evitar re-hashear el mismo path.
        self._hash_index = {}

        # Prefetch en background. 1 sólo worker para no pelear con el
        # ThreadPoolExecutor interno del propio process_image (que ya usa
        # hasta 8 hilos para Tesseract). Más workers aquí sólo congestionarían
        # la CPU sin acelerar nada.
        self._prefetch_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="dpi-prefetch"
        )
        # Lock por hash: evita procesar la misma imagen dos veces si el
        # prefetch y el usuario la piden a la vez.
        self._inflight = {}     # hash -> threading.Lock
        self._inflight_guard = threading.Lock()

        log.info("Workspace cargado: %s (%d imágenes)", self.folder, len(self.tree))
        log.info("Caché en disco: %s", disk_cache.root_path())

    def _hash_for(self, image_path: str) -> str:
        """Devuelve el hash del archivo, cacheando el cálculo por path."""
        if image_path not in self._hash_index:
            self._hash_index[image_path] = hash_image(image_path)
        return self._hash_index[image_path]

    def _lock_for(self, key: str) -> threading.Lock:
        """Lock único por hash para evitar procesamientos duplicados."""
        with self._inflight_guard:
            lock = self._inflight.get(key)
            if lock is None:
                lock = threading.Lock()
                self._inflight[key] = lock
            return lock

    def prefetch(self, start_index: int, count: int = PREFETCH_LOOKAHEAD):
        """
        Lanza en background el OCR de las próximas `count` imágenes
        a partir de `start_index` (sin incluirlo). Si ya están cacheadas,
        cada job es no-op gracias al check de _ocr_cache dentro de analyze().
        """
        for offset in range(1, count + 1):
            idx = start_index + offset
            if idx >= len(self.tree):
                break
            path = self.tree[idx]
            self._prefetch_pool.submit(self._prefetch_one, path, idx)

    def _prefetch_one(self, image_path: str, idx: int):
        """Worker del prefetch. Errores se loguean pero no se propagan."""
        try:
            key = self._hash_for(image_path)
            if key in self._ocr_cache:
                return
            log.debug("Prefetch idx=%d: %s", idx, Path(image_path).name)
            self.analyze(image_path)
        except Exception as e:
            log.warn("Prefetch falló para idx=%d: %s", idx, e)

    def analyze(self, image_path: str) -> dict:
        """OCR (cacheado por hash de contenido, memoria + disco)."""
        key = self._hash_for(image_path)

        # 1. Check rápido en memoria sin lock
        if key in self._ocr_cache:
            log.debug("OCR hit (memoria): %s", Path(image_path).name)
            return self._ocr_cache[key]

        # Lock por hash: si prefetch y usuario piden la misma imagen a la vez,
        # solo uno procesa, el otro espera y reusa el resultado.
        with self._lock_for(key):
            # Re-check tras tomar el lock (otra llamada pudo haber terminado).
            if key in self._ocr_cache:
                return self._ocr_cache[key]

            # 2. Disco
            cached = disk_cache.load(_NS_OCR, key)
            if cached is not None:
                log.info("OCR hit (disco): %s", Path(image_path).name)
                if isinstance(cached.get("raw_text"), dict):
                    cached["raw_text"] = RawTextResult(cached["raw_text"])
                self._ocr_cache[key] = cached
                return cached

            # 3. Miss: procesar y persistir
            log.info("OCR miss, procesando: %s", Path(image_path).name)
            result = process_image(image_path)
            self._ocr_cache[key] = result
            to_save = dict(result)
            if isinstance(result.get("raw_text"), dict):
                to_save["raw_text"] = dict(result["raw_text"])
            disk_cache.save(_NS_OCR, key, to_save)
            return result

    def review(self, image_path: str) -> dict:
        """OCR + análisis LLM (ambos cacheados por hash, memoria + disco)."""
        key = self._hash_for(image_path)

        if key in self._qa_cache:
            log.debug("QA hit (memoria): %s", Path(image_path).name)
            return self._qa_cache[key]

        cached = disk_cache.load(_NS_QA, key)
        if cached is not None:
            log.info("QA hit (disco): %s", Path(image_path).name)
            self._qa_cache[key] = cached
            return cached

        log.info("QA miss, analizando: %s", Path(image_path).name)
        ocr = self.analyze(image_path)
        result = analyze_text(
            text=ocr['text'],
            raw_text=ocr.get('raw_text'),
        )
        self._qa_cache[key] = result
        disk_cache.save(_NS_QA, key, result)
        return result

    def analyze_imgIndex(self, index: int) -> dict:
        if index < 0 or index >= len(self.tree):
            raise IndexError("Index out of range")
        result = self.analyze(self.tree[index])
        # Adelantarse: pre-procesa las siguientes en background mientras
        # el usuario revisa esta imagen y el LLM trabaja sobre ella.
        self.prefetch(index, PREFETCH_LOOKAHEAD)
        return result

    def review_imgIndex(self, index: int) -> dict:
        if index < 0 or index >= len(self.tree):
            raise IndexError("Index out of range")
        result = self.review(self.tree[index])
        # Mismo principio: durante el batch, mientras el LLM trabaja en N
        # los OCRs de N+1, N+2, ... se van procesando en paralelo.
        self.prefetch(index, PREFETCH_LOOKAHEAD)
        return result

    def clear_cache(self):
        self._ocr_cache.clear()
        self._qa_cache.clear()
        self._hash_index.clear()
        log.info("Cachés en memoria limpiados")

    def invalidate_workspace_disk(self) -> dict:
        """
        Borra del caché en disco las entradas que corresponden a las imágenes
        del workspace actual. Devuelve {'ocr': N, 'qa': M} con cuántas borró.
        Las imágenes de OTROS workspaces no se tocan.
        """
        keys = []
        for p in self.tree:
            try:
                keys.append(self._hash_for(p))
            except Exception:
                pass
        n_ocr = disk_cache.purge_keys(_NS_OCR, keys)
        n_qa = disk_cache.purge_keys(_NS_QA, keys)
        self.clear_cache()
        log.info("Workspace invalidado: %d ocr, %d qa", n_ocr, n_qa)
        return {"ocr": n_ocr, "qa": n_qa}

    def invalidate_image(self, image_path: str) -> dict:
        """Invalida una sola imagen (memoria + disco)."""
        try:
            key = self._hash_for(image_path)
        except Exception as e:
            log.warn("No se pudo hashear %s: %s", image_path, e)
            return {"ocr": 0, "qa": 0}
        n_ocr = disk_cache.purge_keys(_NS_OCR, [key])
        n_qa = disk_cache.purge_keys(_NS_QA, [key])
        self._ocr_cache.pop(key, None)
        self._qa_cache.pop(key, None)
        log.info("Imagen invalidada %s: %d ocr, %d qa",
                 Path(image_path).name, n_ocr, n_qa)
        return {"ocr": n_ocr, "qa": n_qa}

    def shutdown(self):
        """Apaga el pool de prefetch. Llamar al cerrar la app o al cambiar workspace."""
        self._prefetch_pool.shutdown(wait=False, cancel_futures=True)
        log.debug("Pool de prefetch apagado")