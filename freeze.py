""" 
 @file
 @brief cx_Freeze script to build OpenShot package with dependencies (for Mac and Windows)
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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
 
 # Syntax to build redistributable package:  python3 freeze.py build

import glob, os, sys, subprocess, fnmatch
from cx_Freeze import setup, Executable

# Determine which JSON library is installed
json_library = None
try:
    import json
    json_library = "json"
except ImportError:
    import simplejson as json
    json_library = "simplejson"

# Find files matching patterns
def find_files(directory, patterns):
	""" Recursively find all files in a folder tree """ 
	for root, dirs, files in os.walk(directory):
		for basename in files:
			for pattern in patterns:
				if fnmatch.fnmatch(basename, pattern):
					filename = os.path.join(root, basename)
					yield filename

# GUI applications require a different base on Windows
base = None
external_so_files = []
if sys.platform == "win32":
    base = "Win32GUI"
    external_so_files = []
    
elif sys.platform == "linux":
	# Find all related SO files
	for filename in find_files('/usr/local/lib/', ['*openshot*.so*']):
		if "python" not in filename:
			external_so_files.append((filename, filename.replace('/usr/local/lib/', '')))

# Get list of all Python files
src_files = []
for filename in find_files('src', ['*.py','*.settings','*.project','*.svg','*.png','*.ui','*.blend','*.html','*.css','*.js']):
	src_files.append((filename, filename.replace('src/', '')))

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = { "packages" : ["os", "sys", "openshot", "PyQt5", "time", "uuid", "shutil", "threading", "subprocess", "re", "math", "subprocess", "xml", "urllib", "webbrowser", json_library],
					  "include_files" : src_files + external_so_files  }

# Create distutils setup object
setup(  name = "OpenShot Video Editor",
		version = "2.0",
		description = "Non-Linear Video Editor for Linux, Windows, and Mac",
		options = {"build_exe": build_exe_options },
		executables = [Executable("src/launch.py", base=base)])
	