/* =========================================================================
   API.js — VivoDPI frontend logic
   Endpoints: /selectFolder, /next, /prev, /process_image, /review_image,
              /processData, /saveReport, /cache/*, /models/*
   ========================================================================= */

// SelectFolder now sends the "reset cache" toggle if the switch is checked.
function SelectFolder() {
    const reset = document.getElementById('resetCacheSwitch');
    const payload = { reset_cache: !!(reset && reset.checked) };

    // Also send the model selected in the dropdown (if any).
    const sel = document.getElementById('modelSelect');
    const chosen = sel && sel.value ? sel.value : null;

    // First, switch the model so the workspace warmup picks it up.
    const setModelPromise = chosen
        ? fetch('/models/select', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name: chosen }),
          }).catch(err => console.warn('[MODEL] select failed:', err))
        : Promise.resolve();

    setModelPromise.then(() => {
        return fetch('/selectFolder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    })
    .then(r => r.json())
    .then(data => window.location.href = data.redirect);
}


// ── Add new model: opens a terminal with instructions ─────────────
function addNewModel() {
    fetch('/models/browse', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'OK') {
                showToast('Terminal de modelos abierta. Refresca la lista cuando termines.', 'info', 5000);
                // After 8s, repopulate the dropdown in case the user downloaded
                // something. Cheap and friendly.
                setTimeout(() => location.reload(), 8000);
            } else {
                showToast('No se pudo abrir la terminal.', 'danger');
            }
        })
        .catch(err => showToast(`Error: ${err}`, 'danger'));
}


function Next() {
    fetch('/next', { method: 'POST' })
        .then(r => r.json())
        .then(data => window.location.href = data.refresh);
}

function Prev() {
    fetch('/prev', { method: 'POST' })
        .then(r => r.json())
        .then(data => window.location.href = data.refresh);
}


// ── ProcessImage chains into ReviewImage on reload (via sessionStorage) ──
function ProcessImage() {
    document.getElementById('image-content').classList.add('d-none');
    document.getElementById('loading-state').classList.remove('d-none');

    document.getElementById('gemini-content').classList.add('d-none');
    document.getElementById('gemini-loading-state').classList.remove('d-none');

    fetch('/process_image', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            sessionStorage.setItem('autoReview', '1');
            window.location.href = data.refresh;
        })
        .catch(err => {
            console.error(err);
            document.getElementById('image-content').classList.remove('d-none');
            document.getElementById('loading-state').classList.add('d-none');
        });
}


// ── Global Gemini result state ────────────────────────────────────
let geminiData = {};
let geminiSummary = '';
let geminiIssues = [];
let geminiOcrWarnings = [];

// Parallel lists (granular access)
let issueTexts = [];
let issueTypes = [];
let issueSeverities = [];
let issueSuggestions = [];
let issueExplanations = [];


async function ReviewImage() {
    document.getElementById('gemini-content').classList.add('d-none');
    document.getElementById('gemini-loading-state').classList.remove('d-none');

    document.getElementById('gemini-summary').textContent = 'Analyzing...';
    document.getElementById('gemini-issues').innerHTML = '';
    document.getElementById('gemini-issues-count').textContent = '0';
    document.getElementById('count-alta').textContent = '0';
    document.getElementById('count-media').textContent = '0';
    document.getElementById('count-baja').textContent = '0';

    const rawJsonEl = document.getElementById('gemini-raw-json');
    if (rawJsonEl) {
        rawJsonEl.textContent = 'Analyzing...';
    }

    geminiData = {};
    geminiSummary = '';
    geminiIssues = [];
    geminiOcrWarnings = [];
    issueTexts = [];
    issueTypes = [];
    issueSeverities = [];
    issueSuggestions = [];
    issueExplanations = [];

    try {
        const res = await fetch('/review_image', { method: 'POST' });
        const data = await res.json();

        if (data.error) {
            document.getElementById('gemini-summary').textContent = `Error: ${data.error}`;
            if (rawJsonEl) rawJsonEl.textContent = JSON.stringify(data, null, 2);
            return;
        }

        // Adapter: map LLM schema to the format the rest of the JS expects.
        // CRITICAL: preserve explanation_en so collectData can forward it.
        const sevMap = { high: 'alta', medium: 'media', low: 'baja' };
        const rawIssues = data.issues || [];
        const normalizedIssues = rawIssues.map(i => ({
            text:           i.text_excerpt    ?? i.text         ?? '',
            type:           i.category        ?? i.type         ?? '',
            severity:       sevMap[i.severity] ?? i.severity    ?? '',
            suggestion:     i.suggestion      ?? '',
            explanation:    i.explanation     ?? '',
            explanation_en: i.explanation_en  ?? '',
            bbox:           i.bbox            ?? null,
            region_ids:     i.region_ids      ?? [],
            confidence:     i.confidence      ?? '',
        }));

        geminiData        = data;
        geminiSummary     = data.summary       || '';
        geminiIssues      = normalizedIssues;
        geminiOcrWarnings = data.ocr_warnings  || [];

        if (rawJsonEl) {
            rawJsonEl.textContent = JSON.stringify(data, null, 2);
        }

        issueTexts        = geminiIssues.map(i => i.text);
        issueTypes        = geminiIssues.map(i => i.type);
        issueSeverities   = geminiIssues.map(i => i.severity);
        issueSuggestions  = geminiIssues.map(i => i.suggestion);
        issueExplanations = geminiIssues.map(i => i.explanation);

        renderSummary();
        renderIssues();
        updateSeverityCounters();

    } catch (err) {
        document.getElementById('gemini-summary').textContent = `Network error: ${err}`;
        if (rawJsonEl) rawJsonEl.textContent = `Error: ${err}`;
    } finally {
        document.getElementById('gemini-content').classList.remove('d-none');
        document.getElementById('gemini-loading-state').classList.add('d-none');
    }
}


function renderSummary() {
    document.getElementById('gemini-summary').textContent =
        geminiSummary || 'No summary available.';
}


// ── Issue list rendering ────────────────────────────────────────
function renderIssues() {
    const container = document.getElementById('gemini-issues');
    document.getElementById('gemini-issues-count').textContent = geminiIssues.length;

    if (geminiIssues.length === 0) {
        container.innerHTML = '<li class="list-group-item bg-secondary text-white border-0 small">No issues detected.</li>';
        return;
    }

    container.innerHTML = geminiIssues.map((issue, idx) => {
        const badge = { alta: 'danger', media: 'warning', baja: 'info' }[issue.severity] || 'secondary';
        return `
          <li class="list-group-item bg-dark text-white border-secondary p-2"
              data-issue-index="${idx}"
              style="cursor: pointer;"
              onclick="toggleIssueDetail(${idx})">
            <div class="d-flex justify-content-between align-items-center">
              <div>
                <span class="badge bg-${badge}">${issue.severity || '?'}</span>
                <small class="text-info ms-1">${issue.type || ''}</small>
              </div>
              <small class="text-secondary">#${idx + 1}</small>
            </div>
            <div class="small mt-1" style="text-align: left;">
              <code class="text-warning">${issue.text || ''}</code>
              <span class="text-secondary">→</span>
              <code class="text-success">${issue.suggestion || ''}</code>
            </div>
            <div id="issue-detail-${idx}" class="small text-white mt-2 d-none" style="text-align: left;">
              <div><strong class="text-warning">Text:</strong> ${issue.text || '—'}</div>
              <div><strong class="text-warning">Category:</strong> ${issue.type || '—'}</div>
              <div><strong class="text-warning">Severity:</strong> ${issue.severity || '—'}</div>
              <div><strong class="text-warning">Suggestion:</strong> ${issue.suggestion || '—'}</div>
              <div><strong class="text-warning">Explanation (ES):</strong> ${issue.explanation || '—'}</div>
              <div><strong class="text-warning">Explanation (EN):</strong> ${issue.explanation_en || '—'}</div>
            </div>
          </li>`;
    }).join('');
}


function toggleIssueDetail(idx) {
    const detail = document.getElementById(`issue-detail-${idx}`);
    if (detail) detail.classList.toggle('d-none');
}


function updateSeverityCounters() {
    document.getElementById('count-alta').textContent  = getIssuesBySeverity('alta').length;
    document.getElementById('count-media').textContent = getIssuesBySeverity('media').length;
    document.getElementById('count-baja').textContent  = getIssuesBySeverity('baja').length;
}


// ── Helpers ────────────────────────────────────────────────────
function getIssue(index) {
    return geminiIssues[index] || null;
}
function getIssuesByType(type) {
    return geminiIssues.filter(i => i.type === type);
}
function getIssuesBySeverity(severity) {
    return geminiIssues.filter(i => i.severity === severity);
}


// ── Scroll the active item into view + init zoom on workspace ──
(function() {
    const container = document.getElementById("workspace-scroll");
    const activeItem = document.getElementById("current-active-item");

    if (container && activeItem) {
        activeItem.scrollIntoView({ behavior: "instant", block: "nearest" });
        requestAnimationFrame(() => {
            container.classList.remove("lista-oculta");
            container.classList.add("lista-visible");
        });
    }

    // Initialize the preview lens zoom interactivity, if present.
    initPreviewZoom();
})();


/* =========================================================================
   PREVIEW LENS — interactive zoom + pan
   Pure JS, no library. Wheel zoom, drag-to-pan, buttons for fine control.
   ========================================================================= */
const _zoomState = {
    scale: 1,
    tx: 0,
    ty: 0,
    minScale: 1,
    maxScale: 8,
    panning: false,
    startX: 0,
    startY: 0,
    startTx: 0,
    startTy: 0,
};

function initPreviewZoom() {
    const img = document.getElementById('preview-img');
    const viewport = img ? img.closest('.zoom-viewport') : null;
    if (!img || !viewport) return;

    const applyTransform = () => {
        img.style.transform =
            `translate(${_zoomState.tx}px, ${_zoomState.ty}px) scale(${_zoomState.scale})`;
    };

    // Reset on every image load (so navigating between pictures starts at 1×).
    const reset = () => {
        _zoomState.scale = 1;
        _zoomState.tx = 0;
        _zoomState.ty = 0;
        applyTransform();
    };
    img.addEventListener('load', reset);

    // Wheel zoom (cursor-anchored)
    viewport.addEventListener('wheel', (e) => {
        e.preventDefault();
        const rect = viewport.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;

        const oldScale = _zoomState.scale;
        const delta = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        let newScale = oldScale * delta;
        newScale = Math.max(_zoomState.minScale, Math.min(_zoomState.maxScale, newScale));

        // Adjust translation so the point under the cursor stays put.
        const k = newScale / oldScale;
        _zoomState.tx = cx - k * (cx - _zoomState.tx);
        _zoomState.ty = cy - k * (cy - _zoomState.ty);
        _zoomState.scale = newScale;
        applyTransform();
    }, { passive: false });

    // Drag-to-pan
    viewport.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        _zoomState.panning = true;
        _zoomState.startX = e.clientX;
        _zoomState.startY = e.clientY;
        _zoomState.startTx = _zoomState.tx;
        _zoomState.startTy = _zoomState.ty;
        viewport.classList.add('is-panning');
    });
    window.addEventListener('mousemove', (e) => {
        if (!_zoomState.panning) return;
        _zoomState.tx = _zoomState.startTx + (e.clientX - _zoomState.startX);
        _zoomState.ty = _zoomState.startTy + (e.clientY - _zoomState.startY);
        applyTransform();
    });
    window.addEventListener('mouseup', () => {
        _zoomState.panning = false;
        viewport.classList.remove('is-panning');
    });

    // Double click = reset
    viewport.addEventListener('dblclick', reset);
}

function zoomIn() {
    _zoomState.scale = Math.min(_zoomState.maxScale, _zoomState.scale * 1.25);
    _applyTransformExternal();
}
function zoomOut() {
    _zoomState.scale = Math.max(_zoomState.minScale, _zoomState.scale / 1.25);
    if (_zoomState.scale === 1) { _zoomState.tx = 0; _zoomState.ty = 0; }
    _applyTransformExternal();
}
function zoomReset() {
    _zoomState.scale = 1;
    _zoomState.tx = 0;
    _zoomState.ty = 0;
    _applyTransformExternal();
}
function _applyTransformExternal() {
    const img = document.getElementById('preview-img');
    if (img) {
        img.style.transform =
            `translate(${_zoomState.tx}px, ${_zoomState.ty}px) scale(${_zoomState.scale})`;
    }
}


/* =========================================================================
   CACHE CONTROL
   ========================================================================= */
function showCacheStats() {
    fetch('/cache/stats')
        .then(r => r.json())
        .then(data => {
            const area = document.getElementById('cache-stats-area');
            if (!data.namespaces || Object.keys(data.namespaces).length === 0) {
                area.innerHTML = `<em>Cache empty</em><br><small>${data.root || ''}</small>`;
                return;
            }
            const rows = Object.entries(data.namespaces).map(([k, v]) =>
                `<div><strong>${k}:</strong> ${v.entries} entries · ${v.human_size}</div>`
            ).join('');
            area.innerHTML = rows + `<small class="text-muted">${data.root}</small>`;
        })
        .catch(err => showToast(`Stats error: ${err}`, 'danger'));
}

function purgeAllCache() {
    if (!confirm('Borrar TODO el cache en disco?')) return;
    fetch('/cache/purge', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'OK') {
                showToast('Cache global borrado.', 'success');
                showCacheStats();
            } else {
                showToast(`Error: ${data.message || 'desconocido'}`, 'danger');
            }
        });
}

function purgeWorkspaceCache() {
    if (!confirm('Borrar el cache del workspace actual?')) return;
    fetch('/cache/purge/workspace', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'OK') {
                showToast(`Workspace cache cleared: ${data.ocr} OCR, ${data.qa} QA.`, 'success');
                showCacheStats();
            } else {
                showToast(`Error: ${data.message || 'desconocido'}`, 'danger');
            }
        });
}

function reprocessCurrentImage() {
    fetch('/cache/purge/current', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'OK') {
                showToast(`Cache de imagen invalidado. Reprocesando…`, 'info');
                // Re-trigger OCR + Analyze immediately
                setTimeout(() => ProcessImage(), 200);
            } else {
                showToast(`Error: ${data.message || 'desconocido'}`, 'danger');
            }
        });
}


/* =========================================================================
   ACCUMULATOR — send the current screen's findings to the server
   ========================================================================= */
function collectData() {
    const archivoOrigen = document.getElementById('current-active-item')?.innerText?.trim() || "captura_origen.png";
    const lienzoAncho = parseInt(document.getElementById('canvas-width')?.value) || 1080;
    const lienzoAlto = parseInt(document.getElementById('canvas-height')?.value) || 2400;

    const mapaInversoSeveridad = { 'alta': 'high', 'media': 'medium', 'baja': 'low' };

    // Forward explanation_en too, so even if the backend can't recover it
    // from the qa_cache, the JS payload still carries it.
    const issuesListos = geminiIssues.map(issue => ({
        category:       issue.type,
        text_excerpt:   issue.text,
        suggestion:     issue.suggestion,
        severity:       mapaInversoSeveridad[issue.severity] || issue.severity,
        explanation:    issue.explanation,
        explanation_en: issue.explanation_en,
        confidence:     issue.confidence || 'high',
        bbox:           issue.bbox,
        region_ids:     issue.region_ids || [],
    }));

    const payload = {
        source_file:  archivoOrigen,
        image_width:  lienzoAncho,
        image_height: lienzoAlto,
        summary:      geminiSummary,
        issues:       issuesListos,
        ocr_warnings: geminiOcrWarnings,
    };

    console.log("[QA-FLOW] Indexing data on server...");

    return fetch('/processData', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'OK') {
            showToast(`Data of <strong>${archivoOrigen}</strong> added to report.`, 'success');
            return data;
        }
        throw new Error(data.message);
    })
    .catch(err => {
        console.error(err);
        showToast(`Indexing error: ${err.message}`, 'danger', 6000);
        throw err;
    });
}


function saveFinalReport() {
    console.log("[QA-FLOW] Requesting Excel generation...");

    return fetch('/saveReport', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'OK') {
            showToast(`Report saved at:<br><small>${data.path}</small>`, 'success', 8000);
        } else if (data.status === 'Cancelado') {
            showToast('Save canceled.', 'secondary');
        } else {
            showToast(`Save error: ${data.message}`, 'danger', 6000);
        }
        return data;
    })
    .catch(err => {
        console.error(err);
        showToast('Server unreachable.', 'danger', 6000);
        throw err;
    });
}


/* =========================================================================
   BATCH AUTOMATION
   ========================================================================= */
let _batchAbort = false;

function _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function _waitFor(conditionFn, timeoutMs = 60000, pollMs = 100) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const tick = () => {
            try {
                if (conditionFn()) return resolve(true);
            } catch (_) { /* ignore */ }
            if (Date.now() - start > timeoutMs) return reject(new Error('timeout'));
            setTimeout(tick, pollMs);
        };
        tick();
    });
}

async function _processImageInline() {
    document.getElementById('image-content')?.classList.add('d-none');
    document.getElementById('loading-state')?.classList.remove('d-none');
    document.getElementById('gemini-content')?.classList.add('d-none');
    document.getElementById('gemini-loading-state')?.classList.remove('d-none');

    const res = await fetch('/process_image', { method: 'POST' });
    if (!res.ok) throw new Error(`process_image HTTP ${res.status}`);
    return res.json();
}

function abortBatch() {
    if (!sessionStorage.getItem('batchRunning')) {
        showToast('No active batch.', 'secondary');
        return;
    }
    _batchAbort = true;
    sessionStorage.removeItem('batchRunning');
    sessionStorage.removeItem('batchTotal');
    sessionStorage.removeItem('batchProgress');
    showToast('Aborting batch…', 'warning', 3000);
}

async function runBatchStep() {
    if (_batchAbort) {
        sessionStorage.removeItem('batchRunning');
        return;
    }

    const total = parseInt(sessionStorage.getItem('batchTotal')) || 0;
    const progress = parseInt(sessionStorage.getItem('batchProgress')) || 0;
    const isLast = (progress + 1) >= total;

    showToast(`Processing ${progress + 1} / ${total}…`, 'info', 2500);

    try {
        await _processImageInline();
        await ReviewImage();

        if (geminiData && geminiData._error) {
            throw new Error(geminiData._error);
        }

        await collectData();

        if (isLast) {
            showToast(`Batch complete (${total} images). Generating report…`, 'success', 4000);
            sessionStorage.removeItem('batchRunning');
            sessionStorage.removeItem('batchTotal');
            sessionStorage.removeItem('batchProgress');
            await _sleep(500);
            await saveFinalReport();
            return;
        }

        sessionStorage.setItem('batchProgress', String(progress + 1));
        await _sleep(600);
        Next();

    } catch (err) {
        console.error(`[BATCH] Error on image ${progress + 1}:`, err);
        showToast(`Image ${progress + 1} failed: ${err.message}. Continuing…`, 'danger', 4000);

        if (isLast) {
            sessionStorage.removeItem('batchRunning');
            sessionStorage.removeItem('batchTotal');
            sessionStorage.removeItem('batchProgress');
            await _sleep(500);
            await saveFinalReport();
        } else {
            sessionStorage.setItem('batchProgress', String(progress + 1));
            await _sleep(600);
            Next();
        }
    }
}

function runBatch() {
    if (sessionStorage.getItem('batchRunning')) {
        showToast('Batch already running. Abort first.', 'warning');
        return;
    }

    const items = document.querySelectorAll('#workspace-scroll .list-group-item');
    const total = items.length;

    if (total === 0) {
        showToast('No images in workspace.', 'warning');
        return;
    }

    let currentIdx = 0;
    items.forEach((el, i) => {
        if (el.id === 'current-active-item') currentIdx = i;
    });
    const remaining = total - currentIdx;

    sessionStorage.setItem('batchRunning', '1');
    sessionStorage.setItem('batchTotal', String(remaining));
    sessionStorage.setItem('batchProgress', '0');

    showToast(`Batch start: ${remaining} images from current.`, 'info', 3000);
    runBatchStep();
}


// Auto-resume: if the batch left a flag before Next(), pick it up.
(function() {
    if (sessionStorage.getItem('batchRunning') === '1') {
        setTimeout(runBatchStep, 400);
    }
})();


/* =========================================================================
   TOASTS (Bootstrap 5)
   ========================================================================= */
function _ensureToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1090';
        document.body.appendChild(container);
    }
    return container;
}

function showToast(message, variant = 'info', delay = 4000) {
    const container = _ensureToastContainer();

    const icons = {
        success:   '✓',
        danger:    '✕',
        warning:   '⚠',
        info:      'ⓘ',
        secondary: '•',
    };

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${variant} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'polite');
    toastEl.setAttribute('aria-atomic', 'true');

    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <strong class="me-2">${icons[variant] || ''}</strong>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto"
                    data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay, autohide: true });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}