# scripts/build-local-win.ps1 — Local Windows build and test script for Zenvi
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build-local-win.ps1
#
# Requires:
#   - Python 3.11 (64-bit), available on PATH
#   - Inno Setup 6 (installed at C:\Program Files (x86)\Inno Setup 6\, or via Chocolatey)
#   - cx_Freeze 7.0.0  (installed via: pip install cx_Freeze==7.0.0)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# ── Parse version from source ────────────────────────────────────────────────
$VER = python -c @"
import re, pathlib
text = pathlib.Path('src/classes/info.py').read_text()
m = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
print(m.group(1))
"@
if (-not $VER) { throw "Could not parse VERSION from src/classes/info.py" }

Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Zenvi Local Windows Build"
Write-Host " Version : $VER"
Write-Host " Python  : $(python --version)"
Write-Host "======================================`n"

# ── Step 1: Install Python dependencies ──────────────────────────────────────
Write-Host "[1/5] Installing Python dependencies..." -ForegroundColor Yellow
pip install --upgrade pip | Out-Null
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# ── Step 2: Freeze with cx_Freeze ────────────────────────────────────────────
Write-Host "[2/5] Running cx_Freeze..." -ForegroundColor Yellow
python freeze.py build --git-branch=production
if ($LASTEXITCODE -ne 0) { throw "cx_Freeze failed (exit $LASTEXITCODE)" }

# ── Step 3: Validate build output ────────────────────────────────────────────
Write-Host "[3/5] Validating build output..." -ForegroundColor Yellow
$BUILD_DIR = "build\exe.win-amd64-3.11"
if (-not (Test-Path $BUILD_DIR)) {
  # Try to find whatever cx_Freeze produced
  $found = Get-ChildItem -Path "build" -Directory -Filter "exe.*" |
           Select-Object -First 1
  if ($found) {
    Write-Warning "Expected '$BUILD_DIR' but found '$($found.FullName)'."
    Write-Warning "Update PY_EXE_DIR in windows-installer.iss if the directory name differs."
    $BUILD_DIR = $found.FullName
  } else {
    throw "No cx_Freeze output directory found under 'build\'. Freeze step may have failed silently."
  }
}

$fileCount = (Get-ChildItem -Path $BUILD_DIR -Recurse -File).Count
Write-Host "  Build directory: $BUILD_DIR ($fileCount files)"
if ($fileCount -lt 10) {
  Write-Warning "Very few files in build output — the freeze step may be incomplete."
}

# ── Step 4: Build Inno Setup installer ───────────────────────────────────────
Write-Host "[4/5] Building Windows installer with Inno Setup..." -ForegroundColor Yellow

$ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $ISCC)) {
  Write-Host "  Inno Setup not found. Attempting install via Chocolatey..."
  choco install innosetup --yes --no-progress
  if ($LASTEXITCODE -ne 0) { throw "Chocolatey install of innosetup failed" }
}
if (-not (Test-Path $ISCC)) {
  throw "ISCC.exe still not found at $ISCC after install attempt"
}

& $ISCC `
  /DVERSION="$VER" `
  /DPY_EXE_DIR="exe.win-amd64-3.11" `
  installer\windows-installer.iss

if ($LASTEXITCODE -ne 0) {
  throw "ISCC.exe failed with exit code $LASTEXITCODE"
}

# Locate the installer output (Inno Setup writes to installer\Output\ by default)
$exe = Get-ChildItem -Path "installer\Output\" -Filter "Zenvi*.exe" `
                     -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $exe) {
  $exe = Get-ChildItem -Path "." -Recurse -Filter "*.exe" |
         Where-Object { $_.Name -notmatch "is_setup" } |
         Select-Object -First 1
}
if (-not $exe) { throw "No installer .exe found after ISCC run" }

$DEST = "Zenvi-v${VER}-x86_64.exe"
Move-Item $exe.FullName $DEST -Force
$fileInfo = Get-Item $DEST

# ── Step 5: Verify ───────────────────────────────────────────────────────────
Write-Host "[5/5] Verifying installer..." -ForegroundColor Yellow
$sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
Write-Host "  File   : $DEST"
Write-Host "  Size   : $sizeMB MB"

if ($fileInfo.Length -lt 1MB) {
  Write-Warning "Installer is very small ($sizeMB MB) — the payload may be missing."
  Write-Warning "Check that PY_EXE_DIR matches the cx_Freeze output directory name."
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host " Build complete!"
Write-Host " Output: $(Resolve-Path $DEST)"
Write-Host "======================================`n"
Write-Host "Test instructions:"
Write-Host "  1. Double-click $DEST to run the installer"
Write-Host "  2. If Windows SmartScreen appears:"
Write-Host "       Click 'More info' → 'Run anyway'"
Write-Host "       (Expected when the installer has no code-signing cert)"
Write-Host "  3. Complete the wizard; Zenvi should appear in the Start menu"
Write-Host "  4. Launch Zenvi and verify it opens, creates a project, and plays back video"
Write-Host ""
