import csv
import json
import os

# Song-URLs in die CSV schreiben
def test_write(song_list):
    # Wenn Datei existiert, bestehende Songs laden
    existing_songs = read_csv()

    # Neue Songs hinzufügen
    existing_songs.extend(song_list)

    # In CSV-Datei speichern
    with open("songlist.csv", mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([json.dumps(existing_songs)])  # JSON-Format beibehalten

# Song-URLs aus CSV lesen
def read_csv():
    if os.path.exists("songlist.csv"):
        with open("songlist.csv", mode="r", encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            existing_data = next(reader, ["[]"])  # Falls Datei leer ist

            try:
                return json.loads(existing_data[0])  # JSON-Daten laden
            except json.JSONDecodeError as e:
                print(f"JSON-Fehler: {e}")
                return []
    return []

# Test-Daten
test_result = [
    "https://soundcloud.com/yunglasso/schneller-als-das-licht-dj-haaland-schranz-remix",
    "https://soundcloud.com/trancestrudel/filow-rasenschach-atzen-remix-free-dl"
]

test_write(test_result)
print(read_csv())  # Sollte die gleiche Struktur zurückgeben
