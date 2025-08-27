from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
import time
import csv
import os
import subprocess
import shutil
import json
import random
import argparse
import glob
from dotenv import load_dotenv
import eyed3 #win machines also need : "pip install python-magic-bin"

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

def getSongUrl(driver, url, topsong):
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

    max_scrolls = 60
    min_wait_new = 0.5
    wait = WebDriverWait(driver, 10)

    start_time = time.time()

    for i in range(max_scrolls):
        anchors = driver.find_elements(
            By.CSS_SELECTOR, "li.soundcloud__item a.sc-link-primary[href]"
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

                if topsong_norm and _norm(hreef) == topsong_norm:
                    print(f"Topsong reached: {topsong_norm}")
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

# Get artwork and MP3 for each song
def getArtworks2(driver, song_url, path):
    print(f"PATH :{path}")
    wait = WebDriverWait(driver, 30)
    #driver.set_window_size(width=1000, height=1000)  # Für headless notwendig
    driver.get("https://soundcloudsdownloader.com/soundcloud-artwork-downloader/")

    # Eingabefeld und Button finden
    input_field = driver.find_element(By.TAG_NAME, "input")
    button = driver.find_element(By.ID, "codehap_submit")

    # URL eingeben und abschicken
    print(song_url)
    input_field.send_keys("https://soundcloud.com"+song_url)
    button.click()
    print(f"Song submitted")
    try:
        time.sleep(random.uniform(3,6))
        button_download_mp3 = WebDriverWait(driver, 100).until(EC.element_to_be_clickable((By.CLASS_NAME, "chbtn")))
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("arguments[0].scrollIntoView(true);", button_download_mp3)
        time.sleep(random.uniform(2,6))
        button_download_mp3 = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "chbtn")))
        button_download_mp3.click()
        wait_for_download(path=path)
        print(f"MP3 Downloaded! : {song_url}")
    except Exception as e:
        print(f"Err clickinf download-btn :{e}")
        with open("debug.html", "w") as f:
            f.write(driver.page_source)

    # Artwork Download
    try: 
        button_download_artwork = driver.find_element(By.CLASS_NAME, "chbtn2")
        time.sleep(random.uniform(2,6))
        button_download_artwork.click()
        wait_for_download(path=path)
        print(f"Artwork Downloaded! : {song_url}")
        time.sleep(random.uniform(3,6))
    except Exception as e:
        print(f"Could not download artwork")


# Main code 
def check_and_download_songs(driver, url, path, topsong):
    load_config()
    if url == "":
        get_input()
    else:
        if path == "":
            set_spotify_folder()

    song_url_list, topsong = getSongUrl(driver, url=url, topsong=topsong)
    set_topsong(topsong=topsong)
    print(song_url_list)
    # Download artwork and eyed3 into the mp3 for each song
    for song_url in list(song_url_list):
        print(f"song_url :{song_url}")
        getArtworks2(driver, song_url, path=path)
        time.sleep(3)
        add_artwork_to_mp3(get_latest_mp3(path),path)

    driver.quit()

def add_artwork_to_mp3(mp3_file_path, download_folder):
    try:
        # Suche nach JPG oder PNG
        image_files = glob.glob(os.path.join(download_folder, '*.jpg')) + \
                      glob.glob(os.path.join(download_folder, '*.png'))

        if not image_files:
            print("Kein Artwork gefunden.")
            return

        # Neueste Bilddatei auswählen
        latest_artwork = max(image_files, key=os.path.getctime)
        print(f"Gefundenes Artwork: {latest_artwork}")

        # Bestimme MIME-Type
        if latest_artwork.lower().endswith('.png'):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"

        # MP3 laden
        audiofile = eyed3.load(mp3_file_path)
        if audiofile is None:
            print("MP3 konnte nicht geladen werden.")
            return

        if audiofile.tag is None:
            audiofile.initTag()

        # Artwork hinzufügen
        with open(latest_artwork, "rb") as img_fp:
            audiofile.tag.images.set(
                3,  # Front cover
                img_fp.read(),
                mime_type
            )

        audiofile.tag.save()
        print("Artwork erfolgreich in MP3 eingebettet.")

        # Artwork verschieben
        artwork_folder = os.path.join(download_folder, "artworks")
        os.makedirs(artwork_folder, exist_ok=True)
        new_artwork_path = os.path.join(artwork_folder, os.path.basename(latest_artwork))
        os.replace(latest_artwork, new_artwork_path)
        print(f"Artwork verschoben nach: {new_artwork_path}")

    except Exception as e:
        print(f"Fehler beim Hinzufügen des Artworks: {e}")

def get_latest_mp3(download_folder): 
        mp3_files = glob.glob(os.path.join(download_folder, '*mp3'))
        if not mp3_files:
            print("No mp3 found for eyed3")
            return None
        latest_mp3 = max(mp3_files, key=os.path.getctime)
        return latest_mp3

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
    getSongUrl(driver, url=url, topsong=topsong)


#add_artwork_to_mp3(get_latest_mp3(path),download_folder=download_folder)
#ächeck_and_download_songs(driver, url=url, path=path, topsong=topsong)
#audiofile = eyed3.load('/home/glockstein/Songs/Santigold - Disparate Youth [Rave Edit] (FREE DL).mp3')
#print(audiofile.tag.images)