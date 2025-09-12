from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import csv
import os
import subprocess
import shutil
import json
import random
import re
import argparse
import glob

import script2

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = "https://soundcloud.com"

def load_config(filename="config.json"):
    global url, path, topsong, is_timed
    try:
        with open(filename, "r") as f:
            config = json.load(f)
            url = config.get("url", "")
            path = config.get("path", "")
            topsong = config.get("topsong", "")
            if topsong == "":
                is_timed = True
            else:
                is_timed = config.get("is_timed", False)
            print(f"Config loaded : url={url}, path={path}, topsong={topsong}, is_timed={is_timed}")
    except FileNotFoundError:
        print("Config file not found.")

from urllib.parse import urljoin, urlparse, urlunparse, unquote

def _to_abc(href: str, base: str = "https://soundcloud.com") -> str | None:
    """
    Macht aus einem href eine absolute, bereinigte SoundCloud-URL:
    - ignoriert javascript:, mailto:, #...
    - macht relative Links absolut (urljoin mit base)
    - entfernt Query + Fragment
    - normalisiert Host + Pfad
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith(("javascript:", "mailto:", "#")):
        return None

    abs_url = urljoin(base, href)
    u = urlparse(abs_url)

    # Nur SoundCloud-Links zulassen (alles andere ignorieren)
    host = u.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if not host.endswith("soundcloud.com"):
        return None

    path = unquote(u.path)
    path = re.sub(r"/+", "/", path).rstrip("/")  # // → / ; trailing slash weg
    return urlunparse((u.scheme, host, path, "", "", ""))

def _norm(s: str) -> str:
    """
    Normiert eine (evtl. relative) URL für stabile Vergleiche:
    - host ohne www., lowercase
    - nur host + path (ohne query/fragment)
    - Pfad ohne trailing slash, dekodiert, // → /
    """
    if not s:
        return ""
    # Relatives als SoundCloud-URL interpretieren
    if not re.match(r"^https?://", s):
        s = urljoin("https://soundcloud.com", s)
    u = urlparse(s)
    host = u.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", unquote(u.path)).rstrip("/")
    return f"{host}{path}"

#Set playlist to keep looking at 
def get_input():
    print("Enter Playlist or UserLikes :")
    url = input().strip()
    write_to_config(data=url, pos="url")
    return url

#Set spotify folder to get downloaded songs to 
def set_spotify_folder():
        path = input("Enter full-path to spotify-locale directory :").strip()
        #resolved_path = os.path.expanduser(path)
        resolved_path = os.path.abspath(path)
        write_to_config(data=path, pos="path")
        return path

def set_topsong(topsong):
    write_to_config(data=topsong, pos="topsong")

def set_timed():
    pass

def write_to_config(data, pos, filename="config.json"):
    with open(filename, "r") as f:
        config = json.load(f)
        config[pos] = data
        with open(filename, "w") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

def wait_for_download(path, timeout=300):
    seconds = 0
    while True:
        files = glob.glob(os.path.join(path, "*.crdownload"))
        if not files: 
            break
        time.sleep(2)
        seconds +=1
        if seconds > timeout:
            raise Exception("Download Timeout")
    print("Download complete")

def scroll(driver):
    ActionChains(driver).scroll_by_amount(0, 1000000).perform()

def scroll_to_btn(driver, btn) :
    ActionChains(driver).scroll_to_element(btn)

def _to_abs(href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    return href if href.startswith("http") else (BASE + href)

def _norm(u: str) -> str:
    # einfache Normalisierung für den Vergleich
    return _to_abs(u).rstrip("/")

def get_latest_mp3(download_folder): 
        mp3_files = glob.glob(os.path.join(download_folder, '*mp3'))
        if not mp3_files:
            print("No mp3 found for eyed3")
            return None
        latest_mp3 = max(mp3_files, key=os.path.getctime)
        return latest_mp3

def getSongUrl(driver, url, topsong, on_item=None):
    topsong_norm = _norm(topsong) if topsong else None
    # Initialize the Chrome driver
    print(f"Starting webdriver on :{url}")
    print(f"Topsong :{topsong}")
    driver.get(url)
    time.sleep(2)  # Give time to load the page

    # Wait for the list of songs to be present
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.soundList__item")))
    time.sleep(1)

    seen_hrefs = set()
    items = []

    max_scrolls = 4
    min_wait_new = 0.5
    wait = WebDriverWait(driver, 10)

    start_time = time.time()

    for i in range(max_scrolls):
        anchors = driver.find_elements(
            By.CSS_SELECTOR, "li.soundList__item a.sc-link-primary[href]"
        )

        found_topsong = False
        for a in anchors:
            try:
                href = _to_abc(a.get_attribute("href"))
                if not href or href in seen_hrefs:
                    continue

                title = a.text.strip()
                seen_hrefs.add(href)
                items.append({"title": title, "href": href})
                print(f"FOUND: {title} -> {href}")

                if on_item:
                    try:
                        on_item(title, href)
                    except Exception as e:
                        print(f"[ERROR] on_item callback failed for {title} / {href} :{e}")

                if topsong_norm and _norm(href) == topsong_norm:
                    print(f"[INFO] Topsong reached: {topsong_norm}")
                    found_topsong = True
                    break
            except Exception as e:
                print(f"Failed extracting href anchor :{e}")
                continue

        if found_topsong:
            break

        #how many before last scroll
        before = len(seen_hrefs)

        #scrollen
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2.0, 5.0))
        try:
            wait.until(lambda d: len(d.find_elements(
                By.CSS_SELECTOR, "li.soundList__item a.sc-link-primary[href]"
            )) > len(anchors))
        except Exception:
            time.sleep(min_wait_new)
            after = len(seen_hrefs)
            if after == before :
                print("No more new items after scroll -> stopping.")
                break
    href_list = [it["href"] for it in items]

    if topsong_norm:
        cut_idx = next((i for i, it in enumerate(items) if _norm(it["href"]) == topsong_norm), None)
        if cut_idx is not None:
            items = items[:cut_idx]     # ohne Topsong
            href_list = [it["href"] for it in items]

    return href_list, items, topsong

def make_download_job():
    def job(title, href, out_dir):
        try:
            #script2 krams hier
            pass
        except Exception as e:
            print(f"[ERROR] Download of {title} from {href} failed :{e}")
    return job

def submitter(title, href):
    #fut = executor.submit(make_download_job(), title, href, out_dir=path)
    fut = executor.submit(script2.process_track,href, client_id="3WvMqSrX1K9rBNLGUNhUO9KRbVOUR9uT", out_dir=path, title_override=title)
    futures.append(fut)
    return fut

def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s.-]", "", name).strip().replace(" ", "_")
    return s[:120] or "track"

def on_item(title, href):
    return executor.submit(downloader.process_track, href, client_id, out_dir, title_override=title)

def process_track(href: str, client_id: str, out_dir: str = ".", title_override: str | None = None) -> dict:
    """
    End-to-End: resolve -> Cover laden -> m3u8 holen -> ffmpeg -> MP3.
    Gibt Pfade zurück.
    """
    track = resolve_track(href, client_id)
    title = title_override or track.get("title") or "track"
    base = slugify(title)
    os.makedirs(out_dir, exist_ok=True)

    cover = os.path.join(out_dir, f"{base}.jpg")
    transcoding = pick_hls_transcoding(track, art_out_path=cover)
    m3u8 = get_playback_m3u8_url(transcoding["url"], client_id, track.get("track_authorization"))

    mp3 = os.path.join(out_dir, f"{base}.mp3")
    # Idempotenz: wenn schon vorhanden, überspringen (optional)
    if not os.path.exists(mp3):
        run_ffmpeg_to_mp3(m3u8, mp3, art_out_path=cover)

    return {"title": title, "mp3": mp3, "cover": cover, "m3u8": m3u8}

executor = ThreadPoolExecutor(max_workers=3)#
futures = []

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", help="full path to spotify-local-dir", type=str)
    parser.add_argument("-t", help="set topsong, script will only download songs listed above", type=str)
    args = parser.parse_args()

    #Parsing arguments
    if args.s :
        print(f"setting spotify-dir to :{args.s}")
        path = args.s
        write_to_config(data=path, pos="path")

    if args.t :
        print(f"setting topsong to :{args.t}")
        topsong = args.t
        write_to_config(data=topsong, pos="topsong")

    url = "https://soundcloud.com/user352647366/likes"
    path = ""
    topsong = ""
    is_timed = False
    t_end = time.time() + 10

    #Get necessary config
    load_config()

    if url == "":
        print("No URL set!")
        url = get_input()

    #Selenium Chrome Options
    options = webdriver.ChromeOptions()
    #options.add_argument("--detach")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--window-size=1000,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    #options.add_argument("--disable-gpu") seems to break under linux
    options.add_argument("--no-sandbox")
    #options.add_argument("--start-maximized")
    options.add_argument("--headless=new")  
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    prefs = {
        "download.default_directory": os.path.abspath(path),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "detach": True,
        "profile.default_content_settings.popups": 0
    }

    #Ublock 
    extension_path = os.path.abspath("ublock.crx")
    options.add_extension(extension_path)

    options.add_experimental_option("prefs", prefs)

    #Starting webdriver
    driver = webdriver.Chrome(options=options)

    #Starting new scraping session
    print("[INFO] Starting new session")
    getSongUrl(driver, url=url, topsong=topsong, on_item=submitter)

    #Pulling songs via ffmpeg
    
    print("[INFO] Downloading songs")
    for f in as_completed(futures):
        try:
            result = f.result()
            print("[OK]", result["title"], "->", result["mp3"])
        except Exception as e:
            print("[ERROR]", e)

driver.quit()
executor.shutdown(wait=True)

