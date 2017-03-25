""" 
 @file
 @brief This file updates the OpenShot.POT (language translation template) by scanning all source files.
 @author Jonathan Thomas <jonathan@openshot.org>
 
 This file helps you generate the POT file that contains all of the translatable
 strings / text in OpenShot.  Because some of our text is in custom XML files,
 the xgettext command can't correctly generate the POT file.  Thus... the 
 existance of this file. =)

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
		$ find -iname "*.po" -exec msgfmt {} -o {}.mo \;

 Command to combine the 2 pot files into 1 file
       $ msgcat ~/openshot/locale/OpenShot/OpenShot_source.pot ~/openshot/openshot/locale/OpenShot/OpenShot_glade.pot -o ~/openshot/main/locale/OpenShot/OpenShot.pot

 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
import xml.dom.minidom as xml
import json
import openshot

# Get the absolute path of this project
path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if path not in sys.path:
    sys.path.append(path)

import classes.info as info
from classes.logger import log

# get the path of the main OpenShot folder
langage_folder_path = os.path.dirname(os.path.abspath(__file__))
openshot_path = os.path.dirname(langage_folder_path)
effects_path = os.path.join(openshot_path, 'effects')
blender_path = os.path.join(openshot_path, 'blender')
transitions_path = os.path.join(openshot_path, 'transitions')
titles_path = os.path.join(openshot_path, 'titles')
export_path = os.path.join(openshot_path, 'presets')
windows_ui_path = os.path.join(openshot_path, 'windows', 'ui')
locale_path = os.path.join(openshot_path, 'locale', 'OpenShot')

log.info("-----------------------------------------------------")
log.info(" Creating temp POT files")
log.info("-----------------------------------------------------")

# create empty temp files in the /openshot/language folder (these are used as temp POT files)
temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot', 'OpenShot_effects.pot', 'OpenShot_export.pot',
              'OpenShot_transitions.pot', 'OpenShot_QtUi.pot']
for temp_file_name in temp_files:
    temp_file_path = os.path.join(langage_folder_path, temp_file_name)
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
    f = open(temp_file_path, "w")
    f.close()

log.info("-----------------------------------------------------")
log.info(" Using xgettext to generate .py POT files")
log.info("-----------------------------------------------------")

# Generate POT for Source Code strings (i.e. strings marked with a _("translate me"))
subprocess.call('find %s -iname "*.py" -exec xgettext -j -o %s --keyword=_ {} \;' % (
openshot_path, os.path.join(langage_folder_path, 'OpenShot_source.pot')), shell=True)

log.info("-----------------------------------------------------")
log.info(" Using Qt's lupdate to generate .ui POT files")
log.info("-----------------------------------------------------")

# Generate POT for Qt *.ui files (which require the lupdate command, and ts2po command)
os.chdir(windows_ui_path)
subprocess.call('lupdate *.ui -ts %s' % (os.path.join(langage_folder_path, 'OpenShot_QtUi.ts')), shell=True)
subprocess.call('lupdate *.ui -ts %s' % (os.path.join(langage_folder_path, 'OpenShot_QtUi.pot')), shell=True)
os.chdir(langage_folder_path)

# Rewrite the UI POT, removing msgctxt
output = open(os.path.join(langage_folder_path, "clean.po"), 'w')
for line in open(os.path.join(langage_folder_path, 'OpenShot_QtUi.pot'), 'r'):
    if not line.startswith('msgctxt'):
        output.write(line)
# Overwrite original PO file
output.close()
shutil.copy(os.path.join(langage_folder_path, "clean.po"), os.path.join(langage_folder_path, 'OpenShot_QtUi.pot'))
os.remove(os.path.join(langage_folder_path, "clean.po"))

# Remove duplciates (if any found)
subprocess.call('msguniq %s --use-first -o %s' % (os.path.join(langage_folder_path, 'OpenShot_QtUi.pot'),
                                      os.path.join(langage_folder_path, 'clean.po')), shell=True)
shutil.copy(os.path.join(langage_folder_path, "clean.po"), os.path.join(langage_folder_path, 'OpenShot_QtUi.pot'))
os.remove(os.path.join(langage_folder_path, "clean.po"))


log.info("-----------------------------------------------------")
log.info(" Updating auto created POT files to set CharSet")
log.info("-----------------------------------------------------")

temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot']
for temp_file in temp_files:
    # get the entire text
    f = open(os.path.join(langage_folder_path, temp_file), "r")
    # read entire text of file
    entire_source = f.read()
    f.close()

    # replace charset
    entire_source = entire_source.replace("charset=CHARSET", "charset=UTF-8")

    # Create Updated POT Output File
    if os.path.exists(os.path.join(langage_folder_path, temp_file)):
        os.remove(os.path.join(langage_folder_path, temp_file))
    f = open(os.path.join(langage_folder_path, temp_file), "w")
    f.write(entire_source)
    f.close()

log.info("-----------------------------------------------------")
log.info(" Scanning custom XML files and finding text")
log.info("-----------------------------------------------------")

# Loop through the Effects XML
effects_text = {}
for file in os.listdir(effects_path):
    if os.path.isfile(os.path.join(effects_path, file)):
        # load xml effect file
        full_file_path = os.path.join(effects_path, file)
        xmldoc = xml.parse(os.path.join(effects_path, file))

        # add text to list
        effects_text[xmldoc.getElementsByTagName("title")[0].childNodes[0].data] = full_file_path
        effects_text[xmldoc.getElementsByTagName("description")[0].childNodes[0].data] = full_file_path

        # get params
        params = xmldoc.getElementsByTagName("param")

        # Loop through params
        for param in params:
            if param.attributes["title"]:
                effects_text[param.attributes["title"].value] = full_file_path

# Append on properties from libopenshot
objects = [openshot.Clip(), openshot.Blur(), openshot.Brightness(),
           openshot.ChromaKey(), openshot.Deinterlace(), openshot.Mask(),
           openshot.Negate(), openshot.Saturation()]

# Loop through each libopenshot object
for object in objects:
    props = json.loads(object.PropertiesJSON(1))

    # Loop through props
    for key in props.keys():
        object = props[key]
        if "name" in object.keys():
            effects_text[object["name"]] = "libopenshot (Clip Properties)"
        if "choices" in object.keys():
            for choice in object["choices"]:
                effects_text[choice["name"]] = "libopenshot (Clip Properties)"

# Append Effect Meta Data
e = openshot.EffectInfo()
props = json.loads(e.Json())

# Loop through props
for effect in props:
    if "name" in effect:
        effects_text[effect["name"]] = "libopenshot (Effect Metadata)"
    if "description" in effect:
        effects_text[effect["description"]] = "libopenshot (Effect Metadata)"

# Loop through the Blender XML
for file in os.listdir(blender_path):
    if os.path.isfile(os.path.join(blender_path, file)):
        # load xml effect file
        full_file_path = os.path.join(blender_path, file)
        xmldoc = xml.parse(os.path.join(blender_path, file))

        # add text to list
        effects_text[xmldoc.getElementsByTagName("title")[0].childNodes[0].data] = full_file_path

        # get params
        params = xmldoc.getElementsByTagName("param")

        # Loop through params
        for param in params:
            if param.attributes["title"]:
                effects_text[param.attributes["title"].value] = full_file_path

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

# Loop through transitions and add to POT file
transitions_text = {}
for file in os.listdir(transitions_path):
    # load xml export file
    full_file_path = os.path.join(transitions_path, file)
    (fileBaseName, fileExtension) = os.path.splitext(file)

    # get transition name
    name = fileBaseName.replace("_", " ").capitalize()

    # add text to list
    transitions_text[name] = full_file_path

    # Look in sub-folders
    for sub_file in os.listdir(full_file_path):
        # load xml export file
        full_subfile_path = os.path.join(full_file_path, sub_file)
        (fileBaseName, fileExtension) = os.path.splitext(sub_file)

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

# Loop through titles and add to POT file
for sub_file in os.listdir(titles_path):
    # load xml export file
    full_subfile_path = os.path.join(titles_path, sub_file)
    (fileBaseName, fileExtension) = os.path.splitext(sub_file)

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
header_text = header_text + '# Copyright (C) 2008-2016 OpenShot Studios, LLC\n'
header_text = header_text + '# This file is distributed under the same license as OpenShot.\n'
header_text = header_text + '# Jonathan Thomas <Jonathan.Oomph@gmail.com>, 2016.\n'
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
temp_files = [['OpenShot_effects.pot', effects_text], ['OpenShot_export.pot', export_text],
              ['OpenShot_transitions.pot', transitions_text]]
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
log.info(" Combine all temp POT files using msgcat command (this removes dupes) ")
log.info("-----------------------------------------------------")

temp_files = ['OpenShot_source.pot', 'OpenShot_glade.pot', 'OpenShot_effects.pot', 'OpenShot_export.pot',
              'OpenShot_transitions.pot', 'OpenShot_QtUi.pot']
command = "msgcat"
for temp_file in temp_files:
    # append files
    command = command + " " + os.path.join(langage_folder_path, temp_file)
command = command + " -o " + os.path.join(locale_path, "OpenShot.pot")

log.info(command)

# merge all 4 temp POT files
subprocess.call(command, shell=True)

log.info("-----------------------------------------------------")
log.info(" Create FINAL POT File from all temp POT files ")
log.info("-----------------------------------------------------")

# get the entire text of OpenShot.POT
f = open(os.path.join(locale_path, "OpenShot.pot"), "r")
# read entire text of file
entire_source = f.read()
f.close()

# Create Final POT Output File
if os.path.exists(os.path.join(locale_path, "OpenShot.pot")):
    os.remove(os.path.join(locale_path, "OpenShot.pot"))
final = open(os.path.join(locale_path, "OpenShot.pot"), "w")
final.write(header_text)
final.write("\n")

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
    temp_file_path = os.path.join(langage_folder_path, temp_file_name)
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

# output success
log.info("-----------------------------------------------------")
log.info(" The /openshot/locale/OpenShot/OpenShot.pot file has")
log.info(" been successfully created with all text in OpenShot.")
log.info("-----------------------------------------------------")
