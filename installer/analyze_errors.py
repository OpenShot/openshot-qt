"""Analyze archived/exported error messages and aggregate data"""
import re
import sys
import os
import json
from urllib.request import Request, urlopen
from collections import OrderedDict

# Read in slack token
if len(sys.argv) >= 2:
    slack_token = sys.argv[1]

# Compile error message matching regex (file path, line number)
error_regex = re.compile(r"([\\|/].*.py).*line (.*),")
c_error_regex = re.compile(r"(openshot::\w*?::.*?)\(")
c_mangled_regex = re.compile(r"ZN(\w*)\s")
openshot_version_regex = re.compile(r"\((.*)\)")

# Message folder with exported archived error messages
messages_folder = "/home/jonathan/Downloads/OpenShot Project Slack export Jul 9 2018 - Aug 8 2018/python-exceptions"
cache_path = local_path = os.path.join(messages_folder, "cache")
version_starts_with = "2.4.2"
scan_cache = False

# Create cache folder (if needed)
if not os.path.exists(cache_path):
    os.mkdir(cache_path)

# Cache all error message attachments (download local files if missing)
if scan_cache:
    for path in os.listdir(messages_folder):
        message_path = os.path.join(messages_folder, path)
        if os.path.isfile(message_path):
            with open(message_path, "r") as f:
                for message in json.load(f):
                    for file_details in message.get("files", []):
                        file_title = file_details.get("title")
                        file_id = file_details.get("id")

                        # Parse openshot version (if any)
                        version = "Unknown"
                        m = openshot_version_regex.search(file_title)
                        if m and m.groups():
                            version = m.groups()[0]

                        # Check version filter
                        if not version.startswith(version_starts_with):
                            # Wrong version, skip to next message
                            continue

                        # Cache attachment (if needed)
                        local_path = os.path.join(cache_path, "%s-%s" % (version, file_id))
                        if not os.path.exists(local_path):
                            attachment_url = file_details.get("url_private_download").split("?")[0]
                            q = Request(attachment_url)
                            q.add_header('Authorization', slack_token)
                            data = urlopen(q).read()

                            with open(local_path, "wb") as f1:
                                print("Writing local file: %s-%s" % (version, file_id))
                                f1.write(data)
                        else:
                            print("Skip existing file: %s-%s" % (version, file_id))

# Data structures to aggregate error data {"file_name.py:line #": count}
error_dict = {}

# Iterate through local message attachments
for path in os.listdir(cache_path):
    version = path.split("-")[0]
    attachment_path = os.path.join(cache_path, path)
    if version.startswith(version_starts_with):
        with open(attachment_path, "r", encoding="utf-8") as f:
            attachment_data = f.read()

            # Python Error Detection
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

            # C++ Error Detection
            for stack_line in c_error_regex.findall(attachment_data):
                # Add key / Increment key count
                key = stack_line
                if error_dict.get(key):
                    error_dict[key] += 1
                else:
                    error_dict[key] = 1

            # C++ Mangled GCC debug symbol Detection (i.e. 11QMetaObject8activateEP7QObjectiiPPv)
            for mangled_line in c_mangled_regex.findall(attachment_data):
                # Walk through the string, and fix stack line
                stack_line = ""
                current_number = ""
                current_number_int = 0
                isDigit = True
                for c in mangled_line:
                    if c.isdigit():
                        if not isDigit:
                            current_number = c
                            stack_line += "::"
                        else:
                            current_number += c
                        isDigit = True
                    else:
                        # Done with digits
                        if isDigit:
                            if current_number:
                                stack_line += c
                                current_number_int = int(current_number) - 1
                                isDigit = False
                        else:
                            if current_number_int > 0:
                                stack_line += c

                            # Decrement current number
                            current_number_int -= 1

                if not stack_line.startswith("openshot::"):
                    # Skip non-openshot methods
                    continue

                # Add key / Increment key count
                key = stack_line
                if error_dict.get(key):
                    error_dict[key] += 1
                else:
                    error_dict[key] = 1

# Ignore the following keys
ignore_keys = ["launch.py:70", "launch.py:77", "Console.py:21", "app.py:154", "app.py:164", "uic/__init__.py:224", "uic/__init__.py:220"]

# Write to output file and display the errors
parent_folder = os.path.dirname(messages_folder)
output_name = os.path.split(messages_folder)[1]
output_path = os.path.join(parent_folder, "%s.txt" % output_name)
with open(output_path, "w") as f:
    for error_key in OrderedDict(sorted(error_dict.items(), key=lambda t: t[1], reverse=True)):
        if error_key not in ignore_keys:
            error_line = "%s\t%s" % (error_key, error_dict[error_key])
            f.write(error_line + "\n")
            print(error_line)