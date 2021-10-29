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
from PyQt5.QtCore import QTranslator, QCoreApplication  # type: ignore
from typing import Any, Dict, List, Optional, Tuple


# Absolute path of the translations directory
LANG_PATH = os.path.dirname(os.path.abspath(__file__))

# Match '%(name)x' format placeholders
TAG_RE = re.compile(r'%\(([^\)]*)\)(.)')


class BadTranslationsError(Exception):
    pass


class Color:
    """Color for message output"""
    _red = '\u001b[31m'
    _yellow = '\u001b[33m'
    _green = '\u001b[32m'
    _reset = '\u001b[0m'

    @classmethod
    def red(cls, *args: Optional[Any]) -> str:
        return cls._red + str(*args) + cls._reset

    @classmethod
    def yellow(cls, *args: Optional[Any]) -> str:
        return cls._yellow + str(*args) + cls._reset

    @classmethod
    def green(cls, *args: Optional[Any]) -> str:
        return cls._green + str(*args) + cls._reset


# Get app instance
app = QCoreApplication(sys.argv)


def build_stringlists() -> Dict[str, List]:
    """ Create a dict containing lists of strings, keyed on source filename"""
    all_strings = {}

    for pot_file in [
        'OpenShot.pot',
        'OpenShot_transitions.pot',
        'OpenShot_blender.pot',
        'OpenShot_emojis.pot',
    ]:
        with open(os.path.join(LANG_PATH, 'OpenShot', pot_file)) as f:
            data = f.read()
        all_strings.update({
            pot_file: re.findall('^msgid \"(.*)\"', data, re.MULTILINE)
        })
    return all_strings


def check_trans(strings: List) -> List[Tuple[str, str]]:
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
        # Ensure that t_vars is a strict subset of s_vars
        if not set(t_vars) <= set(s_vars)
    })
    return list(errors.items())


def process_qm(file: str, stringlists: Dict[str, List[str]]) -> int:
    """Scan a translation file against all provided strings"""
    # Attempt to load translation file
    basename = os.path.splitext(file)[0]
    translator = QTranslator(app)
    if not translator.load(basename, LANG_PATH):
        print(Color.red('QTranslator failed to load') + f' {file}')
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
    invalid_msg = "Invalid"
    if error_count:
        print(f'{file}: ' + Color.red(f'{error_count} total errors'))
    for pot, errset in error_sets.items():
        if not errset:
            continue
        width = len(pot)
        for source, trans in errset:
            print(Color.yellow(f'{pot}:') + f' {source}')
            print(Color.red(f'{invalid_msg:>{width}}:') + f' {trans}\n')
    return error_count


def scan_all(filenames: List = None) -> None:
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

    print(f"Tested {Color.yellow(string_count)} strings on "
          + f"{Color.yellow(lang_count)} translation files.")
    if total_errors > 0:
        raise BadTranslationsError(f"Found {total_errors} translation errors")


# Autorun if used as script
if __name__ == '__main__':
    try:
        scan_all(sys.argv[1:])
    except BadTranslationsError as ex:
        print(Color.red(str(ex) + "! See above."))
        exit(1)
    else:
        print(Color.green("No errors found."))
        exit(0)
