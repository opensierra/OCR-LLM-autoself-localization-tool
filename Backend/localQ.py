# localQ.py
# Análisis con LLM local vía Ollama — una llamada INDEPENDIENTE por imagen.
# Drop-in compatible: mantiene la firma analyze_text(text, raw_text).
#
# Por qué llamadas independientes y NO sesión con historial:
#   Probamos sesión persistente para reutilizar KV cache. En la práctica con
#   gemma4:e2b en CPU el historial acumulado PENALIZA cada nuevo turno (la
#   imagen 2 termina siendo más lenta que la 1). Volvemos a llamadas frescas:
#   cada imagen procesa solo system + su propio JSON, sin arrastre.
#
# Optimizaciones activas:
#   - think=False: gemma4:e2b deja de generar bloque de razonamiento mudo.
#   - System prompt corto (~300 tokens) en lugar del completo.
#   - num_ctx=4096 en vez de 8192 (acelera prefill, libera RAM).
#   - JSON de regiones sin indentar (separadores ajustados).
#   - Pre-filtro de regiones gestionado por region_prefilter.

import json
import time
import ollama

from .region_prefilter import classify_regions, compact_for_llm
from .logger import get_logger, stream_token, stream_end

log = get_logger("LLM")


# ── Configuration ────────────────────────────────────────────
# OLLAMA_MODEL is mutable: the UI lets the user pick a different model
# from a dropdown after selecting a workspace. Always read via _model_name()
# inside calls so a change takes effect on the next request.
OLLAMA_MODEL = "gemma4:e2b"

def set_model(name: str):
    """Cambia el modelo activo en runtime. Se aplica a las siguientes llamadas."""
    global OLLAMA_MODEL
    if name and isinstance(name, str):
        OLLAMA_MODEL = name
        log.info("Modelo activo cambiado a: %s", name)

def get_model() -> str:
    return OLLAMA_MODEL


# Context window. With dense Android screenshots the JSON of regions can
# easily reach 3000-5000 tokens; 16384 leaves room without truncation.
NUM_CTX = 16384

# How long Ollama keeps the model in RAM after the last call.
KEEP_ALIVE = "30m"

INFERENCE_OPTIONS = {
    "temperature": 0.1,
    "num_ctx": NUM_CTX,
    "top_p": 0.9,
    "repeat_penalty": 1.05,
}


# ── Prompt (versión corta para gemma4:e2b en CPU) ────────────
_SYSTEM_PROMPT = """You are a Spanish (LATAM) localization QA tester for Android screenshots.

Each call you receive OCR regions from one screenshot. Detect localization defects.

Reply ONLY with valid JSON, no markdown, this exact shape:
{
  "summary": "<short Spanish summary>",
  "overall_quality": "excellent|good|acceptable|poor|critical",
  "issues": [{
    "text_excerpt": "<verbatim OCR>",
    "category": "Spelling|Grammar|Punctuation|Capitalization|Untranslated text|Mistranslation|Improvement|Inconsistency|Format error|Tone|Language mixture|UI issues|OCR",
    "severity": "high|medium|low",
    "suggestion": "<corrected Spanish, drop-in replacement>",
    "explanation": "<1-2 short Spanish sentences>",
    "explanation_en": "<same explanation translated to English, 1-2 short sentences>",
    "bbox": {"x": int, "y": int, "width": int, "height": int},
    "region_ids": [int],
    "confidence": "high|medium|low"
  }],
  "ocr_warnings": [{"text_excerpt": "<text>", "reason": "<short>", "region_ids": [int]}]
}

Rules:
- suggestion must differ from text_excerpt and be a drop-in string, not advice.
- explanation_en must convey the same meaning as explanation, in clear English.
- Regions with "ctx": true have low OCR confidence; treat as supporting context.
- If no issues: empty arrays + positive summary.
"""


# ── Llamada Ollama (independiente, con streaming visible) ────
def _call_ollama(user_prompt: str) -> str:
    """
    Una sola llamada con system prompt fijo + el user_prompt de esta imagen.
    Sin historial. El KV cache del system prompt SÍ se reutiliza entre
    llamadas si Ollama lo cachea (es el mismo prefix exacto cada vez).
    """
    log.info("Sending to %s...", get_model())

    full_response = ""
    stream = ollama.chat(
        model=get_model(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        format="json",
        stream=True,
        think=False,        # gemma4 e2b/e4b: salta razonamiento previo
        options=INFERENCE_OPTIONS,
        keep_alive=KEEP_ALIVE,
    )

    for chunk in stream:
        token = chunk.get("message", {}).get("content", "")
        full_response += token
        stream_token(token)

    stream_end()
    log.info("Respuesta completada.")
    return full_response.strip()


# ── Conjuntos válidos y helpers ──────────────────────────────
_VALID_CATEGORIES = {
    "Improvement", "Mistranslation", "Untranslated text", "Spelling", "Grammar",
    "Punctuation", "Capitalization", "Language mixture", "Inconsistency",
    "Format error", "Tone", "UI issues", "OCR",
}
_VALID_SEVERITIES = {"high", "medium", "low"}
_VALID_CONFIDENCES = {"high", "medium", "low"}
_VALID_QUALITIES = {"excellent", "good", "acceptable", "poor", "critical"}


def _emit(callback, event_type: str, payload: dict):
    if callback:
        try:
            callback(event_type, payload)
        except Exception:
            pass
    log.debug("%s: %s", event_type, json.dumps(payload, ensure_ascii=False))


def _clamp_bbox(bbox: dict, img_w: int, img_h: int) -> dict:
    if not isinstance(bbox, dict):
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    try:
        x = max(0, min(int(bbox.get("x", 0)), img_w)) if img_w else int(bbox.get("x", 0))
        y = max(0, min(int(bbox.get("y", 0)), img_h)) if img_h else int(bbox.get("y", 0))
        w = max(0, int(bbox.get("width", 0)))
        h = max(0, int(bbox.get("height", 0)))
        if img_w:
            w = min(w, img_w - x)
        if img_h:
            h = min(h, img_h - y)
        return {"x": x, "y": y, "width": w, "height": h}
    except Exception:
        return {"x": 0, "y": 0, "width": 0, "height": 0}


def _validate_and_clean_issue(issue: dict, img_w: int, img_h: int):
    if not isinstance(issue, dict):
        return None
    text = (issue.get("text_excerpt") or "").strip()
    category = (issue.get("category") or "").strip()
    severity = (issue.get("severity") or "").strip().lower()
    suggestion = (issue.get("suggestion") or "").strip()
    if not text or not category or category not in _VALID_CATEGORIES:
        return None
    if not suggestion or suggestion == text:
        return None
    if severity not in _VALID_SEVERITIES:
        severity = "medium"
    confidence = (issue.get("confidence") or "medium").strip().lower()
    if confidence not in _VALID_CONFIDENCES:
        confidence = "medium"
    bbox = _clamp_bbox(issue.get("bbox", {}), img_w, img_h)
    region_ids = issue.get("region_ids", [])
    if not isinstance(region_ids, list):
        region_ids = []
    clean_ids = []
    for rid in region_ids:
        try:
            clean_ids.append(int(rid))
        except Exception:
            pass
    return {
        "text_excerpt": text,
        "category": category,
        "severity": severity,
        "suggestion": suggestion,
        "explanation": (issue.get("explanation") or "").strip(),
        "explanation_en": (issue.get("explanation_en") or "").strip(),
        "bbox": bbox,
        "region_ids": clean_ids,
        "confidence": confidence,
    }


def _validate_and_clean_warning(warning: dict):
    if not isinstance(warning, dict):
        return None
    text = (warning.get("text_excerpt") or "").strip()
    if not text:
        return None
    region_ids = warning.get("region_ids", [])
    if not isinstance(region_ids, list):
        region_ids = []
    clean_ids = []
    for rid in region_ids:
        try:
            clean_ids.append(int(rid))
        except Exception:
            pass
    return {
        "text_excerpt": text,
        "reason": (warning.get("reason") or "").strip(),
        "region_ids": clean_ids,
    }


# ── Función principal ────────────────────────────────────────
def analyze_text(text: str, raw_text=None, max_retries: int = 1, on_progress=None):
    """
    Analiza UNA imagen. Llamada independiente: cada review es un turno fresco
    al modelo, sin historial de imágenes anteriores.
    Firma idéntica a la versión anterior (drop-in para DPI.review()).
    """
    t0 = time.perf_counter()

    img_w = img_h = 0
    regions = []
    if isinstance(raw_text, dict):
        size = raw_text.get("stats", {}).get("image_size", {})
        img_w = int(size.get("width", 0) or 0)
        img_h = int(size.get("height", 0) or 0)
        regions = raw_text.get("regions", [])

    if not regions:
        return {
            "summary": "No se detectaron regiones de texto.",
            "overall_quality": "acceptable",
            "issues": [], "ocr_warnings": [],
            "_meta": {"elapsed_ms": 0.0, "regions_sent": 0},
        }

    send, context, ruido_local = classify_regions(regions)

    _emit(on_progress, "start", {
        "total_regions": len(regions),
        "regions_send": len(send),
        "regions_context": len(context),
        "regions_noise": len(ruido_local),
        "model": get_model(),
    })

    if not send and not context:
        return {
            "summary": "Todas las regiones quedaron por debajo del umbral de confianza.",
            "overall_quality": "acceptable",
            "issues": [],
            "ocr_warnings": ruido_local,
            "_meta": {
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "regions_sent": 0,
            },
        }

    compact = compact_for_llm(send, context)
    chunk_text = "\n".join(r.get("text", "") for r in send if r.get("text"))

    # JSON compacto sin indentación: ahorra ~30-40% de tokens en el prompt.
    regions_json = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))

    user_prompt = "\n".join([
        "## Readable text (visual order)",
        chunk_text or "(empty)",
        "",
        "## raw_ocr (one screenshot; \"ctx\":true = low-confidence support, not suspect)",
        regions_json,
    ])

    last_error = None
    parsed = None
    for attempt in range(max_retries + 1):
        try:
            raw = _call_ollama(user_prompt)
            if not raw:
                raise ValueError("Empty response")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Invalid JSON structure")
            break
        except Exception as e:
            last_error = e
            log.warn("Intento %d falló: %s", attempt + 1, e)
            time.sleep(0.5 * (attempt + 1))

    if parsed is None:
        return {
            "summary": f"Análisis fallido: {type(last_error).__name__}: {last_error}",
            "overall_quality": "acceptable",
            "issues": [],
            "ocr_warnings": ruido_local,
            "_meta": {
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "regions_sent": len(send) + len(context),
                "error": str(last_error),
            },
        }

    clean_issues = []
    for issue in (parsed.get("issues") or []):
        cleaned = _validate_and_clean_issue(issue, img_w, img_h)
        if cleaned:
            clean_issues.append(cleaned)

    clean_warnings = list(ruido_local)
    for warning in (parsed.get("ocr_warnings") or []):
        cleaned = _validate_and_clean_warning(warning)
        if cleaned:
            clean_warnings.append(cleaned)

    summary = (parsed.get("summary") or "").strip()
    quality = (parsed.get("overall_quality") or "").strip().lower()
    if not summary or quality not in _VALID_QUALITIES:
        total = len(clean_issues)
        high = sum(1 for i in clean_issues if i["severity"] == "high")
        if total == 0:
            summary = summary or "Pantalla sin problemas detectados."
            quality = "good"
        else:
            summary = summary or (
                f"Se detectaron {total} problemas de localización "
                f"({high} de alta severidad)."
            )
            quality = "poor" if high >= 3 else "acceptable" if high >= 1 else "good"

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    _emit(on_progress, "done", {
        "total_issues": len(clean_issues),
        "total_warnings": len(clean_warnings),
        "elapsed_ms": elapsed_ms,
    })

    return {
        "summary": summary,
        "overall_quality": quality,
        "issues": clean_issues,
        "ocr_warnings": clean_warnings,
        "_meta": {
            "elapsed_ms": elapsed_ms,
            "regions_total": len(regions),
            "regions_sent": len(send) + len(context),
            "regions_prefiltered": len(ruido_local),
        },
    }