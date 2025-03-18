from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import csv
import os
import json

import eyed3 #win machines also need : "pip install python-magic-bin"

import glob

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = webdriver.ChromeOptions()
options.add_argument("--detach")
options.add_argument("--headless")  # Optional, wenn du den Browser im Hintergrund laufen lassen möchtest.
download_dir = os.path.expanduser("~/home/glockstein/pr/SCtoSP/out")

prefs = {
    "download.default_directory": os.path.abspath(download_dir),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "detach": True,
    "profile.default_content_settings.popups": 0
}

# Write whole array song URLs to CSV
def write_to_csv(song_list):
    existing_songs = read_csv()
    existing_songs.extend(song_list)
    with open("songlist.csv", 'w', newling="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([json.dumps(existing_songs)]) #nimmt ganze liste


# Read song URLs from CSV
def read_csv():
    if os.path.exists("songlist.csv") :
        with open("songlist.csv", mode="r",encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            existing_data = next(reader, ["[]"]) #if empty
            try :
                return json.loads(existing_data[0])
            except json.JSONDecodeError as e :
                print(f"JSONFEHLER: {e}")
                return []
    return []

# Get song URLs from SoundCloud

t_end = time.time() + 10
def scroll(driver):
    ActionChains(driver).scroll_by_amount(0, 1000000).perform()

def scroll_to_btn(driver, btn) :
    ActionChains(driver).scroll_to_element(btn)

def getSongUrl(driver):
    song_url_list = []
    html = driver.get("https://soundcloud.com/user352647366/likes")
    time.sleep(2)  # Give time to load the page

    # Wait for the list of songs to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "soundList__item")))

    while (time.time() < t_end):
        scroll(driver)
        time.sleep(1)

    # Parse the page content
    soup = BeautifulSoup(driver.page_source, "html.parser")

    for url in soup.find_all("li", class_="soundList__item"):
        song_url = url.find("a", class_="sc-link-primary")["href"]
        song_url_list.append("https://soundcloud.com"+song_url)

    return song_url_list
    write_to_csv(song_url_list)
    #read_csv()

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
def check_and_download_songs(driver):
    song_url_list = getSongUrl(driver)
    csv_song_list = read_csv()

    # Check each song's presence in the Music directory
    if not song_url_list == csv_song_list:
        # You need to define this function
        for song_url in song_url_list:
            print("song_url" + song_url)
            getArtworks2(driver, song_url)
    driver.quit()

# Initialize the Chrome driver
driver = webdriver.Chrome(options=options)
options.add_experimental_option("prefs", prefs)

check_and_download_songs(driver)