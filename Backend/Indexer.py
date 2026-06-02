import re
import json
from pathlib import Path

from .report_builder import export_excel
from .logger import get_logger


log = get_logger("INDEX")


# Acumulador global de filas. Cada fila es un dict con las claves que
# espera report_builder.COLUMNS. Mantenemos lista (no DataFrame) para
# evitar dependencia de pandas en esta capa, y porque el orden de
# inserción es importante (refleja el orden de captura de pantallas).
_ACUMULADOR_ROWS: list = []


def selectSavePath(default_name: str = "vivodpi_report.xlsx") -> str | None:
    # Import perezoso: tkinter solo se necesita cuando el usuario va a
    # guardar. Así el módulo se puede importar en servidores sin GUI.
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.asksaveasfilename(
        title="Save QA audit report",
        initialfile=default_name,
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
    )
    root.destroy()
    return file_path or None


# ─── Helpers para enriquecer datos ─────────────────────────
def _extract_pre_analysis(explanation_raw: str):
    """
    Separa el tag [PRE-ANALYSIS ...] (si existe) del cuerpo de la explicación.
    Devuelve (pre_analysis_tag, explanation_body).
    """
    explanation_raw = explanation_raw or ""
    if explanation_raw.startswith("[PRE-ANALYSIS"):
        parts = explanation_raw.split("] - ", 1)
        if len(parts) == 2:
            return parts[0] + "]", parts[1]
    return None, explanation_raw


def _ocr_trust_from_reason(reason: str):
    """Extrae el float de confianza embebido en el texto de warning."""
    if not reason:
        return None
    if any(k in reason.lower() for k in ("confianza", "low", "baja", "trust")):
        match = re.search(r"\b0\.\d+\b", reason)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
    return None


def _region_confidence(raw_text, region_ids):
    """
    Dado el raw_text del OCR y una lista de region_ids, devuelve la
    confianza media de las regiones referenciadas. Usado para rellenar
    OCR Trust en ISSUES (que antes se omitía).
    """
    if not raw_text or not region_ids:
        return None
    regions = raw_text.get("regions") if isinstance(raw_text, dict) else None
    if not regions:
        return None
    confs = []
    for rid in region_ids:
        try:
            r = regions[int(rid)]
            c = r.get("confidence")
            if c is not None:
                confs.append(float(c))
        except (IndexError, KeyError, ValueError, TypeError):
            continue
    if not confs:
        return None
    return sum(confs) / len(confs)


# ─── API pública ───────────────────────────────────────────
def insertData(row: dict):
    """
    Inserta una fila ya construida. Esta firma es nueva (antes era una lista
    de 18 elementos). El llamador es __init__.py vía processCapture.
    """
    if not isinstance(row, dict):
        raise ValueError("row debe ser un dict (esquema nuevo del Indexer)")
    _ACUMULADOR_ROWS.append(row)
    return _ACUMULADOR_ROWS


def processCapture(qa_payload: dict, source_path: str, raw_text=None):
    """
    Convierte la respuesta del LLM (issues + ocr_warnings) y los metadatos
    de una captura en filas del acumulador. ESTA es la entrada principal:
    el endpoint HTTP llama a esto en vez de armar filas a mano.

    Args:
        qa_payload: dict tal cual devuelve analyze_text() o el JS por POST.
                    Debe contener issues, ocr_warnings, summary, image_width,
                    image_height, source_file.
        source_path: ruta absoluta a la imagen original (para embeber en Excel).
        raw_text:   el raw_text del OCR cacheado, opcional. Si se provee,
                    se usa para rellenar OCR Trust en ISSUES.
    """
    source_name = qa_payload.get("source_file") or Path(source_path).name
    img_w = qa_payload.get("image_width") or 0
    img_h = qa_payload.get("image_height") or 0

    issues = qa_payload.get("issues", []) or []
    warnings = qa_payload.get("ocr_warnings", []) or []

    for issue in issues:
        explanation_es = issue.get("explanation") or ""
        explanation_en = issue.get("explanation_en") or ""
        pre_analysis, explain_body = _extract_pre_analysis(explanation_es)

        bbox = issue.get("bbox") or {}
        region_ids = issue.get("region_ids") or []

        # OCR trust DERIVADO de las regiones implicadas, ya no se omite.
        ocr_trust = _region_confidence(raw_text, region_ids)

        row = {
            "type":            "ISSUE",
            "source_name":     source_name,
            "source_path":     source_path,
            "category":        issue.get("category"),
            "text_excerpt":    issue.get("text_excerpt"),
            "suggestion":      issue.get("suggestion"),
            "explanation_es":  explain_body,
            "explanation_en":  explanation_en,
            "severity":        issue.get("severity"),
            "ocr_trust":       ocr_trust,
            "llm_confidence":  issue.get("confidence", "high"),
            "pre_analysis":    pre_analysis,
            "bbox_x":          bbox.get("x"),
            "bbox_y":          bbox.get("y"),
            "bbox_w":          bbox.get("width"),
            "bbox_h":          bbox.get("height"),
            "image_w":         img_w,
            "image_h":         img_h,
            "filtered_by_pre": False,
            "region_ids":      region_ids,
        }
        insertData(row)

    for warning in warnings:
        reason = warning.get("reason") or ""
        ocr_trust = _ocr_trust_from_reason(reason)
        region_ids = warning.get("region_ids") or []

        # warning enriquecido: severity=info, suggestion=None pero text completo
        row = {
            "type":            "WARNING",
            "source_name":     source_name,
            "source_path":     source_path,
            "category":        "OCR Noise",
            "text_excerpt":    warning.get("text_excerpt"),
            "suggestion":      None,           # warnings no proponen reemplazo
            "explanation_es":  reason,
            "explanation_en":  reason,         # warnings vienen en español de localQ;
                                               # el origen es regex sobre la región,
                                               # no LLM, así que reusamos el reason.
            "severity":        "info",         # antes None; ahora explícito
            "ocr_trust":       ocr_trust,
            "llm_confidence":  "low",
            "pre_analysis":    None,
            "bbox_x":          None,           # warnings no tienen bbox
            "bbox_y":          None,
            "bbox_w":          None,
            "bbox_h":          None,
            "image_w":         img_w,
            "image_h":         img_h,
            "filtered_by_pre": True,
            "region_ids":      region_ids,
        }
        insertData(row)


def compileRows() -> list:
    """Saca una copia del acumulador y lo vacía. Devuelve la lista de dicts."""
    global _ACUMULADOR_ROWS
    rows = list(_ACUMULADOR_ROWS)
    _ACUMULADOR_ROWS = []
    return rows


# ─── Export (delegado a report_builder) ────────────────────
def exportExcel(rows, filename: str):
    """
    Genera el Excel final. `rows` puede ser una lista de dicts
    (esquema nuevo) o una lista de listas (esquema viejo de 18 columnas)
    para retro-compatibilidad por si quedan llamadas legacy.
    """
    if not rows:
        log.warn("Sin filas para exportar")
        return
    # Adaptación si vienen listas (legacy)
    if isinstance(rows[0], list):
        from .report_builder import build_rows
        rows = build_rows(rows)
    export_excel(rows, filename)


# ─── API de compatibilidad ─────────────────────────────────
# Mantengo el nombre antiguo compileDataFrame por si algún caller externo
# (el endpoint /saveReport) todavía lo invoca. Ahora devuelve la lista de
# rows, no un DataFrame.
def compileDataFrame():
    """DEPRECATED: usa compileRows(). Nombre conservado por compatibilidad."""
    return compileRows()