#!/usr/bin/python3
"""
 @file
 @brief This file verifies all translations are correctly formatted and have the correct # of string replacements
 @author Jonathan Thomas <jonathan@openshot.org>

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

import os
import re
import fnmatch
import sys
from PyQt5.QtCore import QTranslator, QCoreApplication


# Absolute path of the translations directory
LANG_PATH = os.path.dirname(os.path.abspath(__file__))

# Match '%(name)x' format placeholders
TAG_RE = re.compile(r'%\(([^\)]*)\)(.)')


class color:
    """Color for message output"""
    _red = '\u001b[31m'
    _yellow = '\u001b[33m'
    _green = '\u001b[32m'
    _reset = '\u001b[0m'

    @classmethod
    def red(cls, *args):
        return cls._red + str(*args) + cls._reset

    @classmethod
    def yellow(cls, *args):
        return cls._yellow + str(*args) + cls._reset

    @classmethod
    def green(cls, *args):
        return cls._green + str(*args) + cls._reset


# Get app instance
app = QCoreApplication(sys.argv)


def build_stringlists() -> dict:
    """ Create a dict containing lists of strings, keyed on source filename"""
    all_strings = {}

    for pot in [
        'OpenShot.pot',
        'OpenShot_transitions.pot',
        'OpenShot_blender.pot',
        'OpenShot_emojis.pot',
    ]:

        with open(os.path.join(LANG_PATH, 'OpenShot', pot)) as f:
            data = f.read()
        all_strings.update({
            pot: re.findall('^msgid \"(.*)\"', data, re.MULTILINE)
        })
    return all_strings


def check_trans(strings: list) -> list:
    """Check all strings in a list against a given .qm file"""
    # Test translation of all strings
    translations = {
        source: app.translate("", source)
        for source in strings
    }
    # Check for replacements with mismatched number of % escapes
    errors = {
        s: t for s, t in translations.items()
        if any([
            s.count('%s') != t.count('%s'),
            s.count('%d') != t.count('%d'),
            s.count('%f') != t.count('%f')])
    }
    # Check for missing/added variable names
    # e.g.: "%(clip_id)s %(value)d" changed to "%(clip)s %(value)d"
    # or mismatched types
    # e.g.: "%(seconds)s" changed to "%(seconds)d"
    named_variables = {
        s: (TAG_RE.findall(s), TAG_RE.findall(t))
        for s, t in translations.items()
        if s.count('%(') > 0
    }
    errors.update({
        s: translations[s]
        for s, (s_vars, t_vars) in named_variables.items()
        if sorted(s_vars) != sorted(t_vars)
    })
    return list(errors.items())


def process_qm(file, stringlists) -> int:
    """Scan a translation file against all provided strings"""
    # Attempt to load translation file
    basename = os.path.splitext(file)[0]
    translator = QTranslator(app)
    if not translator.load(basename, LANG_PATH):
        print(color.red('QTranslator failed to load') + f' {file}')
        return 1

    app.installTranslator(translator)

    # Build a dict mapping source POTfiles to lists of error pairs
    error_sets = {
        sourcefile: check_trans(strings)
        for sourcefile, strings in stringlists.items()
    }

    app.removeTranslator(translator)

    # Display any errors found, grouped by source POT file
    error_count = sum([len(v) for v in error_sets.values()])
    if error_count:
        print(f'{file}: ' + color.red(f'{error_count} total errors'))
    for pot, errset in error_sets.items():
        if not errset:
            continue
        width = len(pot)
        msg = "Invalid"
        for source, trans in errset:
            print(color.yellow(f'{pot}:') + f' {source}')
            print(color.red(f'{msg:>{width}}:') + f' {trans}\n')
    return error_count


def scan_all(filenames: list = None) -> int:
    all_strings = build_stringlists()
    if not filenames:
        filenames = fnmatch.filter(os.listdir(LANG_PATH), 'OpenShot*.qm')
    # Loop through language files and count errors
    total_errors = sum([
        process_qm(filename, all_strings)
        for filename in filenames
    ])

    string_count = sum([len(s) for s in all_strings.values()])
    lang_count = len(filenames)

    print(f"Tested {color.yellow(string_count)} strings on "
          + f"{color.yellow(lang_count)} translation files.")
    if total_errors > 0:
        msg = f"Found {total_errors} translation errors! See above."
        raise Exception(msg)
    return sum([])


# Autorun if used as script
if __name__ == '__main__':
    try:
        string_count = scan_all(sys.argv[1:])
    except Exception as ex:
        print(color.red(ex))
        exit(1)
    else:
        print(color.green("No errors found!"))
        exit(0)
