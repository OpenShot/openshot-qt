"""
 @file
 @brief cx_Freeze script to build OpenShot package with dependencies (for Mac and Windows)
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

# Syntax to build redistributable package:  python3 freeze.py build
#
# Troubleshooting: If you encounter an error while attempting to freeze
# the Qt binding's uic/port_v2 folder, remove the __init__.py in that folder. And if
# you are manually compiling the Qt binding on Windows, remove the -strip line
# from the Makefile. On Mac, just delete the port_v2 folder. Also, you
# might need to remove the QtTest module from the active Qt binding's site-packages,
# if you get errors while freezing.
#
# Mac Syntax to Build App Bundle:
# 1) python3 freeze.py bdist_mac --qt-menu-nib="/usr/local/Cellar/qt5/5.4.2/plugins/platforms/" --iconfile=installer/openshot.icns --custom-info-plist=installer/Info.plist --bundle-name="OpenShot Video Editor"
# 2) change Contents/Info.plist to use launch-mac.sh as the Executable name
# 3) manually fix rsvg executable:
#    sudo dylibbundler -od -of -b -x ~/apps/rsvg/rsvg-convert -d ./rsvg-libs/ -p @executable_path/rsvg-libs/
# 4) Code sign and create the DMG (disk image)
#    a) cd ~/apps/openshot-qt-git/
#    b) bash installer/build-mac-dmg.sh
#
# Windows Syntax to Build MSI Installer
# NOTE: Python3.5 requires custom build of cx_Freeze (https://github.com/sekrause/cx_Freeze-wheels). Download, python setup.py build, python setup.py install
# 1) python3 freeze.py bdist_msi
# NOTE: Requires a tweak to cx_freeze: http://stackoverflow.com/questions/24195311/how-to-set-shortcut-working-directory-in-cx-freeze-msi-bundle
# 2) Sign MSI with private code signing key (optional)
#  NOTE: Install Windows 10 SDK first
#  signtool sign /v /f OSStudiosSPC.pfx "OpenShot Video Editor-2.0.0-win32.msi"

import inspect
import glob
import os
import sys
import fnmatch
import json
import subprocess
from shutil import copytree, rmtree, copy
from cx_Freeze import setup, Executable
import cx_Freeze
import shutil
from installer.version_parser import parse_version_info, parse_build_name

PATH = os.path.dirname(os.path.realpath(__file__))  # Primary openshot folder
sys.path.insert(0, os.path.join(PATH, "src"))
from qt_api import QLibraryInfo, QT_API

print (str(cx_Freeze))

QT_BINDING_PACKAGE = {
    "pyqt5": "PyQt{}".format(5),
    "pyqt6": "PyQt{}".format(6),
    "pyside6": "PySide{}".format(6),
}.get(QT_API, "PyQt{}".format(5))

# Set '${ARCHLIB}' envvar to override system library path
ARCHLIB = os.getenv('ARCHLIB', "/usr/lib/x86_64-linux-gnu/")
if not ARCHLIB.endswith('/'):
    ARCHLIB += '/'

# Packages to include
python_packages = ["os",
                   "sys",
                   QT_BINDING_PACKAGE,
                   "openshot",
                   "time",
                   "uuid",
                   "idna",
                   "certifi",
                   "sentry_sdk",
                   "shutil",
                   "threading",
                   "subprocess",
                   "re",
                   "math",
                   "xml",
                   "logging",
                   "urllib",
                   "requests",
                   "zmq",
                   "webbrowser",
                   "json",
                   ]

# Modules to include
python_modules = ["idna.idnadata",
                  "sentry_sdk.integrations.stdlib",
                  "sentry_sdk.integrations.excepthook",
                  "sentry_sdk.integrations.dedupe",
                  "sentry_sdk.integrations.atexit",
                  "sentry_sdk.integrations.modules",
                  "sentry_sdk.integrations.argv",
                  "sentry_sdk.integrations.logging",
                  "sentry_sdk.integrations.threading",
                  ]

# Look for optional --git-branch arg, and remove it
git_branch_name = "develop"
for arg in sys.argv:
    if arg.startswith("--git-branch"):
        sys.argv.remove(arg)
        git_branch_name = arg.split("=")[-1].strip()

# Make a copy of the src tree (temporary for naming reasons only)
openshot_copy_path = os.path.join(PATH, "openshot_qt")
if os.path.exists(os.path.join(PATH, "src")):
    print("Copying modules to openshot_qt directory: %s" % openshot_copy_path)
    # Only make a copy if the SRC directory is present (otherwise ignore this)
    copytree(os.path.join(PATH, "src"), openshot_copy_path)

    # Make a copy of the launch.py script (to name it more appropriately)
    copy(os.path.join(PATH, "src", "launch.py"), os.path.join(PATH, "openshot_qt", "launch-openshot"))

if os.path.exists(openshot_copy_path):
    # Append path to system path
    sys.path.append(openshot_copy_path)
    print("Loaded modules from openshot_qt directory: %s" % openshot_copy_path)

# Detect artifact folder (if any). Prefer the active MSYS2 architecture, while
# preserving the historical x64 -> x86 fallback when MSYSTEM is unset.
msystem_artifact = {
    "clangarm64": "install-arm64",
    "mingw64": "install-x64",
    "mingw32": "install-x86",
}.get(os.getenv("MSYSTEM", "").lower())
artifact_names = [msystem_artifact] if msystem_artifact else ["install-x64", "install-x86"]
artifact_path = next(
    (
        os.path.join(PATH, "build", artifact_name)
        for artifact_name in dict.fromkeys(artifact_names)
        if os.path.exists(os.path.join(PATH, "build", artifact_name))
    ),
    "",
)

# Append possible build server paths
if artifact_path:
    sys.path.insert(0, os.path.join(artifact_path, "lib"))
    sys.path.insert(0, os.path.join(artifact_path, "bin"))

print("Importing OpenShot freeze metadata modules", flush=True)
try:
    from classes import info
    print("Imported classes.info", flush=True)
    from classes.logger import log
    print("Imported classes.logger", flush=True)
except BaseException:
    import traceback
    traceback.print_exc()
    raise
log.info("Execution path: %s" % os.path.abspath(__file__))
log.info("Artifact path detected and added to sys.path: %s" % artifact_path)

# Find files matching patterns
def find_files(directory, patterns):
    """ Recursively find all files in a folder tree """
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if ".pyc" not in basename and "__pycache__" not in basename:
                for pattern in patterns:
                    if fnmatch.fnmatch(basename, pattern):
                        filename = os.path.join(root, basename)
                        yield filename


def find_windows_imports(binary_path):
    """Return DLL imports reported by objdump for a Windows binary."""
    binary_path = os.path.abspath(binary_path)
    if not os.path.isfile(binary_path):
        log.warning("Unable to inspect Windows DLL imports for missing file: %s", binary_path)
        return None
    if "\x00" in binary_path:
        log.warning("Unable to inspect Windows DLL imports for invalid path")
        return None

    log.info("Inspecting Windows DLL imports: %s", binary_path)
    try:
        output = subprocess.check_output(  # nosec B603,B607 - fixed tool, validated file path, no shell.
            ["objdump", "-p", "--", binary_path],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except (OSError, subprocess.CalledProcessError) as ex:
        log.warning("Unable to inspect Windows DLL imports for %s: %s", binary_path, ex)
        return None

    imports = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("DLL Name:"):
            imports.append(line.split(":", 1)[1].strip())

    log.info("Found %s imported DLLs in %s", len(imports), binary_path)
    for dll_name in imports:
        log.info("  imports: %s", dll_name)
    return imports


def find_windows_opencv_dlls(opencv_root=None, opencv_dll_dir=None):
    """Return OpenCV DLLs available in the configured Windows OpenCV install."""
    opencv_bin_paths = []
    if opencv_dll_dir:
        opencv_bin_paths.append(opencv_dll_dir)
    if opencv_root:
        opencv_bin_paths.extend([
            os.path.join(opencv_root, "bin"),
            os.path.join(opencv_root, "x64", "mingw", "bin"),
        ])

    opencv_dlls = []
    for opencv_bin_path in opencv_bin_paths:
        found_dlls = list(find_files(opencv_bin_path, ["*opencv*.dll"]))
        log.info(
            "Found %s Windows OpenCV DLLs in candidate path: %s",
            len(found_dlls), opencv_bin_path
        )
        opencv_dlls.extend(found_dlls)

    if not opencv_dlls and opencv_root:
        log.warning("No Windows OpenCV runtime DLLs found in known bin paths: %s", opencv_bin_paths)
        log.info("Searching Windows OpenCV prefix for runtime DLLs: %s", opencv_root)
        opencv_dlls = list(find_files(opencv_root, ["*opencv*.dll"]))

    dll_by_name = {}
    for dll_path in opencv_dlls:
        dll_name = os.path.basename(dll_path).lower()
        if dll_name in dll_by_name:
            log.info("Ignoring duplicate Windows OpenCV DLL candidate: %s", dll_path)
            continue
        dll_by_name[dll_name] = dll_path
        log.info("Available Windows OpenCV DLL: %s", dll_path)
    return dll_by_name


def find_required_windows_opencv_dlls(seed_binaries, opencv_dlls_by_name):
    """Walk the OpenCV DLL import closure needed by seed Windows binaries."""
    required_dlls = {}
    inspected_binaries = set()
    pending_binaries = list(seed_binaries)

    log.info("Resolving Windows OpenCV DLL dependency closure")
    for seed_binary in seed_binaries:
        log.info("  seed binary: %s", seed_binary)

    while pending_binaries:
        binary_path = pending_binaries.pop(0)
        normalized_binary_path = os.path.normcase(os.path.abspath(binary_path))
        if normalized_binary_path in inspected_binaries:
            continue
        inspected_binaries.add(normalized_binary_path)

        imported_dlls = find_windows_imports(binary_path)
        if imported_dlls is None:
            return None

        for imported_dll in imported_dlls:
            imported_name = imported_dll.lower()
            if "opencv" not in imported_name:
                continue

            resolved_path = opencv_dlls_by_name.get(imported_name)
            if not resolved_path:
                log.warning("Imported OpenCV DLL was not found in configured OpenCV paths: %s", imported_dll)
                continue

            if imported_name not in required_dlls:
                required_dlls[imported_name] = resolved_path
                pending_binaries.append(resolved_path)
                log.info("Required Windows OpenCV DLL: %s -> %s", imported_dll, resolved_path)

    return [required_dlls[name] for name in sorted(required_dlls)]


def should_package_source_file(filename):
    """Return True when a copied openshot_qt source file is needed at runtime."""
    rel_path = os.path.relpath(filename, start=openshot_copy_path)
    rel_parts = rel_path.split(os.sep)

    if rel_parts[0] != "language":
        return True

    basename = rel_parts[-1]

    # The compiled Qt resource module is the runtime source of OpenShot translations.
    if basename in {"__init__.py", "openshot_lang.py"}:
        return True

    # Keep packaged Qt translations for native Qt dialogs/widgets.
    if basename.endswith(".qm") and (basename.startswith("qt_") or basename.startswith("qtbase_")):
        return True

    # Everything else in src/language is build-time/test-time content or loose duplicate
    # translations that are already embedded into openshot_lang.py.
    return False

# GUI applications require a different base on Windows
iconFile = "openshot-qt"
base = None
src_files = []
external_so_files = []
build_options = {}
build_exe_options = {}
exe_name = info.NAME

# Copy QT translations to local folder (to be packaged)
qt_local_path = os.path.join(PATH, "openshot_qt", "language")
qt_system_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
log.info("Qt local translation files path: %s" % qt_local_path)
log.info("Qt system translation files path: %s" % qt_system_path)
if os.path.exists(qt_system_path):
    # Create local QT translation folder (if needed)
    if not os.path.exists(qt_local_path):
        os.mkdir(qt_local_path)
    # Loop through QT translation files and copy them
    for file in os.listdir(qt_system_path):
        # Copy QT translation files
        if (file.startswith("qt_") or file.startswith("qtbase_")) and file.endswith(".qm"):
            log.info("Qt system translation, copied: %s" % file)
            shutil.copyfile(os.path.join(qt_system_path, file), os.path.join(qt_local_path, file))

# Copy git log files into src/settings files (if found)
version_info = {}
if artifact_path:
    share_path = os.path.join(artifact_path, "share")
    log.info("Copy share path to settings: %s" % share_path)
    if os.path.exists(share_path):
        for git_log_filename in os.listdir(share_path):
            git_log_filepath = os.path.join(share_path, git_log_filename)
            if os.path.isfile(git_log_filepath):
                src_files.append((git_log_filepath, "settings/%s" % git_log_filename))
                if os.path.splitext(git_log_filepath)[1] == ".env":
                    # No extension, parse version info
                    version_info.update(parse_version_info(git_log_filepath))

# If version info found (create src/settings/version.json file)
if version_info:
    # Calculate build name from version info
    version_info["build_name"] = parse_build_name(version_info, git_branch_name)
    version_path = os.path.join(openshot_copy_path, "settings", "version.json")
    with open(version_path, "w") as f:
        f.write(json.dumps(version_info, indent=4))

if sys.platform == "win32":
    # Define alternate terminal-based executable
    extra_exe = {"base": None, "name": exe_name + "-cli.exe"}

    # Standard graphical Win32 launcher
    base = "Win32GUI"
    build_exe_options["include_msvcr"] = True
    exe_name += ".exe"

    # Append Windows ICON file
    iconFile += ".ico"

    # Append some additional files for Windows (this is a debug launcher)
    src_files.append((os.path.join(PATH, "installer", "launch-win.bat"), "launch-win.bat"))

    # Add additional package
    python_packages.extend([
        "idna",
        "OpenGL",
        "OpenGL_accelerate",
    ])

    # Manually add BABL extensions (used in ChromaKey effect) - these are loaded at runtime,
    # and thus cx_freeze is not able to detect them
    MSYSTEM = os.getenv('MSYSTEM', "MINGW64").lower()
    babl_ext_path = "c:/msys64/%s/lib/babl-0.1/" % MSYSTEM
    for filename in find_files(babl_ext_path, ["*.dll"]):
        src_files.append((filename, os.path.join("lib", "babl-ext", os.path.relpath(filename, start=babl_ext_path))))

    # Add the Qt image codec runtime DLLs to the app root, since Windows does not search
    # the packaged binding subdir when loading dependencies for imageformat plugins.
    mingw_bin_path = "c:/msys64/%s/bin" % MSYSTEM
    imageformat_runtime_dlls = [
        "libjpeg-8.dll",
        "libjasper-4.dll",
        "libtiff-5.dll",
        "libwebp-7.dll",
        "libwebpdemux-2.dll",
        "libwebpmux-3.dll",
        "liblzma-5.dll",
        "libdeflate.dll",
        "zlib1.dll",
    ]
    for dll_name in imageformat_runtime_dlls:
        dll_path = os.path.join(mingw_bin_path, dll_name)
        if os.path.exists(dll_path):
            src_files.append((dll_path, dll_name))
        else:
            log.warning("Missing optional Windows imageformat runtime DLL: %s", dll_path)

    # libopenshot's Python extension links directly to the OpenCV runtime DLLs.
    # Resolve the OpenCV dependency closure from the explicit CI/toolchain
    # OpenCV path so we don't package stale pacman DLLs or every contrib DLL.
    opencv_root = os.getenv("OPENCV_ROOT")
    opencv_dll_dir = os.getenv("OPENCV_DLL_DIR")
    if opencv_root or opencv_dll_dir:
        opencv_dlls_by_name = find_windows_opencv_dlls(opencv_root, opencv_dll_dir)
        seed_binaries = []
        seed_binaries.extend(glob.glob(os.path.join(PATH, "_openshot*.pyd")))
        if artifact_path:
            seed_binaries.extend(glob.glob(os.path.join(artifact_path, "python", "_openshot*.pyd")))
            seed_binaries.extend(glob.glob(os.path.join(artifact_path, "bin", "*openshot*.dll")))
        seed_binaries = sorted(set(path for path in seed_binaries if os.path.exists(path)))

        if opencv_dlls_by_name and seed_binaries:
            opencv_runtime_dlls = find_required_windows_opencv_dlls(seed_binaries, opencv_dlls_by_name)
            if opencv_runtime_dlls is None:
                log.warning("Falling back to packaging all discovered Windows OpenCV DLLs")
                opencv_runtime_dlls = list(opencv_dlls_by_name.values())
            elif not opencv_runtime_dlls:
                log.warning("No OpenCV imports were discovered from seed binaries; packaging all discovered Windows OpenCV DLLs")
                opencv_runtime_dlls = list(opencv_dlls_by_name.values())
        else:
            if not opencv_dlls_by_name:
                log.warning("No Windows OpenCV runtime DLLs found for OpenCV root: %s", opencv_root)
            if not seed_binaries:
                log.warning("No Windows OpenCV dependency seed binaries found")
            opencv_runtime_dlls = list(opencv_dlls_by_name.values())

        if opencv_runtime_dlls:
            for dll_path in sorted(set(opencv_runtime_dlls)):
                log.info("Adding Windows OpenCV runtime DLL: %s", dll_path)
                src_files.append((dll_path, os.path.basename(dll_path)))
        else:
            log.warning("No Windows OpenCV runtime DLLs found for OpenCV root: %s", opencv_root)
    else:
        log.warning("OPENCV_ROOT is not set; Windows OpenCV runtime DLLs will rely on cx_Freeze detection.")

    # Append all source files
    src_files.append((os.path.join(PATH, "installer", "qt.conf"), "qt.conf"))
    for filename in find_files("openshot_qt", ["*"]):
        if should_package_source_file(filename):
            src_files.append((filename, os.path.join(os.path.relpath(filename, start=openshot_copy_path))))

elif sys.platform == "linux":
    # Find libopenshot.so path (GitLab copies artifacts into local build/install folder)
    libopenshot_path = os.path.join(PATH, "build", "install-x64", "lib")
    if not os.path.exists(libopenshot_path):
        libopenshot_path = os.path.join(PATH, "build", "install-x86", "lib")
    if not os.path.exists(libopenshot_path):
        # Default to user install path
        libopenshot_path = "/usr/local/lib"

    # Find all related SO files
    for filename in find_files(libopenshot_path, ["*openshot*.so*"]):
        if '_' in filename or filename.count(".") == 2:
            external_so_files.append((filename, os.path.relpath(filename, start=libopenshot_path)))

    # Add libresvg (if found)
    resvg_path = "/usr/lib/libresvg.so"
    if os.path.exists(resvg_path):
        external_so_files.append((resvg_path, os.path.basename(resvg_path)))

    # Add Qt xcbglintegrations plugin
    xcbgl_path = ARCHLIB + "qt5/"
    for filename in find_files(os.path.join(xcbgl_path, "plugins", "xcbglintegrations"), ["*"]):
        external_so_files.append((filename, os.path.relpath(filename, start=xcbgl_path)))

    # Add libsoftokn3
    nss_path = ARCHLIB + "nss/"
    for filename in find_files(nss_path, ["*"]):
        external_so_files.append((filename, os.path.basename(filename)))

    # Keep the audio decoding stack self-contained inside the AppImage.
    sndfile_path = "/lib/x86_64-linux-gnu/libsndfile.so.1"
    if os.path.exists(sndfile_path):
        external_so_files.append((sndfile_path, "libsndfile.so.1"))

    # Manually add BABL extensions (used in ChromaKey effect) - these are loaded at runtime,
    # and thus cx_freeze is not able to detect them
    babl_ext_path = ARCHLIB + "babl-0.1/"
    for filename in find_files(babl_ext_path, ["*.so"]):
        src_files.append((filename, os.path.join("lib", "babl-ext", os.path.relpath(filename, start=babl_ext_path))))

    # Append Linux ICON file
    iconFile += ".svg"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

    # Shorten name (since RPM can't have spaces)
    info.PRODUCT_NAME = "openshot-qt"

    # Add custom launcher script for frozen linux version
    src_files.append((os.path.join(PATH, "installer", "launch-linux.sh"), "launch-linux.sh"))

    # Get a list of all openshot.so dependencies (scan these libraries for their dependencies)
    qt_mod_files = []
    from importlib import import_module
    for submod in ['Qt', 'QtSvg', 'QtWidgets', 'QtCore', 'QtGui', 'QtDBus']:
        mod_name = "{}.{}".format(QT_BINDING_PACKAGE, submod)
        mod = import_module(mod_name)
        qt_mod_files.append(inspect.getfile(mod))
    lib_list = qt_mod_files
    try:
        import _ssl
        lib_list.append(inspect.getfile(_ssl))
    except Exception as ex:
        log.warning("Skipping _ssl module: %s", ex)
    for lib_name in [
            os.path.join(libopenshot_path, "libopenshot.so"),
            "/usr/local/lib/libresvg.so",
            ARCHLIB + "qt5/plugins/platforms/libqxcb.so"
            ]:
        if os.path.exists(lib_name):
            lib_list.append(lib_name)

    system_libs_to_skip = {
        "libdl.so.2",
        "librt.so.1",
        "libpthread.so.0",
        "libc.so.6",
        "libstdc++.so.6",
        "libGL.so.1",
        "libxcb.so.1",
        "libX11.so.6",
        "libX11-xcb.so.1",
        "libasound.so.2",
        "libgcc_s.so.1",
        "libICE.so.6",
        "libp11-kit.so.0",
        "libSM.so.6",
        "libm.so.6",
        "libdrm.so.2",
        "libfreetype.so.6",
        "libfontconfig.so.1",
        "libharfbuzz.so.0",
    }

    # Driver/system libs detected inside the AppImage; keep them shared with the host OS.
    # PipeWire must also stay host-provided: it loads host modules/plugins, and bundling
    # libpipewire can mix incompatible AppImage and host PipeWire components at runtime.
    appimage_driver_libs = {
        "libGLdispatch.so.0",
        "libGLX.so.0",
        "libva-drm.so.2",
        "libva-x11.so.2",
        "libva.so.2",
        "libvdpau.so.1",
        "libsystemd.so.0",
        "libdbus-1.so.3",
        "libblkid.so.1",
        "libmount.so.1",
        "libuuid.so.1",
        "libresolv.so.2",
        "libXau.so.6",
        "libXdmcp.so.6",
        "libpipewire-0.3.so.0",
        "libspa-0.2.so",
    }
    system_libs_to_skip.update(appimage_driver_libs)

    include_override_libs = {
        "libgcrypt.so.11",
        "libQt5DBus.so.5",
        "libpng12.so.0",
        "libbz2.so.1.0",
        "libqxcb.so",
        "libxcb-xinerama.so.0",
        "libpcre.so.3",
        "libselinux.so.1",  # required for Arch/Manjaro
        "libssl.so.1.1",
        "libcrypto.so.1.1",
        "libssl.so.3",
        "libcrypto.so.3",
    }

    import subprocess
    for library in lib_list:
        p = subprocess.Popen(["ldd", library], stdout=subprocess.PIPE)
        out, err = p.communicate()
        depends = str(out).replace("\\t", "").replace("\\n", "\n").replace("\'", "").split("\n")

        # Loop through each line of output (which outputs dependencies - one per line)
        for line in depends:
            log.info("ldd raw line: %s" % line)
            lineparts = line.split("=>")
            libname = lineparts[0].strip()

            if len(lineparts) <= 1:
                continue

            libdetails = lineparts[1].strip()
            libdetailsparts = libdetails.split("(")

            if len(libdetailsparts) <= 1:
                continue

            # Determine if dependency is usr installed (or system installed)
            # Or if the dependency matches one of the following exceptions
            # And ignore paths that start with /lib
            libpath = libdetailsparts[0].strip()
            libpath_file = os.path.basename(libpath)
            log.info("libpath: %s, libpath_file: %s" % (libpath, libpath_file))

            include_override = libpath_file in include_override_libs and libpath_file not in system_libs_to_skip
            if ((libpath
                and os.path.exists(libpath)
                and "libnvidia-glcore.so" not in libpath
                and libpath_file not in system_libs_to_skip)
               ) or include_override:
                external_so_files.append((libpath, libpath_file))
            else:
                log.info("Skipping external library: %s" % libpath)

    # Append all source files
    src_files.append((os.path.join(PATH, "installer", "qt.conf"), "qt.conf"))
    for filename in find_files("openshot_qt", ["*"]):
        if should_package_source_file(filename):
            src_files.append((filename, os.path.join(os.path.relpath(filename, start=openshot_copy_path))))

elif sys.platform == "darwin":
    # Copy Mac specific files that cx_Freeze misses
   # Add libresvg (if found)
    resvg_path = "/usr/local/lib/librsvg-2.dylib"
    if os.path.exists(resvg_path):
        external_so_files.append((resvg_path, resvg_path.replace("/usr/local/lib/", "")))

    opencv_root = os.getenv("OPENCV_ROOT")
    if opencv_root:
        opencv_lib_path = os.getenv("OPENCV_FREEZE_LIB_PATH") or os.path.join(opencv_root, "lib")
        build_exe_options.setdefault("bin_path_includes", []).append(opencv_lib_path)
        opencv_runtime_libs = list(find_files(opencv_lib_path, ["*.dylib"]))
        if opencv_runtime_libs:
            for dylib_path in opencv_runtime_libs:
                log.info("Adding macOS OpenCV runtime library: %s", dylib_path)
                external_so_files.append((dylib_path, os.path.basename(dylib_path)))
        else:
            log.warning("No macOS OpenCV runtime libraries found in: %s", opencv_lib_path)
    else:
        log.warning("OPENCV_ROOT is not set; macOS OpenCV runtime libraries will rely on cx_Freeze detection.")

    # Copy openshot.py Python bindings
    src_files.append((os.path.join(PATH, "installer", "launch-mac"), "launch-mac"))

    # Append Mac ICON file
    iconFile += ".hqx"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

    # Manually add BABL extensions (used in ChromaKey effect) - these are loaded at runtime,
    # and thus cx_freeze is not able to detect them
    babl_ext_path = "/usr/local/lib/babl-0.1"
    for filename in find_files(babl_ext_path, ["*.dylib"]):
        src_files.append((filename, os.path.join("lib", "babl-ext", os.path.relpath(filename, start=babl_ext_path))))

    qt_plugins_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    if os.path.exists(qt_plugins_path):
        for filename in find_files(qt_plugins_path, ["*"]):
            relative_filepath = os.path.relpath(filename, start=qt_plugins_path)
            plugin_name = os.path.dirname(relative_filepath)
            if plugin_name in ["imageformats", "platforms"]:
                external_so_files.append((filename, relative_filepath))
    else:
        log.warning("Qt plugins path not found on macOS: %s", qt_plugins_path)

    # Append all source files
    src_files.append((os.path.join(PATH, "installer", "qt.conf"), "qt.conf"))
    for filename in find_files("openshot_qt", ["*"]):
        if should_package_source_file(filename):
            src_files.append((filename, os.path.join("lib", os.path.relpath(filename, start=openshot_copy_path))))

    # Exclude gif library which crashes on Mac
    build_exe_options["bin_excludes"] = ["/System/Library/Frameworks/ImageIO.framework/Versions/A/Resources/libGIF.dylib",
                                         "/usr/local/opt/giflib/lib/libgif.dylib",
                                         "/usr/local/opt/tesseract/lib/libtesseract.4.dylib",
                                         "/usr/local/opt/leptonica/lib/liblept.5.dylib"]

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options["packages"] = python_packages
build_exe_options["include_files"] = src_files + external_so_files
build_exe_options["includes"] = python_modules
build_exe_options["excludes"] = ["distutils",
                                 "numpy",
                                 "setuptools",
                                 "tkinter",
                                 "pydoc_data",
                                 "pycparser",
                                 "pkg_resources",
                                 "{}.QtWebChannel".format(QT_BINDING_PACKAGE),
                                 "{}.QtWebEngine".format(QT_BINDING_PACKAGE),
                                 "{}.QtWebEngineCore".format(QT_BINDING_PACKAGE),
                                 "{}.QtWebEngineWidgets".format(QT_BINDING_PACKAGE),
                                 "{}.QtWebSockets".format(QT_BINDING_PACKAGE),
                                 "{}.QtWebKit".format(QT_BINDING_PACKAGE),
                                 "{}.QtWebKitWidgets".format(QT_BINDING_PACKAGE)]
if sys.platform == "darwin":
    build_exe_options["excludes"].append("sentry_sdk.integrations.django")

# Set options
build_options["build_exe"] = build_exe_options

# Define launcher executable to create
exes = [Executable("openshot_qt/launch.py",
                   base=base,
                   icon=os.path.join(PATH, "xdg", iconFile),
                   shortcutName="%s" % info.PRODUCT_NAME,
                   shortcutDir="ProgramMenuFolder",
                   targetName=exe_name,
                   copyright=info.COPYRIGHT)]

try:
    # Include extra launcher configuration, if defined
    exes.append(Executable("openshot_qt/launch.py",
                base=extra_exe['base'],
                icon=os.path.join(PATH, "xdg", iconFile),
                targetName=extra_exe['name'],
                copyright=info.COPYRIGHT))
except NameError:
    pass

# Create distutils setup object
setup(name=info.PRODUCT_NAME,
      version=info.VERSION,
      description=info.DESCRIPTION,
      author=info.COMPANY_NAME,
      options=build_options,
      executables=exes)


# Remove temporary folder (if SRC folder present)
if os.path.exists(os.path.join(PATH, "src")):
    rmtree(openshot_copy_path, True)

# Fix a few things on the frozen folder(s)
build_path = os.path.join(PATH, "build")


def prune_frozen_root(root_path, patterns):
    """Remove files/directories matching glob patterns under a frozen output root."""
    for pattern in patterns:
        full_pattern = os.path.join(root_path, pattern)
        for remove_path in glob.glob(full_pattern):
            if os.path.isfile(remove_path):
                log.info("Removing unneeded file: %s" % remove_path)
                os.unlink(remove_path)
            elif os.path.isdir(remove_path):
                log.info("Removing unneeded folder: %s" % remove_path)
                rmtree(remove_path)


if sys.platform == "darwin":
    # Mac issues with frozen folder and *.app folder
    # We need to rewrite many dependency paths and library IDs
    from installer.fix_qt5_rpath import *
    for frozen_path in os.listdir(build_path):
            if frozen_path.startswith("exe"):
                fix_rpath(os.path.join(build_path, frozen_path))
            elif frozen_path.endswith(".app"):
                fix_rpath(os.path.join(build_path, frozen_path, "Contents", "MacOS"))
                print_min_versions(os.path.join(build_path, frozen_path, "Contents", "MacOS"))

elif sys.platform == "linux":
    # Linux issues with frozen folder
    # We need to remove some excess folders/files that are unneeded bloat
    for frozen_path in os.listdir(build_path):
            if frozen_path.startswith("exe"):
                prune_frozen_root(os.path.join(build_path, frozen_path), [
                    "lib/openshot_qt/",
                    "lib/*opencv*",
                    "lib/libopenshot*",
                    "translations/",
                    "locales/",
                ])

# We need to remove some excess folders/files that are unneeded bloat
# All 3 OSes
all_platform_prune_patterns = [
    "lib/babl-ext/libbabl-0.1-0.*",
    "lib/babl-ext/libgcc_s_seh-1.*",
    "lib/babl-ext/liblcms2-2.*",
    "lib/babl-ext/libwinpthread-1.*",
    "lib/babl-ext/msvcrt.*",
    "lib/PyQt5/QtWebChannel.*",
    "lib/PyQt5/QtWebChannel-*",
    "lib/PyQt5/QtWebEngine.*",
    "lib/PyQt5/QtWebEngine-*",
    "lib/PyQt5/QtWebEngineCore.*",
    "lib/PyQt5/QtWebEngineCore-*",
    "lib/PyQt5/QtWebEngineWidgets.*",
    "lib/PyQt5/QtWebEngineWidgets-*",
    "lib/PyQt5/QtWebKit.*",
    "lib/PyQt5/QtWebKit-*",
    "lib/PyQt5/QtWebKitWidgets.*",
    "lib/PyQt5/QtWebKitWidgets-*",
    "lib/PyQt5/QtWebSockets.*",
    "lib/PyQt5/QtWebSockets-*",
    "lib/PyQt5/bindings/QtWebChannel",
    "lib/PyQt5/bindings/QtWebEngine",
    "lib/PyQt5/bindings/QtWebEngineCore",
    "lib/PyQt5/bindings/QtWebEngineWidgets",
    "lib/PyQt5/bindings/QtWebKit",
    "lib/PyQt5/bindings/QtWebKitWidgets",
    "PyQt5.uic.widget-plugins/qtwebenginewidgets.py",
    "PyQt5.uic.widget-plugins/qtwebkit.py",
    "PyQt5.uic.widget-plugins/__pycache__/qtwebenginewidgets.*",
    "PyQt5.uic.widget-plugins/__pycache__/qtwebkit.*",
    "QtWebChannel",
    "QtWebEngine",
    "QtWebEngineCore",
    "QtWebEngineWidgets",
    "QtWebSockets",
    "Qt5WebChannel.dll",
    "Qt5WebEngine.dll",
    "Qt5WebEngineCore.dll",
    "Qt5WebEngineWidgets.dll",
    "Qt5WebKit.dll",
    "Qt5WebKitWidgets.dll",
    "language/OpenShot_*.qm",
    "lib/language/OpenShot_*.qm",
    "lib/openshot_qt/language/OpenShot_*.qm",
]

for frozen_path in os.listdir(build_path):
        if frozen_path.startswith("exe"):
            prune_frozen_root(os.path.join(build_path, frozen_path), all_platform_prune_patterns)
        elif frozen_path.endswith(".app"):
            prune_frozen_root(
                os.path.join(build_path, frozen_path, "Contents", "MacOS"),
                all_platform_prune_patterns,
            )
