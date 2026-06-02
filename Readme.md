# VivoDPI

Internal QA tooling for Spanish (LATAM) localization auditing of Android
screenshots. Combines computer-vision OCR (Tesseract + MSER) with LLM-based
linguistic review to surface defects: spelling, grammar, mistranslations,
untranslated strings, UI truncation, inconsistencies, etc.

Output is a consolidated Excel report with embedded annotated screenshots
and a 14-column schema ready for follow-up by the dev team.

---

## 1. Base Tools Installation

Run the installers located in `./bin` in this order:

1. **Python 3.12.10**
   During installation, check "Add Python 3.12 to PATH" before clicking
   "Install Now".

2. **Tesseract OCR**
   Run `tesseract-ocr-w64-setup-5.5.0.20241111.exe`.
   Select all additional language and script packages — this does not slow
   down OCR and lets you switch operating language in `Backend/screenshot_ocr.py`.
   During installation, change the destination path to: `./tesseract` (relative
   to the project root). The path is resolved by `Backend/env.py`.

3. **Ollama**
   Run `OllamaSetup.exe` with default options.
   After installation, pull the model used by the local QA pipeline:

   ```
   ollama pull gemma3:e2b
   ```

   That downloads ~2 GB and registers the model so the backend can find it.
   The model is now selectable from the UI dropdown on the index page —
   the dropdown is populated by calling `ollama list` at startup.

## 2. Project Environment Setup

From the project root, in CMD or PowerShell:

```
prepare_env.bat
```

Creates the venv and installs everything in `requirements.txt`. First time
you install Python/Tesseract you may need to restart the terminal or IDE
for PATH changes to take effect.

## 3. Running

```
launch.bat
```

Starts the Flask backend on `http://127.0.0.1:5000` and opens it in a
pywebview window (maximized).

Stop it by closing the window. The Ollama service keeps running independently
in the background.

---

## 4. User-Facing Workflow

### Index page

When the app starts you see a landing page with:
- **Ollama Model dropdown** populated from `ollama list`. Pick the model
  you want for this session.
- **Add model button** opens a terminal window with `ollama pull` instructions.
- **Start fresh toggle**: if checked, the disk cache for the chosen
  workspace is wiped before processing begins.
- **Select directory**: opens a native folder picker, then routes through
  a loading screen while the chosen model warms up in RAM.

### Loading screen

After selecting the workspace, the UI shows a loading card while Ollama
loads the model into memory. This typically takes a few seconds for small
models (gemma3:e2b) up to a minute for larger ones. The screen polls
`/models/status` once per second; when it returns `ready`, the workspace
opens automatically. If the warmup fails (model not pulled, Ollama not
running), the screen shows an error message instead.

### Workspace screen

Three columns:

- **Left (Workspace)**: file list, primary actions (Workspace / Add /
  Auto / Export), and cache controls (Reprocess / Clear ws / Clear all /
  Stats).
- **Center (Preview lens)**: the screenshot, full-width inside the column,
  fixed 50vh height. Initial state shows the clean original. Pressing OCR
  switches to a loading state (blurred backdrop + sweep light + spinner).
  After processing, it shows the cached preview with green/orange OCR
  boxes drawn on it. Wheel zoom and drag pan inside the frame.
- **Right (Control)**: OCR / Analyze / Previous / Next + per-severity
  counters and the issue list.

### Typical loop (single screenshot)

1. Workspace button → pick the folder of screenshots.
2. Wait for the loading screen → workspace opens.
3. **OCR** → runs the Tesseract+MSER pipeline.
4. **Analyze** → sends the OCR output to the LLM, results appear on the right.
5. **Add** → indexes the current screen's issues into the accumulator.
6. Move to the next image with **Next**.
7. When done, **Export** → opens a save dialog and writes the Excel report.

The **Auto** button runs the full loop (OCR → Analyze → Add → Next) across
all remaining images, then auto-exports. Implemented in
`Backend/static/js/API.js` as `runBatch()`.

---

## 5. Architecture

### High-level flow

```
folder of PNGs
      |
      v
  DPI (Backend/DPI.py)          <- workspace state, caches, prefetch
      |
      +--> screenshot_ocr.py    <- MSER + CLAHE + multi-PSM Tesseract
      |
      +--> region_prefilter.py  <- three-band classification by OCR confidence
      |
      +--> localQ.py            <- local Ollama LLM, JSON-strict
      |    (or gemini_qa.py)    <- cloud fallback (Gemini 2.5 Flash)
      |
      v
  Indexer.py                    <- 14-column row schema
      |
      v
  report_builder.py             <- openpyxl, embedded thumbnails, filters
      |
      v
  vivodpi_qa_report.xlsx
```

### File-by-file

| File | Purpose |
|------|---------|
| `Backend/__init__.py` | Flask app factory. All HTTP routes live here. |
| `Backend/env.py` | Config constants (paths, host/port, language, image extensions). |
| `Backend/DPI.py` | Workspace abstraction. Owns the in-memory + on-disk caches, the prefetch thread pool, and the path↔hash mapping. |
| `Backend/screenshot_ocr.py` | OCR pipeline: dual-MSER detection, IoU dedup, CLAHE per-region, multi-PSM voting. Runs at native resolution. |
| `Backend/region_prefilter.py` | Three-band classifier (send / context / noise) by OCR confidence. |
| `Backend/localQ.py` | Local LLM analysis via Ollama. One independent call per image. `think=False`, `num_ctx=16384`, compact JSON. Dynamic model via `set_model()`. |
| `Backend/gemini_qa.py` | Cloud LLM alternative (Gemini 2.5 Flash). Same `analyze_text` signature for drop-in swap. |
| `Backend/Indexer.py` | Accumulator + dispatch to `report_builder`. |
| `Backend/report_builder.py` | Excel generator: embedded thumbnails, red bbox annotation, color chips, auto-filter, conditional formatting. |
| `Backend/disk_cache.py` | Filesystem KV cache under `%APPDATA%/VivoDPI/cache/`. Namespaces: `ocr`, `qa`. Functions: `load`, `save`, `purge`, `purge_keys`, `stats`, `list_keys`. |
| `Backend/ollama_admin.py` | Model listing (`ollama list`), warmup state machine, "browse models" terminal launcher. |
| `Backend/logger.py` | Central logging. `get_logger(name)` plus `stream_token`/`stream_end` for LLM streaming. |
| `Backend/templates/*.html` | Jinja templates: `father.html` base, `index.html` landing, `Loading.html` model warmup, `workspace.html` main. |
| `Backend/static/js/API.js` | All frontend logic: HTTP calls, issue rendering, batch runner, zoom-pan preview, cache controls. |
| `Backend/static/css/main.css` | Dark theme + Bootstrap polish: workspace list items, preview frame, zoom controls, processing-card animation. |
| `main.py` | Entry point. Spawns Flask in a thread, waits for `/status`, opens the pywebview window. |

### Cache strategy

Two layers. Both keyed by `hash_image(path)` (MD5 of file size + first 64 KB).
Hashing means a workspace can be moved or renamed and the caches stay valid.

- **In-memory** (`DPI._ocr_cache`, `DPI._qa_cache`): one dict per workspace
  instance. Cleared when the workspace is replaced.
- **On disk** (`%APPDATA%/VivoDPI/cache/{ocr,qa}/<hash>.json`): survives
  app restarts. Plain JSON, one file per entry, atomic writes.

Lookup order on each request: memory → disk → process. A new result is
written to both layers.

The UI exposes the cache via four buttons (workspace pane):
- **Reprocess**: invalidate the current image (memory + disk) and re-run OCR.
- **Clear ws**: wipe only the entries belonging to the current workspace.
- **Clear all**: wipe the entire on-disk cache (all workspaces).
- **Stats**: show entries and size per namespace.

The "Start fresh" switch on the index page triggers Clear ws automatically
on the chosen workspace before processing begins.

### LLM pipeline (local)

For each screenshot:

```
raw_text (regions with confidence)
      |
      v
classify_regions  ──>  send (conf >= 0.95)    ──>  prompted as candidates
   (region_prefilter)   context (0.80–0.95)   ──>  prompted with ctx:true
                       noise (< 0.80)         ──>  goes straight into
                                                    ocr_warnings (never to LLM)
      |
      v
build user_prompt:
  - readable text (visual order)
  - raw_ocr JSON, separators=(",",":") for token economy
      |
      v
ollama.chat(model=<selected>, format="json", think=False, ...)
  - one independent call per image (no session history)
  - streaming via stream_token() so the user sees JSON live
      |
      v
parse + validate + clamp bbox + return
```

Key knobs (top of `localQ.py`):

- `OLLAMA_MODEL` — initial default; runtime-mutable via `set_model()` from the
  UI dropdown.
- `NUM_CTX = 16384` — context window. Bigger than strictly needed for dense
  Android screenshots, but eliminates truncation/reorganization that
  smaller values triggered.
- `KEEP_ALIVE = "30m"` — how long Ollama holds the model in RAM after
  the last call.
- `INFERENCE_OPTIONS` — temperature 0.1 (structured extraction, not
  generation), top_p 0.9, repeat_penalty 1.05.

`think=False` is critical for gemma3 e2b/e4b variants — they're reasoning
models that emit a hidden thought block before the JSON unless disabled.

### Region pre-filter

Three-band system. Tunable at the top of `region_prefilter.py`:

```python
SEND_CONF = 0.95     # >= goes to LLM as candidate
CONTEXT_CONF = 0.80  # >= and < SEND_CONF goes to LLM with ctx:true
                     # < CONTEXT_CONF is noise (ocr_warnings only)
```

Mojibake with confidence >= `SEND_CONF` is always routed to noise.
`MAX_REGIONS_TO_LLM = 120` caps the total `send + context` per prompt.

### Threading model

Single Flask process, multi-threaded:

- The HTTP server is Flask's default threaded server.
- `DPI` owns one `ThreadPoolExecutor(max_workers=1)` for prefetch.
- A per-hash `threading.Lock` deduplicates concurrent work.
- Ollama calls are blocking from Python's perspective; Ollama handles
  the model on its own process.
- `ollama_admin.warmup_model()` spawns a daemon thread so the UI never
  blocks waiting for the model to load.

### Configuration knobs at a glance

| Variable | File | Default | Why you'd change it |
|---|---|---|---|
| `HOST`, `PORT`, `DEBUG` | `env.py` | `127.0.0.1`, `5000`, `False` | Standard Flask settings |
| `LANGUAGE` | `env.py` | `"es"` | Shown in the UI navbar |
| `TESSERACT_PATH` | `env.py` | `./tesseract/tesseract.exe` | If Tesseract is installed elsewhere |
| `GEMINI_API_KEY` | `env.py` | `None` | Needed only if using the cloud QA backend |
| `OLLAMA_MODEL` | `localQ.py` | `"gemma3:e2b"` | Initial model; UI dropdown overrides it |
| `NUM_CTX` | `localQ.py` | `16384` | Decrease if low on RAM; increase if prompts overflow |
| `SEND_CONF`, `CONTEXT_CONF` | `region_prefilter.py` | `0.95`, `0.80` | Tune what reaches the LLM |
| `PREFETCH_LOOKAHEAD` | `DPI.py` | `3` | How many images to OCR in background |
| `OCR_MAX_SIDE` | `screenshot_ocr.py` | (no global downscale) | OCR runs at native resolution |
| `DPI_LOG_LEVEL` | env var | `INFO` | Set to `WARN` for quieter batch runs |
| `DPI_LOG_STREAM` | env var | `1` | Set to `0` to silence LLM token stream |

---

## 6. HTTP Endpoints

Cache:
- `GET  /cache/stats` — namespaces, entries, sizes.
- `POST /cache/purge` — wipe all on-disk cache.
- `POST /cache/purge/workspace` — wipe cache of the current workspace.
- `POST /cache/purge/current` — invalidate current image.

Models:
- `GET  /models/list` — `{available, models, current}`.
- `POST /models/select` body `{name}` — switch active model and warmup.
- `POST /models/browse` — open a cmd terminal with `ollama pull` instructions.
- `POST /models/warmup` — pre-load the current model.
- `GET  /models/status` — current warmup state (used by the loading screen).

Workspace / processing:
- `POST /selectFolder` body `{reset_cache}` — pick folder, optionally
  clear its cache, kick off model warmup. Returns redirect to `/model_loading`.
- `GET  /model_loading` — Loading.html with polling.
- `GET  /workspace` — main UI.
- `POST /process_image` — OCR for the current image index.
- `POST /review_image` — LLM analysis (OCR runs first if needed).
- `POST /processData` — accumulate one image's issues into the report.
- `POST /saveReport` — flush accumulator to Excel via `report_builder`.

---

## 7. Excel Output Schema

`Backend/report_builder.py` produces a single-sheet workbook with 14
columns, AutoFilter enabled, frozen header row, conditional formatting on
severity, and embedded thumbnails (one per row).

| Column | Type | Notes |
|---|---|---|
| Type | chip | `ISSUE` (red) / `WARNING` (amber) |
| Severity | chip | `high` red / `medium` orange / `low` yellow / `info` green |
| Screenshot | text | Basename of the source file |
| Annotated | image | Embedded thumbnail with a red 4-px rectangle around the issue's bbox. Warnings show the clean image without a rectangle. |
| Category | text | One of 13 LLM categories, or `OCR Noise` for warnings |
| OCR Text | text (mono) | Verbatim OCR output for the region |
| Suggestion | text (mono) | Drop-in replacement from the LLM; for warnings, the reason for the discard |
| Explanation (ES) | text | LLM rationale, Spanish, 1–2 sentences |
| Explanation (EN) | text | Same rationale, English |
| LLM Confidence | chip | green / amber / grey |
| OCR Trust | float | Mean OCR confidence of the regions backing the issue |
| Region IDs | text | Comma-separated region IDs from the OCR raw_text |
| Pre-Filtered | bool | Was this row routed by the pre-filter (warnings) or by the LLM (issues) |
| Source Path | text (hidden by default) | Full path on disk; useful for the dev to open the file |

Row backgrounds: ISSUE rows have a soft red fill, WARNING rows have a
pale yellow fill, so even at a glance the type is obvious.

Image dimensions: thumbnails are scaled to fit a 240×360 px box (aspect
ratio preserved). Very tall scroll-style captures become narrow strips
inside the box rather than blowing up the row height.

---

## 8. Debugging Tips

- **Logs**: format is `[HH:MM:SS] [MODULE] message`. Modules: `HTTP`,
  `DPI`, `OCR`, `LLM`, `CACHE`, `REPORT`, `OLLAMA`. Silence streaming with
  `DPI_LOG_STREAM=0`.

- **Cache misbehaving**: delete `%APPDATA%\VivoDPI\cache` and reopen the
  workspace, or use the "Clear all" button. The cache is plain JSON, you
  can inspect individual files.

- **Stale interface**: pywebview / Chromium cache HTML aggressively.
  If a UI change doesn't show up, hit `Ctrl+F5` inside the window or
  delete `%LOCALAPPDATA%\pywebview`.

- **Bboxes off**: bboxes are reported in the **original** image coordinate
  space. The OCR pipeline runs at native resolution, so the
  back-projection step is the identity — if they're off, the issue is
  upstream (MSER produced a wrong bbox).

- **Model not found**: run `ollama list` to see what's installed; pull the
  missing model. The dropdown on the index page calls `ollama list` and
  shows the result; if it says "Ollama not detected in PATH", the
  `ollama` command isn't reachable from the Python process.

- **Warmup stuck**: check `/models/status` directly in the browser. If it
  stays in `loading` forever, the Ollama service is unresponsive — restart
  it. If it goes to `error`, the message field tells you why.