param(
    [int] $WaitSeconds = 15,
    [string] $OutputRoot = ([Environment]::GetFolderPath("Desktop"))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDir = Join-Path $OutputRoot "OpenShot-MSIX-Diagnostics-$timestamp"
$archivePath = "$outputDir.zip"
New-Item -Path $outputDir -ItemType Directory -Force | Out-Null

function Write-Report {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Action
    )

    $path = Join-Path $outputDir "$Name.txt"
    try {
        & $Action 2>&1 | Out-String -Width 4096 | Set-Content -Path $path -Encoding UTF8
    } catch {
        "Collection failed: $($_ | Out-String)" | Set-Content -Path $path -Encoding UTF8
    }
}

$package = Get-AppxPackage -Name "OpenShotVideoEditor" -ErrorAction SilentlyContinue |
    Sort-Object Version -Descending |
    Select-Object -First 1
if (-not $package) {
    throw "OpenShotVideoEditor is not installed for the current user."
}

$startTime = (Get-Date).AddMinutes(-2)
$applicationId = "OPENSHOTQT"
$activationTarget = "shell:AppsFolder\$($package.PackageFamilyName)!$applicationId"

Write-Report -Name "00-system" -Action {
    Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture
    $PSVersionTable
}
Write-Report -Name "01-package" -Action {
    $package | Format-List *
    "Dependencies:"
    $package.Dependencies | Format-List Name, PackageFullName, Architecture, Version, Status
}

$manifest = Get-AppxPackageManifest -Package $package.PackageFullName
$manifest.Save((Join-Path $outputDir "AppxManifest.xml"))

$executables = @(
    "openshot-qt-cli.exe",
    "openshot-qt.exe"
)
Write-Report -Name "02-files-signatures-hashes" -Action {
    foreach ($name in $executables) {
        $path = Join-Path $package.InstallLocation $name
        "=== $path ==="
        Get-Item -LiteralPath $path | Format-List FullName, Length, CreationTimeUtc, LastWriteTimeUtc, VersionInfo
        Get-AuthenticodeSignature -LiteralPath $path | Format-List Status, StatusMessage, SignerCertificate
        Get-FileHash -LiteralPath $path -Algorithm SHA256 | Format-List
    }
}
Write-Report -Name "03-acls" -Action {
    & icacls.exe $package.InstallLocation
    foreach ($name in $executables) {
        & icacls.exe (Join-Path $package.InstallLocation $name)
    }
}
Write-Report -Name "04-environment-before-launch" -Action {
    Get-ChildItem Env: | Sort-Object Name | Format-Table -AutoSize
    "Activation target: $activationTarget"
    "Collection start: $startTime"
}

Start-Process -FilePath "explorer.exe" -ArgumentList $activationTarget
Start-Sleep -Seconds $WaitSeconds

Write-Report -Name "05-processes-after-launch" -Action {
    Get-Process | Where-Object {
        $_.ProcessName -match "OpenShot"
    } | Format-List *
}

$startupLog = Join-Path $env:LOCALAPPDATA "OpenShot Video Editor\msix-startup.log"
if (Test-Path -LiteralPath $startupLog -PathType Leaf) {
    Copy-Item -LiteralPath $startupLog -Destination (Join-Path $outputDir "msix-startup.log")
} else {
    "Diagnostic launcher did not create: $startupLog" |
        Set-Content -Path (Join-Path $outputDir "msix-startup-NOT-CREATED.txt") -Encoding UTF8
}

$eventLogs = @(
    "Application",
    "Microsoft-Windows-AppModel-Runtime/Admin",
    "Microsoft-Windows-TWinUI/Operational",
    "Microsoft-Windows-AppXDeploymentServer/Operational",
    "Microsoft-Windows-CodeIntegrity/Operational",
    "Microsoft-Windows-AppLocker/EXE and DLL"
)
foreach ($eventLog in $eventLogs) {
    $safeName = $eventLog -replace '[^A-Za-z0-9.-]', '_'
    Write-Report -Name "event-$safeName" -Action {
        Get-WinEvent -FilterHashtable @{LogName = $eventLog; StartTime = $startTime} -ErrorAction Stop |
            Where-Object {
                $_.Message -match "OpenShot|openshot-qt|$($package.PackageFamilyName)" -or
                $eventLog -eq "Application"
            } |
            Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message |
            Format-List
    }
}

Write-Report -Name "06-windows-error-reporting" -Action {
    Get-ChildItem "C:\ProgramData\Microsoft\Windows\WER\ReportArchive" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "OpenShot|openshot" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 20 FullName, CreationTimeUtc, LastWriteTimeUtc
    Get-ChildItem "$env:LOCALAPPDATA\CrashDumps" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "OpenShot|openshot" } |
        Select-Object FullName, Length, CreationTimeUtc, LastWriteTimeUtc
}

Compress-Archive -Path (Join-Path $outputDir "*") -DestinationPath $archivePath -Force
Write-Host "OpenShot MSIX diagnostics collected: $archivePath"
