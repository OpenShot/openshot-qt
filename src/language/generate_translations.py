#!/usr/bin/python3
"""
 @file
 @brief This file updates the OpenShot.POT (language translation template) by scanning all source files.
 @author Jonathan Thomas <jonathan@openshot.org>

 This file helps you generate the POT file that contains all of the translatable
 strings / text in OpenShot.  Because some of our text is in custom XML files,
 the xgettext command can't correctly generate the POT file.  Thus... the
 existence of this file. =)

 Command to create the individual language PO files (Ascii files)
		$ msginit --input=OpenShot.pot --locale=fr_FR
		$ msginit --input=OpenShot.pot --locale=es

 Command to update the PO files (if text is added or changed)
		$ msgmerge en_US.po OpenShot.pot -U
		$ msgmerge es.po OpenShot.pot -U

 Command to compile the Ascii PO files into binary MO files
		$ msgfmt en_US.po --output-file=en_US/LC_MESSAGES/OpenShot.mo
		$ msgfmt es.po --output-file=es/LC_MESSAGES/OpenShot.mo

 Command to compile all PO files in a folder
		$ find -iname "*.po" -exec msgfmt {} -o {}.mo \\;

 Command to combine the 2 pot files into 1 file
       $ msgcat ~/openshot/locale/OpenShot/OpenShot_source.pot ~/openshot/openshot/locale/OpenShot/OpenShot_glade.pot -o ~/openshot/main/locale/OpenShot/OpenShot.pot

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import shutil
import datetime
import os
import subprocess
import sys
import re
import json

# Try to get the security-patched XML functions from defusedxml
try:
  from defusedxml import minidom as xml
except ImportError:
  from xml.dom import minidom as xml

import openshot

# Get the absolute path of this project
path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if path not in sys.path:
    sys.path.append(path)

import classes.info as info
from classes.logger import log
from classes.effect_init import effect_options

# get the path of the main OpenShot folder
language_folder_path = os.path.dirname(os.path.abspath(__file__))
openshot_path = os.path.dirname(language_folder_path)
effects_path = os.path.join(openshot_path, 'effects')
blender_path = os.path.join(openshot_path, 'blender')
transitions_path = os.path.join(openshot_path, 'transitions')
titles_path = os.path.join(openshot_path, 'titles')
export_path = os.path.join(openshot_path, 'presets')
windows_ui_path = os.path.join(openshot_path, 'windows', 'ui')

log.info("-----------------------------------------------------")
log.info(" Creating temp POT files")
log.info("-----------------------------------------------------")

# create empty temp POT files
temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot', 'OpenShot_effects.pot', 'OpenShot_export.pot',
              'OpenShot_transitions.pot', 'OpenShot_QtUi.pot']
for temp_file_name in temp_files:
    temp_file_path = os.path.join(language_folder_path, temp_file_name)
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
    f = open(temp_file_path, "w")
    f.close()

log.info("-----------------------------------------------------")
log.info(" Using xgettext to generate .py POT files")
log.info("-----------------------------------------------------")

# Generate POT for Source Code strings (i.e. strings marked with a _("translate me"))
subprocess.call(r'find %s -iname "*.py" -exec xgettext -j -o %s --keyword=_ {} \;' % (
    openshot_path, os.path.join(language_folder_path, 'OpenShot_source.pot')), shell=True)

log.info("-----------------------------------------------------")
log.info(" Using Qt's lupdate to generate .ui POT files")
log.info("-----------------------------------------------------")

# Generate POT for Qt *.ui files (which require the lupdate command, and ts2po command)
os.chdir(windows_ui_path)
subprocess.call('lupdate *.ui -ts %s' % (os.path.join(language_folder_path, 'OpenShot_QtUi.ts')), shell=True)
subprocess.call('lupdate *.ui -ts %s' % (os.path.join(language_folder_path, 'OpenShot_QtUi.pot')), shell=True)
os.chdir(language_folder_path)

# Rewrite the UI POT, removing msgctxt
output = open(os.path.join(language_folder_path, "clean.po"), 'w')
for line in open(os.path.join(language_folder_path, 'OpenShot_QtUi.pot'), 'r'):
    if not line.startswith('msgctxt'):
        output.write(line)
# Overwrite original PO file
output.close()
shutil.copy(os.path.join(language_folder_path, "clean.po"), os.path.join(language_folder_path, 'OpenShot_QtUi.pot'))
os.remove(os.path.join(language_folder_path, "clean.po"))

# Remove duplicates (if any found)
subprocess.call('msguniq %s --use-first -o %s' % (os.path.join(language_folder_path, 'OpenShot_QtUi.pot'),
                                                  os.path.join(language_folder_path, 'clean.po')), shell=True)
shutil.copy(os.path.join(language_folder_path, "clean.po"), os.path.join(language_folder_path, 'OpenShot_QtUi.pot'))
os.remove(os.path.join(language_folder_path, "clean.po"))


log.info("-----------------------------------------------------")
log.info(" Updating auto created POT files to set CharSet")
log.info("-----------------------------------------------------")

temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot']
for temp_file in temp_files:
    # get the entire text
    f = open(os.path.join(language_folder_path, temp_file), "r")
    # read entire text of file
    entire_source = f.read()
    f.close()

    # replace charset
    entire_source = entire_source.replace("charset=CHARSET", "charset=UTF-8")

    # Create Updated POT Output File
    if os.path.exists(os.path.join(language_folder_path, temp_file)):
        os.remove(os.path.join(language_folder_path, temp_file))
    f = open(os.path.join(language_folder_path, temp_file), "w")
    f.write(entire_source)
    f.close()

log.info("-----------------------------------------------------")
log.info(" Scanning effects & resources used by OpenShot")
log.info("-----------------------------------------------------")

props = json.loads(openshot.Clip().PropertiesJSON(1))

# Loop through props
effects_text = {}
for key in props.keys():
    property = props[key]
    if "name" in property:
        effects_text[property["name"]] = "libopenshot (Clip Properties)"
    if "choices" in property:
        for choice in property["choices"]:
            effects_text[choice["name"]] = "libopenshot (Clip Properties)"

# Loop through each libopenshot effect
objects = json.loads(openshot.EffectInfo.Json())
for object in objects:
    class_name = object.get("class_name")
    props = json.loads(openshot.EffectInfo().CreateEffect(class_name).PropertiesJSON(1))

    # Loop through props
    for key in props.keys():
        property = props[key]
        if key == "objects":
            continue # Skip tracker / object detection property
        if "name" in property:
            effects_text[property["name"]] = "libopenshot (Effect Properties)"
        if "choices" in object:
            for choice in property["choices"]:
                effects_text[choice["name"]] = "libopenshot (Effect Properties)"

# Append Effect Init Data
# Loop through props
for effect in effect_options:
    for param in effect_options[effect]:
        if "title" in param:
            effects_text[param["title"]] = "effect_init (Effect parameter for %s)" % effect
        if "values" in param:
            for value in param["values"]:
                effects_text[value["name"]] = "effect_init (Effect parameter for %s)" % effect

# Append Effect Meta Data
e = openshot.EffectInfo()
props = json.loads(e.Json())

# Loop through props
for effect in props:
    if "name" in effect:
        effects_text[effect["name"]] = "libopenshot (Effect Metadata)"
    if "description" in effect:
        effects_text[effect["description"]] = "libopenshot (Effect Metadata)"

# Append LUT category and file names (for ColorMap effect)
for folder in os.listdir(info.COLORS_PATH):
    category_name = folder.replace("_", " ").title()
    folder_path = os.path.join(info.COLORS_PATH, folder)
    if os.path.isdir(folder_path):
        for filename in os.listdir(folder_path):
            basename, extension = os.path.splitext(filename)
            if filename.endswith(".cube"):
                lut_name = basename.replace("_", " ").title()
                effects_text[category_name] = "ColorMap effect lookup (Category)"
                effects_text[lut_name] = "ColorMap effect lookup (Name)"

# Append Emoji Data
emoji_text = { "translator-credits": "Translator credits to be translated by LaunchPad" }
emoji_metadata_path = os.path.join(info.PATH, "emojis", "data", "openmoji-optimized.json")
emoji_ignore_keys = ("Keyboard", "Sunset", "Key", "Right arrow", "Left arrow", "Bubbles",
                     "Twitter", "Instagram", "Scale", "Simple", "Close", "Forward", "Copy",
                     "Filter", "Details", "Duplicate", "Edit", "Delete")
with open(emoji_metadata_path, 'r', encoding="utf-8") as f:
    emoji_metadata = json.load(f)

    # Loop through props
    for filename, emoji in emoji_metadata.items():
        emoji_name = emoji["annotation"].capitalize()
        emoji_group = emoji["group"].split('-')[0].capitalize()
        if "annotation" in emoji and emoji_name not in emoji_ignore_keys:
            emoji_text[emoji_name] = "Emoji Metadata (Displayed Name)"
        if "group" in emoji and emoji_group not in effects_text and emoji_group not in emoji_ignore_keys:
            emoji_text[emoji_group] = "Emoji Metadata (Group Filter name)"

# Loop through the Blender XML
blender_text = { "translator-credits": "Translator credits to be translated by LaunchPad" }
blender_ignore_keys = ("Title", "Alpha", "Blur", "Font Name", "Yes", "No", "On", "Off", "Default")
for file in os.listdir(blender_path):
    if os.path.isfile(os.path.join(blender_path, file)):
        # load xml effect file
        full_file_path = os.path.join(blender_path, file)
        xmldoc = xml.parse(os.path.join(blender_path, file))

        # add text to list
        translation_key = xmldoc.getElementsByTagName("title")[0].childNodes[0].data
        if translation_key not in blender_ignore_keys:
            blender_text[translation_key] = full_file_path

        # get params
        params = xmldoc.getElementsByTagName("param")

        # Loop through params
        for param in params:
            if param.attributes["title"]:
                translation_key = param.attributes["title"].value
                if translation_key not in blender_ignore_keys:
                    blender_text[param.attributes["title"].value] = full_file_path

                    # Loop through child nodes of each param
                    for child in param.childNodes:
                        if child.nodeName == "values":
                            for value in child.getElementsByTagName("value"):
                                if value.hasAttribute("name"):
                                    value_name = value.getAttribute("name")
                                    if value_name not in blender_ignore_keys:
                                        blender_text[value_name] = full_file_path

# Loop through the Export Settings XML
export_text = {}
for file in os.listdir(export_path):
    if os.path.isfile(os.path.join(export_path, file)):
        # load xml export file
        full_file_path = os.path.join(export_path, file)
        xmldoc = xml.parse(os.path.join(export_path, file))

        # add text to list
        export_text[xmldoc.getElementsByTagName("type")[0].childNodes[0].data] = full_file_path
        export_text[xmldoc.getElementsByTagName("title")[0].childNodes[0].data] = full_file_path

# Loop through Settings
settings_file = open(os.path.join(info.PATH, 'settings', '_default.settings'), 'r').read()
settings = json.loads(settings_file)
category_names = []
for setting in settings:
    if "type" in setting and setting["type"] != "hidden":
        # Add visible settings
        export_text[setting["title"]] = "Settings for %s" % setting["setting"]
    if "type" in setting and setting["type"] != "hidden":
        # Add visible category names
        if setting["category"] not in category_names:
            export_text[setting["category"]] = "Settings Category for %s" % setting["category"]
            category_names.append(setting["category"])
        if "translate_values" in setting and setting.get("translate_values"):
            # Add translatable dropdown keys
            for value in setting.get("values", []):
                export_text[value["name"]] = "Settings for %s" % setting["setting"]

# Include UI Theme Names (for translation)
from themes.manager import ThemeName
for theme_name in ThemeName.get_sorted_theme_names():
    export_text[theme_name] = "User-Interface Theme Name"

# Loop through transitions and add to POT file
transitions_text = { "translator-credits": "Translator credits to be translated by LaunchPad" }
transitions_ignore_keys = ("Common", "Fade")
for file in os.listdir(transitions_path):
    # load xml export file
    full_file_path = os.path.join(transitions_path, file)
    (fileBaseName, fileExtension) = os.path.splitext(file)

    # get transition name
    name = fileBaseName.replace("_", " ").capitalize()

    # add text to list
    if name not in transitions_ignore_keys:
        transitions_text[name] = full_file_path

    # Look in sub-folders
    for sub_file in os.listdir(full_file_path):
        # load xml export file
        full_subfile_path = os.path.join(full_file_path, sub_file)
        fileBaseName = os.path.splitext(sub_file)[0]

        # split the name into parts (looking for a number)
        suffix_number = None
        name_parts = fileBaseName.split("_")
        if name_parts[-1].isdigit():
            suffix_number = name_parts[-1]

        # get transition name
        name = fileBaseName.replace("_", " ").capitalize()

        # replace suffix number with placeholder (if any)
        if suffix_number:
            name = name.replace(suffix_number, "%s")

        # add text to list
        if name not in transitions_ignore_keys:
            transitions_text[name] = full_subfile_path

# Loop through titles and add to POT file
for sub_file in os.listdir(titles_path):
    # load xml export file
    full_subfile_path = os.path.join(titles_path, sub_file)
    fileBaseName = os.path.splitext(sub_file)[0]

    # split the name into parts (looking for a number)
    suffix_number = None
    name_parts = fileBaseName.split("_")
    if name_parts[-1].isdigit():
        suffix_number = name_parts[-1]

    # get transition name
    name = fileBaseName.replace("_", " ").capitalize()

    # replace suffix number with placeholder (if any)
    if suffix_number:
        name = name.replace(suffix_number, "%s")

    # add text to list
    transitions_text[name] = full_subfile_path


log.info("-----------------------------------------------------")
log.info(" Creating the custom XML POT files")
log.info("-----------------------------------------------------")

# header of POT file
header_text = ""
header_text = header_text + '# OpenShot Video Editor POT Template File.\n'
header_text = header_text + '# Copyright (C) 2008-2018 OpenShot Studios, LLC\n'
header_text = header_text + '# This file is distributed under the same license as OpenShot.\n'
header_text = header_text + '# Jonathan Thomas <Jonathan.Oomph@gmail.com>, 2018.\n'
header_text = header_text + '#\n'
header_text = header_text + '#, fuzzy\n'
header_text = header_text + 'msgid ""\n'
header_text = header_text + 'msgstr ""\n'
header_text = header_text + '"Project-Id-Version: OpenShot Video Editor (version: %s)\\n"\n' % info.VERSION
header_text = header_text + '"Report-Msgid-Bugs-To: Jonathan Thomas <Jonathan.Oomph@gmail.com>\\n"\n'
header_text = header_text + '"POT-Creation-Date: %s\\n"\n' % datetime.datetime.now()
header_text = header_text + '"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"\n'
header_text = header_text + '"Last-Translator: Jonathan Thomas <Jonathan.Oomph@gmail.com>\\n"\n'
header_text = header_text + '"Language-Team: https://translations.launchpad.net/+groups/launchpad-translators\\n"\n'
header_text = header_text + '"MIME-Version: 1.0\\n"\n'
header_text = header_text + '"Content-Type: text/plain; charset=UTF-8\\n"\n'
header_text = header_text + '"Content-Transfer-Encoding: 8bit\\n"\n'

# Create POT files for the custom text (from our XML files)
temp_files = [['OpenShot_effects.pot', effects_text],
              ['OpenShot_export.pot', export_text],
              ['OpenShot_transitions.pot', transitions_text],
              ['OpenShot_emojis.pot', emoji_text],
              ['OpenShot_blender.pot', blender_text]
              ]
for temp_file, text_dict in temp_files:
    f = open(temp_file, "w")

    # write header
    f.write(header_text)

    # loop through each line of text
    for k, v in text_dict.items():
        if k:
            f.write('\n')
            f.write('#: %s\n' % v)
            f.write('msgid "%s"\n' % k)
            f.write('msgstr ""\n')

    # close file
    f.close()

log.info("-----------------------------------------------------")
log.info(" Combine all temp POT files using msgcat command ")
log.info(" (this removes dupes) ")
log.info("-----------------------------------------------------")

temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot', 'OpenShot_effects.pot',
              'OpenShot_export.pot', 'OpenShot_QtUi.pot']
command = "msgcat"
for temp_file in temp_files:
    # append files
    command = command + " " + os.path.join(language_folder_path, temp_file)
command = command + " -o " + os.path.join(language_folder_path, "OpenShot", "OpenShot.pot")

log.info(command)

# merge all 4 temp POT files
subprocess.call(command, shell=True)

log.info("-----------------------------------------------------")
log.info(" Create FINAL POT File from all temp POT files ")
log.info("-----------------------------------------------------")

# get the entire text of OpenShot.POT
f = open(os.path.join(language_folder_path, "OpenShot", "OpenShot.pot"), "r")
# read entire text of file
entire_source = f.read()
f.close()

# Create Final POT Output File
if os.path.exists(os.path.join(language_folder_path, "OpenShot", "OpenShot.pot")):
    os.remove(os.path.join(language_folder_path, "OpenShot", "OpenShot.pot"))
final = open(os.path.join(language_folder_path, "OpenShot", "OpenShot.pot"), "w")
final.write(header_text)
final.write("\n")

# Move transitions POT file to final location
if os.path.exists(os.path.join(language_folder_path, "OpenShot_transitions.pot")):
    os.rename(os.path.join(language_folder_path, "OpenShot_transitions.pot"),
              os.path.join(language_folder_path, "OpenShot", "OpenShot_transitions.pot"))

# Move emoji POT file to final location
if os.path.exists(os.path.join(language_folder_path, "OpenShot_emojis.pot")):
    os.rename(os.path.join(language_folder_path, "OpenShot_emojis.pot"),
              os.path.join(language_folder_path, "OpenShot", "OpenShot_emojis.pot"))

# Move blender POT file to final location
if os.path.exists(os.path.join(language_folder_path, "OpenShot_blender.pot")):
    os.rename(os.path.join(language_folder_path, "OpenShot_blender.pot"),
              os.path.join(language_folder_path, "OpenShot", "OpenShot_blender.pot"))

# Trim the beginning off of each POT file
start_pos = entire_source.find("#: ")
trimmed_source = entire_source[start_pos:]

# Add to Final POT File
final.write(trimmed_source)
final.write("\n")

# Close final POT file
final.close()

log.info("-----------------------------------------------------")
log.info(" Remove all temp POT files ")
log.info("-----------------------------------------------------")

# Delete all 4 temp files
temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot', 'OpenShot_effects.pot', 'OpenShot_export.pot',
              'OpenShot_transitions.pot', 'OpenShot_QtUi.pot', 'OpenShot_QtUi.ts']
for temp_file_name in temp_files:
    temp_file_path = os.path.join(language_folder_path, temp_file_name)
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

# output success
log.info("-----------------------------------------------------")
log.info(" The OpenShot.pot file has been successfully created ")
log.info(" with all text in OpenShot.")
log.info("")
log.info(" Checking for duplicate keys...")
log.info("-----------------------------------------------------")

# Find any duplicate translations between our 4 template files
# If these duplicates are translated differently, we will end up
# with conflicts, and both translations will be combined incorrectly
all_strings = {}

for pot_file in [
    'OpenShot.pot',
    'OpenShot_transitions.pot',
    'OpenShot_blender.pot',
    'OpenShot_emojis.pot',
]:
    with open(os.path.join(language_folder_path, "OpenShot", pot_file)) as f:
        data = f.read()
        for key in re.findall('^msgid \"(.*)\"', data, re.MULTILINE):
            if key not in all_strings:
                all_strings[key] = "%s | %s" % (key, pot_file)
            elif key and key not in ('translator-credits', ):
                log.info(' ERROR: Duplicate key found: %s::%s' % (pot_file, all_strings[key]))
