<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VivoDPI — Internal Documentation</title>
<style>
  :root {
    --bg:          #1a1d21;
    --surface:     #212529;
    --surface-2:   #2a2e33;
    --border:      #3a3f47;
    --primary:     #0d6efd;
    --primary-soft: rgba(13, 110, 253, 0.12);
    --text:        #f1f3f5;
    --text-muted:  #adb5bd;
    --text-dim:    #78909c;
    --green:       #2e7d32;
    --orange:      #f57c00;
    --red:         #d32f2f;
    --yellow:      #fbc02d;
    --mono: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }

  .wrapper {
    max-width: 980px;
    margin: 0 auto;
    padding: 4rem 2rem 6rem;
  }

  /* Header */
  header.doc-header {
    border-bottom: 1px solid var(--border);
    padding-bottom: 2rem;
    margin-bottom: 3rem;
  }
  .eyebrow {
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 0.6rem;
  }
  h1 {
    font-size: 3rem;
    font-weight: 800;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.02em;
    line-height: 1.1;
  }
  h1 .accent { color: var(--primary); }
  .subtitle {
    color: var(--text-muted);
    font-size: 1.1rem;
    max-width: 70ch;
  }

  /* Headings */
  h2 {
    font-size: 1.7rem;
    font-weight: 700;
    margin: 3.5rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
    letter-spacing: -0.01em;
  }
  h2 .num {
    display: inline-block;
    color: var(--primary);
    margin-right: 0.6rem;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
  }
  h3 {
    font-size: 1.15rem;
    font-weight: 600;
    margin: 2rem 0 0.8rem;
    color: var(--text);
  }

  p { margin: 0 0 1rem; color: var(--text); }
  p.muted { color: var(--text-muted); }

  /* Links */
  a {
    color: var(--primary);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.15s ease;
  }
  a:hover { border-bottom-color: var(--primary); }

  /* Inline code */
  code {
    font-family: var(--mono);
    font-size: 0.88em;
    background: var(--surface-2);
    color: var(--primary);
    padding: 0.12em 0.42em;
    border-radius: 4px;
    border: 1px solid var(--border);
  }

  /* Code blocks */
  pre {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--primary);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    overflow-x: auto;
    margin: 1rem 0 1.5rem;
    font-family: var(--mono);
    font-size: 0.85rem;
    color: var(--text);
    line-height: 1.55;
  }
  pre code {
    background: transparent;
    border: none;
    color: inherit;
    padding: 0;
    border-radius: 0;
    font-size: inherit;
  }

  /* Lists */
  ul, ol { padding-left: 1.4rem; margin: 0 0 1.25rem; }
  li { margin-bottom: 0.4rem; }
  ul ul, ol ol { margin-top: 0.4rem; }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0 2rem;
    font-size: 0.92rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  th {
    text-align: left;
    background: var(--surface-2);
    color: var(--text);
    padding: 0.7rem 1rem;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  td {
    padding: 0.7rem 1rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    color: var(--text-muted);
  }
  tr:last-child td { border-bottom: none; }
  td code { font-size: 0.85em; }

  /* Callouts */
  .callout {
    background: var(--primary-soft);
    border-left: 3px solid var(--primary);
    padding: 1rem 1.25rem;
    margin: 1.5rem 0;
    border-radius: 0 8px 8px 0;
    color: var(--text);
  }
  .callout strong { color: var(--primary); }

  /* TOC */
  nav.toc {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 3rem;
  }
  nav.toc h4 {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-muted);
    margin: 0 0 0.8rem;
  }
  nav.toc ol {
    list-style: none;
    padding: 0;
    margin: 0;
    counter-reset: toc-counter;
  }
  nav.toc li {
    counter-increment: toc-counter;
    margin-bottom: 0.3rem;
  }
  nav.toc li::before {
    content: counter(toc-counter, decimal-leading-zero) "  ";
    color: var(--text-dim);
    font-family: var(--mono);
    font-size: 0.85em;
  }
  nav.toc a { border: none; }

  /* Footer */
  footer.doc-footer {
    margin-top: 5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 0.85rem;
    text-align: center;
  }

  /* Severity color chips inline */
  .chip {
    display: inline-block;
    padding: 0.08em 0.55em;
    border-radius: 3px;
    color: #fff;
    font-size: 0.78em;
    font-weight: 600;
    margin-right: 0.2em;
    vertical-align: baseline;
  }
  .chip.red    { background: var(--red); }
  .chip.orange { background: var(--orange); }
  .chip.yellow { background: var(--yellow); color: #2a2e33; }
  .chip.green  { background: var(--green); }
</style>
</head>
<body>

<div class="wrapper">

  <header class="doc-header">
    <div class="eyebrow">Internal Documentation · QA Tool</div>
    <h1>Vivo<span class="accent">DPI</span></h1>
    <p class="subtitle">
      Internal QA tooling for Spanish (LATAM) localization auditing of Android
      screenshots. Combines computer-vision OCR (Tesseract + MSER) with LLM-based
      linguistic review to surface defects: spelling, grammar, mistranslations,
      untranslated strings, UI truncation, inconsistencies, etc. Output is a
      consolidated Excel report with embedded annotated screenshots and a
      14-column schema ready for follow-up by the dev team.
    </p>
  </header>

  <nav class="toc">
    <h4>Contents</h4>
    <ol>
      <li><a href="#s1">Base Tools Installation</a></li>
      <li><a href="#s2">Project Environment Setup</a></li>
      <li><a href="#s3">Running</a></li>
      <li><a href="#s4">User-Facing Workflow</a></li>
      <li><a href="#s5">Architecture</a></li>
      <li><a href="#s6">HTTP Endpoints</a></li>
      <li><a href="#s7">Excel Output Schema</a></li>
      <li><a href="#s8">Debugging Tips</a></li>
    </ol>
  </nav>

  <!-- ====================================================== -->
  <h2 id="s1"><span class="num">01</span>Base Tools Installation</h2>

  <p>Run the installers located in <code>./bin</code> in this order:</p>

  <h3>1. Python 3.12.10</h3>
  <p>During installation, check <strong>"Add Python 3.12 to PATH"</strong> before clicking "Install Now".</p>

  <h3>2. Tesseract OCR</h3>
  <p>
    Run <code>tesseract-ocr-w64-setup-5.5.0.20241111.exe</code>.
    Select all additional language and script packages during install. The
    pipeline currently calls Tesseract with <code>-l spa</code> (Spanish);
    that string is hardcoded in <code>screenshot_ocr.py::_run_tess()</code>
    and is the only place to change if you ever switch the operating
    language. During the Tesseract installation, change the destination
    path to <code>./tesseract</code> (relative to the project root). The
    path is resolved by <code>Backend/env.py</code>.
  </p>

  <h3>3. Ollama</h3>
  <p>Run <code>OllamaSetup.exe</code> with default options. After installation, pull a starter model:</p>
  <pre><code>ollama pull gemma4:e2b</code></pre>
  <p>
    <code>gemma4:e2b</code> is the default that <code>localQ.py</code>
    reads at startup, but the active model is mutable at runtime: the
    dropdown on the index page calls <code>ollama list</code> and the
    user's pick takes effect for the rest of the session via
    <code>set_model()</code>. The "+ Add model" button opens a styled
    PowerShell window with <code>ollama pull</code> guidance to install
    additional models without leaving the app.
  </p>

  <!-- ====================================================== -->
  <h2 id="s2"><span class="num">02</span>Project Environment Setup</h2>

  <p>From the project root, in CMD or PowerShell:</p>
  <pre><code>prepare_env.bat</code></pre>
  <p>
    Creates a virtualenv at <code>./venv</code> and installs everything in
    <code>requirements.txt</code>. First time you install Python or
    Tesseract you may need to restart the terminal or IDE for PATH changes
    to take effect.
  </p>

  <!-- ====================================================== -->
  <h2 id="s3"><span class="num">03</span>Running</h2>

  <pre><code>launch.bat</code></pre>
  <p>
    The launcher activates the venv at <code>./venv</code> and runs
    <code>main.py</code>, which spawns the Flask backend on
    <code>http://127.0.0.1:5000</code> in a thread and opens a pywebview
    window pointing at it. Stop the application by closing the window. The
    Ollama service runs as a separate process and is unaffected.
  </p>
  <p>
    A native Tkinter dialog is used for folder selection, so the very
    first interaction (clicking "Select directory") spawns a system-modal
    OS picker — this is expected, not a glitch.
  </p>

  <!-- ====================================================== -->
  <h2 id="s4"><span class="num">04</span>User-Facing Workflow</h2>

  <h3>Index page</h3>
  <p>The landing page presents:</p>
  <ul>
    <li><strong>Ollama Model dropdown</strong> populated from <code>ollama list</code> at page load. Pick the model for this session.</li>
    <li><strong>+ Add model</strong> opens a styled PowerShell window with <code>ollama pull</code> instructions.</li>
    <li><strong>Start fresh toggle</strong>: if checked, the disk cache for the chosen workspace is wiped before processing begins.</li>
    <li><strong>Select directory</strong>: opens the native Tkinter folder picker, then routes through a loading screen while the chosen model warms up in RAM.</li>
  </ul>

  <h3>Loading screen</h3>
  <p>
    After selecting the workspace, a loading card appears while Ollama
    loads the model into memory. Duration depends on model size and disk
    speed. The screen polls <code>/models/status</code> once per second;
    when it returns <code>ready</code>, the workspace opens automatically.
    On failure (model not pulled, Ollama not running, etc.), an error
    message is shown with the underlying cause.
  </p>

  <h3>Workspace screen</h3>
  <p>Three columns:</p>
  <ul>
    <li><strong>Left (Workspace)</strong>: file list, primary actions (Workspace / Add / Auto / Export) and cache controls (Reprocess / Clear ws / Clear all / Stats).</li>
    <li><strong>Center (Preview lens)</strong>: the screenshot, full-width inside the column, fixed 50vh height. Initial state shows the clean original. Pressing OCR switches to a loading state (blurred backdrop + sweep light + spinner). After processing, it shows the cached preview with green/orange OCR boxes. Wheel zoom and drag pan inside the frame.</li>
    <li><strong>Right (Control)</strong>: OCR / Analyze / Previous / Next plus per-severity counters and the issue list.</li>
  </ul>

  <h3>Typical loop (single screenshot)</h3>
  <ol>
    <li><strong>Workspace</strong> → pick the folder of screenshots.</li>
    <li>Wait for the loading screen → workspace opens.</li>
    <li><strong>OCR</strong> → runs the Tesseract+MSER pipeline.</li>
    <li><strong>Analyze</strong> → sends the OCR output to the LLM, results appear on the right.</li>
    <li><strong>Add</strong> → indexes the current screen's issues into the accumulator.</li>
    <li>Move to the next image with <strong>Next</strong>.</li>
    <li>When done, <strong>Export</strong> → opens a save dialog and writes the Excel report.</li>
  </ol>
  <p>
    The <strong>Auto</strong> button runs the full loop (OCR → Analyze → Add → Next) across
    all remaining images, then auto-exports. Implemented in
    <code>Backend/static/js/API.js</code> as <code>runBatch()</code>.
  </p>

  <!-- ====================================================== -->
  <h2 id="s5"><span class="num">05</span>Architecture</h2>

  <h3>High-level flow</h3>
  <pre><code>folder of PNGs
      |
      v
  DPI (Backend/DPI.py)          &lt;- workspace state, caches, prefetch
      |
      +--&gt; screenshot_ocr.py    &lt;- MSER + CLAHE + multi-PSM Tesseract
      |
      +--&gt; region_prefilter.py  &lt;- three-band classification by OCR confidence
      |
      +--&gt; localQ.py            &lt;- local Ollama LLM, JSON-strict
      |                            (or gemini_qa.py for cloud, manual swap)
      |
      v
  Indexer.py                    &lt;- accumulator + dispatch
      |
      v
  report_builder.py             &lt;- 14-column schema, openpyxl, thumbnails
      |
      v
  vivodpi_qa_report.xlsx</code></pre>

  <div class="callout">
    <strong>About the Gemini fallback:</strong> the cloud QA backend is
    not an automatic failover. It is a drop-in module with the same
    <code>analyze_text(text, raw_text)</code> signature. To use it,
    edit <code>Backend/DPI.py</code> and switch the
    <code>from .localQ import analyze_text</code> line to
    <code>from .gemini_qa import analyze_text</code>. A valid
    <code>GEMINI_API_KEY</code> in <code>env.py</code> is required.
  </div>

  <h3>File-by-file</h3>
  <table>
    <thead><tr><th>File</th><th>Purpose</th></tr></thead>
    <tbody>
      <tr><td><code>Backend/__init__.py</code></td><td>Flask app factory. All HTTP routes live here.</td></tr>
      <tr><td><code>Backend/env.py</code></td><td>Config constants (paths, host/port, language, image extensions).</td></tr>
      <tr><td><code>Backend/DPI.py</code></td><td>Workspace abstraction. Owns the in-memory + on-disk caches, the prefetch thread pool, and the path↔hash mapping.</td></tr>
      <tr><td><code>Backend/screenshot_ocr.py</code></td><td>OCR pipeline: dual-MSER detection, IoU dedup, CLAHE per-region, multi-PSM voting. Runs at native resolution.</td></tr>
      <tr><td><code>Backend/region_prefilter.py</code></td><td>Three-band classifier (send / context / noise) by OCR confidence.</td></tr>
      <tr><td><code>Backend/localQ.py</code></td><td>Local LLM via Ollama. One independent call per image. <code>think=False</code>, <code>num_ctx=16384</code>. Active model mutable at runtime via <code>set_model()</code>.</td></tr>
      <tr><td><code>Backend/gemini_qa.py</code></td><td>Cloud LLM alternative (Gemini 2.5 Flash). Same <code>analyze_text</code> signature. Manual drop-in, no automatic fallback.</td></tr>
      <tr><td><code>Backend/Indexer.py</code></td><td>Accumulator. Receives one image's results, normalizes them into row dicts, and stores them in a global list. Delegates Excel generation to <code>report_builder</code>.</td></tr>
      <tr><td><code>Backend/report_builder.py</code></td><td>Excel generator with the 14-column schema: embedded thumbnails, red bbox annotation, color chips, auto-filter, conditional formatting.</td></tr>
      <tr><td><code>Backend/disk_cache.py</code></td><td>Filesystem KV cache under <code>%APPDATA%/VivoDPI/cache/</code> (Windows) or <code>~/.cache/VivoDPI/</code> (others). Namespaces: <code>ocr</code>, <code>qa</code>.</td></tr>
      <tr><td><code>Backend/ollama_admin.py</code></td><td>Model listing (<code>ollama list</code>), warmup state machine, "browse models" terminal launcher (PowerShell with ANSI styling).</td></tr>
      <tr><td><code>Backend/logger.py</code></td><td>Central logging. <code>get_logger(name)</code> plus <code>stream_token</code>/<code>stream_end</code> for LLM streaming. Modules in use: <code>HTTP</code>, <code>DPI</code>, <code>OCR</code>, <code>LLM</code>, <code>CACHE</code>, <code>REPORT</code>, <code>INDEX</code>, <code>OLLAMA</code>.</td></tr>
      <tr><td><code>Backend/templates/*.html</code></td><td>Jinja templates: <code>father.html</code> base, <code>index.html</code> landing, <code>Loading.html</code> model warmup, <code>workspace.html</code> main.</td></tr>
      <tr><td><code>Backend/static/js/API.js</code></td><td>All frontend logic: HTTP calls, issue rendering, batch runner, zoom-pan preview, cache controls.</td></tr>
      <tr><td><code>Backend/static/css/main.css</code></td><td>Custom CSS layered on top of Bootstrap 5: workspace list polish, preview frame, zoom controls, the blue "sweep light" animation used during processing.</td></tr>
      <tr><td><code>main.py</code></td><td>Entry point. Spawns Flask in a thread, polls <code>/status</code> until the server responds, then opens the pywebview window.</td></tr>
    </tbody>
  </table>

  <h3>Cache strategy</h3>
  <p>
    Two layers, both keyed by <code>hash_image(path)</code> (MD5 of file
    size + first 64 KB). Hashing means a workspace can be moved or renamed
    and the caches stay valid.
  </p>
  <ul>
    <li><strong>In-memory</strong> (<code>DPI._ocr_cache</code>, <code>DPI._qa_cache</code>): one dict per workspace instance. Cleared when the workspace is replaced.</li>
    <li><strong>On disk</strong> (<code>%APPDATA%/VivoDPI/cache/{ocr,qa}/&lt;hash&gt;.json</code> on Windows; <code>~/.cache/VivoDPI/...</code> elsewhere): survives app restarts. Plain JSON, one file per entry, atomic writes.</li>
  </ul>
  <p>Lookup order on each request: memory → disk → process. A new result is written to both layers.</p>
  <p>The UI exposes four cache controls (workspace pane):</p>
  <ul>
    <li><strong>Reprocess</strong>: invalidate the current image (memory + disk) and re-run OCR.</li>
    <li><strong>Clear ws</strong>: wipe only the entries belonging to the current workspace.</li>
    <li><strong>Clear all</strong>: wipe the entire on-disk cache (all workspaces).</li>
    <li><strong>Stats</strong>: show entries and size per namespace.</li>
  </ul>

  <h3>LLM pipeline (local)</h3>
  <pre><code>raw_text (regions with confidence)
      |
      v
classify_regions  ──&gt;  send (conf &gt;= 0.95)    ──&gt;  prompted as candidates
   (region_prefilter)   context (0.80–0.95)   ──&gt;  prompted with ctx:true
                       noise (&lt; 0.80)         ──&gt;  goes straight into
                                                    ocr_warnings (never to LLM)
      |
      v
build user_prompt:
  - readable text (visual order)
  - raw_ocr JSON, separators=(",",":")
      |
      v
ollama.chat(model=&lt;selected&gt;, format="json", think=False, ...)
      |
      v
parse + validate + clamp bbox + return</code></pre>

  <div class="callout">
    <strong>think=False is critical</strong> for gemma4 e2b/e4b variants —
    they are reasoning models that emit a hidden thought block before the
    JSON unless disabled. Without this flag the first-token latency
    balloons by minutes on CPU. The flag is hardcoded in
    <code>localQ.py::_call_ollama()</code>.
  </div>

  <h3>Region pre-filter</h3>
  <p>Three-band system. Tunable at the top of <code>region_prefilter.py</code>:</p>
  <pre><code>SEND_CONF = 0.95     # &gt;= goes to LLM as candidate
CONTEXT_CONF = 0.80  # &gt;= and &lt; SEND_CONF goes to LLM with ctx:true
                     # &lt; CONTEXT_CONF is noise (ocr_warnings only)</code></pre>
  <p>
    Mojibake with confidence &gt;= <code>SEND_CONF</code> is always routed
    to noise (set <code>DROP_HIGH_CONF_MOJIBAKE = False</code> to disable
    that behavior). <code>MAX_REGIONS_TO_LLM = 120</code> caps the total
    <code>send + context</code> per prompt.
  </p>

  <h3>Configuration knobs at a glance</h3>
  <table>
    <thead><tr><th>Variable</th><th>File</th><th>Default</th><th>Notes</th></tr></thead>
    <tbody>
      <tr><td><code>HOST</code>, <code>PORT</code>, <code>DEBUG</code></td><td><code>env.py</code></td><td><code>127.0.0.1</code>, <code>5000</code>, <code>False</code></td><td>Standard Flask settings</td></tr>
      <tr><td><code>LANGUAGE</code></td><td><code>env.py</code></td><td><code>"es"</code></td><td>Shown in the UI navbar</td></tr>
      <tr><td><code>TESSERACT_PATH</code></td><td><code>env.py</code></td><td><code>./tesseract/tesseract.exe</code></td><td>If Tesseract is installed elsewhere</td></tr>
      <tr><td><code>GEMINI_API_KEY</code></td><td><code>env.py</code></td><td><code>None</code></td><td>Required only if switching to the cloud QA backend</td></tr>
      <tr><td><code>OLLAMA_MODEL</code></td><td><code>localQ.py</code></td><td><code>"gemma4:e2b"</code></td><td>Initial model; the UI dropdown overrides it for the running session</td></tr>
      <tr><td><code>NUM_CTX</code></td><td><code>localQ.py</code></td><td><code>16384</code></td><td>Decrease if low on RAM; increase only if prompts overflow</td></tr>
      <tr><td><code>KEEP_ALIVE</code></td><td><code>localQ.py</code></td><td><code>"30m"</code></td><td>How long Ollama keeps the model in RAM after the last call</td></tr>
      <tr><td><code>SEND_CONF</code>, <code>CONTEXT_CONF</code></td><td><code>region_prefilter.py</code></td><td><code>0.95</code>, <code>0.80</code></td><td>Tune what reaches the LLM</td></tr>
      <tr><td><code>MAX_REGIONS_TO_LLM</code></td><td><code>region_prefilter.py</code></td><td><code>120</code></td><td>Cap on <code>send + context</code> per prompt</td></tr>
      <tr><td><code>PREFETCH_LOOKAHEAD</code></td><td><code>DPI.py</code></td><td><code>3</code></td><td>How many images to OCR in background</td></tr>
      <tr><td><code>DPI_LOG_LEVEL</code></td><td>env var</td><td><code>INFO</code></td><td>Set to <code>WARN</code> for quieter batch runs</td></tr>
      <tr><td><code>DPI_LOG_STREAM</code></td><td>env var</td><td><code>1</code></td><td>Set to <code>0</code> to silence LLM token stream</td></tr>
    </tbody>
  </table>

  <!-- ====================================================== -->
  <h2 id="s6"><span class="num">06</span>HTTP Endpoints</h2>

  <h3>Cache</h3>
  <ul>
    <li><code>GET /cache/stats</code> — namespaces, entries, sizes.</li>
    <li><code>POST /cache/purge</code> — wipe all on-disk cache.</li>
    <li><code>POST /cache/purge/workspace</code> — wipe cache of the current workspace.</li>
    <li><code>POST /cache/purge/current</code> — invalidate current image.</li>
  </ul>

  <h3>Models</h3>
  <ul>
    <li><code>GET /models/list</code> — <code>{available, models, current}</code>.</li>
    <li><code>POST /models/select</code> body <code>{name}</code> — switch active model and warmup.</li>
    <li><code>POST /models/browse</code> — open a styled PowerShell terminal with <code>ollama pull</code> instructions.</li>
    <li><code>POST /models/warmup</code> — pre-load the current model.</li>
    <li><code>GET /models/status</code> — current warmup state (used by the loading screen).</li>
  </ul>

  <h3>Workspace / processing</h3>
  <ul>
    <li><code>GET /status</code> — minimal "Flask is up" probe. Used by <code>main.py</code> to know when to open the pywebview window.</li>
    <li><code>GET /</code> — index page.</li>
    <li><code>POST /selectFolder</code> body <code>{reset_cache}</code> — pick folder, optionally clear its cache, kick off model warmup. Returns redirect to <code>/model_loading</code>.</li>
    <li><code>GET /model_loading</code> — loading screen with polling.</li>
    <li><code>GET /workspace</code> — main UI.</li>
    <li><code>POST /next</code>, <code>POST /prev</code> — navigation.</li>
    <li><code>GET /img/&lt;path&gt;</code> — serves an image from the workspace folder (path-restricted to the current workspace).</li>
    <li><code>POST /process_image</code> — OCR for the current image index.</li>
    <li><code>POST /review_image</code> — LLM analysis (OCR runs first if needed).</li>
    <li><code>POST /processData</code> — accumulate one image's issues into the report.</li>
    <li><code>POST /saveReport</code> — flush accumulator to Excel.</li>
  </ul>

  <!-- ====================================================== -->
  <h2 id="s7"><span class="num">07</span>Excel Output Schema</h2>

  <p>
    <code>Backend/report_builder.py</code> produces a single-sheet workbook
    with 14 columns, AutoFilter enabled, frozen header row, conditional
    formatting on severity, and embedded thumbnails (one per row).
  </p>

  <table>
    <thead><tr><th>Column</th><th>Type</th><th>Notes</th></tr></thead>
    <tbody>
      <tr><td>Type</td><td>chip</td><td><span class="chip red">ISSUE</span> / <span class="chip orange">WARNING</span></td></tr>
      <tr><td>Severity</td><td>chip</td><td><span class="chip red">high</span> <span class="chip orange">medium</span> <span class="chip yellow">low</span> <span class="chip green">info</span></td></tr>
      <tr><td>Screenshot</td><td>text</td><td>Basename of the source file</td></tr>
      <tr><td>Annotated</td><td>image</td><td>Embedded thumbnail with a red 4-px rectangle around the issue's bbox. Warnings show the clean image without a rectangle.</td></tr>
      <tr><td>Category</td><td>text</td><td>One of 13 LLM categories, or <code>OCR Noise</code> for warnings.</td></tr>
      <tr><td>OCR Text</td><td>mono</td><td>Verbatim OCR output.</td></tr>
      <tr><td>Suggestion</td><td>mono</td><td>Drop-in replacement from the LLM; for warnings, the reason for the discard.</td></tr>
      <tr><td>Explanation (ES)</td><td>text</td><td>LLM rationale, Spanish, 1–2 sentences.</td></tr>
      <tr><td>Explanation (EN)</td><td>text</td><td>Same rationale, English.</td></tr>
      <tr><td>LLM Confidence</td><td>chip</td><td>green / amber / grey.</td></tr>
      <tr><td>OCR Trust</td><td>float</td><td>Mean OCR confidence of the regions backing the issue.</td></tr>
      <tr><td>Region IDs</td><td>text</td><td>Comma-separated region IDs from the OCR raw_text.</td></tr>
      <tr><td>Pre-Filtered</td><td>bool</td><td>Was this row routed by the pre-filter (warnings) or by the LLM (issues).</td></tr>
      <tr><td>Source Path</td><td>text</td><td><em>Hidden by default.</em> Full path on disk; useful for the dev to open the file.</td></tr>
    </tbody>
  </table>

  <p>
    Row backgrounds: ISSUE rows have a soft red fill, WARNING rows a pale
    yellow fill — at a glance the type is obvious. Thumbnails are scaled to
    fit a 240×360 px box (aspect ratio preserved). Very tall scroll-style
    captures become narrow strips inside the box rather than blowing up the
    row height. Images are anchored to their cells with <code>TwoCellAnchor</code>
    + <code>editAs="oneCell"</code>, so they move and resize together with
    the cell when the table is filtered or sorted.
  </p>

  <!-- ====================================================== -->
  <h2 id="s8"><span class="num">08</span>Debugging Tips</h2>

  <h3>Logs</h3>
  <p>
    Format is <code>[HH:MM:SS] [MODULE] message</code>. Modules in use:
    <code>HTTP</code>, <code>DPI</code>, <code>OCR</code>, <code>LLM</code>,
    <code>CACHE</code>, <code>REPORT</code>, <code>INDEX</code>,
    <code>OLLAMA</code>. Silence streaming with <code>DPI_LOG_STREAM=0</code>;
    raise the verbosity floor with <code>DPI_LOG_LEVEL=WARN</code> for batch
    runs.
  </p>

  <h3>Cache misbehaving</h3>
  <p>
    Delete <code>%APPDATA%\VivoDPI\cache</code> and reopen the workspace,
    or use the "Clear all" button. The cache is plain JSON, you can
    inspect individual files.
  </p>

  <h3>Stale interface</h3>
  <p>
    pywebview / Chromium cache HTML aggressively. If a UI change doesn't
    show up, hit <code>Ctrl+F5</code> inside the window or delete
    <code>%LOCALAPPDATA%\pywebview</code>.
  </p>

  <h3>Bboxes off</h3>
  <p>
    Bboxes are reported in the <strong>original</strong> image coordinate
    space. The OCR pipeline runs at native resolution, so the
    back-projection step is the identity — if they're off, the issue is
    upstream (MSER produced a wrong bbox).
  </p>

  <h3>Model not found</h3>
  <p>
    Run <code>ollama list</code> to see what's installed; pull the missing
    model. The dropdown on the index page calls <code>ollama list</code> and
    shows the result; if it says "Ollama not detected in PATH", the
    <code>ollama</code> command isn't reachable from the Python process.
  </p>

  <h3>Warmup stuck</h3>
  <p>
    Check <code>/models/status</code> directly in the browser. If it stays
    in <code>loading</code> forever, the Ollama service is unresponsive —
    restart it. If it goes to <code>error</code>, the message field tells
    you why.
  </p>

  <footer class="doc-footer">
    VivoDPI · Internal tooling · Build 1.0.0
  </footer>

</div>
</body>
</html>
