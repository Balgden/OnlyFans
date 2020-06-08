import csv
import json
import logging
import os
from os.path import dirname as up
import platform
import re
from itertools import chain

from bs4 import BeautifulSoup
import requests

path = up(up(os.path.realpath(__file__)))
os.chdir(path)

# Open config.json and fill in OPTIONAL information
json_global_settings = None
os_name = platform.system()


def assign_vars(config):
    global json_global_settings

    json_config = config
    json_global_settings = json_config["settings"]


def rename_duplicates(seen, filename):
    filename_lower = filename.lower()
    if filename_lower not in seen:
        seen.add(filename_lower)
    else:
        count = 1
        while filename_lower in seen:
            filename = filename+" ("+str(count)+")"
            filename_lower = filename.lower()
            count += 1
        seen.add(filename_lower)
    return [seen, filename]


def parse_links(site_name, input_link):
    if site_name in {"onlyfans", "starsavn"}:
        username = input_link.rsplit('/', 1)[-1]
        return username

    if site_name in {"fourchan", "bbwchan"}:
        if "catalog" in input_link:
            input_link = input_link.split("/")[1]
            print(input_link)
            return input_link
        if input_link[-1:] == "/":
            input_link = input_link.split("/")[3]
            return input_link
        if "4chan.org" not in input_link:
            return input_link


def clean_text(string, remove_spaces=False):
    matches = ["\n", "<br>"]
    for m in matches:
        string = string.replace(
            m, " ").strip()
    string = ' '.join(string.split())
    string = BeautifulSoup(string, 'lxml').get_text()
    SAFE_PTN = "[^0-9a-zA-Z-_.'()]+"
    string = re.sub(SAFE_PTN, ' ',  string.strip()
                    ).strip()
    if remove_spaces:
        string = string.replace(' ', '_')
    return string


def reformat(directory, post_id,media_id, file_name, text, ext, date, username, format_path, date_format, maximum_length):
    post_id = "" if post_id is None else str(post_id)
    media_id = "" if media_id is None else str(media_id)
    has_text = False
    if "{text}" in format_path:
        has_text = True
    path = format_path.replace("{post_id}", post_id)
    path = path.replace("{media_id}", media_id)
    path = path.replace("{username}", username)
    filtered_text = text[:maximum_length]
    directory = directory.replace(text, filtered_text)
    path = path.replace("{text}", filtered_text)
    date = date.strftime(date_format)
    path = path.replace("{date}", date)
    path = path.replace("{file_name}", file_name)
    path = path.replace("{ext}", ext)
    directory2 = directory + path

    if has_text:
        count_string = len(path)
        text_count = len(filtered_text)
        if count_string > maximum_length:
            text_limit = count_string - text_count
            path = path.replace(
                filtered_text, filtered_text[:-text_limit])
            directory2 = directory + path
    return directory2


def format_media_set(location, media_set):
    x = {}
    x["type"] = location
    x["valid"] = []
    x["invalid"] = []
    for y in media_set:
        x["valid"].extend(y[0])
        x["invalid"].extend(y[1])
    return x


def format_image(directory, timestamp):
    if os_name == "Windows":
        from win32_setctime import setctime
        setctime(directory, timestamp)


def export_archive(datas, archive_directory):
    # Not Finished
    export_type = json_global_settings["export_type"]
    if export_type == "json":
        with open(archive_directory+".json", 'w') as outfile:
            json.dump(datas, outfile)
    if export_type == "csv":
        with open(archive_directory+'.csv', mode='w', encoding='utf-8', newline='') as csv_file:
            for data in datas:
                fieldnames = []
                media_type = data["type"].lower()
                valid = list(chain.from_iterable(data["valid"]))
                invalid = list(chain.from_iterable(data["invalid"]))
                if valid:
                    fieldnames.extend(valid[0].keys())
                elif invalid:
                    fieldnames.extend(invalid[0].keys())
                header = [media_type]+fieldnames
                if len(fieldnames) > 1:
                    writer = csv.DictWriter(csv_file, fieldnames=header)
                    writer.writeheader()
                    for item in valid:
                        writer.writerow({**{media_type: "valid"}, **item})
                    for item in invalid:
                        writer.writerow({**{media_type: "invalid"}, **item})


def get_directory(directory):
    if directory:
        directory = os.path.expanduser(directory)
        os.makedirs(directory, exist_ok=True)
        return directory
    else:
        return os.path.abspath(".sites")


def format_directory(j_directory, site_name, username, location="", api_type=""):
    directory = j_directory

    user_directory = directory+"/"+site_name + "/"+username+"/"
    metadata_directory = user_directory+"Metadata/"
    directories = []
    count = 0
    cats = ["", "Free", "Paid"]
    if "/sites/" == j_directory:
        user_directory = os.path.dirname(os.path.dirname(
            os.path.realpath(__file__))) + user_directory
        metadata_directory = os.path.dirname(os.path.dirname(
            os.path.realpath(__file__))) + metadata_directory
        for cat in cats:
            directories.append(
                [location, os.path.join(user_directory, api_type, cat, location+"/")])
    else:
        for cat in cats:
            directories.append(
                [location, os.path.join(user_directory, api_type, cat, location+"/")])
        count += 1
    return [user_directory, metadata_directory, directories]


def are_long_paths_enabled():
    if os_name == "Windows":
        from ctypes import WinDLL, c_ubyte
        ntdll = WinDLL('ntdll')

        if hasattr(ntdll, 'RtlAreLongPathsEnabled'):

            ntdll.RtlAreLongPathsEnabled.restype = c_ubyte
            ntdll.RtlAreLongPathsEnabled.argtypes = ()
            return bool(ntdll.RtlAreLongPathsEnabled())

        else:
            return False


def check_for_dupe_file(download_path, content_length):
    found = False
    if os.path.isfile(download_path):
        local_size = os.path.getsize(download_path)
        if local_size == content_length:
            found = True
    return found


def json_request(session, link, method="GET", stream=False, json_format=True, data={}):
    count = 0
    while count < 11:
        try:
            headers = session.headers
            if json_format:
                headers["accept"] = "application/json, text/plain, */*"
            if data:
                r = session.request(method, link, json=data, stream=stream)
            else:
                r = session.request(method, link, stream=stream)
            content_type = r.headers['Content-Type']
            if json_format:
                if "application/json;" not in content_type:
                    count += 1
                    continue
                return json.loads(r.text)
            else:
                return r
        except (ConnectionResetError) as e:
            log_error.exception(e)
            count += 1
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            log_error.exception(e)
            count += 1
        except Exception as e:
            log_error.exception(e)
            count += 1
            # input("Enter to continue")


def update_config(json_config):
    path = os.path.join('.settings', 'config.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(json_config, f, ensure_ascii=False, indent=2)


def choose_auth(array):
    string = ""
    names = []
    array = [{"auth_count": -1, "username": "All"}]+array
    name_count = len(array)
    if name_count > 1:

        count = 0
        for x in array:
            name = x["username"]
            string += str(count)+" = "+name
            names.append(x)
            if count+1 != name_count:
                string += " | "

            count += 1

    print("Auth Usernames: "+string)
    value = int(input().strip())
    if value:
        names = [names[value]]
    else:
        names.pop(0)
    return names


def is_me(user_api):
    if "email" in user_api:
        return True
    else:
        return False


def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""
    log_filename = ".logs/"+log_file
    os.makedirs(os.path.dirname(log_filename), exist_ok=True)
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s')

    handler = logging.FileHandler(log_filename, 'w+', encoding='utf-8')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


log_error = setup_logger('errors', 'errors.log')
