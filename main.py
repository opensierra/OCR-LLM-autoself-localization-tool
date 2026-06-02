import threading
import time
import requests
import webview
from Backend import create_app
from Backend.env import URL_DEF

ICON_PATH = r'Backend\static\images\icon.ico'

def run_server():
    create_app()

if __name__ == "__main__":
    # 1. Start server in a background thread
    threading.Thread(target=run_server, daemon=True).start()

    # 2. Minimalist boot sequence
    status_url = f"{URL_DEF}/status"
    while True:
        try:
            response = requests.get(status_url, timeout=2)
            if response.status_code == 200 and response.json().get("state") == "ready":
                break
        except:
            pass
        time.sleep(1)

    # 3. Launch GUI
    webview.create_window('Vivo DPI', URL_DEF, maximized=True)
    webview.start(icon=ICON_PATH)
