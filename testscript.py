import os
import json
import subprocess
import shutil
import pathlib
import argparse
import json 

url = ""
path = ""
topsong = ""
is_timed = False

def load_config(filename="config.json"):
    with open(filename, "r") as f:
        config = json.load(f)
    return config["url"], config["path"], config["topsong"]
url, path, topsong = load_config()


def get_input():
        print("Enter Path :")
        path = input().strip()
        return path

load_config()

def write_to_config(data, pos, filename="config.json"):
    with open(filename, "r") as f:
        config = json.load(f)
        config[pos] = data

        with open(filename, "w") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

testarr = ["a", "b", "c", "d"]

for i in testarr:
    if i == topsong :
        

#print(f"url : {url}")
#print(f"path : {path}")
print(f"topsong : {topsong}")