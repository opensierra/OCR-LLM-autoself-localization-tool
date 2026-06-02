from Backend.Indexer import (
    processCapture,
    compileRows,
    exportExcel,
    selectSavePath,
)

from .env import HOST, PORT, DEBUG, LANGUAGE
from .DPI import DPI
from .logger import get_logger
from flask import Flask, jsonify, redirect, render_template, request, url_for, send_file, abort
from pathlib import Path
from urllib.parse import unquote


log = get_logger("HTTP")


current_workspace = None
proceced_paths = {}
extracted_text = None
raw_text = None
imgIndex = 0


def create_app():
    app = Flask(__name__)
    # Estáticos (CSS, JS, plantillas): sin caché agresivo en disco. Cambiar
    # un archivo y refrescar debe verse inmediatamente. El cache fuerte se
    # mantiene SOLO para las screenshots vía /img (ruta dedicada más abajo),
    # que son las que realmente vale la pena cachear.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Forzar no-cache en todas las respuestas HTML/JSON normales. Esto evita
    # que pywebview se quede con la versión vieja de workspace.html al
    # iterar sobre el frontend.
    @app.after_request
    def _no_cache_html_json(resp):
        ct = resp.headers.get("Content-Type", "")
        if ct.startswith(("text/html", "application/json", "text/javascript",
                          "application/javascript", "text/css")):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        return resp

    # Endpoint mínimo que main.py consulta para saber cuándo abrir la ventana.
    # Solo confirma que Flask está aceptando peticiones.
    @app.route('/status')
    def status():
        return jsonify({"state": "ready"})

    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/workspace')
    def workspace():
        if current_workspace is None:
            return redirect(url_for('home'))
        current_img = current_workspace.tree[imgIndex]
        return render_template(
            'workspace.html',
            language=LANGUAGE,
            tree=current_workspace.tree,
            imgIndex=imgIndex,
            current_img=current_img,
            processed_paths=proceced_paths,
            extracted_text=extracted_text,
            raw_text=raw_text
        )

    @app.route('/img/<path:abs_path>')
    def serve_image(abs_path):
        if current_workspace is None:
            abort(403)
        p = Path(unquote(abs_path)).resolve()
        # Seguridad: solo servir imágenes que están en el workspace actual
        allowed = {Path(x).resolve() for x in current_workspace.tree}
        if p not in allowed:
            abort(403)
        # Las imágenes del workspace son inmutables mientras el path no cambie.
        # Caché agresivo: 1 día, evita que el navegador re-pida en cada render.
        resp = send_file(p)
        resp.headers["Cache-Control"] = "public, max-age=86400, immutable"
        return resp

    @app.route('/selectFolder', methods=['POST'])
    def select_folder():
        global current_workspace, imgIndex
        # Apagar pool de prefetch del workspace anterior si existe
        if current_workspace is not None:
            current_workspace.shutdown()

        # Crear nuevo workspace (esto abre el diálogo de Tkinter)
        current_workspace = DPI()
        imgIndex = 0

        # Opción del frontend: "reset_cache" -> empezar de cero
        data = request.get_json(silent=True) or {}
        if data.get("reset_cache"):
            current_workspace.invalidate_workspace_disk()
            log.info("Workspace iniciado con cache limpio")

        # Pre-cargar el modelo Ollama actual en RAM en background
        # El cliente va a /model_loading mientras esto sucede.
        try:
            from . import ollama_admin
            from .localQ import get_model
            ollama_admin.warmup_model(get_model())
        except Exception as e:
            log.warn("Warmup automático falló: %s", e)

        return jsonify({"redirect": url_for('model_loading')})

    @app.route('/model_loading')
    def model_loading():
        """Loading screen shown after selecting workspace; polls /models/status."""
        from . import ollama_admin
        from .localQ import get_model
        state = ollama_admin.get_warmup_state()
        # If the model is already ready (rare race: user reloads), bounce to workspace
        if state.get("state") == "ready":
            return redirect(url_for('workspace'))
        return render_template(
            'Loading.html',
            model=state.get("model") or get_model(),
        )

    @app.route('/next', methods=['POST'])
    def next():
        global imgIndex
        if current_workspace is None:
            return jsonify({"error": "no workspace"}), 400
        imgIndex = (imgIndex + 1) % len(current_workspace.tree)
        return jsonify({"refresh": url_for('workspace')})

    @app.route('/prev', methods=['POST'])
    def prev():
        global imgIndex
        if current_workspace is None:
            return jsonify({"error": "no workspace"}), 400
        imgIndex = (imgIndex - 1) % len(current_workspace.tree)
        return jsonify({"refresh": url_for('workspace')})

    @app.route('/process_image', methods=['POST'])
    def process_image():
        global current_workspace, imgIndex, proceced_paths, extracted_text, raw_text
        log.info("OCR solicitado (imgIndex=%d)", imgIndex)

        enviroment = current_workspace.analyze_imgIndex(imgIndex)
        proceced_paths[imgIndex] = enviroment['preview_path']
        extracted_text = enviroment['text']
        raw_text = enviroment['raw_text']
        log.info("OCR completado para imgIndex=%d", imgIndex)
        return jsonify({"refresh": url_for('workspace')})

    @app.route('/review_image', methods=['POST'])
    def review_image():
        if current_workspace is None:
            log.warn("review_image sin workspace activo")
            return jsonify({"error": "no workspace"}), 400

        log.info("Review solicitado (imgIndex=%d)", imgIndex)
        try:
            review = current_workspace.review_imgIndex(imgIndex)
            log.info("Review completado: %d issues", len(review.get('issues', [])))
            return jsonify(review)
        except Exception as e:
            log.error("Review falló: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route('/processData', methods=['POST'])
    def api_procesar_datos():
        """
        Recibe el JSON del LLM de una captura, lo acumula en el Indexer.
        El armado de filas ahora vive en Indexer.processCapture(); aquí solo
        rescatamos la ruta absoluta de la imagen y el raw_text cacheado
        para enriquecer las filas (imagen embebida + OCR trust real).
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "Error", "message": "No se recibieron datos válidos"}), 400

            source_file = data.get("source_file", "desconocido.png")

            # Resolver source_path absoluto desde el workspace actual.
            # El JS envía rutas con separadores de Windows ('\\') o con barras
            # normales según el render Jinja. Comparamos por basename puro
            # con os.path.basename (que entiende ambos separadores en cualquier OS).
            import os as _os
            source_path = None
            raw_text_cached = None
            target_name = _os.path.basename(source_file.replace("\\", "/"))

            if current_workspace is not None:
                for p in current_workspace.tree:
                    p_name = _os.path.basename(p.replace("\\", "/"))
                    if p_name == target_name or p == source_file:
                        source_path = p
                        try:
                            cached = current_workspace._ocr_cache.get(
                                current_workspace._hash_for(p)
                            )
                            if cached:
                                raw_text_cached = cached.get("raw_text")
                        except Exception as e:
                            log.warn("No pude obtener raw_text para %s: %s", p, e)
                        break

            if source_path is None:
                log.warn("processData: source_path no resuelto para %s", source_file)
                source_path = source_file

            # IMPORTANTE: el JS normaliza los issues y descarta campos como
            # explanation_en. En lugar de fiarnos del JSON que mandó el front,
            # recuperamos el resultado AUTORITATIVO del cache del LLM, donde
            # están todos los campos intactos. Lo que mandó el JS solo se
            # usa como confirmación de qué pantalla indexar.
            authoritative = None
            if source_path != source_file and current_workspace is not None:
                try:
                    h = current_workspace._hash_for(source_path)
                    authoritative = current_workspace._qa_cache.get(h)
                except Exception as e:
                    log.warn("No pude leer qa_cache para %s: %s", source_path, e)

            payload_for_indexer = authoritative if authoritative else data
            # source_file e image_w/h hay que preservarlos del data original
            # (el qa_cache no los tiene; vienen del request del JS).
            payload_for_indexer = {
                **payload_for_indexer,
                "source_file": data.get("source_file", source_file),
                "image_width": data.get("image_width"),
                "image_height": data.get("image_height"),
            }

            processCapture(
                qa_payload=payload_for_indexer,
                source_path=source_path,
                raw_text=raw_text_cached,
            )

            return jsonify({
                "status": "OK",
                "message": f"Captura '{Path(source_path).name}' indexada correctamente."
            })

        except Exception as e:
            log.error("processData falló: %s", e)
            return jsonify({"status": "Error", "message": str(e)}), 500

    @app.route('/saveReport', methods=['POST'])
    def api_guardar_excel():
        """
        Vuelca el acumulador a Excel via report_builder (imágenes embebidas,
        filtros, formato condicional). Limpia el acumulador al terminar.
        """
        try:
            rows = compileRows()
            if not rows:
                return jsonify({
                    "status": "Error",
                    "message": "El acumulador está vacío. Indexa datos primero."
                }), 400

            ruta_destino = selectSavePath(default_name="vivodpi_qa_report.xlsx")
            if ruta_destino:
                exportExcel(rows, filename=ruta_destino)
                log.info("Reporte exportado a %s (%d filas)", ruta_destino, len(rows))
                return jsonify({"status": "OK", "path": ruta_destino})
            else:
                return jsonify({
                    "status": "Cancelado",
                    "message": "Operación de guardado cancelada por el usuario."
                })

        except Exception as e:
            log.error("saveReport falló: %s", e)
            return jsonify({"status": "Error", "message": str(e)}), 500

    # ── Cache control endpoints ────────────────────────────────
    @app.route('/cache/stats', methods=['GET'])
    def cache_stats():
        """Stats globales del cache en disco."""
        from . import disk_cache
        return jsonify(disk_cache.stats())

    @app.route('/cache/purge', methods=['POST'])
    def cache_purge_all():
        """Borra TODO el cache en disco (todos los workspaces)."""
        from . import disk_cache
        try:
            disk_cache.purge()
            if current_workspace is not None:
                current_workspace.clear_cache()
            log.info("Cache global purgado")
            return jsonify({"status": "OK"})
        except Exception as e:
            log.error("cache_purge_all falló: %s", e)
            return jsonify({"status": "Error", "message": str(e)}), 500

    @app.route('/cache/purge/workspace', methods=['POST'])
    def cache_purge_workspace():
        """Borra solo las entradas del workspace actual."""
        if current_workspace is None:
            return jsonify({"status": "Error", "message": "no workspace"}), 400
        try:
            result = current_workspace.invalidate_workspace_disk()
            return jsonify({"status": "OK", **result})
        except Exception as e:
            log.error("cache_purge_workspace falló: %s", e)
            return jsonify({"status": "Error", "message": str(e)}), 500

    @app.route('/cache/purge/current', methods=['POST'])
    def cache_purge_current():
        """Invalida la imagen visible actualmente (forzar reprocesar)."""
        if current_workspace is None:
            return jsonify({"status": "Error", "message": "no workspace"}), 400
        try:
            path = current_workspace.tree[imgIndex]
            result = current_workspace.invalidate_image(path)
            return jsonify({"status": "OK", **result})
        except Exception as e:
            log.error("cache_purge_current falló: %s", e)
            return jsonify({"status": "Error", "message": str(e)}), 500

    # ── Ollama model endpoints ──────────────────────────────────
    @app.route('/models/list', methods=['GET'])
    def models_list():
        """Lista de modelos disponibles vía `ollama list`."""
        from . import ollama_admin
        return jsonify({
            "available": ollama_admin.is_ollama_available(),
            "models": ollama_admin.list_models(),
            "current": _current_model_name(),
        })

    @app.route('/models/select', methods=['POST'])
    def models_select():
        """Cambia el modelo activo y lanza warmup en background."""
        from . import ollama_admin
        from .localQ import set_model
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"status": "Error", "message": "name required"}), 400
        set_model(name)
        ollama_admin.warmup_model(name)
        return jsonify({"status": "OK", "current": name})

    @app.route('/models/browse', methods=['POST'])
    def models_browse():
        """Abre una terminal con instrucciones para descargar modelos."""
        from . import ollama_admin
        ok = ollama_admin.open_browse_models_terminal()
        return jsonify({"status": "OK" if ok else "Error"})

    @app.route('/models/warmup', methods=['POST'])
    def models_warmup():
        """Pre-carga el modelo actual."""
        from . import ollama_admin
        from .localQ import get_model
        ok = ollama_admin.warmup_model(get_model())
        return jsonify({"status": "OK" if ok else "Error", "model": get_model()})

    @app.route('/models/status', methods=['GET'])
    def models_status():
        """Current warmup state (polled by the loading screen)."""
        from . import ollama_admin
        return jsonify(ollama_admin.get_warmup_state())

    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False)


def _current_model_name() -> str:
    from .localQ import get_model
    return get_model()