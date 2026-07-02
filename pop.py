import warnings
warnings.filterwarnings("ignore")

import json
import logging
import time
import random
from pathlib import Path
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
TARGET_URL = "https://igualdadynodiscriminacion.igualdad.gob.es/menured/quejas-y-consultas/"
PDF_NAME = "Expedia-does-Guide.pdf"
PDF_PATH = BASE_DIR / PDF_NAME
PROXY_FILE = BASE_DIR / "proxies.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("equality_upload")

# --- XHR INTERCEPT ---
XHR_INTERCEPT_JS = """(function () { 
    if (window.__ajax_log_installed) return; 
    window.__ajax_log_installed = true; 
    window.__ajax_log = []; 
    var _open = XMLHttpRequest.prototype.open; 
    var _send = XMLHttpRequest.prototype.send; 
    XMLHttpRequest.prototype.open = function (method, url) { this.__url = url || ''; return _open.apply(this, arguments); }; 
    XMLHttpRequest.prototype.send = function (body) { 
        var xhr = this; 
        xhr.addEventListener('load', function () { 
            try { 
                if (xhr.__url && xhr.__url.indexOf('admin-ajax.php') !== -1) { 
                    window.__ajax_log.push({ url: xhr.__url, status: xhr.status, body: xhr.responseText || '' }); 
                } 
            } catch (e) {} 
        }); 
        return _send.apply(this, arguments); 
    }; 
})();"""

# --- PROXY UTILS ---
def load_proxies():
    if not PROXY_FILE.exists(): return []
    with PROXY_FILE.open("r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def get_proxy_bundle():
    proxies = load_proxies()
    if not proxies: return None
    p = random.choice(proxies)
    parts = p.split(':') # Expected: IP:PORT:USER:PASSWORD
    return {
        "http": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}",
        "https": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    }

# --- AJAX PARSER ---
def capture_upload_url(driver, timeout=40):
    """Parses JSON from the intercepted AJAX log with fixed slash logic"""
    logger.info(f"⏳ Capturing upload URL...")
    deadline = time.time() + timeout
    
    while time.time() < deadline:
        time.sleep(1)
        try:
            log = driver.execute_script("return window.__ajax_log || [];")
            for entry in log:
                body = entry.get("body", "")
                if "success" in body and "file" in body:
                    data = json.loads(body)
                    if data.get("success") and "data" in data:
                        filename = data["data"].get("file")
                        folder = data["data"].get("path", "")
                        
                        # Ensure folder path ends with slash for valid URL construction
                        if folder and not folder.endswith('/'):
                            folder += '/'
                            
                        if filename:
                            return f"https://igualdadynodiscriminacion.igualdad.gob.es/wp-content/uploads/wp_dndcf7_uploads/wpcf7-files/{folder}{filename}"
        except: continue
    return None

# --- MAIN EXECUTION ---
def main():
    proxy_config = get_proxy_bundle()
    sw_options = {"proxy": proxy_config} if proxy_config else {}
    
    options = Options()
    options.add_argument("--start-maximized")
    
    # Initialize driver with proxy options
    driver = webdriver.Chrome(options=options, seleniumwire_options=sw_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": XHR_INTERCEPT_JS})
    
    try:
        driver.get(TARGET_URL)
        time.sleep(3)
        
        # Locate input
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", file_input)
        
        logger.info(f"📤 Uploading: {PDF_NAME}")
        file_input.send_keys(str(PDF_PATH))
        
        # Capture the URL
        url = capture_upload_url(driver)
        
        if url:
            print(f"\n🎉 SUCCESS! URL: {url}")
            with open("upload_result.txt", "w") as f: f.write(url)
        else:
            print("\n❌ Failed to capture URL. Check network logs in DevTools.")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()