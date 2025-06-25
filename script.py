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
options.add_argument("--headless")  

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
    print("Starting webdriver on :{url}")
    song_url_list = set()
    html = driver.get(url)
    time.sleep(2)  # Give time to load the page

    # Wait for the list of songs to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "soundList__item")))

    start_time = time.time()

    while True:
        # Parse the page content
        soup = BeautifulSoup(driver.page_source, "html.parser")
        topsong = soup.find("li", class_="soundList__item")
        for url in soup.find_all("li", class_="soundList__item"):
            if not url:
                print("No songs found..")
                break
            if url != topsong:
                song_url = url.find("a", class_="sc-link-primary")["href"]
                song_url_list.add("https://soundcloud.com"+song_url)
            else : print(f"Topsong reached :{topsong}") 
            break

    scroll(driver)
    time.sleep(1)

    return song_url_list, topsong

# Get artwork and MP3 for each song
def getArtworks2(driver, song_url):
    wait = WebDriverWait(driver,30)
    driver.set_window_size(width=1000, height=1000) #needed for headless to find elements
    driver.get("https://soundcloudsdownloader.com/soundcloud-artwork-downloader/")
    time.sleep(2)  # Wait for the page to load

    # Find input field and submit button on the page
    input_field = driver.find_element(By.TAG_NAME, "input")
    button = driver.find_element(By.ID, "codehap_submit")
    
    # Submit song URL
    input_field.send_keys(song_url)
    button.click()
    time.sleep(5)

    # Download MP3 and artwork
    try:
        button_download_mp3 = driver.find_element(By.CLASS_NAME, "chbtn")
        wait.until(EC.element_to_be_clickable(button_download_mp3))
        button_download_mp3.click()
        time.sleep(2)
        print(f"MP3 Downloaded! : {song_url}")
        #Move file to dir
        list_of_files = glob.glob('/home/glockstein/Downloads/*.mp3') #check for .mp3 files
        latest_file = max(list_of_files, key=os.path.getctime) #get creation_time
        print(f"neuste mp3 :{latest_file}")
        dir_to = "/home/glockstein/pr/SCtoSP/out/"+os.path.basename(latest_file) # erstellt dirname mit filename 
        mp3_file_path = dir_to = "/home/glockstein/pr/SCtoSP/out/"+os.path.basename(latest_file) #needed for eyed3
        os.replace(latest_file, dir_to) # moved file zu neuen dir+file_name

        button_download_artwork = driver.find_element(By.CLASS_NAME, "chbtn2")
        #wait.until(EC.element_to_be_clickable(button_download_artwork))
        button_download_artwork.click()
        time.sleep(2)
        print(f"Artwork Downloaded! : {song_url}")
        #Move file to dir
        list_of_files = glob.glob('/home/glockstein/Downloads/*.jpg') #check for .mp3 files
        latest_file = max(list_of_files, key=os.path.getctime) #get creation_time
        print(f"neustes Artowrk :{latest_file}")
        dir_to = "/home/glockstein/pr/SCtoSP/artworks/"+os.path.basename(latest_file)
        artwork_file_path = "/home/glockstein/pr/SCtoSP/artworks/"+os.path.basename(latest_file) #needed for eyed3
        os.replace(latest_file, dir_to)
        
        #Adding cover to metadata
        try :
            audiofile = eyed3.load(mp3_file_path)
            if audiofile.tag is None:
                audiofile.initTag()
            with open(artwork_file_path, "rb") as img:
                audiofile.tag.images.set(3, img.read(), "image/jpg")
            print(audiofile.info)
            audiofile.tag.save()
            print("Artwork in metadata hinzugefügt")
        except Exception as e:
            print(f"Fehler eyed3 : {e}")
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
        print("song_url" + song_url)
        getArtworks2(driver, song_url)
    driver.quit()

load_config()
check_and_download_songs(driver, url=url, path=path, topsong=topsong)