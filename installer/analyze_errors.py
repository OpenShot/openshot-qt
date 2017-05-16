"""Analyze archived/exported error messages and aggregate data"""
import re
import os
import json
import urllib.request
from collections import OrderedDict


# Compile error message matching regex (file path, line number)
error_regex = re.compile(r"([\\|/].*.py).*line (.*),")
openshot_version_regex = re.compile(r"\((.*)\)")

# Message folder with exported archived error messages
messages_folder = "python-exceptions"
cache_path = local_path = os.path.join(messages_folder, "cache")
version_starts_with = "2.3"
scan_cache = True

# Cache all error message attachments (download local files if missing)
if scan_cache:
    for path in os.listdir(messages_folder):
        message_path = os.path.join(messages_folder, path)
        if os.path.isfile(message_path):
            with open(message_path, "r") as f:
                for message in json.load(f):
                    if message.get("file"):
                        file_title = message.get("file").get("title")
                        file_id = message.get("file").get("id")

                        # Parse openshot version (if any)
                        version = "Unknown"
                        g = openshot_version_regex.search(file_title).groups()
                        if g:
                            version = g[0]

                        # Check version filter
                        if not version.startswith(version_starts_with):
                            # Wrong version, skip to next message
                            continue

                        # Cache attachment (if needed)
                        local_path = os.path.join(cache_path, "%s-%s" % (version, file_id))
                        if not os.path.exists(local_path):
                            attachment_url = message.get("file").get("url_private_download")
                            response = urllib.request.urlopen(attachment_url)
                            data = response.read()

                            with open(local_path, "wb") as f1:
                                print("Writing local file: %s-%s" % (version, file_id))
                                f1.write(data)
                        else:
                            print("Skip existing file: %s-%s" % (version, file_id))

# Data structures to aggregate error data {"file_name.py:line #": count}
error_dict = {}

# Iterate through local message attachments
for path in os.listdir(cache_path):
    attachment_path = os.path.join(cache_path, path)
    with open(attachment_path, "r", encoding="utf-8") as f:
        attachment_data = f.read()

        for r in error_regex.findall(attachment_data):
            file_path = r[0]
            line_num = r[1]
            file_parts = []

            # Split file path, and only keep file name (cross platform path detection)
            if "/" in file_path:
                file_parts = file_path.split("/")
            elif "\\" in file_path:
                file_parts = file_path.split("\\")

            # If __init__.py, also append folder name
            if file_parts:
                if file_parts[-1] == "__init__.py":
                    file_name = "%s/%s" % (file_parts[-2], file_parts[-1])
                else:
                    file_name = file_parts[-1]
            else:
                # Not possible to split
                file_name = file_path

            # Add key / Increment key count
            key = "%s:%s" % (file_name, line_num)
            if error_dict.get(key):
                error_dict[key] += 1
            else:
                error_dict[key] = 1

# Sort dict
for error_key in OrderedDict(sorted(error_dict.items(), key=lambda t: t[1], reverse=True)):
    print("%s\t%s" % (error_key, error_dict[error_key]))