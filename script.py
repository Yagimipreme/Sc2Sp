from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import csv
import os
import json
import subprocess
import shutil
import json
import random
import argparse
import glob

import eyed3 #win machines also need : "pip install python-magic-bin"

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

url = ""
path = ""
topsong = ""
is_timed = False
t_end = time.time() + 10

def load_config(filename="config.json"):
    with open(filename, "r") as f:
        config = json.load(f)
    return config["url"], config["path"], config["topsong"]
url, path, topsong = load_config()

parser = argparse.ArgumentParser()
parser.add_argument("-s", help="full path to spotify-local-dir", type=str)
parser.add_argument("-t", help="set topsong, script will only download songs listed above", type=str)
args = parser.parse_args()

if args.s :
    print(f"setting spotify-dir to :{args.s}")
    path = args.s
    write_to_config(data=path, pos="path")

if args.t :
    print(f"setting topsong to :{args.t}")
    topsong = args.t
    write_to_config(data=topsong, pos="topsong")

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

driver = webdriver.Chrome(options=options)
#driver = webdriver.Chrome()

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

def getSongUrl(driver, url, topsong):
    # Initialize the Chrome driver
    print(f"Starting webdriver on :{url}")
    print(f"Topsong :{topsong}")
    song_url_list = []
    html = driver.get(url)
    time.sleep(2)  # Give time to load the page

    # Wait for the list of songs to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "soundList__item")))

    start_time = time.time()

    while True:
        # Parse the page content
        soup = BeautifulSoup(driver.page_source, "html.parser")
        song_elements = soup.find_all("li", class_="soundList__item")

        if not song_elements:
            print(f"No songs found..")
            break

        found_topsong = False

        for item in song_elements:
            try:
                song_url = item.find("a", class_="sc-link-primary")["href"]
                if song_url not in song_url_list:
                    print(f"FOUND :{song_url}")
                    song_url_list.append(song_url)
                
                if song_url == topsong:
                    print(f"Topsong reached :{topsong}")
                    found_topsong = True
                    break

            except Exception as e:
                print(f"Failed at :{e}")
                continue

        if found_topsong:
            break

        scroll(driver)
        time.sleep(2)

    return list(song_url_list), topsong#noch topsong zurückgeben

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
        print(f"🗂️ Artwork verschoben nach: {new_artwork_path}")

    except Exception as e:
        print(f"Fehler beim Hinzufügen des Artworks: {e}")

def get_latest_mp3(download_folder): 
        mp3_files = glob.glob(os.path.join(download_folder, '*mp3'))
        if not mp3_files:
            print("No mp3 found for eyed3")
            return None
        latest_mp3 = max(mp3_files, key=os.path.getctime)
        return latest_mp3

#add_artwork_to_mp3(get_latest_mp3(path),download_folder=download_folder)
check_and_download_songs(driver, url=url, path=path, topsong=topsong)
#print(audiofile = eyed3.load('Moneyboy-Monte Carlo(Franzhakke Edit).mp3'))