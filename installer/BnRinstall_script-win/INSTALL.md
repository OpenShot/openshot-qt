# INSTALL.md

## Purpose

This guide is for running **OpenShot BnR 1.0.1** on Windows and using it to bootstrap, build, verify, and launch OpenShot from source.

This helper is meant to complement the OpenShot project's existing installer and packaging work. It is most useful when you are trying to get a Windows source-build environment working end to end on a stock or half-broken Windows machine and you want readable logs instead of guesswork.

## How this differs from the official installer

OpenShot already ships official installer and packaging tooling. That upstream tooling is for packaging and release work.

**OpenShot BnR is different:** it focuses on restoring prerequisites, cloning the repos, building native dependencies, verifying the bindings, and generating launch helpers so a source build actually runs on stock Windows.

## Upstream attribution

OpenShot project links:

- Website: https://www.openshot.org/
- Source repository: https://github.com/OpenShot/openshot-qt
- Developer docs: https://www.openshot.org/static/files/user-guide/developers.html

## Before you start

You should have:

- Windows 10 or later
- internet access for package resolution and repository pulls
- a Python 3 interpreter available through `py -3` or `python`
- permission to elevate when the script requests admin access

## Fast path

```bash
py -3 OpenShot_BnR_v1_0.py
```

The script will:
1. check Windows support and elevation
2. find or restore WinGet, Git, and MSYS2
3. refresh MSYS2 and resolve dependencies against the live UCRT64 package list
4. clone or update the OpenShot repositories
5. build `libopenshot-audio`
6. build `libopenshot`
7. verify Python bindings in installed and source-build modes
8. generate launcher and distribution helper files

## Information-only commands

```bash
py -3 OpenShot_BnR_v1_0.py --usage
py -3 OpenShot_BnR_v1_0.py --help
py -3 OpenShot_BnR_v1_0.py man
py -3 OpenShot_BnR_v1_0.py --about
py -3 OpenShot_BnR_v1_0.py --version
py -3 OpenShot_BnR_v1_0.py --docs
py -3 OpenShot_BnR_v1_0.py --install
py -3 OpenShot_BnR_v1_0.py --manual-install
py -3 OpenShot_BnR_v1_0.py --log-guide
py -3 OpenShot_BnR_v1_0.py --troubleshoot
py -3 OpenShot_BnR_v1_0.py --license
py -3 OpenShot_BnR_v1_0.py --debug
```

## What gets created

Common outputs include:

- `C:\OpenShotBuild\Launch-OpenShot-Qt.cmd`
- `C:\OpenShotBuild\Launch-OpenShot-Qt.py`
- portable/frozen build helper scripts
- `openshot-installer.log`
- `openshot-installer-state.json`
- `openshot-installer-relay.log`

## What success looks like

A good result looks like this:

- the prerequisite, dependency, repo, and build stages pass
- the bindings import successfully in installed or source-build mode
- launcher files are generated
- OpenShot reaches a real UI startup path
- the session log reads like a real launch, not a fake smoke test

## Troubleshooting basics

### `ModuleNotFoundError: No module named 'openshot'`
The runtime bootstrap path is wrong or incomplete. Check the generated launcher files and the runtime bootstrap section of the log.

### `winget` missing
The script tries to restore or guide the WinGet/App Installer path, but locked-down systems may still need manual setup. See `MANUAL_INSTALL.md`.

### MSYS2 packages fail or drift
The helper reads against live UCRT64 package data. If the machine is stale or partially broken, finish the MSYS2 update cycle manually first, then rerun.

## Notes for upstream review

This package intentionally keeps the OpenShot attribution visible because the point is to support the OpenShot workflow, not hijack it.


## OpenShot pull request fit

This helper is packaged to fit OpenShot's usual GitHub contribution flow: make changes in a branch based on `develop`, open a PR to `develop`, and explain clearly that this helper complements the existing packaging installer by focusing on stock-Windows source builds. If the work is still under review, a draft / WIP PR is appropriate.
