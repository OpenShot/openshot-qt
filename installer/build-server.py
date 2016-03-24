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
sys.path.append(os.path.join(PATH, 'src'))

import datetime
import platform
import shutil
from classes import info
from slacker import Slacker
import stat
import subprocess
import sys
import tinys3
import traceback


freeze_command = None
output_lines = []
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
    freeze_command = 'python3 /Users/jonathan/apps/openshot-qt-git/freeze.py bdist_mac --iconfile=installer/openshot.icns --custom-info-plist=installer/Info.plist --bundle-name="OpenShot Video Editor"'
    project_paths = [("/Users/jonathan/apps/libopenshot-audio-git", '-DCMAKE_CXX_COMPILER=clang++ -DCMAKE_C_COMPILER=clang -D"CMAKE_BUILD_TYPE:STRING=Release" -D"CMAKE_OSX_DEPLOYMENT_TARGET=10.9" ../'),
                     ("/Users/jonathan/apps/libopenshot-git", '-DCMAKE_CXX_COMPILER=/usr/local/opt/gcc48/bin/g++-4.8 -DCMAKE_C_COMPILER=/usr/local/opt/gcc48/bin/gcc-4.8 -DCMAKE_PREFIX_PATH=/usr/local/qt5/5.5/clang_64 -DPYTHON_INCLUDE_DIR=/Library/Frameworks/Python.framework/Versions/3.5/include/python3.5m -DPYTHON_LIBRARY=/Library/Frameworks/Python.framework/Versions/3.5/lib/libpython3.5.dylib -DPython_FRAMEWORKS=/Library/Frameworks/Python.framework/ -D"CMAKE_BUILD_TYPE:STRING=Release" -D"CMAKE_OSX_SYSROOT=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.9.sdk" -D"CMAKE_OSX_DEPLOYMENT_TARGET=10.9" ../ -D”CMAKE_INSTALL_RPATH_USE_LINK_PATH=1” -D"ENABLE_RUBY=0"'),
                     ("/Users/jonathan/apps/openshot-qt-git", "")]

elif platform.system() == "Windows":
    make_command = "mingw32-make"
    freeze_command = "python C:\\Users\\Jonathan\\apps\\openshot-qt-git\\freeze.py bdist_msi"
    project_paths = [("C:\\Users\\Jonathan\\apps\\libopenshot-audio-git", '-G "MinGW Makefiles" ../ -D"CMAKE_BUILD_TYPE:STRING=Release"'),
                     ("C:\\Users\\Jonathan\\apps\\libopenshot-git", '-G "MinGW Makefiles" ../ -D"CMAKE_BUILD_TYPE:STRING=Release"'),
                     ("C:\\Users\\Jonathan\\apps\\openshot-qt-git", "")]


def run_command(command):
    """Utility function to return output from command line"""
    p = subprocess.Popen(command, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b"")

def output(line):
    """Append output to list and print it"""
    print(line)
    output_lines.append(line)
    if isinstance(line, bytes):
        log.write(line.decode('UTF-8'))
    else:
        log.write(line)

def error(line):
    """Append error output to list and print it"""
    print("Error: %s" % line)
    errors_detected.append(line)
    if isinstance(line, bytes):
        log.write(line.decode('UTF-8'))
    else:
        log.write(line)

def truncate(message):
    """Truncate the message with ellipses"""
    if len(message) < 256:
        return message
    else:
        return "%s..." % message[:256]

def slack(message):
    """Append a message to slack #build-server channel"""
    print("Slack: %s" % message)
    if slack_object:
        slack_object.chat.post_message("#build-server", truncate(message[:256]))

def slack_upload_log(log, title):
    """Upload a file to slack and notify a slack channel"""
    # Close log file
    log.close()

    print("Slack Upload: %s" % log_path)
    if slack_object:
        slack_object.files.upload(log_path, title=title, channels="#build-server")

    # Re-open the log (for append)
    log = open(log_path, "a")

def upload(file_path, s3_bucket):
    """Upload a file to S3 (retry 3 times)"""
    if s3_connection:
        folder_path, file_name = os.path.split(file_path)
        for attempt in range(3):
            try:
                # Attempt the upload
                with open(file_path, "rb") as f:
                    s3_connection.upload(file_name, f, s3_bucket)
                # Successfully uploaded!
                break
            except Exception as ex:
                # Quietly fail, and try again
                if attempt < 2:
                    output("Amazon S3 upload failed... trying again")
                else:
                    # Throw loud exception
                    raise ex


try:
    # Validate command-line arguments
    # argv[1] = Slack_token
    # argv[2] = S3 access key
    # argv[3] = S3 secret key
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

    # Start log
    output("%s Build Log for %s" % (platform.system(), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # Loop through projects
    for project_path, cmake_args in project_paths:
        # Change os directory
        os.chdir(project_path)

        # Get number of commits
        for line in run_command("git rev-list --count master"):
            commit_data[project_path] = int(line)
            output("# of commits found for %s: %s" % (project_path, commit_data[project_path]))

        # Check for new version in git
        needs_update = True
        for line in run_command("git fetch -v --dry-run"):
            output(line)
            if "[up to date]".encode("UTF-8") in line:
                needs_update = False
                break

        if needs_update:
            # Get latest from git
            for line in run_command("git pull origin master"):
                output(line)

            # Sync these changes to bzr (if build-server running on linux)
            if platform.system() == "Linux":
                for line in run_command("git bzr push"):
                    output(line)

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

        # Get GIT description of openshot-qt-git branch (i.e. v2.0.6-18-ga01a98c)
        openshot_qt_git_desc = ""
        for line in run_command("git describe --tags"):
            openshot_qt_git_desc = "OpenShot-%s" % line.decode("utf-8").replace("\n","")
            output("git description of openshot-qt-git: %s" % openshot_qt_git_desc)

            # Add num of commits from libopenshot and libopenshot-audio (for naming purposes)
            openshot_qt_git_desc = "%s-%s-%s" % (openshot_qt_git_desc, commit_data[project_paths[0][0]], commit_data[project_paths[1][0]])

        # Check for left over openshot-qt dupe folder
        if os.path.exists(os.path.join(project_path, "openshot_qt")):
            shutil.rmtree(os.path.join(project_path, "openshot_qt"))
        if os.path.exists(os.path.join(project_path, "build")):
            shutil.rmtree(os.path.join(project_path, "build"))
        if os.path.exists(os.path.join(project_path, "dist")):
            shutil.rmtree(os.path.join(project_path, "dist"))

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
        elif platform.system() == "Windows":
            app_name += "-x86_32.msi"
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
                        if "error".encode("UTF-8") in line:
                            error("AppImageKit Error: %s" % line)
                        if "completed sucessfully".encode("UTF-8") in line:
                            app_image_success = True

                    # Was the AppImage creation successful
                    if not app_image_success:
                        # AppImage failed
                        error("AppImageKit Error: AppImageAssistant did not output 'completed successfully'")
                        needs_upload = False


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

                # Was the DMG creation successful
                if app_image_success:
                    # Rename DMG (to be consistent with other OS installers)
                    os.rename(os.path.join(project_path, "build", "OpenShot-%s.dmg" % info.VERSION), app_build_path)

                else:
                    # DMG failed
                    error("Build-Mac-DMG Error: Did not output 'Your image is ready'")
                    needs_upload = False


            if platform.system() == "Windows":

                # Create MSI (OpenShot-%s-x86_32.MSI)
                app_image_success = True

                # Rename MSI (to be consistent with other OS installers)
                os.rename(os.path.join(project_path, "dist", "OpenShot Video Editor-%s-win32.msi" % info.VERSION), app_build_path)

                key_sign_command = '"C:\\Program Files (x86)\\kSign\\kSignCMD.exe" /f "%s" /p "%s" /d "OpenShot Video Editor" /du "http://www.openshot.org" "%s"' % (windows_key, windows_key_password, app_build_path)
                # Sign MSI
                for line in run_command(key_sign_command):
                    output(line)
                    if line:
                        app_image_success = False

                # Was the MSI creation successful
                if not app_image_success:
                    # MSI failed
                    error("Key Sign Error: Had output when none was expected")
                    needs_upload = False


        if needs_upload:
            # Check if app exists
            if os.path.exists(app_build_path):
                # Upload file to S3
                output("S3: Uploading %s to Amazon S3" % app_build_path)
                upload(app_build_path, app_upload_bucket)

                # Notify Slack
                slack("%s: Successful build: http://%s/%s" % (platform.system(), app_upload_bucket, app_name))
                slack_upload_log(log, "%s: Build logs for %s" % (platform.system(), app_name))

                # Copy app to uploads folder (so it will be skipped next time)
                shutil.copyfile(app_build_path, app_upload_path)

            else:
                # App doesn't exist (something went wrong)
                error("App Missing Error: %s does not exist" % app_build_path)


except Exception as ex:
    tb = traceback.format_exc()
    error("Unhandled exception: %s - %s" % (str(ex), str(tb)))


# Report any errors detected
if errors_detected:
    slack("%s: Build errors were detected: %s" % (platform.system(), errors_detected))
    slack_upload_log(log, "%s: Error log" % platform.system())
else:
    output("Successful build server run!")

# Close file
log.close()

















