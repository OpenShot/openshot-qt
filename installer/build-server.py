"""
 @file
 @brief Build server used to generate daily builds of libopenshot-audio, libopenshot, and openshot-qt
 @author Jonathan Thomas <jonathan@openshot.org>

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

import os
import sys

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder

import datetime
import platform
import shutil
from slacker import Slacker
import re
import stat
import subprocess
import sys
import tinys3
import traceback
from PyQt5.QtCore import QLibraryInfo
from github3 import login


freeze_command = None
errors_detected = []
make_command = "make"
project_paths = []
slack_token = None
slack_object = None
s3_access_key = None
s3_secret_key = None
s3_connection = None
windows_key = None
windows_key_password = None
github_user = None
github_pass = None
github_release = None
windows_32bit = False
commit_data = {}

# Create temp log
log_path = os.path.join(PATH, 's3-builds', 'build-server.log')
log = open(log_path, 'w+')


# Determine the paths and cmake args for each platform
if platform.system() == "Linux":
    freeze_command = "python3 /home/jonathan/apps/openshot-qt-git/freeze.py build"
    project_paths = [("/home/jonathan/apps/libopenshot-audio-git", "../"),
                     ("/home/jonathan/apps/libopenshot-git", "../"),
                     ("/home/jonathan/apps/openshot-qt-git", "")]

elif platform.system() == "Darwin":
    freeze_command = '/Library/Frameworks/Python.Framework/Versions/3.6/bin/python3.6 /Users/jonathan/apps/openshot-qt-git/freeze.py bdist_mac --iconfile=installer/openshot.icns --custom-info-plist=installer/Info.plist --bundle-name="OpenShot Video Editor"'
    project_paths = [("/Users/jonathan/apps/libopenshot-audio-git", '-DCMAKE_CXX_COMPILER=clang++ -DCMAKE_C_COMPILER=clang -D"CMAKE_BUILD_TYPE:STRING=Release" -D"CMAKE_OSX_SYSROOT=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.9.sdk" -D"CMAKE_OSX_DEPLOYMENT_TARGET=10.9" ../'),
                     ("/Users/jonathan/apps/libopenshot-git", '-DCMAKE_CXX_COMPILER=/usr/local/opt/gcc48/bin/g++-4.8 -DCMAKE_C_COMPILER=/usr/local/opt/gcc48/bin/gcc-4.8 -DCMAKE_PREFIX_PATH=/usr/local/qt5/5.5/clang_64 -DPYTHON_INCLUDE_DIR=/Library/Frameworks/Python.framework/Versions/3.6/include/python3.6m -DPYTHON_LIBRARY=/Library/Frameworks/Python.framework/Versions/3.6/lib/libpython3.6.dylib -DPython_FRAMEWORKS=/Library/Frameworks/Python.framework/ -D"CMAKE_BUILD_TYPE:STRING=Debug" -D"CMAKE_OSX_SYSROOT=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.9.sdk" -D"CMAKE_OSX_DEPLOYMENT_TARGET=10.9" ../ -D"CMAKE_INSTALL_RPATH_USE_LINK_PATH=1" -D"ENABLE_RUBY=0"'),
                     ("/Users/jonathan/apps/openshot-qt-git", "")]

elif platform.system() == "Windows":
    make_command = "mingw32-make"
    freeze_command = "python3 C:\\Users\\Jonathan\\apps\\openshot-qt-git\\freeze.py build"
    project_paths = [["C:\\Users\\Jonathan\\apps\\libopenshot-audio-git", '-G "MinGW Makefiles" ../ -D"CMAKE_BUILD_TYPE:STRING=Release"'],
                     ["C:\\Users\\Jonathan\\apps\\libopenshot-git", '-G "MinGW Makefiles" ../ -D"CMAKE_BUILD_TYPE:STRING=Release"'],
                     ["C:\\Users\\Jonathan\\apps\\openshot-qt-git", ""]]


def run_command(command, working_dir=None):
    """Utility function to return output from command line"""
    p = subprocess.Popen(command, shell=True, cwd=working_dir,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b"")

def output(line):
    """Append output to list and print it"""
    print(line)
    if isinstance(line, bytes):
        line = line.decode('UTF-8').strip()

    if not line.endswith(os.linesep):
        # Append missing line return (if needed)
        line += "\n"
    log.write(line)

def error(line):
    """Append error output to list and print it"""
    print("Error: %s" % line)
    errors_detected.append(line)
    if isinstance(line, bytes):
        log.write(line.decode('UTF-8'))
    else:
        log.write(line)

def truncate(message, max=256):
    """Truncate the message with ellipses"""
    if len(message) < max:
        return message
    else:
        return "%s..." % message[:max]

def slack(message):
    """Append a message to slack #build-server channel"""
    print("Slack: %s" % message)
    if slack_object:
        slack_object.chat.post_message("#build-server", truncate(message[:256]))

def slack_upload_log(log, title, comment=None):
    """Upload a file to slack and notify a slack channel"""
    # Close log file
    log.close()

    print("Slack Upload: %s" % log_path)
    if slack_object:
        for attempt in range(3):
            try:
                # Upload build log to slack (and append platform icon to comment [:linux:, :windows:, or :darwin:])
                slack_object.files.upload(log_path, filetype="txt", filename="%s-build-server.txt" % platform.system(),
                                          title=title, initial_comment=':%s: %s' % (platform.system().lower(), comment), channels="#build-server")
                # Successfully uploaded!
                break
            except Exception as ex:
                # Quietly fail, and try again
                if attempt < 2:
                    output("Upload log to Slack failed... trying again")
                else:
                    # Throw loud exception
                    raise Exception('Log upload to Slack failed: %s' % log_path, ex)

    # Re-open the log (for append)
    log = open(log_path, "a")

def get_release(repo, tag_name):
    """Fetch the GitHub release tagged with the given tag and return it
    @param repo:        github3 repository object
    @returns:           github3 release object or None
    """
    for release in repo.iter_releases():
        if release.tag_name == tag_name:
            return release

def upload(file_path, github_release):
    """Upload a file to GitHub (retry 3 times)"""
    url = None
    if s3_connection:
        folder_path, file_name = os.path.split(file_path)
        for attempt in range(3):
            try:
                # Attempt the upload
                with open(file_path, "rb") as f:
                    # Upload to GitHub
                    asset = github_release.upload_asset("application/octet-stream", file_name, f)
                    url = asset.to_json()["browser_download_url"]
                # Successfully uploaded!
                break
            except Exception as ex:
                # Quietly fail, and try again
                if attempt < 2:
                    output("Upload failed... trying again")
                else:
                    # Throw loud exception
                    raise Exception('Upload failed. Verify that this file is not already uploaded: %s' % file_path, ex)

    return url


try:
    # Validate command-line arguments
    if len(sys.argv) >= 2:
        slack_token = sys.argv[1]
        slack_object = Slacker(slack_token)
    if len(sys.argv) >= 4:
        s3_access_key = sys.argv[2]
        s3_secret_key = sys.argv[3]
        s3_connection = tinys3.Connection(s3_access_key, s3_secret_key, tls=True)
    if len(sys.argv) >= 6:
        windows_key = sys.argv[4]
        windows_key_password = sys.argv[5]
    if len(sys.argv) >= 8:
        github_user = sys.argv[6]
        github_pass = sys.argv[7]

        # Login and get "GitHub" object
        gh = login(github_user, github_pass)
        repo = gh.repository("OpenShot", "openshot-qt")

    if len(sys.argv) >=9:
        windows_32bit = False
        if sys.argv[8] == 'True':
            windows_32bit = True

        # Set some Windows specific environment variables
        if windows_32bit:
            # 32-bit windows
            os.environ['LIBOPENSHOT_AUDIO_DIR'] = r'C:\\msys32\\usr'
            os.environ['UNITTEST_DIR'] = r'C:\\msys32\\usr'
            os.environ['ZMQDIR'] = r'C:\\msys32\\usr'
            os.environ['PATH'] = r'C:\msys32\mingw32\bin;C:\msys32\mingw32\lib;C:\msys32\usr\lib\cmake\UnitTest++;C:\msys32\home\jonathan\depot_tools;C:\msys32\usr;C:\msys32\usr\lib;' + os.environ['PATH']

            # Append path onto project list
            project_paths[0][-1] += ' -D"CMAKE_INSTALL_PREFIX:PATH=C:\\msys32\\usr"'
            project_paths[1][-1] += ' -D"CMAKE_INSTALL_PREFIX:PATH=C:\\msys32\\usr"'

        else:
            # 64-bit windows
            os.environ['LIBOPENSHOT_AUDIO_DIR'] = r'C:\\msys64\\usr'
            os.environ['UNITTEST_DIR'] = r'C:\\msys64\\usr'
            os.environ['ZMQDIR'] = r'C:\\msys64\\usr'
            os.environ['PATH'] = r'C:\msys64\msys64\bin;C:\msys64\msys64\lib;C:\msys64\usr\lib\cmake\UnitTest++;C:\msys64\home\jonathan\depot_tools;C:\msys64\usr;C:\msys64\usr\lib;' + os.environ['PATH']

            # Append path onto project list
            project_paths[0][-1] += ' -D"CMAKE_INSTALL_PREFIX:PATH=C:\\msys64\\usr"'
            project_paths[1][-1] += ' -D"CMAKE_INSTALL_PREFIX:PATH=C:\\msys64\\usr"'

    # Start log
    output("%s Build Log for %s" % (platform.system(), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # Get latest version of all projects (git pull)
    for project_path, cmake_args in project_paths:
        # Change os directory
        os.chdir(project_path)

        # Get number of commits
        for line in run_command("git rev-list --count master"):
            commit_data[project_path] = int(line)
            output("# of commits found for %s: %s" % (project_path, commit_data[project_path]))

        # Check for new version in git
        for line in run_command("git fetch -v --dry-run"):
            output(line)
            if "[up to date]".encode("UTF-8") in line:
                break

        # Get latest from git
        for line in run_command("git pull origin master"):
            output(line)

        # Get latest tags from git
        for line in run_command("git fetch --tags"):
            output(line)

        # Sync these changes to bzr (if build-server running on linux)
        if platform.system() == "Linux":
            for line in run_command("git bzr push"):
                output(line)

    # Get GIT description of openshot-qt-git branch (i.e. v2.0.6-18-ga01a98c)
    openshot_qt_git_desc = ""
    for line in run_command("git describe --tags"):
        git_description = line.decode("utf-8").strip()
        openshot_qt_git_desc = "OpenShot-%s" % git_description

        # Add num of commits from libopenshot and libopenshot-audio (for naming purposes)
        # If not an official release
        if "-" in git_description:
            # Make filename more descriptive for daily builds
            openshot_qt_git_desc = "%s-%s-%s" % (
            openshot_qt_git_desc, commit_data[project_paths[0][0]], commit_data[project_paths[1][0]])
            output("git description of openshot-qt-git: %s" % openshot_qt_git_desc)

            # Get daily git_release object
            github_release = get_release(repo, "daily")
        else:
            # Get official version release (i.e. v2.1.0, v2.x.x)
            github_release = get_release(repo, git_description)

            # If no release is found, create a new one
            if not github_release:
                # Create a new release if one if missing
                github_release = repo.create_release(git_description, target_commitish="master", prerelease=True)

    # Detect version number from git description
    version = re.search('v(.+?)($|-)', openshot_qt_git_desc).groups()[0]

    # Create uploads path (if not found)
    upload_path = os.path.join(project_path, "s3-uploads")
    if not os.path.exists(upload_path):
        os.mkdir(upload_path)
    builds_path = os.path.join(project_path, "s3-builds")
    if not os.path.exists(builds_path):
        os.mkdir(builds_path)

    # Determine the name and path of the final installer
    app_name = openshot_qt_git_desc
    app_upload_bucket = ""
    if platform.system() == "Linux":
        app_name += "-x86_64.AppImage"
        app_upload_bucket = "releases.openshot.org/linux"
    elif platform.system() == "Darwin":
        app_name += "-x86_64.dmg"
        app_upload_bucket = "releases.openshot.org/mac"
    elif platform.system() == "Windows" and not windows_32bit:
        app_name += "-x86_64.exe"
        app_upload_bucket = "releases.openshot.org/windows"
    elif platform.system() == "Windows" and windows_32bit:
        app_name += "-x86.exe"
        app_upload_bucket = "releases.openshot.org/windows"
    app_build_path = os.path.join(builds_path, app_name)
    app_upload_path = os.path.join(upload_path, app_name)

    # Does this version need to be built?
    needs_build = False
    if not os.path.exists(app_build_path) and not os.path.exists(app_upload_path):
        needs_build = True

    # Does this version need to be uploaded?
    needs_upload = False
    if not os.path.exists(app_upload_path):
        needs_upload = True

    if needs_build:
        # Check for left over build folders
        if os.path.exists(os.path.join(project_path, "openshot_qt")):
            shutil.rmtree(os.path.join(project_path, "openshot_qt"))
        if os.path.exists(os.path.join(project_path, "build")):
            shutil.rmtree(os.path.join(project_path, "build"))
        if os.path.exists(os.path.join(project_path, "dist")):
            shutil.rmtree(os.path.join(project_path, "dist"))

        # Copy QT translations to local folder (to be packaged)
        qt_local_path = os.path.join(project_path, "src", "locale", "QT")
        qt_system_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
        if os.path.exists(qt_system_path):
            # Create local QT translation folder (if needed)
            if not os.path.exists(qt_local_path):
                os.mkdir(qt_local_path)
            # Loop through QT translation files and copy them
            for file in os.listdir(qt_system_path):
                # Copy QT locale files
                if file.startswith("qt_") and file.endswith(".qm"):
                    shutil.copyfile(os.path.join(qt_system_path, file), os.path.join(qt_local_path, file))

        # Loop through projects
        for project_path, cmake_args in project_paths:
            # Change os directory
            os.chdir(project_path)

            # Remove build folder & re-create it
            build_folder = os.path.join(project_path, "build")
            if os.path.exists(build_folder):
                shutil.rmtree(build_folder)
            os.makedirs(build_folder)

            # Change to build folder
            os.chdir(build_folder)

            # Skip to next project if no cmake args are found (only some projects need to be compiled)
            if not cmake_args:
                output("Skipping compilation for %s" % project_path)
                continue

            # Run CMAKE (configure all project files, and get ready to compile)
            for line in run_command("cmake %s" % cmake_args):
                output(line)
                if "CMake Error".encode("UTF-8") in line or "Configuring incomplete".encode("UTF-8") in line:
                    error("Cmake Error: %s" % line)

            # Run MAKE (compile binaries, python bindings, executables, etc...)
            for line in run_command(make_command):
                output(line)
                if ": error:".encode("UTF-8") in line or "No targets specified".encode("UTF-8") in line:
                    error("Make Error: %s" % line)

            # Run MAKE INSTALL (copy binaries to install directory)
            for line in run_command("%s install" % make_command):
                output(line)
                if "[install] Error".encode("UTF-8") in line or "CMake Error".encode("UTF-8") in line:
                    error("Make Install Error: %s" % line)


        # Now that everything is updated, let's create the installers
        if not errors_detected:
            # Change to openshot-qt dir
            project_path = project_paths[2][0]
            os.chdir(project_path)

            # Freeze it (if needed)
            for line in run_command(freeze_command):
                output(line)
                if "logger:ERROR".encode("UTF-8") in line and not "importlib/__init__.pyc".encode("UTF-8") in line and not "zinfo".encode("UTF-8") in line:
                    error("Freeze Error: %s" % line)

            # Successfully frozen - Time to create installers
            if platform.system() == "Linux":

                # Find exe folder
                exe_dirs = os.listdir(os.path.join(project_path, "build"))
                if len(exe_dirs) == 1:
                    exe_dir = exe_dirs[0]

                    # Create AppDir folder
                    app_dir_path = os.path.join(project_path, "build", "OpenShot.AppDir")
                    os.mkdir(app_dir_path)
                    os.mkdir(os.path.join(app_dir_path, "usr"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "share"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "share", "pixmaps"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "share", "mime"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "share", "mime", "packages"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "lib"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "lib", "mime"))
                    os.mkdir(os.path.join(app_dir_path, "usr", "lib", "mime", "packages"))

                    # Create AppRun file
                    app_run_path = os.path.join(app_dir_path, "AppRun")
                    shutil.copyfile("/home/jonathan/apps/AppImageKit/AppRun", app_run_path)

                    # Create .desktop file
                    with open(os.path.join(app_dir_path, "openshot-qt.desktop"), "w") as f:
                        f.write('[Desktop Entry]\nName=OpenShot Video Editor\nGenericName=Video Editor\nX-GNOME-FullName=OpenShot Video Editor\nComment=Create and edit amazing videos and movies\nExec=openshot-qt.wrapper %F\nTerminal=false\nIcon=openshot-qt\nType=Application')

                    # Copy some installation-related files
                    shutil.copyfile(os.path.join(project_path, "xdg", "openshot-qt.svg"), os.path.join(app_dir_path, "openshot-qt.svg"))
                    shutil.copyfile(os.path.join(project_path, "xdg", "openshot-qt.svg"), os.path.join(app_dir_path, "usr", "share", "pixmaps", "openshot-qt.svg"))
                    shutil.copyfile(os.path.join(project_path, "xdg", "openshot-qt.xml"), os.path.join(app_dir_path, "usr", "share", "mime", "packages", "openshot-qt.xml"))
                    shutil.copyfile(os.path.join(project_path, "xdg", "openshot-qt"), os.path.join(app_dir_path, "usr", "lib", "mime", "packages", "openshot-qt"))

                    # Copy the entire frozen app
                    shutil.copytree(os.path.join(project_path, "build", exe_dir), os.path.join(app_dir_path, "usr", "bin"))

                    # Copy desktop integration wrapper (prompts users to install shortcut)
                    launcher_path = os.path.join(app_dir_path, "usr", "bin", "openshot-qt")
                    os.rename(os.path.join(app_dir_path, "usr", "bin", "launch-linux.sh"), launcher_path)
                    desktop_wrapper = os.path.join(app_dir_path, "usr", "bin", "openshot-qt.wrapper")
                    shutil.copyfile("/home/jonathan/apps/AppImageKit/desktopintegration", desktop_wrapper)

                    # Change permission of AppRun (and desktop.wrapper) file (add execute permission)
                    st = os.stat(app_run_path)
                    os.chmod(app_run_path, st.st_mode | stat.S_IEXEC)
                    os.chmod(desktop_wrapper, st.st_mode | stat.S_IEXEC)
                    os.chmod(launcher_path, st.st_mode | stat.S_IEXEC)

                    # Create AppImage (OpenShot-%s-x86_64.AppImage)
                    app_image_success = False
                    for line in run_command('/home/jonathan/apps/AppImageKit/AppImageAssistant "%s" "%s"' % (app_dir_path, app_build_path)):
                        output(line)
                        if "completed sucessfully".encode("UTF-8") in line:
                            app_image_success = True

                    # Was the AppImage creation successful
                    if not app_image_success or errors_detected:
                        # AppImage failed
                        error("AppImageKit Error: AppImageAssistant did not output 'completed successfully'")
                        needs_upload = False

                        # Delete build (since something failed)
                        os.remove(app_build_path)


            if platform.system() == "Darwin":

                # Create DMG (OpenShot-%s-x86_64.DMG)
                app_image_success = False

                # Build app.bundle and create DMG
                for line in run_command("bash installer/build-mac-dmg.sh"):
                    output(line)
                    if "error".encode("UTF-8") in line or "rejected".encode("UTF-8") in line:
                        error("Build-Mac-DMG Error: %s" % line)
                    if "Your image is ready".encode("UTF-8") in line:
                        app_image_success = True

                # Rename DMG (to be consistent with other OS installers)
                for dmg_path in os.listdir(os.path.join(project_path, "build")):
                    if os.path.isfile(os.path.join(project_path, "build", dmg_path)) and dmg_path.endswith(".dmg"):
                        os.rename(os.path.join(project_path, "build", dmg_path), app_build_path)

                # Was the DMG creation successful
                if not app_image_success or errors_detected:
                    # DMG failed
                    error("Build-Mac-DMG Error: Did not output 'Your image is ready'")
                    needs_upload = False

                    # Delete build (since key signing might have failed)
                    os.remove(app_build_path)


            if platform.system() == "Windows":

                # Move python folder structure, since Cx_Freeze doesn't put it in the correct place
                exe_dir = os.path.join(PATH, 'build', 'exe.mingw-3.6')
                python_dir = os.path.join(exe_dir, 'lib', 'python3.6')
                if not os.path.exists(python_dir):
                    os.mkdir(python_dir)

                    # Copy all non-zip files from /lib/ into /python3.X/
                    for lib_file in os.listdir(os.path.join(exe_dir, 'lib')):
                        if not ".zip" in lib_file and not lib_file == "python3.6":
                            lib_src_path = os.path.join(os.path.join(exe_dir, 'lib'), lib_file)
                            lib_dst_path = os.path.join(os.path.join(python_dir), lib_file)
                            shutil.move(lib_src_path, lib_dst_path)

                # Delete debug Qt libraries (since they are not needed, and cx_Freeze grabs them)
                for sub_folder in ['', 'platforms', 'imageformats']:
                    parent_path = exe_dir
                    if sub_folder:
                        parent_path = os.path.join(parent_path, sub_folder)
                    for debug_qt_lib in os.listdir(parent_path):
                        if debug_qt_lib.endswith("d.dll"):
                            # Delete the debug dll
                            os.remove(os.path.join(parent_path, debug_qt_lib))

                only_64_bit = "x64"
                if windows_32bit:
                    only_64_bit = ""

                # Create Installer (OpenShot-%s-x86_64.exe)
                inno_success = True
                inno_command = '"C:\Program Files (x86)\Inno Setup 5\iscc.exe" /Q /DVERSION=%s /DONLY_64_BIT=%s "%s"' % (version, only_64_bit, os.path.join(PATH, 'installer', 'windows-installer.iss'))
                inno_output = ""
                # Compile Inno installer
                for line in run_command(inno_command):
                    output(line)
                    if line:
                        inno_success = False
                        inno_output = line

                # Was the Inno Installer successful
                inno_output_exe = os.path.join(project_path, "installer", "Output", "OpenShot.exe")
                if not inno_success or not os.path.exists(inno_output_exe):
                    # Installer failed
                    error("Inno Compiler Error: Had output when none was expected (%s)" % inno_output)
                    needs_upload = False
                else:
                    # Rename exe to correct name / path
                    os.rename(inno_output_exe, app_build_path)
                    # Clean-up empty folder created by Inno compiler
                    os.rmdir(os.path.join(PATH, 'installer', 'Output'))

                # Sign the installer
                key_sign_success = True
                key_sign_command = '"C:\\Program Files (x86)\\kSign\\kSignCMD.exe" /f "%s" /p "%s" /d "OpenShot Video Editor" /du "http://www.openshot.org" "%s"' % (windows_key, windows_key_password, app_build_path)
                key_sign_output = ""
                # Sign MSI
                for line in run_command(key_sign_command):
                    output(line)
                    if line:
                        key_sign_success = False
                        key_sign_output = line

                # Was the MSI creation successful
                if not key_sign_success:
                    # MSI failed
                    error("Key Sign Error: Had output when none was expected (%s)" % key_sign_output)
                    needs_upload = False

                    # Delete build (since key signing might have failed)
                    os.remove(app_build_path)

        # Remove temporary files
        if os.path.exists(qt_local_path):
            shutil.rmtree(qt_local_path)


    if needs_upload:
        # Check if app exists
        if os.path.exists(app_build_path):
            # Upload file to GitHub
            output("GitHub: Uploading %s to GitHub Release: %s" % (app_build_path, github_release.tag_name))
            download_url = upload(app_build_path, github_release)

            # Create torrent and upload
            torrent_path = "%s.torrent" % app_build_path
            torrent_command = 'mktorrent -a "udp://tracker.openbittorrent.com:80/announce, udp://tracker.publicbt.com:80/announce, udp://tracker.opentrackr.org:1337" -c "OpenShot Video Editor %s" -w "%s" -o "%s" "%s"' % (version, download_url, "%s.torrent" % app_name, app_name)
            torrent_output = ""
            # Create torrent
            for line in run_command(torrent_command, builds_path):
                output(line)
                if line:
                    torrent_output = line.decode('UTF-8').strip()

            if not torrent_output.endswith("Writing metainfo file... done."):
                # Torrent failed
                error("Torrent Error: Unexpected output (%s)" % torrent_output)

            else:
                # Torrent succeeded! Upload the torrent to github
                url = upload(torrent_path, github_release)

                # Notify Slack
                slack_upload_log(log, "%s: Build logs for %s" % (platform.system(), app_name), "Successful build: %s" % download_url)

                # Move app to uploads folder, and remove from build folder (so it will be skipped next time)
                shutil.copyfile(app_build_path, app_upload_path)
                os.remove(app_build_path)
                shutil.copyfile(torrent_path, "%s.torrent" % app_upload_path)
                os.remove(torrent_path)

        else:
            # App doesn't exist (something went wrong)
            error("App Missing Error: %s does not exist" % app_build_path)

except Exception as ex:
    tb = traceback.format_exc()
    error("Unhandled exception: %s - %s" % (str(ex), str(tb)))


# Report any errors detected
if errors_detected:
    slack_upload_log(log, "%s: Error log" % platform.system(), ":skull_and_crossbones: %s" % truncate(errors_detected[0], 150))

















