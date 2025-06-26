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
import argparse

import eyed3 #win machines also need : "pip install python-magic-bin"

import glob

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
options.add_argument("--detach")
#options.add_argument("--headless")  

prefs = {
    "download.default_directory": os.path.abspath(path),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "detach": True,
    "profile.default_content_settings.popups": 0
}

options.add_experimental_option("prefs", prefs)
driver = webdriver.Chrome(options=options)

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

# Get song URLs from SoundCloud

def scroll(driver):
    ActionChains(driver).scroll_by_amount(0, 1000000).perform()

def scroll_to_btn(driver, btn) :
    ActionChains(driver).scroll_to_element(btn)

def getSongUrl(driver, url, topsong):
    # Initialize the Chrome driver
    print(f"Starting webdriver on :{url}")
    print(f"Topsong :{topsong}")
    song_url_list = set()
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
                    song_url_list.add(song_url)
                
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

    return song_url_list, topsong

# Get artwork and MP3 for each song
def getArtworks2(driver, song_url, path):
    wait = WebDriverWait(driver, 30)
    driver.set_window_size(width=1000, height=1000)  # Für headless notwendig
    driver.get("https://soundcloudsdownloader.com/soundcloud-artwork-downloader/")
    time.sleep(5)

    # Eingabefeld und Button finden
    input_field = driver.find_element(By.TAG_NAME, "input")
    button = driver.find_element(By.ID, "codehap_submit")

    # URL eingeben und abschicken
    input_field.send_keys(song_url)
    button.click()
    time.sleep(5)

    try:
        # MP3 Download
        button_download_mp3 = driver.find_element(By.CLASS_NAME, "chbtn")
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "chbtn")))
        button_download_mp3.click()
        time.sleep(2)
        print(f"MP3 Downloaded! : {song_url}")

        # Move MP3 file
        downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        mp3_files = glob.glob(os.path.join(downloads_folder, '*.mp3'))
        latest_mp3 = max(mp3_files, key=os.path.getctime)
        print(f"Latest MP3: {latest_mp3}")

        mp3_out_folder = os.path.join(path, "out")
        os.makedirs(mp3_out_folder, exist_ok=True)
        mp3_file_path = os.path.join(mp3_out_folder, os.path.basename(latest_mp3))
        os.replace(latest_mp3, mp3_file_path)

        # Artwork Download
        button_download_artwork = driver.find_element(By.CLASS_NAME, "chbtn2")
        button_download_artwork.click()
        time.sleep(2)
        print(f"Artwork Downloaded! : {song_url}")

        # Move artwork file
        jpg_files = glob.glob(os.path.join(downloads_folder, '*.jpg'))
        latest_artwork = max(jpg_files, key=os.path.getctime)
        print(f"Latest Artwork: {latest_artwork}")

        artwork_folder = os.path.join(path, "artworks")
        os.makedirs(artwork_folder, exist_ok=True)
        artwork_file_path = os.path.join(artwork_folder, os.path.basename(latest_artwork))
        os.replace(latest_artwork, artwork_file_path)

        # Add artwork to MP3 metadata
        try:
            audiofile = eyed3.load(mp3_file_path)
            if audiofile.tag is None:
                audiofile.initTag()
            with open(artwork_file_path, "rb") as img:
                audiofile.tag.images.set(3, img.read(), "image/jpeg")
            audiofile.tag.save()
            print("Artwork in metadata hinzugefügt")
        except Exception as e:
            print(f"Fehler eyed3: {e}")

    except Exception as e:
        print(f"Error downloading: {e}")


# Main code to check songs in the directory and fetch if missing
def check_and_download_songs(driver, url, path, topsong):
    load_config()
    if url == "":
        get_input()
    else:
        if path == "":
            set_spotify_folder()

    song_url_list = getSongUrl(driver, url=url, topsong=topsong)
    set_topsong(topsong=topsong)

    # Check each song's presence in the Music directory
    for song_url in song_url_list:
        print(f"song_url :{song_url}")
        getArtworks2(driver, song_url, path=path)
    driver.quit()

load_config()
getArtworks2(driver, "https://soundcloud.com/crim3s/stay-ugly", path=path)
#check_and_download_songs(driver, url=url, path=path, topsong=topsong)