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

import datetime
import platform
import re
import shutil
import shlex
import stat
import subprocess
import sysconfig
import traceback
from github3 import login, GitHubError
from requests.auth import HTTPBasicAuth
from requests import post
from version_parser import parse_version_info, parse_build_name

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
PY_ABI = sysconfig.get_config_var('py_version_short')

# Access info class (for version info)
sys.path.append(os.path.join(PATH, 'src', 'classes'))
import info

freeze_command = None
errors_detected = []
make_command = "make"
zulip_token = None
windows_key = None
windows_key_password = None
github_user = None
github_pass = None
github_release = None
windows_32bit = False
version_info = {}

# Create temp log
os.makedirs(os.path.join(PATH, 'build'), exist_ok=True)
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
    short_command = shlex.split(command)[0]  # We don't need to print args
    output("Running %s... (%s)" % (short_command, working_dir))
    p = subprocess.Popen(
        command,
        shell=True,
        cwd=working_dir,
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
    return "%s..." % message[:maxlen]


def zulip_upload_log(zulip_token, log, title, comment=None):
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
    if hasattr(repo, 'releases'):
        release_iter = repo.releases()
    else:
        release_iter = repo.iter_releases()
    for release in release_iter:
        if release.tag_name == tag_name:
            return release


def upload(file_path, github_release):
    """Upload a file to GitHub (retry 3 times)"""
    url = None
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    def remove_existing_asset():
        """Remove a conflicting asset from the release (if any)"""
        # pick the right asset-list provider
        if hasattr(github_release, 'original_assets'):
            asset_list = github_release.original_assets
        else:
            asset_list = github_release.assets
        for asset in asset_list:
            if asset.name == file_name:
                output(f"GitHub: Removing conflicting installer asset from {github_release.tag_name}: {file_name}")
                try:
                    asset.delete()
                except Exception as ex:
                    output(f"GitHub: Failed to delete asset: {ex}")
                break

    # Try up to 3 times
    for attempt in range(1, 4):
        remove_existing_asset()

        try:
            # Attempt the upload
            with open(file_path, "rb") as f:
                # Upload to GitHub
                output(f"GitHub: Uploading asset from {github_release.tag_name}: "
                       f"{file_name} (size: {file_size} bytes) [attempt {attempt}]")
                asset = github_release.upload_asset("application/octet-stream", file_name, f)
                if hasattr(asset, 'browser_download_url'):
                    url = asset.browser_download_url
                else:
                    url = asset.to_json()["browser_download_url"]
            # Successfully uploaded!
            break
        except Exception as ex:
            # log the failure
            msg = ex
            if isinstance(ex, GitHubError):
                msg = ex.response.json()
            output(f"GitHub: Upload attempt {attempt} failed: {msg}")

            if attempt == 3:
                # out of retries — bubble up
                raise Exception(f"Upload failed after {attempt} attempts. "
                                f"Verify that this file isn't already uploaded: {file_path}", ex)

    return url


def main():
    # Only run this code when directly executing this script. Parts of this file
    # are also used in the deploy.py script.
    try:
        # Validate command-line arguments
        if len(sys.argv) >= 2:
            zulip_token = sys.argv[1]
        if len(sys.argv) >= 4:
            windows_key = sys.argv[2]
            windows_key_password = sys.argv[3]
        if len(sys.argv) >= 6:
            github_user = sys.argv[4]
            github_pass = sys.argv[5]

            # Login and get "GitHub" object
            gh = login(github_user, github_pass)
            repo = gh.repository("OpenShot", "openshot-qt")

        if len(sys.argv) >= 7:
            windows_32bit = False
            if sys.argv[6] == 'True':
                windows_32bit = True

        git_branch_name = "develop"
        if len(sys.argv) >= 8:
            git_branch_name = sys.argv[7]

        mac_password = ""
        if len(sys.argv) >= 9:
            mac_password = sys.argv[8]

        # Start log
        output(
            "%s Build Log for %s (branch: %s)" % (
                platform.system(),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                git_branch_name)
            )

        # Detect artifact folder (if any)
        artifact_path = os.path.join(PATH, "build", "install-x64")
        if not os.path.exists(artifact_path):
            artifact_path = os.path.join(PATH, "build", "install-x86")
        if not os.path.exists(artifact_path):
            # Default to user install path
            artifact_path = ""

        # Parse artifact version files (if found)
        for repo_name in ["libopenshot-audio", "libopenshot", "openshot-qt"]:
            data_file = f"{repo_name}.env"
            version_info.update(
                parse_version_info(os.path.join(artifact_path, "share", data_file)))
        output(str(version_info))

        # Get GIT description of openshot-qt-git branch (i.e. v2.0.6-18-ga01a98c)
        openshot_qt_git_desc = parse_build_name(version_info, git_branch_name)
        needs_upload = True

        # Get daily git_release object
        github_release = get_release(repo, "daily")
        if git_branch_name != "develop" and not git_branch_name.startswith("release"):
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
            icons = [
                ("scalable", os.path.join(PATH, "xdg", "openshot-qt.svg")),
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
                            os.path.join(dest, "org.openshot.OpenShot.xml"))

            # Install AppStream XML metadata
            dest = os.path.join(app_dir_path, "usr", "share", "metainfo")
            os.makedirs(dest, exist_ok=True)
            shutil.copyfile(os.path.join(PATH, "xdg", "org.openshot.OpenShot.appdata.xml"),
                            os.path.join(dest, "org.openshot.OpenShot.appdata.xml"))

            # Copy the entire frozen app
            shutil.copytree(os.path.join(PATH, "build", exe_dir),
                            os.path.join(app_dir_path, "usr", "bin"))

            # Copy .desktop file, replacing Exec= commandline
            desk_in = os.path.join(PATH, "xdg", "org.openshot.OpenShot.desktop")
            desk_out = os.path.join(app_dir_path, "org.openshot.OpenShot.desktop")
            with open(desk_in, "r") as inf, open(desk_out, "w") as outf:
                for line in inf:
                    if line.startswith("Exec="):
                        outf.write("Exec=openshot-qt-launch %F\n")
                    else:
                        outf.write(line)
            # Copy modified .desktop file to usr/share/applciations
            dest = os.path.join(app_dir_path, "usr", "share", "applications")
            os.makedirs(dest, exist_ok=True)
            shutil.copyfile(os.path.join(app_dir_path, "org.openshot.OpenShot.desktop"),
                            os.path.join(dest, "org.openshot.OpenShot.desktop"))

            # Rename executable launcher script
            launcher_path = os.path.join(app_dir_path, "usr", "bin", "openshot-qt-launch")
            os.rename(os.path.join(app_dir_path, "usr", "bin", "launch-linux.sh"), launcher_path)

            # Create AppRun file
            app_run_path = os.path.join(app_dir_path, "AppRun")
            shutil.copyfile("/home/ubuntu/apps/AppImageKit/AppRun", app_run_path)

            # Add execute bit to file mode for AppRun and scripts
            st = os.stat(app_run_path)
            os.chmod(app_run_path, st.st_mode | stat.S_IEXEC)
            os.chmod(launcher_path, st.st_mode | stat.S_IEXEC)

            # Create AppImage (OpenShot-%s-x86_64.AppImage)
            app_image_success = False
            for line in run_command(" ".join([
                '/home/ubuntu/apps/AppImageKit/appimagetool-x86_64.AppImage',
                '"%s"' % app_dir_path,
                '"%s"' % app_build_path
            ])):
                output(line)
            app_image_success = os.path.exists(app_build_path)

            # Was the AppImage creation successful
            if not app_image_success or errors_detected:
                # AppImage failed
                error("AppImageKit Error: appimagetool did not output the AppImage file")
                needs_upload = False

                # Delete build (since something failed)
                os.remove(app_build_path)

        if platform.system() == "Darwin":
            # Create DMG (OpenShot-%s-x86_64.DMG)
            app_image_success = False

            # Build app.bundle and create DMG
            for line in run_command(f'bash installer/build-mac-dmg.sh "{mac_password}"'):
                output(line)
                if (
                        ("error".encode("UTF-8") in line
                         and "No errors".encode("UTF-8") not in line)
                        or "rejected".encode("UTF-8") in line
                ):
                    error("Build-Mac-DMG Error: %s" % line)
                if "Your image is ready".encode("UTF-8") in line:
                    app_image_success = True

            # Rename DMG (to be consistent with other OS installers)
            for dmg_path in os.listdir(os.path.join(PATH, "build")):
                if (
                        os.path.isfile(os.path.join(PATH, "build", dmg_path))
                        and dmg_path.endswith(".dmg")
                ):
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
            exe_dir = os.path.join(PATH, 'build', 'exe.mingw-{}'.format(PY_ABI))
            python_dir = os.path.join(exe_dir, 'lib', 'python{}'.format(PY_ABI))

            # Remove a redundant openshot_qt module folder (duplicates lots of files)
            duplicate_openshot_qt_path = os.path.join(python_dir, 'openshot_qt')
            if os.path.exists(duplicate_openshot_qt_path):
                shutil.rmtree(duplicate_openshot_qt_path, True)

            # Remove the following paths. cx_Freeze is including many unneeded files. This prunes them out.
            paths_to_delete = [
                'mediaservice',
                'imageformats',
                'platforms',
                'printsupport',
                'lib/openshot_qt',
                'resvg.dll',
                ]
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
                    shutil.copytree(
                        os.path.join('C:\\msys64\\mingw32\\share\\qt5\\plugins', replace_name),
                        os.path.join(exe_dir, replace_name))
                else:
                    shutil.copytree(
                        os.path.join('C:\\msys64\\mingw64\\share\\qt5\\plugins', replace_name),
                        os.path.join(exe_dir, replace_name))

            # Copy Qt5Core.dll, Qt5Svg.dll to root of frozen directory
            paths_to_copy = [
                ("Qt5Core.dll", "C:\\msys64\\mingw64\\bin\\"),
                ("Qt5Svg.dll", "C:\\msys64\\mingw64\\bin\\"),
                ]
            if windows_32bit:
                paths_to_copy = [
                    ("Qt5Core.dll", "C:\\msys64\\mingw32\\bin\\"),
                    ("Qt5Svg.dll", "C:\\msys64\\mingw32\\bin\\"),
                    ]
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
            verpatch_command = " ".join([
                'verpatch.exe',
                '{}'.format(launcher_exe),
                '/va',
                '/high "{}"'.format(info.VERSION),
                '/pv "{}"'.format(info.VERSION),
                '/s product "{}"'.format(info.PRODUCT_NAME),
                '/s company "{}"'.format(info.COMPANY_NAME),
                '/s copyright "{}"'.format(info.COPYRIGHT),
                '/s desc "{}"'.format(info.PRODUCT_NAME),
                ])
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
            inno_command = " ".join([
                'iscc.exe',
                '/Q',
                '/DVERSION=%s' % version,
                '/DONLY_64_BIT=%s' % only_64_bit,
                '/DPY_EXE_DIR=%s' % "exe.mingw-{}".format(PY_ABI),
                '"%s"' % os.path.join(PATH, 'installer', 'windows-installer.iss'),
                ])
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
            key_sign_command = " ".join([
                'kSignCMD.exe',
                '/f "%s%s"' % (windows_key, only_64_bit),
                '/p "%s"' % windows_key_password,
                '/d "OpenShot Video Editor"',
                '/du "http://www.openshot.org"',
                '"%s"' % app_build_path,
                ])
            key_sign_output = ""
            # Sign MSI
            for line in run_command(key_sign_command):
                output(line)
                if line and "will expire" not in line.decode('UTF-8'):
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
            tracker_list = [
                "udp://tracker.openbittorrent.com:80/announce",
                "udp://tracker.publicbt.com:80/announce",
                "udp://tracker.opentrackr.org:1337",
                ]
            torrent_command = " ".join([
                'mktorrent',
                '-a "%s"' % (", ".join(tracker_list)),
                '-c "OpenShot Video Editor %s"' % version,
                '-w "%s"' % download_url,
                '-o "%s"' % ("%s.torrent" % app_name),
                '"%s"' % app_name,
                ])
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
                zulip_upload_log(
                    zulip_token, log,
                    "%s: Build logs for %s" % (platform.system(), app_name),
                    "Successful *%s* build: %s" % (git_branch_name, download_url))

    except Exception as ex:
        tb = traceback.format_exc()
        error("Unhandled exception: %s - %s" % (str(ex), str(tb)))

    if not errors_detected:
        output("Successfully completed build-server script!")
    else:
        # Report any errors detected
        output("build-server script failed!")
        zulip_upload_log(
            zulip_token, log,
            "%s: Error log for *%s* build" % (platform.system(), git_branch_name),
            ":skull_and_crossbones: %s" % truncate(errors_detected[0], 100))
        exit(1)


if __name__ == "__main__":
    main()
