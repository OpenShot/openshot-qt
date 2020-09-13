"""Analyze the OS X app bundle for OpenShot, and find all external dependencies"""
import os
import subprocess
from subprocess import call
import re

# Symbolic Link Qt Frameworks into Python3/PyQt5 Framework
# IMPORTANT to run after installing PyQt5
PATH = "/usr/local/qt5.15.X/qt5.15/5.15.0/clang_64/lib"

# Find files matching patterns
for file in os.listdir(PATH):
    if file.endswith(".framework"):
        file_path = os.path.join(PATH, file)
        file_parts = file_path.split("/")
        new_path = os.path.join("/Library/Frameworks/Python.framework/Versions/3.6/lib", file_parts[-1])
        print(new_path)
        if os.path.exists(new_path):
            # Remove old sym links
            os.unlink(new_path)

        # Create new symlink to Qt frameworks
        call(["ln", "-s", file_path, new_path])

# Symbolic Link Qt Frameworks into Python3/PyQt5 Framework
# IMPORTANT to run after installing PyQt5
PATH = "/usr/local/qt5.15.X/qt5.15/5.15.0/clang_64/lib"

# Find files matching patterns
for file in os.listdir(PATH):
    if file.endswith(".framework"):
        file_path = os.path.join(PATH, file)
        file_parts = file_path.split("/")
        new_path = os.path.join("/Library/Frameworks/Python.framework/Versions/3.6/lib/python3.6/site-packages/PyQt5/lib", file_parts[-1])
        print(new_path)
        if os.path.exists(new_path):
            # Remove old sym links
            os.unlink(new_path)

        # Create new symlink to Qt frameworks
        call(["ln", "-s", file_path, new_path])


# FIX PyQt5 library paths
# This is NOT required anymore (leaving here as an example)
#PATH = "/Library/Frameworks/Python.framework/Versions/3.6/lib/python3.6/site-packages/PyQt5/"

# Find files matching patterns
#for root, dirs, files in os.walk(PATH):
#    for basename in files:
#        file_path = os.path.join(root, basename)
#        file_parts = file_path.split("/")
#
#        if ".dylib" in file_path or ".so" in file_path:
#
#            #print (file_path)
#            print ("install_name_tool %s -id %s" % (file_path, file_path))
#            call(["install_name_tool", file_path, "-id", file_path])
#
#            raw_output = subprocess.Popen(["oTool", "-L", file_path], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
#            for output in raw_output.split("\n")[1:-1]:
#                if output and not "is not an object file" in output:
#                    dependency_path = output.split('\t')[1].split(' ')[0]
#                    dependency_version = output.split('\t')[1].split(' (')[1].replace(')','')
#
#                    if "@rpath" in dependency_path:
#                        command = 'install_name_tool "%s" -change "%s" "%s"' % (file_path, dependency_path, dependency_path.replace("@rpath", os.path.join(PATH, "lib")))
#                        print (command)
#                        call(["install_name_tool", file_path, "-change", dependency_path, dependency_path.replace("@rpath", os.path.join(PATH, "lib"))])


# Print ALL MINIMUM and SDK VERSIONS for files in OpenShot build folder
# This does not list all dependent libraries though, and sometimes one of those can cause issues.
# PATH = "/Users/jonathan/builds/7d5103a1/0/OpenShot/openshot-qt/build/exe.macosx-10.6-intel-3.6"
# REGEX_SDK_MATCH = re.compile(r'.*(LC_VERSION_MIN_MACOSX).*version (\d+\.\d+).*sdk (\d+\.\d+).*(cmd)', re.DOTALL)
#
# # Find files matching patterns
# for root, dirs, files in os.walk(PATH):
#    for basename in files:
#        file_path = os.path.join(root, basename)
#        file_parts = file_path.split("/")
#
#        raw_output = subprocess.Popen(["oTool", "-l", file_path], stdout=subprocess.PIPE).communicate()[0].decode('utf-8')
#        matches = REGEX_SDK_MATCH.findall(raw_output)
#        if matches and len(matches[0]) == 4:
#            min_version = matches[0][1]
#            sdk_version = matches[0][2]
#            print("min: %s\tsdk: %s\t%s" % (min_version, sdk_version, file_path))
#            if min_version in ['10.14', '10.15']:
#                print("ERROR!!!! Minimum OS X version not met for %s" % file_path)
