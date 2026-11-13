# Troubleshooting

## Permission and elevation problems

### Symptom
- the script cannot install tools
- `winget` recovery fails
- files under `C:\OpenShotBuild` do not update
- launchers are created but builds do not complete

### What it usually means
You are not running with the permissions needed to install tools or write to the build location.

### Fixes
- let the script elevate when Windows prompts you
- start PowerShell or Command Prompt **as Administrator** and rerun the script
- if company policy blocks elevation, use the **manual install** path first, then rerun the build

## WinGet / App Installer problems

### Symptom
- `winget` is not found
- the script says WinGet is unavailable
- Store/App Installer is stale or disabled

### Fixes
- update or install App Installer using Microsoft’s official App Installer docs
- on Store-enabled machines, install/update **App Installer** from the Microsoft Store
- on locked-down machines, skip WinGet bootstrap and install Git + MSYS2 manually

## Git problems

### Symptom
- repo clone fails
- `git` not found

### Fixes
- install Git for Windows manually
- reopen your terminal after install
- confirm `git --version` works before rerunning the script

## MSYS2 problems

### Symptom
- `msys2_shell.cmd` missing
- `pacman` missing
- UCRT64 package operations fail

### Fixes
- install MSYS2 manually
- open the **UCRT64** shell, not a random MSYS shell
- run the update sequence manually before retrying

```bash
pacman -Sy --noconfirm
pacman -Syu --noconfirm --needed
pacman -Su --noconfirm --needed
```

## Manual install fallback

If the automatic path is fighting you, the shortest path is:

1. install Git for Windows
2. install MSYS2
3. install Python for Windows if needed
4. install the typical UCRT64 packages from `MANUAL_INSTALL.md`
5. rerun the script or build manually from there

## Runtime launch problems

### Symptom
- build is green but OpenShot does not open
- `ModuleNotFoundError: No module named 'openshot'`
- launcher exits quickly

### Fixes
- use the generated launcher, not an ad-hoc shell command first
- try both:
  - `cmd /c "C:\OpenShotBuild\Launch-OpenShot-Qt.cmd"`
  - `py -3 "C:\OpenShotBuild\Launch-OpenShot-Qt.py"`
- compare the failing log to the successful log walkthrough in `LOG_GUIDE.md`

## Package helper problems

### Symptom
- portable/frozen helper fails

### Fix
Do **not** package first. Get the normal source-build launch clean first. Packaging a broken runtime just gives you a shinier failure.

## What to collect before asking for help

- stage summary
- artifacts block
- `--debug` output
- `openshot-installer.log`
- the exact command you ran


See also: RELEASE_GUIDE.md for the public-release checklist and final QA pass.
