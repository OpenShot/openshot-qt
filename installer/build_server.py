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
import json

import datetime
import platform
import re
import shutil
import shlex
import stat
import subprocess
import sysconfig
import time
import traceback
import zipfile
from collections import deque
from github3 import login, GitHubError
from requests.auth import HTTPBasicAuth
from requests import post
from version_parser import parse_version_info, parse_build_name

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
PY_ABI = sysconfig.get_config_var('py_version_short')

# Access info class (for version info)
sys.path.append(os.path.join(PATH, 'src'))
sys.path.append(os.path.join(PATH, 'src', 'classes'))
import info

freeze_command = None
errors_detected = []
make_command = "make"
zulip_token = None
github_user = None
github_pass = None
github_release = None
windows_32bit = False
version_info = {}
windows_mode = "full"
LINUX_PORTAL_THEME_PLUGIN = (
    "/usr/lib/x86_64-linux-gnu/qt5/plugins/platformthemes/"
    "libqxdgdesktopportal.so"
)
# Create temp log
os.makedirs(os.path.join(PATH, 'build'), exist_ok=True)
log_path = os.path.join(PATH, 'build', 'build-server.log')
log = open(log_path, 'w+')


def output(line):
    """Append output to list and print it"""
    if isinstance(line, bytes):
        line = line.decode('UTF-8', errors="replace")

    line = str(line).rstrip("\r\n")
    print(line)

    if not line.endswith(os.linesep):
        # Append missing line return (if needed)
        line += "\n"
    log.write(line)


def install_linux_portal_theme(app_dir_path):
    """Bundle Qt's XDG desktop portal platform theme in the AppImage."""
    if not os.path.isfile(LINUX_PORTAL_THEME_PLUGIN):
        raise FileNotFoundError(
            "Missing Qt XDG desktop portal plugin: %s\n"
            "Install it on the build server with:\n"
            "  sudo apt-get install qt5-xdgdesktopportal-platformtheme"
            % LINUX_PORTAL_THEME_PLUGIN
        )

    plugin_dir = os.path.join(
        app_dir_path, "usr", "bin", "platformthemes")
    os.makedirs(plugin_dir, exist_ok=True)
    plugin_path = os.path.join(
        plugin_dir, os.path.basename(LINUX_PORTAL_THEME_PLUGIN))
    shutil.copy2(LINUX_PORTAL_THEME_PLUGIN, plugin_path)
    output("Bundled Qt XDG desktop portal plugin: %s" % plugin_path)


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
    retry_delay_seconds = 5
    for attempt in range(1, 4):
        try:
            output("GitHub: Looking up release by tag: %s [attempt %s/3]" % (tag_name, attempt))

            if hasattr(repo, 'release_by_tag_name'):
                return repo.release_by_tag_name(tag_name)

            output("GitHub: Direct release lookup unavailable; scanning releases")
            if hasattr(repo, 'releases'):
                release_iter = repo.releases()
            else:
                release_iter = repo.iter_releases()
            for release in release_iter:
                if release.tag_name == tag_name:
                    return release
            return None
        except Exception as ex:
            if attempt == 3:
                raise
            output("GitHub: Release lookup failed: %s; retrying in %s seconds" % (
                truncate(str(ex)), retry_delay_seconds))
            time.sleep(retry_delay_seconds)
            retry_delay_seconds *= 2


def upload(file_path, github_release):
    """Upload a file to GitHub (retry 3 times)"""
    url = None
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    def delete_existing_asset(asset):
        """Delete an existing release asset across github3 API variants."""
        if hasattr(asset, 'delete'):
            return asset.delete()

        asset_id = getattr(asset, 'id', None)
        if asset_id is not None:
            for method_name in ('delete_asset', 'delete_release_asset'):
                delete_method = getattr(github_release, method_name, None)
                if delete_method:
                    return delete_method(asset_id)

        delete_method = getattr(asset, '_delete', None)
        delete_url = getattr(asset, '_api', None) or getattr(asset, 'url', None)
        if delete_method and delete_url:
            return delete_method(delete_url)

        raise AttributeError(
            "No supported asset deletion API found for asset %s (type: %s)" % (
                file_name, type(asset).__name__,
            )
        )

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
                    delete_existing_asset(asset)
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


def run_command_with_exit_code(command, working_dir=None, stream_output=True, failure_tail_lines=120):
    """Run command and stream output to log, returning process exit code"""
    short_command = shlex.split(command)[0]  # We don't need to print args
    output("Running %s... (%s)" % (short_command, working_dir))
    p = subprocess.Popen(
        command,
        shell=True,
        cwd=working_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    captured_output = deque(maxlen=failure_tail_lines)
    for line in iter(p.stdout.readline, b""):
        if stream_output:
            output(line)
        else:
            captured_output.append(line)

    exit_code = p.wait()
    if not stream_output and exit_code != 0:
        output("Command failed with exit code %s. Last %s output lines:" % (
            exit_code, len(captured_output)))
        for line in captured_output:
            output(line)
    return exit_code


def shell_quote(value):
    """Quote a value for Windows shell commands."""
    return '"%s"' % str(value).replace('"', '\\"')


def get_signtool_path():
    return os.getenv(
        "SIGNTOOL_PATH",
        "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.26100.0\\x64\\signtool.exe")


def get_azure_codesign_dlib_path():
    return os.getenv(
        "AZURE_CODESIGN_DLIB_PATH",
        "C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\MicrosoftArtifactSigningClientTools\\Azure.CodeSigning.Dlib.dll")


def get_windows_authenticode_subject(signed_path):
    """Return the Authenticode signer subject from a signed Windows artifact."""
    configured_subject = os.getenv("WINDOWS_MSIX_PUBLISHER")
    if configured_subject:
        output("Using WINDOWS_MSIX_PUBLISHER for MSIX manifest publisher: %s" % configured_subject)
        return configured_subject

    powershell_command = (
        "param([string]$Path) "
        "$ErrorActionPreference = 'Stop'; "
        "$signature = Get-AuthenticodeSignature -LiteralPath $Path; "
        "Write-Host ('Authenticode status: ' + $signature.Status); "
        "if (-not $signature.SignerCertificate) { "
        "  throw ('No signer certificate found for ' + $Path + '; status=' + $signature.Status) "
        "}; "
        "$signature.SignerCertificate.Subject"
    )

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "& { %s }" % powershell_command,
        signed_path,
    ]
    try:
        subject_output = subprocess.check_output(  # nosec B603 - fixed command, no shell.
            command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as ex:
        error("Failed to inspect signed Windows package certificate subject. PowerShell output: %s" %
              ex.output.decode("UTF-8", errors="replace"))
        raise

    output_lines = [
        line.strip()
        for line in subject_output.decode("UTF-8", errors="replace").splitlines()
        if line.strip()
    ]
    for line in output_lines[:-1]:
        output(line)
    if not output_lines:
        raise RuntimeError("Get-AuthenticodeSignature returned no output for %s" % signed_path)
    return output_lines[-1]


def get_msix_manifest_metadata(msix_path):
    """Return key identity/properties values from an MSIX manifest."""
    try:
        from defusedxml import minidom

        with zipfile.ZipFile(msix_path, "r") as package:
            with package.open("AppxManifest.xml") as manifest_file:
                manifest_document = minidom.parse(manifest_file)

        metadata = {
            "publisher": None,
            "publisher_display_name": None,
            "version": None,
            "application_id": None,
            "executable": None,
            "entry_point": None,
        }
        for element in manifest_document.getElementsByTagName("*"):
            if element.localName == "Identity":
                metadata["publisher"] = element.getAttribute("Publisher")
                metadata["version"] = element.getAttribute("Version")
            elif element.localName == "PublisherDisplayName":
                metadata["publisher_display_name"] = "".join(
                    node.data
                    for node in element.childNodes
                    if node.nodeType == node.TEXT_NODE
                )
            elif element.localName == "Application":
                metadata["application_id"] = element.getAttribute("Id")
                metadata["executable"] = element.getAttribute("Executable")
                metadata["entry_point"] = element.getAttribute("EntryPoint")
        return metadata
    except Exception as ex:
        error("Failed to read MSIX manifest metadata: %s" % ex)
        return None


def get_expected_msix_version():
    """Return the artifact OpenShot version in the four-part MSIX format."""
    source_version = version_info.get("openshot-qt", {}).get("VERSION")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?$", source_version or "")
    if not match:
        raise RuntimeError("Invalid or missing openshot-qt artifact version: %s" % source_version)
    return ".".join((match.group(1), match.group(2), match.group(3), match.group(4) or "0"))


def replace_msix_visual_assets(package_root):
    """Replace every Packaging Tool logo variant using the canonical OpenShot logo."""
    from PIL import Image

    package_assets_dir = os.path.join(package_root, "Assets")
    source_logo_path = os.path.join(PATH, "xdg", "icon", "512", "openshot-qt.png")
    asset_specs = {
        "StoreLogo": (50, 50),
        "OPENSHOTQT-Square44x44Logo": (44, 44),
        "OPENSHOTQT-Square71x71Logo": (71, 71),
        "OPENSHOTQT-Square150x150Logo": (150, 150),
        "OPENSHOTQT-Square310x310Logo": (310, 310),
        "OPENSHOTQT-Wide310x150Logo": (310, 150),
    }
    if not os.path.isfile(source_logo_path):
        error("Canonical OpenShot logo not found: %s" % source_logo_path)
        return False

    os.makedirs(package_assets_dir, exist_ok=True)
    with Image.open(source_logo_path) as source_logo:
        source_logo = source_logo.convert("RGBA")
        existing_assets = os.listdir(package_assets_dir)
        for asset_stem, default_size in asset_specs.items():
            matching_names = [
                filename for filename in existing_assets
                if filename.lower().startswith(asset_stem.lower())
                and filename.lower().endswith(".png")
            ]
            base_name = "%s.png" % asset_stem
            if base_name not in matching_names:
                matching_names.append(base_name)

            for package_name in matching_names:
                package_path = os.path.join(package_assets_dir, package_name)
                canvas_size = default_size
                if os.path.isfile(package_path):
                    with Image.open(package_path) as existing_asset:
                        canvas_size = existing_asset.size
                logo_edge = max(1, round(min(canvas_size) * 0.92))
                resized_logo = source_logo.resize((logo_edge, logo_edge), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
                position = (
                    (canvas_size[0] - logo_edge) // 2,
                    (canvas_size[1] - logo_edge) // 2,
                )
                canvas.alpha_composite(resized_logo, position)
                canvas.save(package_path, format="PNG")
                output("Replaced MSIX visual asset from canonical logo: %s (%sx%s)" % (
                    package_name, canvas_size[0], canvas_size[1]))
    return True


def prepare_windows_msix_for_signing(msix_path, signed_installer_path):
    """Normalize the MSIX manifest and replace generated visual assets."""
    signer_subject = get_windows_authenticode_subject(signed_installer_path)
    publisher_display_name = os.getenv("WINDOWS_MSIX_PUBLISHER_DISPLAY_NAME", "OpenShot Studios")
    output("Windows signing certificate subject: %s" % signer_subject)

    manifest_metadata = get_msix_manifest_metadata(msix_path)
    if not manifest_metadata:
        return False
    output("MSIX manifest publisher before signing: %s" % manifest_metadata["publisher"])
    output("MSIX manifest publisher display name before signing: %s" %
           manifest_metadata["publisher_display_name"])
    expected_version = get_expected_msix_version()
    if manifest_metadata["version"] != expected_version:
        error("Unexpected MSIX version: %s (expected artifact version %s)" % (
            manifest_metadata["version"], expected_version))
        return False
    expected_application = {
        "application_id": "OPENSHOTQT",
        "executable": "openshot-qt.exe",
        "entry_point": "Windows.FullTrustApplication",
    }
    for key, expected_value in expected_application.items():
        if manifest_metadata[key] != expected_value:
            error("Unexpected MSIX %s: %s (expected %s)" % (
                key, manifest_metadata[key], expected_value))
            return False

    signtool_path = get_signtool_path()
    makeappx_path = os.getenv(
        "MAKEAPPX_PATH",
        os.path.join(os.path.dirname(signtool_path), "MakeAppx.exe"))
    if not os.path.exists(makeappx_path):
        error("MakeAppx.exe not found: %s" % makeappx_path)
        return False

    unpack_dir = "%s.unpack" % msix_path
    repacked_path = "%s.repacked.msix" % msix_path
    if os.path.isdir(unpack_dir):
        shutil.rmtree(unpack_dir)
    if os.path.exists(repacked_path):
        os.remove(repacked_path)

    unpack_command = " ".join([
        shell_quote(makeappx_path),
        "unpack",
        "/o",
        "/p", shell_quote(msix_path),
        "/d", shell_quote(unpack_dir),
    ])
    if run_command_with_exit_code(unpack_command, stream_output=False) != 0:
        error("Failed to unpack MSIX package: %s" % msix_path)
        return False

    manifest_path = os.path.join(unpack_dir, "AppxManifest.xml")
    if not os.path.exists(manifest_path):
        error("MSIX manifest not found after unpacking: %s" % manifest_path)
        return False

    if not replace_msix_visual_assets(unpack_dir):
        return False
    diagnostic_executable = "openshot-qt-cli.exe"
    if not os.path.isfile(os.path.join(unpack_dir, diagnostic_executable)):
        error("MSIX diagnostic executable not found: %s" % diagnostic_executable)
        return False
    output("Using existing frozen executable for MSIX diagnostics: %s" %
           diagnostic_executable)

    try:
        from defusedxml import minidom

        with open(manifest_path, "rb") as manifest_file:
            manifest_document = minidom.parse(manifest_file)

        identity = None
        for element in manifest_document.getElementsByTagName("*"):
            if element.localName == "Identity":
                identity = element
                break
        if identity is None:
            error("MSIX manifest Identity element not found: %s" % manifest_path)
            return False

        application = None
        visual_elements = None
        default_tile = None
        package_logo = None
        for element in manifest_document.getElementsByTagName("*"):
            if element.localName == "Application":
                application = element
            elif element.localName == "VisualElements":
                visual_elements = element
            elif element.localName == "DefaultTile":
                default_tile = element
            elif element.localName == "Logo" and element.parentNode.localName == "Properties":
                package_logo = element
        if not all((application, visual_elements, default_tile, package_logo)):
            error("MSIX manifest is missing required application visual metadata")
            return False

        application.setAttribute("Executable", diagnostic_executable)
        application.setAttribute("EntryPoint", "Windows.FullTrustApplication")
        visual_elements.setAttribute("BackgroundColor", "transparent")

        current_publisher = identity.getAttribute("Publisher")
        output("MSIX manifest publisher before signing: %s" % current_publisher)
        if current_publisher != signer_subject:
            output("Updating MSIX manifest publisher to match signing certificate subject")
            identity.setAttribute("Publisher", signer_subject)

        publisher_display_name_element = None
        for element in manifest_document.getElementsByTagName("*"):
            if element.localName == "PublisherDisplayName":
                publisher_display_name_element = element
                break
        if publisher_display_name_element is None:
            error("MSIX manifest PublisherDisplayName element not found: %s" % manifest_path)
            return False

        current_display_name = "".join(
            node.data
            for node in publisher_display_name_element.childNodes
            if node.nodeType == node.TEXT_NODE
        )
        output("MSIX manifest publisher display name before signing: %s" % current_display_name)
        if current_display_name != publisher_display_name:
            output("Updating MSIX manifest publisher display name to: %s" % publisher_display_name)
            for child in list(publisher_display_name_element.childNodes):
                publisher_display_name_element.removeChild(child)
            publisher_display_name_element.appendChild(
                manifest_document.createTextNode(publisher_display_name)
            )

        with open(manifest_path, "wb") as manifest_file:
            manifest_file.write(manifest_document.toxml(encoding="UTF-8"))
    except Exception as ex:
        error("Failed to update MSIX manifest publisher: %s" % ex)
        return False

    pack_command = " ".join([
        shell_quote(makeappx_path),
        "pack",
        "/o",
        "/h", "SHA256",
        "/d", shell_quote(unpack_dir),
        "/p", shell_quote(repacked_path),
    ])
    if run_command_with_exit_code(pack_command, stream_output=False) != 0 or not os.path.exists(repacked_path):
        error("Failed to repack MSIX package: %s" % msix_path)
        return False

    shutil.move(repacked_path, msix_path)
    shutil.rmtree(unpack_dir)
    output("Repacked MSIX package for signing: %s" % msix_path)
    final_metadata = get_msix_manifest_metadata(msix_path)
    if not final_metadata or final_metadata["executable"] != diagnostic_executable:
        error("Repacked MSIX does not use the diagnostic CLI executable")
        return False
    return True


def dump_appx_packaging_events():
    """Log recent AppxPackagingOM events for MSIX signing diagnostics."""
    command = " ".join([
        "powershell.exe",
        "-NoProfile",
        "-Command",
        shell_quote(
            "Get-WinEvent -LogName 'Microsoft-Windows-AppxPackaging/Operational' -MaxEvents 8 | "
            "Select-Object TimeCreated, Id, ProviderName, Message | Format-List"
        ),
    ])
    try:
        for line in run_command(command):
            output(line)
    except Exception as ex:
        error("Unable to read AppxPackagingOM event log: %s" % ex)


def sign_windows_installer(installer_path, debug=False):
    """Sign a Windows installer package with Azure Code Signing"""
    output("Signing Windows package: %s" % installer_path)

    azure_tenant = os.getenv("AZURE_TENANT_ID")
    azure_client = os.getenv("AZURE_CLIENT_ID")
    azure_secret = os.getenv("AZURE_CLIENT_SECRET")
    azure_account = os.getenv("AZURE_CODESIGN_ACCOUNT_NAME")
    azure_profile = os.getenv("AZURE_CODESIGN_CERT_PROFILE_NAME")

    required_vars = {
        "AZURE_TENANT_ID": azure_tenant,
        "AZURE_CLIENT_ID": azure_client,
        "AZURE_CLIENT_SECRET": azure_secret,
        "AZURE_CODESIGN_ACCOUNT_NAME": azure_account,
        "AZURE_CODESIGN_CERT_PROFILE_NAME": azure_profile,
    }
    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        error("Azure Code Signing configuration missing: %s" % ", ".join(missing))
        return False

    metadata = {
        "Endpoint": os.getenv("AZURE_CODESIGN_ENDPOINT", "https://eus.codesigning.azure.net/"),
        "CodeSigningAccountName": azure_account,
        "CertificateProfileName": azure_profile,
        "CorrelationId": os.getenv("AZURE_CODESIGN_CORRELATION_ID", "openshot-gitlab")
    }
    metadata_path = os.path.join(PATH, "build", "azure-codesign-metadata.json")
    with open(metadata_path, "w", encoding="UTF-8") as f:
        json.dump(metadata, f)

    signtool_path = get_signtool_path()
    dlib_path = get_azure_codesign_dlib_path()
    timestamp_url = os.getenv("AZURE_CODESIGN_TIMESTAMP_URL", "http://timestamp.acs.microsoft.com")

    sign_command = " ".join([
        shell_quote(signtool_path),
        "sign",
        "/debug" if debug else "",
        "/v",
        "/fd SHA256",
        '/tr "%s"' % timestamp_url,
        "/td SHA256",
        "/dlib", shell_quote(dlib_path),
        "/dmdf", shell_quote(metadata_path),
        shell_quote(installer_path),
    ])
    success = run_command_with_exit_code(sign_command, stream_output=False) == 0
    if success:
        output("Successfully signed Windows package: %s" % installer_path)
    if not success and installer_path.lower().endswith((".msix", ".appx", ".msixbundle", ".appxbundle")):
        dump_appx_packaging_events()
    return success


def sign_windows_msix_artifacts(signed_installer_path):
    """Sign any MSIX artifacts prepared for the x64 Windows signing job."""
    msix_dir = os.path.join(PATH, "build", "msix")
    if not os.path.isdir(msix_dir):
        return True

    msix_paths = [
        os.path.join(msix_dir, filename)
        for filename in os.listdir(msix_dir)
        if filename.lower().endswith(".msix")
    ]
    if not msix_paths:
        return True

    for msix_path in msix_paths:
        output("Found Windows MSIX artifact: %s" % msix_path)
        if not prepare_windows_msix_for_signing(msix_path, signed_installer_path):
            error("Windows MSIX preparation failed: %s" % msix_path)
            return False
        if not sign_windows_installer(msix_path, debug=True):
            error("Windows MSIX signing failed: %s" % msix_path)
            return False

    return True


def main():
    # Only run this code when directly executing this script. Parts of this file
    # are also used in the deploy.py script.
    try:
        windows_mode = "full"
        git_branch_name = "develop"

        # Validate command-line arguments
        if len(sys.argv) >= 2:
            zulip_token = sys.argv[1]
        if len(sys.argv) >= 6:
            git_branch_name = sys.argv[5]
        if len(sys.argv) >= 4:
            github_user = sys.argv[2]
            github_pass = sys.argv[3]

            # Login and get "GitHub" object
            gh = login(github_user, github_pass)
            repo = gh.repository("OpenShot", "openshot-qt")

        if len(sys.argv) >= 5:
            windows_32bit = False
            if sys.argv[4] == 'True':
                windows_32bit = True

        mac_password = ""
        if len(sys.argv) >= 7:
            mac_password = sys.argv[6]
        if len(sys.argv) >= 8:
            windows_mode = sys.argv[7]

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

            # Prefer the desktop's native file picker through XDG portals.
            install_linux_portal_theme(app_dir_path)

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
            only_64_bit = "x64"
            if windows_32bit:
                only_64_bit = ""

            if windows_mode != "sign-upload-only":
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

                # Add version metadata to frozen app launcher
                launcher_exe = os.path.join(exe_dir, "openshot-qt.exe")
                verpatch_success = True
                verpatch_command = " ".join([
                    'verpatch.exe',
                    '{}'.format(launcher_exe),
                    '/va',
                    '/high "{}"'.format(version),
                    '/pv "{}"'.format(version),
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

            # Build-only mode: stop after generating installer artifacts.
            if windows_mode == "build-only":
                needs_upload = False
            elif os.path.exists(app_build_path):
                sign_success = sign_windows_installer(app_build_path)
                if sign_success and not windows_32bit:
                    sign_success = sign_windows_msix_artifacts(app_build_path)
                if not sign_success:
                    needs_upload = False
                    os.remove(app_build_path)
            else:
                error("Windows signing step could not find installer: %s" % app_build_path)
                needs_upload = False

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
