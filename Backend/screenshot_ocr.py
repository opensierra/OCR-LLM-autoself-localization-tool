# screenshot_ocr.py - High-quality OCR pipeline tuned for Android screenshots.
#
# Quality strategy:
#   - Two-pass MSER detection (tight + permissive) to catch both small and
#     large text, then deduplicate overlapping regions.
#   - CLAHE per-region for contrast enhancement on tricky backgrounds.
#   - Multi-PSM voting: tries PSM 7 (single line) and PSM 6 (uniform block),
#     keeps the one with higher mean confidence per region.
#   - No global downscale: pipeline runs at the screenshot's native
#     resolution. Per-region upscaling still happens when text is too small.
#
# Speed: still parallel via ThreadPoolExecutor. With current settings, an
# Android screenshot (1080x2400) takes 2-6 seconds typically; very dense
# screens with 30+ regions can reach 15s. The pipeline can run in the
# background while the LLM works on a different image.

import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytesseract

from .env import TESSERACT_PATH
from .logger import get_logger

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


log = get_logger("OCR")


# Region detection / deduplication tunables
MIN_REGION_W = 8
MIN_REGION_H = 8
# Boxes whose smaller one is >= this fraction inside the other are merged
# (containment-based dedup; see _dedupe_boxes).
CONTAINMENT_MERGE_THRESHOLD = 0.80
MIN_REGION_HEIGHT_FOR_UPSCALE = 40 # below this, region is upscaled before OCR

# Single MSER detector. Earlier versions ran two passes (tight + loose) but
# profiling showed they produce nearly identical boxes on UI screenshots —
# the second pass was pure cost. One well-tuned detector covers both small
# and large text because Android UIs use a limited range of font sizes.
_MSER = cv2.MSER_create(delta=4, min_area=20, max_area=20000, max_variation=0.30)


# RawTextResult: dict for the LLM, with human-friendly rendering for Jinja.
class RawTextResult(dict):
    def _render_human(self) -> str:
        regions = self.get('regions', [])
        stats = self.get('stats', {})
        if not regions:
            return self.get('plain', '') or '(no regions)'

        size = stats.get('image_size', {})
        lines = [
            f"[stats] regions={stats.get('regions_total', 0)}  "
            f"kept={stats.get('regions_kept', 0)}  "
            f"mean_conf={stats.get('mean_confidence', 0)}  "
            f"low_conf_words={stats.get('low_conf_words', 0)}  "
            f"mojibake_regions={stats.get('mojibake_regions', 0)}  "
            f"image={size.get('width', '?')}x{size.get('height', '?')}",
            "-" * 60,
        ]
        for r in regions:
            rid = r.get('region_id', '?')
            conf = r.get('confidence', 0)
            b = r.get('bbox', {})
            text = r.get('text', '') or '(empty)'
            flags = []
            if r.get('filtered_out'):   flags.append('FILTERED')
            if r.get('bg_dark'):        flags.append('dark')
            if r.get('has_gradient'):   flags.append('gradient')
            if r.get('mojibake'):       flags.append('MOJIBAKE')
            if r.get('near_edge'):      flags.append('near_edge')
            flag_str = f"  [{', '.join(flags)}]" if flags else ''
            lines.append(
                f"#{rid:>3}  conf={conf:.2f}  "
                f"bbox=({b.get('x', 0)},{b.get('y', 0)} "
                f"{b.get('width', 0)}x{b.get('height', 0)}){flag_str}"
            )
            lines.append(f"      {text}")
        return "\n".join(lines)

    def __str__(self):  return self._render_human()
    def __html__(self): return self._render_human()


# Mojibake detection (kept verbatim; cheap and useful for the LLM).
_MOJIBAKE_PATTERN = re.compile(
    r'[\uFFFD\u25A1\u25AF\u25AE]'
    r'|[\u0080-\u009F]'
    r'|Â[^\w\s]|Ã[^\w\s]'
)
def _detect_mojibake(text: str) -> bool:
    return bool(text and _MOJIBAKE_PATTERN.search(text))


def _boxes_from_mask(mask: np.ndarray, w: int, h: int) -> list:
    """Group a binary glyph mask into line-level bounding boxes.

    The horizontal dilation that joins glyphs into lines is scaled to the
    typical glyph height (estimated from the raw components), so the same
    code works on small body text and large headers without bridging the
    wide gaps between separate UI columns."""
    if not mask.any():
        return []

    # Estimate typical glyph height so the line-grouping dilation can be
    # proportional rather than a magic constant.
    n0, _, stats0, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    glyph_heights = [int(stats0[i, cv2.CC_STAT_HEIGHT]) for i in range(1, n0)
                     if stats0[i, cv2.CC_STAT_HEIGHT] >= MIN_REGION_H]
    if glyph_heights:
        glyph_heights.sort()
        typical_h = glyph_heights[len(glyph_heights) // 2]
    else:
        typical_h = 20

    # Horizontal gap to bridge ~= 0.9x glyph height. Empirically, on UI text
    # the inter-word gap is roughly 0.7x the glyph height while the gap between
    # separate columns is many times larger (often 10x+). Bridging ~0.9x height
    # joins words within a line into one region — which means ONE OCR call per
    # line instead of one per word — while leaving the column gap untouched.
    kx = max(6, int(typical_h * 0.9))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 2))
    dilated = cv2.dilate(mask, kernel, iterations=1)

    # 4-connectivity (not 8) keeps vertically-adjacent lines separate:
    # 8-connectivity links them through the diagonal touch of
    # ascenders/descenders, collapsing separate lines into a paragraph block.
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(dilated, connectivity=4)
    boxes = []
    for i in range(1, n_labels):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        cw = int(stats[i, cv2.CC_STAT_WIDTH])
        ch = int(stats[i, cv2.CC_STAT_HEIGHT])
        if cw < MIN_REGION_W or ch < MIN_REGION_H:
            continue
        # Discard absurd aspect ratios that can't possibly be text
        if cw / max(ch, 1) > 60 or ch / max(cw, 1) > 20:
            continue
        # Discard full-image components
        if cw > w * 0.95 and ch > h * 0.95:
            continue
        boxes.append((x, y, cw, ch))
    return boxes


def _union_box(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = min(ax, bx); y1 = min(ay, by)
    x2 = max(ax + aw, bx + bw); y2 = max(ay + ah, by + bh)
    return (x1, y1, x2 - x1, y2 - y1)


def _containment(a, b) -> float:
    """Fraction of the SMALLER box that lies inside the larger box.
    Returns ~1.0 when one box is essentially contained in the other,
    regardless of their relative sizes (unlike IoU, which is dragged
    down when the two boxes differ a lot in area)."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    smaller = min(aw * ah, bw * bh)
    return inter / smaller if smaller > 0 else 0.0


def _dedupe_boxes(boxes: list) -> list:
    """Merge near-duplicate boxes. We merge only when one box is largely
    CONTAINED in another (containment >= 0.80) — that means the tight and
    loose passes found the same region. We deliberately do NOT merge boxes
    that merely overlap at the edges, because that union would swallow
    neighboring text and is the main cause of mixed-region boxes."""
    if not boxes:
        return []
    # Sort by area descending so the biggest box absorbs the ones inside it
    boxes_sorted = sorted(boxes, key=lambda b: -b[2] * b[3])
    kept = []
    for b in boxes_sorted:
        merged = False
        for i, k in enumerate(kept):
            # Merge only if b is mostly inside k (or vice-versa).
            if _containment(b, k) >= CONTAINMENT_MERGE_THRESHOLD:
                kept[i] = _union_box(b, k)
                merged = True
                break
        if not merged:
            kept.append(b)
    return kept


def _detect_regions(gray: np.ndarray) -> list:
    """Single MSER pass on normal + inverted grayscale, then line grouping
    and containment dedup. One pass instead of two: profiling showed the old
    tight/loose passes produced nearly identical boxes, so the second was
    pure cost with no recall benefit."""
    pts_normal, _ = _MSER.detectRegions(gray)
    pts_inverted, _ = _MSER.detectRegions(cv2.bitwise_not(gray))

    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    for pts in pts_normal + pts_inverted:
        mask[pts[:, 1], pts[:, 0]] = 255

    boxes = _boxes_from_mask(mask, w, h)
    return _dedupe_boxes(boxes)


def _apply_clahe(gray: np.ndarray) -> np.ndarray:
    """Contrast-limited adaptive histogram equalization on the crop.
    Helps with gradients, low-contrast UIs, dark modes."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _run_tess(binary: np.ndarray, psm: int):
    """Single Tesseract invocation, returns dict or None on error."""
    config = f'--oem 1 --psm {psm} -l spa -c preserve_interword_spaces=1'
    try:
        return pytesseract.image_to_data(
            binary, config=config, output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return None


def _score_tess_output(data) -> float:
    """Mean confidence across non-empty words. Used to pick best PSM."""
    if data is None:
        return -1.0
    confs = []
    for i in range(len(data['text'])):
        t = (data['text'][i] or '').strip()
        c = int(data['conf'][i])
        if t and c >= 0:
            confs.append(c)
    if not confs:
        return -1.0
    return sum(confs) / len(confs)


def _recognize(gray: np.ndarray, bbox: tuple) -> dict:
    """Recognize text in one region. Multi-PSM voting; returns best output."""
    x, y, w, h = bbox
    # Padding generoso: la dilatación MSER suele dejar la bbox justo al filo
    # del último glifo, lo que recorta ascenders/descenders y baja la confianza.
    pad = 8
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(gray.shape[1], x + w + pad), min(gray.shape[0], y + h + pad)

    empty_meta = {'bg_dark': False, 'has_gradient': False, 'mojibake': False}
    if x2 - x1 < 5 or y2 - y1 < 5:
        return {
            'text': '', 'confidence': 0.0, 'words': [],
            'offset_xy': (x1, y1, 1.0, 1.0), 'meta': empty_meta,
        }

    crop = gray[y1:y2, x1:x2]
    ch, cw = crop.shape

    # Per-region upscale if it's small
    if ch < MIN_REGION_HEIGHT_FOR_UPSCALE:
        f = min(60 / ch, 3.0)
        new_w, new_h = int(cw * f), int(ch * f)
        crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        scale_x = cw / new_w
        scale_y = ch / new_h
    else:
        scale_x = scale_y = 1.0

    # Dark mode: invert
    bg_is_dark = float(np.mean(crop)) < 127
    if bg_is_dark:
        crop = cv2.bitwise_not(crop)

    # Gradient detection
    h_c, w_c = crop.shape
    q1 = float(np.mean(crop[:h_c // 2, :w_c // 2]))
    q2 = float(np.mean(crop[:h_c // 2, w_c // 2:]))
    q3 = float(np.mean(crop[h_c // 2:, :w_c // 2]))
    q4 = float(np.mean(crop[h_c // 2:, w_c // 2:]))
    has_gradient = float(np.std([q1, q2, q3, q4])) > 18.0

    # CLAHE for better local contrast (especially on gradient backgrounds)
    enhanced = _apply_clahe(crop)

    # Binarization
    if has_gradient:
        block = max(15, (h_c // 2) | 1)
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, block, 10,
        )
    else:
        _, binary = cv2.threshold(
            enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

    border = 12
    binary = cv2.copyMakeBorder(
        binary, border, border, border, border,
        cv2.BORDER_CONSTANT, value=255,
    )

    # Conditional multi-PSM. The first PSM (chosen by aspect ratio) handles
    # the vast majority of UI text. We only fall back to additional PSMs when
    # the first result is weak, which is where they actually help. On clean
    # text this turns 2-3 Tesseract calls into 1 — the single biggest speedup
    # in the pipeline, since recognition dominates the runtime.
    aspect = binary.shape[1] / max(1, binary.shape[0])
    psms_to_try = [7, 6] if aspect > 1.5 else [6, 7]
    if aspect > 4.0:
        psms_to_try.append(11)

    # Confidence at or above this on the first PSM means "good enough, stop".
    PSM_EARLY_EXIT_SCORE = 75.0

    best_data = None
    best_score = -1.0
    for psm in psms_to_try:
        data = _run_tess(binary, psm)
        score = _score_tess_output(data)
        if score > best_score:
            best_score = score
            best_data = data
        # Early exit: the first sufficiently-confident PSM wins.
        if best_score >= PSM_EARLY_EXIT_SCORE:
            break

    data = best_data
    if data is None:
        return {
            'text': '', 'confidence': 0.0, 'words': [],
            'offset_xy': (x1, y1, scale_x, scale_y),
            'meta': {'bg_dark': bg_is_dark, 'has_gradient': has_gradient, 'mojibake': False},
        }

    words = []
    confs = []
    texts = []
    for i in range(len(data['text'])):
        t = (data['text'][i] or '').strip()
        c = int(data['conf'][i])
        if c < 0:
            continue
        words.append({
            'word': t,
            'conf': round(c / 100.0, 3),
            'low_conf': c < 50,
            'level': int(data['level'][i]),
            'block_num': int(data['block_num'][i]),
            'par_num': int(data['par_num'][i]),
            'line_num': int(data['line_num'][i]),
            'word_num': int(data['word_num'][i]),
            'bbox_local': (
                int(data['left'][i]) - border,
                int(data['top'][i]) - border,
                int(data['width'][i]),
                int(data['height'][i]),
            ),
        })
        if t:
            texts.append(t)
            confs.append(c)

    text = ' '.join(texts)
    avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0

    # Post-OCR sanity: if the recognized text is only symbols/punctuation
    # (no letter or digit at all), it's almost certainly noise. Drop it
    # so it doesn't pollute the LLM prompt.
    if text and not re.search(r"[\w\u00C0-\u024F]", text):
        text = ''
        avg_conf = 0.0
        words = []

    return {
        'text': text,
        'confidence': round(avg_conf, 3),
        'words': words,
        'offset_xy': (x1, y1, scale_x, scale_y),
        'meta': {
            'bg_dark': bool(bg_is_dark),
            'has_gradient': bool(has_gradient),
            'mojibake': _detect_mojibake(text),
        },
    }


def _word_bbox_to_image(local_bbox, offset_xy) -> dict:
    """Map word bbox from preprocessed crop to original image coordinates."""
    lx, ly, lw, lh = local_bbox
    x_off, y_off, sx, sy = offset_xy
    return {
        'x': int(x_off + lx * sx),
        'y': int(y_off + ly * sy),
        'width': int(lw * sx),
        'height': int(lh * sy),
    }


def _detect_truncation(regions_data, img_w, img_h):
    """Mark each region with `near_edge=True` if it touches image edge
    or another region directly to its right (likely truncation)."""
    EDGE_TOL = 8
    NEIGHBOR_TOL = 4

    by_row = {}
    for r in regions_data:
        b = r['bbox']
        y_mid = b['y'] + b['height'] / 2
        key = int(y_mid) // 30
        by_row.setdefault(key, []).append(r)
        by_row.setdefault(key - 1, []).append(r)
        by_row.setdefault(key + 1, []).append(r)

    for r in regions_data:
        b = r['bbox']
        right = b['x'] + b['width']
        bottom = b['y'] + b['height']
        touches_img_edge = (img_w - right) <= EDGE_TOL or (img_h - bottom) <= EDGE_TOL

        touches_neighbor = False
        y_mid = b['y'] + b['height'] / 2
        for other in by_row.get(int(y_mid) // 30, ()):
            if other is r:
                continue
            ob = other['bbox']
            if not (ob['y'] <= y_mid <= ob['y'] + ob['height']):
                continue
            gap = ob['x'] - right
            if 0 <= gap <= NEIGHBOR_TOL:
                touches_neighbor = True
                break

        r['near_edge'] = bool(touches_img_edge or touches_neighbor)


def process_image(image_path: str, preview_dir: str = None, force: bool = False) -> dict:
    """Process a screenshot at native resolution. Returns a dict with text,
    raw_text (RawTextResult), boxes (kept), preview_path, and elapsed_ms."""
    t0 = time.perf_counter()

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    img_h, img_w = img.shape[:2]
    log.info("Processing %s at native %dx%d", Path(image_path).name, img_w, img_h)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    bboxes = _detect_regions(gray)
    log.debug("Detected %d candidate regions after dedupe", len(bboxes))

    if bboxes:
        workers = min(8, max(2, len(bboxes)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda b: _recognize(gray, b), bboxes))
    else:
        results = []

    regions_data = []
    boxes = []
    plain_parts = []
    all_confs = []
    low_conf_word_count = 0
    mojibake_regions = 0

    CONF_KEEP = 0.40

    for idx, (bbox, rec) in enumerate(zip(bboxes, results)):
        x, y, w, h = bbox
        region_bbox = {'x': x, 'y': y, 'width': w, 'height': h}

        words_out = []
        for p in rec['words']:
            wb = _word_bbox_to_image(p['bbox_local'], rec['offset_xy'])
            if p['low_conf']:
                low_conf_word_count += 1
            words_out.append({
                'word': p['word'],
                'conf': p['conf'],
                'bbox': wb,
                'block': p['block_num'],
                'line': p['line_num'],
                'word_num': p['word_num'],
                'low_conf': p['low_conf'],
            })

        text = rec['text']
        conf = rec['confidence']
        kept = bool(text) and conf >= CONF_KEEP
        meta = rec['meta']

        if meta.get('mojibake'):
            mojibake_regions += 1

        regions_data.append({
            'region_id': idx,
            'text': text,
            'confidence': conf,
            'bbox': region_bbox,
            'words': words_out,
            'filtered_out': not kept,
            'bg_dark': meta.get('bg_dark', False),
            'has_gradient': meta.get('has_gradient', False),
            'mojibake': meta.get('mojibake', False),
        })

        if kept:
            plain_parts.append(text)
            all_confs.append(conf)
            boxes.append({
                'text': text,
                'confidence': conf,
                **region_bbox,
            })

    _detect_truncation(regions_data, img_w, img_h)

    raw_text = RawTextResult({
        'plain': "\n".join(plain_parts),
        'regions': regions_data,
        'stats': {
            'regions_total': len(regions_data),
            'regions_kept': len(boxes),
            'mean_confidence': round(sum(all_confs) / len(all_confs), 3) if all_confs else 0.0,
            'low_conf_words': low_conf_word_count,
            'mojibake_regions': mojibake_regions,
            'image_size': {'width': img_w, 'height': img_h},
        },
    })

    # Preview with boxes drawn on the original image
    preview_dir = Path('Backend/static/images/cache')
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_filename = f"{Path(image_path).stem}_preview.png"
    preview_path = preview_dir / preview_filename

    if force or not preview_path.exists():
        canvas = img.copy()
        for b in boxes:
            color = (0, 200, 0) if b['confidence'] > 0.8 else (0, 150, 255)
            cv2.rectangle(
                canvas,
                (b['x'], b['y']),
                (b['x'] + b['width'], b['y'] + b['height']),
                color, 2,
            )
        cv2.imwrite(str(preview_path), canvas)

    # Reading order: group boxes into visual rows, then left-to-right within
    # each row. A fixed 15px band misgroups text on high-DPI screenshots
    # (where a line is 40-60px tall) and on dense ones. We derive the band
    # height from the median box height so it adapts to the screenshot's scale.
    if boxes:
        median_h = sorted(b['height'] for b in boxes)[len(boxes) // 2]
        band = max(10, int(median_h * 0.6))
    else:
        band = 15
    boxes.sort(key=lambda b: (b['y'] // band, b['x']))
    text_joined = "\n".join(b['text'] for b in boxes)

    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    log.info(
        "OCR done for %s in %.1f ms (%d regions, %d kept)",
        Path(image_path).name, elapsed, len(regions_data), len(boxes),
    )

    return {
        'text': text_joined,
        'raw_text': raw_text,
        'boxes': boxes,
        'preview_path': preview_filename,
        'elapsed_ms': elapsed,
    }