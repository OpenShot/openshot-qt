Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-TemplateInstallerPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TemplatePath
    )

    [xml] $templateXml = Get-Content -Path $TemplatePath -Raw
    $pathPattern = '^(?:[A-Za-z]:\\|\\\\).+\.exe$'
    $silentArgsPattern = '/VERYSILENT|/SUPPRESSMSGBOXES|/NORESTART|/SP-'
    $preferredNamePattern = 'installer|setup|source|path|file'

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($node in $templateXml.SelectNodes('//*')) {
        foreach ($attribute in $node.Attributes) {
            $value = $attribute.Value.Trim()
            $contextText = "$($node.InnerText) $($node.ParentNode.InnerText)"
            if ($value -match $pathPattern -and $contextText -match $silentArgsPattern) {
                $candidates.Add($value)
            }
        }
    }

    $uniqueCandidates = @($candidates | Select-Object -Unique)
    if ($uniqueCandidates.Count -eq 0) {
        foreach ($node in $templateXml.SelectNodes('//*')) {
            foreach ($attribute in $node.Attributes) {
                $value = $attribute.Value.Trim()
                if ($value -match $pathPattern -and
                    (($attribute.Name -match $preferredNamePattern) -or ($node.Name -match $preferredNamePattern))) {
                    $candidates.Add($value)
                }
            }

            if ($node.ChildNodes.Count -eq 1 -and $node.FirstChild.NodeType -eq [System.Xml.XmlNodeType]::Text) {
                $value = $node.InnerText.Trim()
                if ($value -match $pathPattern -and $node.Name -match $preferredNamePattern) {
                    $candidates.Add($value)
                }
            }
        }

        $uniqueCandidates = @($candidates | Select-Object -Unique)
    }

    if ($uniqueCandidates.Count -eq 0) {
        foreach ($node in $templateXml.SelectNodes('//*')) {
            foreach ($attribute in $node.Attributes) {
                $value = $attribute.Value.Trim()
                if ($value -match $pathPattern) {
                    $candidates.Add($value)
                }
            }

            if ($node.ChildNodes.Count -eq 1 -and $node.FirstChild.NodeType -eq [System.Xml.XmlNodeType]::Text) {
                $value = $node.InnerText.Trim()
                if ($value -match $pathPattern) {
                    $candidates.Add($value)
                }
            }
        }

        $uniqueCandidates = @($candidates | Select-Object -Unique)
    }

    if ($uniqueCandidates.Count -ne 1) {
        throw "Expected exactly one installer .exe path in MSIX template, found $($uniqueCandidates.Count): $($uniqueCandidates -join ', ')"
    }

    return $uniqueCandidates[0]
}

function Assert-SingleArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Artifacts,

        [Parameter(Mandatory = $true)]
        [string] $Description
    )

    if ($Artifacts.Count -ne 1) {
        throw "Expected exactly one $Description, found $($Artifacts.Count): $($Artifacts.FullName -join ', ')"
    }
}

function Resolve-MsixPackagingTool {
    param(
        [Parameter(Mandatory = $true)]
        [object] $ToolPackage
    )

    $ToolDir = $ToolPackage.InstallLocation
    Write-Host "MSIX Packaging Tool package location: $ToolDir"

    $rootExe = Join-Path $ToolDir "MsixPackagingTool.exe"
    Write-Host "Checking package-root CLI path: $rootExe"
    if (Test-Path -Path $rootExe -PathType Leaf) {
        return $rootExe
    }

    $aliasCommand = @(Get-Command "MsixPackagingTool.exe" -ErrorAction SilentlyContinue)
    if ($aliasCommand.Count -gt 0) {
        $aliasPath = $aliasCommand[0].Path
        if (-not $aliasPath) {
            $aliasPath = $aliasCommand[0].Source
        }
        Write-Host "Using MSIX Packaging Tool app execution alias: $aliasPath"
        return $aliasPath
    }

    $manifestPath = Join-Path $ToolDir "AppxManifest.xml"
    if (Test-Path -Path $manifestPath -PathType Leaf) {
        [xml] $manifestXml = Get-Content -Path $manifestPath -Raw
        $appNodes = $manifestXml.SelectNodes("//*[local-name()='Application']")
        foreach ($appNode in $appNodes) {
            $appId = $appNode.GetAttribute("Id")
            $executable = $appNode.GetAttribute("Executable")
            if ($appId -eq "Msix.App" -and $executable) {
                $manifestExe = Join-Path $ToolDir $executable
                Write-Host "Checking manifest executable for ${appId}: $manifestExe"
                if (Test-Path -Path $manifestExe -PathType Leaf) {
                    return $manifestExe
                }
            }
        }
    }

    $packageExeMatches = @(
        Get-ChildItem -Path $ToolDir -Filter "*.exe" -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Msix.*Packaging.*Tool.*\.exe$' -or $_.Name -eq "MsixPackagingTool.exe" }
    )

    if ($packageExeMatches.Count -eq 1) {
        Write-Host "Using MSIX Packaging Tool executable found under package location: $($packageExeMatches[0].FullName)"
        return $packageExeMatches[0].FullName
    }

    $allPackageExes = @(
        Get-ChildItem -Path $ToolDir -Filter "*.exe" -File -Recurse -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
    )
    throw "MSIX Packaging Tool CLI not found. Checked package-root path, app execution alias, manifest AppID Msix.App, and package executable search. Package executables found: $($allPackageExes -join ', ')"
}

if (-not (Test-Administrator)) {
    throw "MSIX packaging requires an elevated/admin Windows runner."
}

Set-Service wuauserv -StartupType Manual
Start-Service wuauserv

$installerMatches = @(Get-ChildItem -Path "build" -Filter "OpenShot-*-x86_64.exe" -File)
Assert-SingleArtifact -Artifacts $installerMatches -Description "build\OpenShot-*-x86_64.exe installer"
$installerPath = $installerMatches[0].FullName
Write-Host "Using Inno installer: $installerPath"

$toolPackage = Get-AppxPackage Microsoft.MSIXPackagingTool
if (-not $toolPackage) {
    throw "Microsoft.MSIXPackagingTool is not installed."
}

$ToolDir = $toolPackage.InstallLocation
$ToolExe = Resolve-MsixPackagingTool -ToolPackage $toolPackage
Write-Host "Using MSIX Packaging Tool: $ToolExe"

$templatePath = "C:\OpenShot-MSIX\OpenShotTemplate\OpenShot_template.xml"
if (-not (Test-Path -Path $templatePath -PathType Leaf)) {
    throw "MSIX template not found: $templatePath"
}

$templateText = Get-Content -Path $templatePath -Raw
foreach ($arg in @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-")) {
    if ($templateText -notmatch [regex]::Escape($arg)) {
        throw "MSIX template is missing required Inno silent argument: $arg"
    }
}

$expectedInstallerPath = Get-TemplateInstallerPath -TemplatePath $templatePath
Write-Host "MSIX template expects installer: $expectedInstallerPath"

if (([System.IO.Path]::GetFullPath($installerPath)) -ne ([System.IO.Path]::GetFullPath($expectedInstallerPath))) {
    $expectedInstallerDir = Split-Path -Path $expectedInstallerPath -Parent
    New-Item -Path $expectedInstallerDir -ItemType Directory -Force | Out-Null
    Copy-Item -Path $installerPath -Destination $expectedInstallerPath -Force
    Write-Host "Copied installer to template path: $expectedInstallerPath"
}

$outputDir = Join-Path $PWD "build\msix"
New-Item -Path $outputDir -ItemType Directory -Force | Out-Null
Remove-Item -Path (Join-Path $outputDir "*.msix") -Force -ErrorAction SilentlyContinue

$startTime = Get-Date
& $ToolExe create-package --template $templatePath -v
if ($LASTEXITCODE -ne 0) {
    throw "MSIX Packaging Tool failed with exit code $LASTEXITCODE."
}

$searchRoots = @(
    (Split-Path -Path $templatePath -Parent),
    "C:\OpenShot-MSIX",
    $PWD.Path
) | Select-Object -Unique

$generatedPackages = @(
    foreach ($root in $searchRoots) {
        if (Test-Path -Path $root) {
            Get-ChildItem -Path $root -Filter "*.msix" -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -ge $startTime.AddSeconds(-2) }
        }
    }
) | Sort-Object FullName -Unique | Sort-Object LastWriteTime -Descending

Assert-SingleArtifact -Artifacts $generatedPackages -Description "generated .msix package"

$generatedPackage = $generatedPackages[0]
$artifactPath = Join-Path $outputDir "OpenShot-x86_64.msix"
Copy-Item -Path $generatedPackage.FullName -Destination $artifactPath -Force
Write-Host "Published MSIX artifact: $artifactPath"
