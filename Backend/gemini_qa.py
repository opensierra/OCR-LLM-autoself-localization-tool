# gemini_qa.py — Análisis de texto extraído de screenshots con Gemini.
import json
import time

from google import genai
from google.genai import types

from .env import GEMINI_API_KEY


_client = None
def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


_SYSTEM_PROMPT =  """You are a senior localization QA tester for Android software, specialized in Spanish (Latin America neutral by default, with Colombian market priority).

You will receive two views of OCR data from a screenshot:

1) `text`: human-readable version, reordered by visual rows.
2) `raw_ocr`: full OCR structure with regions, individual words, confidence levels, and bounding boxes in the ORIGINAL image. Use this as technical evidence and as the source of coordinates for any issue you report.

Your goal: detect and classify real software/localization defects, distinguishing them from OCR noise. When OCR noise is itself a visible problem on screen, you may still report it.


ERROR CATEGORIES (use these EXACT values for `category`):

- Improvement: text is correct but could be more natural, clearer, or more idiomatic for the target market on mobile devices.
- Mistranslation: translation conveys the wrong meaning or inaccurate semantic definition vs. the likely source context.
- Untranslated text: source-language text (typically English) left in the localized UI.
- Spelling: misspelled word or typos in the target language.
- Grammar: agreement, conjugation, prepositions, syntax errors, or gender/number mismatches.
- Punctuation: missing, extra, or incorrect punctuation marks, including mandatory Spanish inverted opening signs.
- Capitalization: wrong casing for the target language conventions (e.g. English title case where Spanish sentence case is expected).
- Language mixture: two or more languages mixed within the same UI surface.
- Inconsistency: same concept, action, or feature labeled differently across distinct components on the screen.
- Format error: wrong format for dates (DD/MM/AAAA), times, numbers, currency (COP: "1.234.567,89"), units, or addresses.
- Tone: register inappropriate for the product (overly formal, informal, robotic, archaic, or rude).
- UI issues: visible UI problems detectable from OCR: truncation, overlap, missing text, container too small for the content.
- OCR: the screen visibly shows text that is corrupted, illegible, or rendered incorrectly AND this would be a problem the user perceives.


OUTPUT RULES:

- `text_excerpt`: EXACT OCR text, verbatim.
- `suggestion`: drop-in replacement string. NOT advice. Must differ from text_excerpt.
- `explanation`: 1-2 short sentences in SPANISH explaining what is wrong and why the suggestion fixes it.
- `explanation_en`: SAME explanation translated to English, 1-2 short sentences. Must convey the same meaning as `explanation`.
- Each issue MUST include a `bbox` in absolute pixel coordinates of the ORIGINAL image.
- `region_ids` must be the integer region_id(s) backing the bbox.
- `confidence`: how sure YOU are this is a real bug (not OCR engine noise). high/medium/low.
- If the screen is clean: return `issues: []` and a positive `summary` in Spanish.
"""


# Strict schema for Gemini (response_schema guarantees structural validity)
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "overall_quality": {
            "type": "string",
            "enum": ["excellent", "good", "acceptable", "poor", "critical"],
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text_excerpt": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "Improvement",
                            "Mistranslation",
                            "Untranslated text",
                            "Spelling",
                            "Grammar",
                            "Punctuation",
                            "Capitalization",
                            "Language mixture",
                            "Inconsistency",
                            "Format error",
                            "Tone",
                            "UI issues",
                            "OCR",
                        ],
                    },
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "suggestion": {"type": "string"},
                    "explanation": {"type": "string"},
                    "explanation_en": {"type": "string"},
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                        "required": ["x", "y", "width", "height"],
                    },
                    "region_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": [
                    "text_excerpt", "category", "severity",
                    "suggestion", "explanation", "explanation_en",
                    "bbox", "region_ids", "confidence",
                ],
            },
        },
        "ocr_warnings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text_excerpt": {"type": "string"},
                    "reason": {"type": "string"},
                    "region_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["text_excerpt", "reason"],
            },
        },
    },
    "required": ["summary", "overall_quality", "issues", "ocr_warnings"],
}


def _compact_raw_for_llm(raw_text: dict, max_regions: int = 120) -> dict:
    if not isinstance(raw_text, dict):
        return {'plain': str(raw_text), 'regions': [], 'stats': {}}
    regions = raw_text.get('regions', [])[:max_regions]
    compact_regions = []
    for r in regions:
        low_words = [
            {'w': w['word'], 'c': w['conf']}
            for w in r.get('words', []) if w.get('low_conf')
        ]
        compact_regions.append({
            'id': r.get('region_id'),
            'text': r.get('text', ''),
            'conf': r.get('confidence', 0),
            'bbox': r.get('bbox', {}),
            'low_conf_words': low_words,
            'filtered_out': r.get('filtered_out', False),
        })
    return {
        'plain': raw_text.get('plain', ''),
        'regions': compact_regions,
        'stats': raw_text.get('stats', {}),
    }


def _clamp_bbox(bbox: dict, img_w: int, img_h: int) -> dict:
    if not isinstance(bbox, dict):
        return {'x': 0, 'y': 0, 'width': 0, 'height': 0}
    x = max(0, min(int(bbox.get('x', 0)), img_w))
    y = max(0, min(int(bbox.get('y', 0)), img_h))
    w = max(0, min(int(bbox.get('width', 0)), img_w - x))
    h = max(0, min(int(bbox.get('height', 0)), img_h - y))
    return {'x': x, 'y': y, 'width': w, 'height': h}


def analyze_text(text: str, raw_text=None, max_retries: int = 2) -> dict:
    raw_compact = _compact_raw_for_llm(raw_text) if raw_text is not None else None

    img_w = img_h = 0
    if isinstance(raw_text, dict):
        size = raw_text.get('stats', {}).get('image_size', {})
        img_w = int(size.get('width', 0))
        img_h = int(size.get('height', 0))

    parts = [
        "## Readable text (visual order)",
        "```",
        text or "(empty)",
        "```",
    ]
    if raw_compact:
        parts += [
            "",
            "## raw_ocr (full technical evidence from Tesseract + MSER)",
            "```json",
            json.dumps(raw_compact, ensure_ascii=False, indent=2),
            "```",
        ]
    user_prompt = "\n".join(parts)

    client = _get_client()
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type='application/json',
                    response_schema=_RESPONSE_SCHEMA,
                    temperature=0.2,
                ),
            )
            result = json.loads(response.text)

            result.setdefault('summary', '')
            result.setdefault('overall_quality', 'acceptable')
            result.setdefault('issues', [])
            result.setdefault('ocr_warnings', [])

            if img_w and img_h:
                for issue in result['issues']:
                    if 'bbox' in issue:
                        issue['bbox'] = _clamp_bbox(issue['bbox'], img_w, img_h)
                    issue.setdefault('explanation_en', '')

            return result

        except json.JSONDecodeError as e:
            last_err = e
        except Exception as e:
            last_err = e

        time.sleep(0.5 * (attempt + 1))

    return {
        'summary': f'Analysis failed: {type(last_err).__name__}: {last_err}',
        'overall_quality': 'acceptable',
        'issues': [],
        'ocr_warnings': [],
        '_error': str(last_err),
    }