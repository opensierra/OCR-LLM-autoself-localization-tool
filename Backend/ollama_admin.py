# ollama_admin.py - Administración del servicio Ollama desde la app.
# Listar modelos, obtener detalles, y abrir terminal para que el usuario
# descargue nuevos modelos.

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .logger import get_logger


log = get_logger("OLLAMA")


# Estado global del warmup, consultado por /models/status para que la
# pantalla de carga sepa cuándo redirigir.
_WARMUP_STATE = {
    "state": "idle",     # idle | loading | ready | error
    "model": "",
    "message": "",
    "started_at": 0.0,
    "finished_at": 0.0,
}
_WARMUP_LOCK = threading.Lock()


def get_warmup_state() -> dict:
    with _WARMUP_LOCK:
        return dict(_WARMUP_STATE)


def _set_warmup_state(**kwargs):
    with _WARMUP_LOCK:
        _WARMUP_STATE.update(kwargs)


def is_ollama_available() -> bool:
    """¿Está el ejecutable de Ollama en PATH?"""
    return shutil.which("ollama") is not None


def list_models() -> list:
    """
    Lista los modelos disponibles localmente vía `ollama list`.
    Devuelve [{'name': 'gemma4:e2b', 'size': '2.0 GB', 'modified': '...'}].
    Si Ollama no está disponible, devuelve [].
    """
    if not is_ollama_available():
        log.warn("ollama no está en PATH")
        return []

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        log.warn("Falló `ollama list`: %s", e)
        return []

    if result.returncode != 0:
        log.warn("`ollama list` devolvió código %d: %s",
                 result.returncode, result.stderr)
        return []

    models = []
    lines = result.stdout.strip().split("\n")
    # First line is header: NAME  ID  SIZE  MODIFIED
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        # Name is first; modified is last 2-3 tokens; size is two tokens before
        name = parts[0]
        # Reconstruct from the right: e.g. "2.0 GB 5 days ago"
        # We rely on Ollama's stable output: <name> <id> <size num> <size unit> <modified...>
        try:
            size = f"{parts[2]} {parts[3]}"
            modified = " ".join(parts[4:])
        except IndexError:
            size = "?"
            modified = ""
        models.append({"name": name, "size": size, "modified": modified})
    return models


def open_browse_models_terminal():
    """
    Open a styled terminal window with `ollama pull` instructions.
    Windows only.

    Implementation note: we use PowerShell instead of a .cmd batch file.
    PowerShell handles ANSI escapes natively (no `reg add` dance), UTF-8
    output cleanly, and at the end we drop the user into an interactive
    shell so they can type the `ollama pull` command directly.
    """
    if sys.platform != "win32":
        log.warn("open_browse_models_terminal: Windows only")
        return False

    script_path = Path.home() / "vivodpi_browse_models.ps1"

    # PowerShell script. PowerShell prints ANSI sequences natively and modern
    # Windows Terminal / conhost honor them. We use single-line Write-Host
    # statements with $() interpolation — avoids the +concat pitfalls.
    ps_script = r"""$Host.UI.RawUI.WindowTitle = 'VivoDPI - Model Manager'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Clear-Host

$ESC    = [char]27
$cyan   = "$ESC[96m"
$gray   = "$ESC[90m"
$green  = "$ESC[92m"
$white  = "$ESC[97m"
$bold   = "$ESC[1m"
$reset  = "$ESC[0m"

Write-Host ""
Write-Host "  $cyan$bold┌────────────────────────────────────────────────────────┐$reset"
Write-Host "  $cyan$bold|              VivoDPI  -  Model Manager                 |$reset"
Write-Host "  $cyan$bold└────────────────────────────────────────────────────────┘$reset"
Write-Host ""
Write-Host "  $cyan${bold}1.$reset Explore available models on the web:"
Write-Host "     $gray->$reset ${white}https://ollama.com/library$reset"
Write-Host ""
Write-Host "  $cyan${bold}2.$reset Download a model by name:"
Write-Host "     ${green}ollama pull <model_name>$reset"
Write-Host ""
Write-Host "  ${gray}Please pick a model that suits your machine. Smaller models load faster$reset"
Write-Host "  ${gray}and use less RAM; larger models trade speed for quality.$reset"
Write-Host ""
Write-Host "  $cyan${bold}3.$reset To see the updated list of models, restart the app."
Write-Host ""
Write-Host "  ${gray}----------------------------------------------------------$reset"
Write-Host "  $white${bold}Type your command below:$reset"
Write-Host ""
"""
    # Write as UTF-8 with BOM so PowerShell doesn't choke on non-ASCII chars
    # if the user has a non-English locale.
    script_path.write_text(ps_script, encoding="utf-8-sig")

    try:
        # Launch a new console window:
        #  - powershell with -NoExit so the prompt stays after the script
        #  - -ExecutionPolicy Bypass so the script is not blocked
        #  - -File <our script>
        subprocess.Popen(
            [
                "powershell",
                "-NoExit",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        log.info("Model browser terminal opened")
        return True
    except Exception as e:
        log.warn("Could not open terminal: %s", e)
        return False


def warmup_model(model_name: str) -> bool:
    """
    Pre-loads an Ollama model into RAM. Non-blocking: spawns a thread and
    publishes progress to _WARMUP_STATE so the UI can poll /models/status.
    Returns True if it managed to spawn the thread.
    """
    if not is_ollama_available():
        _set_warmup_state(state="error", model=model_name,
                          message="Ollama is not available in PATH",
                          started_at=time.time(), finished_at=time.time())
        return False

    _set_warmup_state(state="loading", model=model_name,
                      message=f"Loading {model_name} into memory…",
                      started_at=time.time(), finished_at=0.0)

    def _do_warmup():
        try:
            log.info("Warmup starting for %s", model_name)
            import ollama
            ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": "ping"}],
                options={"num_predict": 1, "num_ctx": 16384},
                keep_alive="30m",
            )
            log.info("Warmup completed for %s", model_name)
            _set_warmup_state(state="ready", message="Model ready.",
                              finished_at=time.time())
        except Exception as e:
            log.warn("Warmup failed for %s: %s", model_name, e)
            _set_warmup_state(state="error",
                              message=f"Could not load model: {e}",
                              finished_at=time.time())

    t = threading.Thread(target=_do_warmup, daemon=True, name="ollama-warmup")
    t.start()
    return True