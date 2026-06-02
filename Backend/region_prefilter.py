# region_prefilter.py
# Pre-filtro de regiones OCR ANTES de llamar a cualquier LLM (local o Gemini).
#
# Objetivo: no gastar inferencia (ni tokens) en regiones que son ruido OCR
# con alta certeza, y reducir el tamaño del prompt sin perder bugs reales.
#
# Reutilizable: tanto localQ.py como gemini_qa.py importan classify_regions().
#
# División de responsabilidades (importante):
#   - Este módulo juzga la CALIDAD DE LA SEÑAL OCR (confianza, mojibake, etc.).
#   - NO juzga el contenido lingüístico. Si una región es "basura típica"
#     (1 carácter, solo símbolos, un número suelto) pero tiene buena confianza,
#     se manda al LLM y es ÉL quien decide si es un bug. (Decisión de diseño.)
#
# Salida: tres bandas.
#   send    -> confianza >= 0.95: señal segura, al LLM como candidata.
#   context -> confianza 0.80–0.95: dudosa, al LLM CON ADVERTENCIA (ctx: true).
#   noise   -> confianza < 0.80 (o mojibake seguro/filtrado): ruido OCR,
#              no toca el LLM. Queda registrado en ocr_warnings.

import re


# ── Parámetros (tres bandas) ─────────────────────────────────
# >= SEND_CONF (0.80): señal segura, candidata directa al LLM (send).
# [CONTEXT_CONF, SEND_CONF) (0.60–0.80): dudosa, va al LLM con advertencia (context).
# < CONTEXT_CONF (0.60): ruido, no toca el LLM (noise -> ocr_warnings).
SEND_CONF = 0.80
CONTEXT_CONF = 0.60

# Mojibake con confianza alta: por decisión del usuario, SIEMPRE a ruido.
# Cambia a False si algún día quieres que el LLM evalúe bugs de render reales.
DROP_HIGH_CONF_MOJIBAKE = True

# Tope de regiones enviadas al LLM (send + context). Si se supera,
# se recortan primero las de 'context', luego las 'send' de menor confianza.
MAX_REGIONS_TO_LLM = 120


# Patrón de mojibake — mismo espíritu que screenshot_ocr._MOJIBAKE_PATTERN,
# duplicado aquí a propósito para que el pre-filtro sea autónomo y no dependa
# de importar el módulo de OCR (evita acoplamiento circular).
_MOJIBAKE_PATTERN = re.compile(
    r'[\uFFFD\u25A1\u25AF\u25AE]'          # □ ▯ ▮ y replacement char
    r'|[\u0080-\u009F]'                    # control C1
    r'|Â[^\w\s]|Ã[^\w\s]'                  # UTF-8 leído como Latin-1
)


def _has_mojibake(region: dict) -> bool:
    # Confía en la flag del OCR si ya viene calculada; si no, la deriva del texto.
    if region.get("mojibake"):
        return True
    text = region.get("text") or ""
    return bool(_MOJIBAKE_PATTERN.search(text))


def _conf(region: dict) -> float:
    try:
        return float(region.get("confidence", 0) or 0)
    except Exception:
        return 0.0


def _warning(region: dict, reason: str) -> dict:
    rid = region.get("region_id")
    return {
        "text_excerpt": (region.get("text") or "").strip(),
        "reason": reason,
        "region_ids": [rid] if rid is not None else [],
    }


def classify_regions(regions: list):
    """
    Clasifica las regiones OCR en tres cubos: (send, context, noise).

    Args:
        regions: lista de dicts tal como los produce screenshot_ocr.process_image
                 (cada uno con text, confidence, bbox, words, mojibake,
                  filtered_out, near_edge, region_id...).

    Returns:
        (send, context, noise)
          send    : list[region]  -> candidatas para el LLM
          context : list[region]  -> el LLM las ve como apoyo, no como sospechosas
          noise   : list[dict]    -> warnings listos (formato ocr_warnings)
    """
    send = []
    context = []
    noise = []

    for r in regions:
        text = (r.get("text") or "").strip()

        # 1. Sin texto -> no aporta nada al LLM, ni siquiera como warning útil.
        if not text:
            continue

        conf = _conf(r)
        moji = _has_mojibake(r)

        # 2. Mojibake con confianza alta -> ruido siempre (decisión del usuario).
        #    Con confianza baja igual cae en el filtro de confianza de abajo.
        if moji and DROP_HIGH_CONF_MOJIBAKE and conf >= SEND_CONF:
            noise.append(_warning(
                r, f"Texto corrupto (mojibake) con confianza {conf:.2f}; descartado como ruido OCR."
            ))
            continue

        # 3. Marcada como filtrada por el propio OCR -> ruido.
        if r.get("filtered_out"):
            noise.append(_warning(
                r, f"Región filtrada por el OCR (confianza {conf:.2f})."
            ))
            continue

        # 4. Confianza por debajo del piso de contexto -> ruido.
        if conf < CONTEXT_CONF:
            noise.append(_warning(
                r, f"Confianza OCR muy baja ({conf:.2f}); descartada antes del LLM."
            ))
            continue

        # 5. Banda de advertencia (CONTEXT_CONF <= conf < SEND_CONF) -> context.
        #    0.80–0.95: va al LLM pero marcada como dudosa (ctx: true), para que
        #    el modelo la trate con cautela y la use sobre todo como apoyo
        #    (inconsistencias / fragmentación entre vecinas).
        #    El mojibake de esta banda también aterriza aquí.
        if conf < SEND_CONF or moji:
            context.append(r)
            continue

        # 6. Señal segura (>= SEND_CONF, 0.95) -> candidata directa.
        send.append(r)

    # 7. Tope de regiones: si send+context excede MAX_REGIONS_TO_LLM,
    #    recortar primero la banda de advertencia (context), luego las
    #    seguras (send) de menor confianza. Lo recortado va a ruido.
    total = len(send) + len(context)
    if total > MAX_REGIONS_TO_LLM:
        context.sort(key=_conf)  # peores primero
        while len(send) + len(context) > MAX_REGIONS_TO_LLM and context:
            dropped = context.pop(0)
            noise.append(_warning(
                dropped, "Región omitida por límite de contexto (MAX_REGIONS_TO_LLM)."
            ))
        if len(send) > MAX_REGIONS_TO_LLM:
            send.sort(key=_conf, reverse=True)
            sobrantes = send[MAX_REGIONS_TO_LLM:]
            send = send[:MAX_REGIONS_TO_LLM]
            for dropped in sobrantes:
                noise.append(_warning(
                    dropped, "Región omitida por límite de contexto (MAX_REGIONS_TO_LLM)."
                ))

    return send, context, noise


def compact_for_llm(send: list, context: list):
    """
    Forma compacta y barata en tokens para el prompt.
    Las regiones de 'context' se marcan con "ctx": true para que el LLM
    sepa que son apoyo (inconsistencias / fragmentación), no sospechosas.
    """
    out = []
    for r in send:
        out.append(_compact_one(r, is_context=False))
    for r in context:
        out.append(_compact_one(r, is_context=True))
    # Orden estable por id para que el LLM lea coherente
    out.sort(key=lambda x: (x.get("id") if x.get("id") is not None else 1e9))
    return out


def _compact_one(r: dict, is_context: bool) -> dict:
    low_words = [
        {"w": w.get("word", ""), "c": w.get("conf", 0)}
        for w in r.get("words", []) if w.get("low_conf")
    ]
    entry = {
        "id": r.get("region_id"),
        "text": r.get("text", ""),
        "conf": round(_conf(r), 2),
        "bbox": r.get("bbox", {}),
        "low_conf_words": low_words,
    }
    if is_context:
        entry["ctx"] = True
    return entry