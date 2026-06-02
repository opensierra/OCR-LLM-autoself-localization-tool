from os import path

MODEL_NAME = "deepseek-r1:1.5b" # "gemma4:e2b" "gemma4:e4b"  "qwen3.5:0.8b" 

routeBackend = path.dirname(path.abspath(__file__))
routeRoot = path.dirname(routeBackend)

TESSERACT_PATH = path.join(routeRoot, "tesseract", "tesseract.exe")
CACHE_DIR = "Backend/static/images"

GEMINI_API_KEY = None

HOST        = "127.0.0.1"
PORT        = 5000
DEBUG       = False
URL_DEF = f"http://{HOST}:{PORT}"

LANGUAGE = "es-CO"

IMG_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}

