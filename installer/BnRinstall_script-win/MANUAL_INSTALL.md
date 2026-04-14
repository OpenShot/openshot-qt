# Manual Install and Package Guide

OpenShot BnR can bootstrap a lot automatically, but sometimes you want the manual route: locked-down machine, permissions trouble, Store-disabled images, or a release process where you want every dependency explained before you install it.

## What this file covers

This guide gives you:

- the external prerequisites the script depends on
- the typical MSYS2 UCRT64 packages the script resolves
- what each package does in plain English
- official project URLs
- official license URLs where practical
- attribution for each vendor or upstream project
- direct install or fetch examples using `winget`, `git`, and `curl`

## External prerequisites

| Component | What it does | Project URL | License URL | Attribution | Example command |
|---|---|---|---|---|---|
| WinGet / App Installer | Windows package manager used to bootstrap or recover missing tools on supported Windows installs. | https://learn.microsoft.com/en-us/windows/package-manager/winget/ | https://github.com/microsoft/winget-cli/blob/master/LICENSE | Microsoft / Microsoft Learn | `winget --info` |
| Git for Windows | Native Git client on Windows so the script can clone and update repositories. | https://git-scm.com/install/windows | https://github.com/git-for-windows/git/blob/main/COPYING | Git for Windows project | `winget install --id Git.Git -e` |
| MSYS2 | Windows-native build environment with Bash, pacman, GCC, Make, and the UCRT64 package repo. | https://www.msys2.org/docs/installer/ | https://github.com/msys2/MSYS2-packages/blob/master/COPYING | MSYS2 project | `winget install --id MSYS2.MSYS2 -e` |
| Python for Windows | Runs the top-level script and supports helper tooling outside MSYS2 when needed. | https://www.python.org/downloads/windows/ | https://docs.python.org/3/license.html | Python Software Foundation | `winget install --id Python.Python.3.14 -e` |
| OpenShot docs | Upstream architecture, build notes, and user/developer reference. | https://www.openshot.org/static/files/user-guide/developers.html | https://github.com/OpenShot/openshot-qt/blob/develop/LICENSE | OpenShot project | open in browser |

## Upstream repositories

| Repository | Role | Repository URL | License URL | Attribution | Clone command |
|---|---|---|---|---|---|
| OpenShot BnR | This project: bootstrap, build, run, and distro-prep wrapper. | https://github.com/tibberous/BnRinstall_script-win | https://opensource.org/license/mit | Trenton Tompkins • community helper around OpenShot | `git clone https://github.com/tibberous/BnRinstall_script-win` |
| libopenshot-audio | C++ audio layer used by OpenShot. | https://github.com/OpenShot/libopenshot-audio | https://github.com/OpenShot/libopenshot-audio/blob/develop/LICENSE | OpenShot project | `git clone https://github.com/OpenShot/libopenshot-audio.git` |
| libopenshot | C++ video/timeline/effects core and Python bindings. | https://github.com/OpenShot/libopenshot | https://github.com/OpenShot/libopenshot/blob/develop/LICENSE | OpenShot project | `git clone https://github.com/OpenShot/libopenshot.git` |
| openshot-qt | Python + PyQt desktop application. | https://github.com/OpenShot/openshot-qt | https://github.com/OpenShot/openshot-qt/blob/develop/LICENSE | OpenShot project | `git clone https://github.com/OpenShot/openshot-qt.git` |

## Direct fetch examples

### Get this project without Git

```bash
curl -L -o OpenShot_BnR.zip https://github.com/tibberous/BnRinstall_script-win/archive/refs/heads/main.zip
```

### Clone the full source tree

```bash
git clone https://github.com/tibberous/BnRinstall_script-win
git clone https://github.com/OpenShot/libopenshot-audio.git
git clone https://github.com/OpenShot/libopenshot.git
git clone https://github.com/OpenShot/openshot-qt.git
```

### Install external prerequisites with WinGet

```bash
winget install --id Git.Git -e
winget install --id MSYS2.MSYS2 -e
winget install --id Python.Python.3.14 -e
```

## Typical MSYS2 UCRT64 packages the script resolves

These are the common capabilities the script scores against the live UCRT64 repo. Exact package choices can drift over time, but these are the usual targets.

| Capability | Typical package | What it does | Package URL | Project / package license | Attribution |
|---|---|---|---|---|---|
| GCC / G++ | `mingw-w64-ucrt-x86_64-gcc` | Compiles the native C and C++ parts of the OpenShot stack. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-gcc | https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html | MSYS2 package index / GCC project |
| GNU Make | `mingw-w64-ucrt-x86_64-make` | Runs Makefile-based builds. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-make | https://git.savannah.gnu.org/cgit/make.git/tree/COPYING | MSYS2 package index / GNU Make |
| CMake | `mingw-w64-ucrt-x86_64-cmake` | Generates and drives the build configuration. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-cmake | https://cmake.org/licensing/ | MSYS2 package index / Kitware |
| Ninja | `mingw-w64-ucrt-x86_64-ninja` | Optional fast build runner. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-ninja | https://github.com/ninja-build/ninja/blob/master/COPYING | MSYS2 package index / Ninja project |
| FFmpeg | `mingw-w64-ucrt-x86_64-ffmpeg` | Media libraries and tools for decode, encode, and processing. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-ffmpeg | https://ffmpeg.org/legal.html | MSYS2 package index / FFmpeg project |
| SWIG | `mingw-w64-ucrt-x86_64-swig` | Generates glue code for Python bindings. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-swig | https://github.com/swig/swig/blob/master/LICENSE | MSYS2 package index / SWIG project |
| Doxygen | `mingw-w64-ucrt-x86_64-doxygen` | Optional API docs generator. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-doxygen | https://github.com/doxygen/doxygen/blob/master/LICENSE | MSYS2 package index / Doxygen project |
| ZeroMQ | `mingw-w64-ucrt-x86_64-zeromq` | Messaging layer used by parts of the OpenShot stack. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-zeromq | https://github.com/zeromq/libzmq/blob/master/COPYING.LESSER | MSYS2 package index / ZeroMQ project |
| Python | `mingw-w64-ucrt-x86_64-python` | Python runtime inside UCRT64. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-python?repo=ucrt64 | https://docs.python.org/3/license.html | MSYS2 package index / Python Software Foundation |
| pip | `mingw-w64-ucrt-x86_64-python-pip` | Python package installer for helper venvs and optional tools. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-python-pip | https://github.com/pypa/pip/blob/main/LICENSE.txt | MSYS2 package index / PyPA |
| PyQt5 | `mingw-w64-ucrt-x86_64-python-pyqt5` | Qt5 bindings for Python; this is the UI layer that OpenShot-Qt needs. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-python-pyqt5 | https://www.riverbankcomputing.com/commercial/license-faq | MSYS2 package index / Riverbank |
| pyzmq | `mingw-w64-ucrt-x86_64-python-pyzmq` | Python bindings for ZeroMQ. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-python-pyzmq | https://github.com/zeromq/pyzmq/blob/main/LICENSE.md | MSYS2 package index / pyzmq project |
| cx_Freeze | `mingw-w64-ucrt-x86_64-python-cx-freeze` | Optional packaging helper for standalone builds. | https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-python-cx-freeze | https://github.com/marcelotduarte/cx_Freeze/blob/main/LICENSE.md | MSYS2 package index / cx_Freeze project |
| Rust | `mingw-w64-ucrt-x86_64-rust` | Optional toolchain some packages may want. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-rust | https://www.rust-lang.org/policies/licenses | MSYS2 package index / Rust project |
| Catch | `mingw-w64-ucrt-x86_64-catch` | Optional C++ unit test framework. | https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-catch | https://github.com/catchorg/Catch2/blob/devel/LICENSE.txt | MSYS2 package index / Catch2 project |

## Manual MSYS2 package install example

```bash
pacman -Sy --noconfirm
pacman -Syu --noconfirm --needed
pacman -Su --noconfirm --needed
pacman -S --needed --noconfirm   mingw-w64-ucrt-x86_64-gcc   mingw-w64-ucrt-x86_64-make   mingw-w64-ucrt-x86_64-cmake   mingw-w64-ucrt-x86_64-ninja   mingw-w64-ucrt-x86_64-ffmpeg   mingw-w64-ucrt-x86_64-swig   mingw-w64-ucrt-x86_64-doxygen   mingw-w64-ucrt-x86_64-zeromq   mingw-w64-ucrt-x86_64-python   mingw-w64-ucrt-x86_64-python-pip   mingw-w64-ucrt-x86_64-python-pyqt5   mingw-w64-ucrt-x86_64-python-pyzmq   mingw-w64-ucrt-x86_64-python-cx-freeze   mingw-w64-ucrt-x86_64-rust   mingw-w64-ucrt-x86_64-catch
```

## When manual install is the better move

- `winget` is missing or blocked by policy
- Store / App Installer is disabled
- the machine is locked down and you need to inspect each dependency
- you want deterministic prep before the main script runs
- you are building a release machine and want clean notes for every package

## Attribution summary

These package and project links point at the official vendor or upstream project pages used by this project. Check those pages for the latest releases, hashes, installer notes, or upstream licensing changes.
