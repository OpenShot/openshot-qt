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
import re
import stat
import subprocess
import sys
import tinys3
import time
import traceback
from github3 import login
from requests.auth import HTTPBasicAuth
from requests import post

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
# Access info class (for version info)
sys.path.append(os.path.join(PATH, 'src', 'classes'))
import info

freeze_command = None
errors_detected = []
make_command = "make"
zulip_token = None
s3_access_key = None
s3_secret_key = None
s3_connection = None
windows_key = None
windows_key_password = None
github_user = None
github_pass = None
github_release = None
windows_32bit = False
version_info = {}

# Create temp log
log_path = os.path.join(PATH, 'build', 'build-server.log')
log = open(log_path, 'w+')


def output(line):
    """Append output to list and print it"""
    print(line)
    if isinstance(line, bytes):
        line = line.decode('UTF-8').strip()

    if not line.endswith(os.linesep):
        # Append missing line return (if needed)
        line += "\n"
    log.write(line)


def run_command(command, working_dir=None):
    """Utility function to return output from command line"""
    short_command = command.split('" ')[0]  # We don't need to print args
    output("Running %s... (%s)" % (short_command, working_dir))
    p = subprocess.Popen(command, shell=True, cwd=working_dir,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b"")


def error(line):
    """Append error output to list and print it"""
    print("Error: %s" % line)
    errors_detected.append(line)
    if isinstance(line, bytes):
        log.write(line.decode('UTF-8'))
    else:
        log.write(line)


def truncate(message, maxlen=256):
    """Truncate the message with ellipses"""
    if len(message) < maxlen:
        return message
    else:
        return "%s..." % message[:maxlen]


def zulip_upload_log(log, title, comment=None):
    """Upload a file to zulip and notify a zulip channel"""
    output("Zulip Upload: %s" % log_path)

    # Write log file
    log.flush()

    # Authentication for Zulip
    zulip_auth = HTTPBasicAuth('builder-bot@openshot.zulipchat.com', zulip_token)
    filename = "%s-build-server.txt" % platform.system()

    # Upload file to Zulip
    zulip_url = 'https://openshot.zulipchat.com/api/v1/user_uploads'
    zulip_upload_url = ''
    resp = post(zulip_url, data={}, auth=zulip_auth, files={filename: (filename, open(log_path, "rb"))})
    if resp.ok:
        zulip_upload_url = resp.json().get("uri", "")
    print(resp)

    # Determine topic
    topic = "Successful Builds"
    if "skull" in comment:
        topic = "Failed Builds"

    # SEND MESSAGE
    zulip_url = 'https://openshot.zulipchat.com/api/v1/messages'
    zulip_data = {
        "type": "stream",
        "to": "build-server",
        "subject": topic,
        "content": ':%s: %s [Build Log](%s)' % (platform.system().lower(), comment, zulip_upload_url)
    }

    resp = post(zulip_url, data=zulip_data, auth=zulip_auth)

    # Re-open the log (for append)
    log = open(log_path, "a")
    print(resp)

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
    if not s3_connection:
        return None
    url = None
    file_name = os.path.basename(file_path)

    # Check if this asset is already uploaded
    for asset in github_release.assets:
        if asset.name == file_name:
            raise Exception('Duplicate asset already uploaded: %s (%s)' % (file_path, asset.to_json()["browser_download_url"]))

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

def parse_version_info(version_path):
    """Parse version info from gitlab artifacts"""
    # Get name of version file
    version_name = os.path.basename(version_path)
    version_info[version_name] = {
        "CI_PROJECT_NAME": None,
        "CI_COMMIT_REF_NAME": None,
        "CI_COMMIT_SHA": None,
        "CI_JOB_ID": None,
        "CI_PIPELINE_ID": None,
        }

    if os.path.exists(version_path):
        with open(version_path, "r") as f:
            # Parse each line in f as a 'key:value' string
            version_info[version_name].update(
                (l.strip().split(':') for l in f.readlines()))
    else:
        # Fail
        raise Exception("Missing version artifacts: %s (%s)" % (version_path, str(version_info)))


try:
    # Validate command-line arguments
    if len(sys.argv) >= 2:
        zulip_token = sys.argv[1]
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

    if len(sys.argv) >= 9:
        windows_32bit = False
        if sys.argv[8] == 'True':
            windows_32bit = True

    git_branch_name = "develop"
    if len(sys.argv) >= 10:
        git_branch_name = sys.argv[9]

    # Start log
    output("%s Build Log for %s (branch: %s)" % (platform.system(), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), git_branch_name))

    # Detect artifact folder (if any)
    artifact_path = os.path.join(PATH, "build", "install-x64")
    if not os.path.exists(artifact_path):
        artifact_path = os.path.join(PATH, "build", "install-x86")
    if not os.path.exists(artifact_path):
        # Default to user install path
        artifact_path = ""

    # Parse artifact version files (if found)
    parse_version_info(os.path.join(artifact_path, "share", "libopenshot-audio"))
    parse_version_info(os.path.join(artifact_path, "share", "libopenshot"))
    parse_version_info(os.path.join(artifact_path, "share", "openshot-qt"))
    output(str(version_info))

    # Get GIT description of openshot-qt-git branch (i.e. v2.0.6-18-ga01a98c)
    openshot_qt_git_desc = ""
    needs_upload = True

    pipeline_id = version_info.get('openshot-qt').get('CI_PIPELINE_ID')
    if git_branch_name.startswith("release"):
        # Name release candidates with pipeline ID for uniqueness
        openshot_qt_git_desc = "OpenShot-v%s-release-candidate-%s" % (
            info.VERSION, pipeline_id)
        # Get daily git_release object
        github_release = get_release(repo, "daily")
    elif git_branch_name == "master":
        # Get official version release (i.e. v2.1.0, v2.x.x)
        openshot_qt_git_desc = "OpenShot-v%s" % info.VERSION
        github_release_name = "v%s" % info.VERSION
        github_release = get_release(repo, github_release_name)

        # If no release is found, create a new one
        if not github_release:
            # Create a new release if one if missing
            github_release = repo.create_release(github_release_name, target_commitish="master", prerelease=True)
    else:
        # Generate unique name using library commit SHAs and pipeline ID
        openshot_qt_git_desc = "OpenShot-v%s-%s-%s-%s" % (
            info.VERSION,
            pipeline_id,
            version_info.get('libopenshot').get('CI_COMMIT_SHA')[:8],
            version_info.get('libopenshot-audio').get('CI_COMMIT_SHA')[:8],
            )
        # Get daily git_release object
        github_release = get_release(repo, "daily")
        if git_branch_name != "develop":
            # Only upload develop-branch pipelines as Daily Builds
            needs_upload = False

    # Output git description
    output("git description of openshot-qt-git: %s" % openshot_qt_git_desc)

    # Detect version number from git description
    version = re.search('v(.+?)($|-)', openshot_qt_git_desc).groups()[0]

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
    builds_path = os.path.join(PATH, "build")
    app_build_path = os.path.join(builds_path, app_name)
    app_upload_path = os.path.join(builds_path, app_name)

    # Successfully frozen - Time to create installers
    if platform.system() == "Linux":
        # Locate exe_dir
        for exe_path in os.listdir(os.path.join(PATH, "build")):
            if exe_path.startswith('exe.linux'):
                exe_dir = exe_path
                break

        app_dir_path = os.path.join(PATH, "build", "OpenShot.AppDir")

        # Recursively create AppDir /usr folder
        os.makedirs(os.path.join(app_dir_path, "usr"), exist_ok=True)

        # XDG Freedesktop icon paths
        icons = [ ("scalable", os.path.join(PATH, "xdg", "openshot-qt.svg")),
                  ("64x64", os.path.join(PATH, "xdg", "icon", "64", "openshot-qt.png")),
                  ("128x128", os.path.join(PATH, "xdg", "icon", "128", "openshot-qt.png")),
                  ("256x256", os.path.join(PATH, "xdg", "icon", "256", "openshot-qt.png")),
                  ("512x512", os.path.join(PATH, "xdg", "icon", "512", "openshot-qt.png")),
                ]

        # Copy desktop icons
        icon_theme_path = os.path.join(app_dir_path, "usr", "share", "icons", "hicolor")

        # Copy each icon
        for icon_size, icon_path in icons:
            dest_icon_path = os.path.join(icon_theme_path, icon_size, "apps", os.path.split(icon_path)[-1])
            os.makedirs(os.path.split(dest_icon_path)[0], exist_ok=True)
            shutil.copyfile(icon_path, dest_icon_path)

        # Install .DirIcon AppImage icon (256x256)
        # See: https://docs.appimage.org/reference/appdir.html
        shutil.copyfile(icons[3][1], os.path.join(app_dir_path, ".DirIcon"))

        # Install program icon
        shutil.copyfile(icons[0][1], os.path.join(app_dir_path, "openshot-qt.svg"))

        dest = os.path.join(app_dir_path, "usr", "share", "pixmaps")
        os.makedirs(dest, exist_ok=True)

        # Copy pixmaps (as a 64x64 PNG & SVG)
        shutil.copyfile(icons[0][1], os.path.join(dest, "openshot-qt.svg"))
        shutil.copyfile(icons[1][1], os.path.join(dest, "openshot-qt.png"))

        # Install MIME handler
        dest = os.path.join(app_dir_path, "usr", "share", "mime", "packages")
        os.makedirs(dest, exist_ok=True)
        shutil.copyfile(os.path.join(PATH, "xdg", "org.openshot.OpenShot.xml"),
                        os.path.join(dest, "openshot-qt.xml"))

        # Copy the entire frozen app
        shutil.copytree(os.path.join(PATH, "build", exe_dir),
                        os.path.join(app_dir_path, "usr", "bin"))

        # Copy .desktop file, replacing Exec= commandline
        desk_in = os.path.join(PATH, "xdg", "org.openshot.OpenShot.desktop")
        desk_out = os.path.join(app_dir_path, "openshot-qt.desktop")
        with open(desk_in, "r") as inf, open(desk_out, "w") as outf:
            for line in inf:
                if line.startswith("Exec="):
                    outf.write("Exec=openshot-qt-launch.wrapper %F\n")
                else:
                    outf.write(line)

        # Copy desktop integration wrapper (prompts users to install shortcut)
        launcher_path = os.path.join(app_dir_path, "usr", "bin", "openshot-qt-launch")
        os.rename(os.path.join(app_dir_path, "usr", "bin", "launch-linux.sh"), launcher_path)
        desktop_wrapper = os.path.join(app_dir_path, "usr", "bin", "openshot-qt-launch.wrapper")
        shutil.copyfile("/home/ubuntu/apps/AppImageKit/desktopintegration", desktop_wrapper)

        # Create AppRun.64 file (the real one)
        app_run_path = os.path.join(app_dir_path, "AppRun")
        shutil.copyfile("/home/ubuntu/apps/AppImageKit/AppRun", app_run_path)

        # Add execute bit to file mode for AppRun and scripts
        st = os.stat(app_run_path)
        os.chmod(app_run_path, st.st_mode | stat.S_IEXEC)
        os.chmod(desktop_wrapper, st.st_mode | stat.S_IEXEC)
        os.chmod(launcher_path, st.st_mode | stat.S_IEXEC)

        # Create AppImage (OpenShot-%s-x86_64.AppImage)
        app_image_success = False
        for line in run_command('/home/ubuntu/apps/AppImageKit/AppImageAssistant "%s" "%s"' % (app_dir_path, app_build_path)):
            output(line)
        app_image_success = os.path.exists(app_build_path)

        # Was the AppImage creation successful
        if not app_image_success or errors_detected:
            # AppImage failed
            error("AppImageKit Error: AppImageAssistant did not output the AppImage file")
            needs_upload = False

            # Delete build (since something failed)
            os.remove(app_build_path)


    if platform.system() == "Darwin":

        # Create DMG (OpenShot-%s-x86_64.DMG)
        app_image_success = False

        # Build app.bundle and create DMG
        for line in run_command("bash installer/build-mac-dmg.sh"):
            output(line)
            if ("error".encode("UTF-8") in line and "No errors".encode("UTF-8") not in line) or "rejected".encode("UTF-8") in line:
                error("Build-Mac-DMG Error: %s" % line)
            if "Your image is ready".encode("UTF-8") in line:
                app_image_success = True

        # Rename DMG (to be consistent with other OS installers)
        for dmg_path in os.listdir(os.path.join(PATH, "build")):
            if os.path.isfile(os.path.join(PATH, "build", dmg_path)) and dmg_path.endswith(".dmg"):
                os.rename(os.path.join(PATH, "build", dmg_path), app_build_path)

        # Was the DMG creation successful
        if not app_image_success or errors_detected:
            # DMG failed
            error("Build-Mac-DMG Error: Did not output 'Your image is ready'")
            needs_upload = False

            # Delete build (since key signing might have failed)
            os.remove(app_build_path)


    if platform.system() == "Windows":

        # Move python folder structure, since Cx_Freeze doesn't put it in the correct place
        exe_dir = os.path.join(PATH, 'build', 'exe.mingw-3.7')
        python_dir = os.path.join(exe_dir, 'lib', 'python3.7')

        # Remove a redundant openshot_qt module folder (duplicates lots of files)
        duplicate_openshot_qt_path = os.path.join(python_dir, 'openshot_qt')
        if os.path.exists(duplicate_openshot_qt_path):
            shutil.rmtree(duplicate_openshot_qt_path, True)

        # Remove the following paths. cx_Freeze is including many unneeded files. This prunes them out.
        paths_to_delete = ['mediaservice', 'imageformats', 'platforms', 'printsupport', 'lib/openshot_qt', 'resvg.dll']
        for delete_path in paths_to_delete:
            full_delete_path = os.path.join(exe_dir, delete_path)
            output("Delete path: %s" % full_delete_path)
            if os.path.exists(full_delete_path):
                if os.path.isdir(full_delete_path):
                    # Delete Folder
                    shutil.rmtree(full_delete_path)
                else:
                    # Delete File
                    os.unlink(full_delete_path)
            else:
                output("Invalid delete path: %s" % full_delete_path)

        # Replace these folders (cx_Freeze messes this up, so this fixes it)
        paths_to_replace = ['imageformats', 'platforms']
        for replace_name in paths_to_replace:
            if windows_32bit:
                shutil.copytree(os.path.join('C:\\msys32\\mingw32\\share\\qt5\\plugins', replace_name), os.path.join(exe_dir, replace_name))
            else:
                shutil.copytree(os.path.join('C:\\msys64\\mingw64\\share\\qt5\\plugins', replace_name), os.path.join(exe_dir, replace_name))

        # Copy Qt5Core.dll, Qt5Svg.dll to root of frozen directory
        paths_to_copy = [("Qt5Core.dll", "C:\\msys64\\mingw64\\bin\\"), ("Qt5Svg.dll", "C:\\msys64\\mingw64\\bin\\")]
        if windows_32bit:
            paths_to_copy = [("Qt5Core.dll", "C:\\msys32\\mingw32\\bin\\"), ("Qt5Svg.dll", "C:\\msys32\\mingw32\\bin\\")]
        for qt_file_name, qt_parent_path in paths_to_copy:
            qt5_path = os.path.join(qt_parent_path, qt_file_name)
            new_qt5_path = os.path.join(exe_dir, qt_file_name)
            if os.path.exists(qt5_path) and not os.path.exists(new_qt5_path):
                output("Copying %s to %s" % (qt5_path, new_qt5_path))
                shutil.copy(qt5_path, new_qt5_path)

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

        # Add version metadata to frozen app launcher
        launcher_exe = os.path.join(exe_dir, "openshot-qt.exe")
        verpatch_success = True
        verpatch_command = '"verpatch.exe" "{}" /va /high "{}" /pv "{}" /s product "{}" /s company "{}" /s copyright "{}" /s desc "{}"'.format(launcher_exe, info.VERSION, info.VERSION, info.PRODUCT_NAME, info.COMPANY_NAME, info.COPYRIGHT, info.PRODUCT_NAME)
        verpatch_output = ""
        # version-stamp executable
        for line in run_command(verpatch_command):
            output(line)
            if line:
                verpatch_success = False
                verpatch_output = line

        # Was the verpatch command successful
        if not verpatch_success:
            # Verpatch failed (not fatal)
            error("Verpatch Error: Had output when none was expected (%s)" % verpatch_output)

        # Copy uninstall files into build folder
        for file in os.listdir(os.path.join("c:/", "InnoSetup")):
            shutil.copyfile(os.path.join("c:/", "InnoSetup", file), os.path.join(PATH, "build", file))

        # Create Installer (OpenShot-%s-x86_64.exe)
        inno_success = True
        inno_command = '"iscc.exe" /Q /DVERSION=%s /DONLY_64_BIT=%s "%s"' % (version, only_64_bit, os.path.join(PATH, 'installer', 'windows-installer.iss'))
        inno_output = ""
        # Compile Inno installer
        for line in run_command(inno_command):
            output(line)
            if line:
                inno_success = False
                inno_output = line

        # Was the Inno Installer successful
        inno_output_exe = os.path.join(PATH, "installer", "Output", "OpenShot.exe")
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
        key_sign_command = '"kSignCMD.exe" /f "%s%s" /p "%s" /d "OpenShot Video Editor" /du "http://www.openshot.org" "%s"' % (windows_key, only_64_bit, windows_key_password, app_build_path)
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


    # Upload Installer to GitHub (if build path exists)
    if needs_upload and os.path.exists(app_build_path):
        # Upload file to GitHub
        output("GitHub: Uploading %s to GitHub Release: %s" % (app_build_path, github_release.tag_name))
        download_url = upload(app_build_path, github_release)

        # Create torrent and upload
        torrent_path = "%s.torrent" % app_build_path
        torrent_command = 'mktorrent -a "udp://tracker.openbittorrent.com:80/announce, udp://tracker.publicbt.com:80/announce, udp://tracker.opentrackr.org:1337" -c "OpenShot Video Editor %s" -w "%s" -o "%s" "%s"' % (version, download_url, "%s.torrent" % app_name, app_name)
        torrent_output = ""

        # Remove existing torrents (if any found)
        if os.path.exists(torrent_path):
            os.remove(torrent_path)

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

            # Notify Zulip
            zulip_upload_log(log, "%s: Build logs for %s" % (platform.system(), app_name), "Successful *%s* build: %s" % (git_branch_name, download_url))

except Exception as ex:
    tb = traceback.format_exc()
    error("Unhandled exception: %s - %s" % (str(ex), str(tb)))

if not errors_detected:
    output("Successfully completed build-server script!")
else:
    # Report any errors detected
    output("build-server script failed!")
    zulip_upload_log(log, "%s: Error log for *%s* build" % (platform.system(), git_branch_name), ":skull_and_crossbones: %s" % truncate(errors_detected[0], 100))
    exit(1)
