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

function Assert-TemplateInstallerPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TemplatePath,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedInstallerPath
    )

    $templateInstallerPath = Get-TemplateInstallerPath -TemplatePath $TemplatePath
    if (([System.IO.Path]::GetFullPath($templateInstallerPath)) -ne ([System.IO.Path]::GetFullPath($ExpectedInstallerPath))) {
        throw "Generated MSIX template points at '$templateInstallerPath', expected '$ExpectedInstallerPath'"
    }
}

function Set-TemplateAttribute {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory = $true)]
        [string] $TemplatePath,

        [Parameter(Mandatory = $true)]
        [string] $ElementName,

        [Parameter(Mandatory = $true)]
        [string] $AttributeName,

        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    [xml] $templateXml = Get-Content -Path $TemplatePath -Raw
    $elements = @($templateXml.SelectNodes("//*[local-name()='$ElementName']"))
    if ($elements.Count -ne 1) {
        throw "Expected one $ElementName element in MSIX template, found $($elements.Count)."
    }

    $attribute = $elements[0].Attributes[$AttributeName]
    if (-not $attribute) {
        throw "MSIX template $ElementName element has no $AttributeName attribute."
    }
    $attribute.Value = $Value

    if ($PSCmdlet.ShouldProcess($TemplatePath, "Set $ElementName.$AttributeName")) {
        $templateXml.Save($TemplatePath)
        return $true
    }
    return $false
}

function Get-MsixVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ArtifactRoot
    )

    $versionFile = Join-Path $ArtifactRoot "build\install-x64\share\openshot-qt.env"
    if (-not (Test-Path -Path $versionFile -PathType Leaf)) {
        throw "OpenShot version metadata not found: $versionFile"
    }

    $versionLines = @(Get-Content -Path $versionFile | Where-Object { $_ -match '^VERSION:' })
    if ($versionLines.Count -ne 1) {
        throw "Expected one VERSION entry in $versionFile, found $($versionLines.Count)."
    }
    $version = ($versionLines[0] -split ':', 2)[1].Trim()
    if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:\.([0-9]+))?(?:[-+].*)?$') {
        throw "Unsupported OpenShot version for MSIX: $version"
    }

    $revision = if ($Matches[4]) { $Matches[4] } else { "0" }
    return "$($Matches[1]).$($Matches[2]).$($Matches[3]).$revision"
}

function Assert-SourceInstallerNotPackaged {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PackagePath,

        [Parameter(Mandatory = $true)]
        [string] $SourceInstallerPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $sourceInstallerName = [System.IO.Path]::GetFileName($SourceInstallerPath)
    $archive = [System.IO.Compression.ZipFile]::OpenRead($PackagePath)
    try {
        $capturedInstallers = @(
            foreach ($entry in $archive.Entries) {
                $normalizedName = $entry.FullName -replace '\\', '/'
                if ($normalizedName -like "VFS/AppVPackageDrive/*/$sourceInstallerName" -or
                    $normalizedName -like "VFS/AppVPackageDrive/*/OpenShot-*-x86_64.exe") {
                    $entry.FullName
                }
            }
        )
    }
    finally {
        $archive.Dispose()
    }

    if ($capturedInstallers.Count -gt 0) {
        throw "MSIX package includes the source installer, which should not be packaged: $($capturedInstallers -join ', ')"
    }
}

function Resolve-MsixPackagingTool {
    param(
        [Parameter(Mandatory = $true)]
        [object] $ToolPackage
    )

    $ToolDir = $ToolPackage.InstallLocation
    Write-Information "MSIX Packaging Tool package location: $ToolDir"

    $rootExe = Join-Path $ToolDir "MsixPackagingTool.exe"
    Write-Information "Checking package-root CLI path: $rootExe"
    if (Test-Path -Path $rootExe -PathType Leaf) {
        return $rootExe
    }

    $aliasCommand = @(Get-Command "MsixPackagingTool.exe" -ErrorAction SilentlyContinue)
    if ($aliasCommand.Count -gt 0) {
        $aliasPath = $aliasCommand[0].Path
        if (-not $aliasPath) {
            $aliasPath = $aliasCommand[0].Source
        }
        Write-Information "Using MSIX Packaging Tool app execution alias: $aliasPath"
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
                Write-Information "Checking manifest executable for ${appId}: $manifestExe"
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
        Write-Information "Using MSIX Packaging Tool executable found under package location: $($packageExeMatches[0].FullName)"
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

$installerMatches = @(Get-ChildItem -Path "build" -Filter "OpenShot-*-x86_64.exe" -File)
Assert-SingleArtifact -Artifacts $installerMatches -Description "build\OpenShot-*-x86_64.exe installer"
$installerPath = $installerMatches[0].FullName
Write-Information "Using Inno installer: $installerPath"

$toolPackage = Get-AppxPackage Microsoft.MSIXPackagingTool
if (-not $toolPackage) {
    throw "Microsoft.MSIXPackagingTool is not installed."
}

$ToolDir = $toolPackage.InstallLocation
$ToolExe = Resolve-MsixPackagingTool -ToolPackage $toolPackage
Write-Information "Using MSIX Packaging Tool: $ToolExe"

$templatePath = Join-Path $PSScriptRoot "openshot-msix-template.xml"
if (-not (Test-Path -Path $templatePath -PathType Leaf)) {
    throw "MSIX template not found: $templatePath"
}

$outputDir = Join-Path $PWD "build\msix"
New-Item -Path $outputDir -ItemType Directory -Force | Out-Null
Remove-Item -Path (Join-Path $outputDir "*.msix") -Force -ErrorAction SilentlyContinue
$toolLogPath = Join-Path $outputDir "msix-packaging-tool.log"
Remove-Item -Path $toolLogPath -Force -ErrorAction SilentlyContinue

$templateText = Get-Content -Path $templatePath -Raw
foreach ($arg in @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-")) {
    if ($templateText -notmatch [regex]::Escape($arg)) {
        throw "MSIX template is missing required Inno silent argument: $arg"
    }
}

$expectedInstallerPath = Get-TemplateInstallerPath -TemplatePath $templatePath
Write-Information "MSIX template expects installer: $expectedInstallerPath"

$sourceInstallerDir = Join-Path ([System.IO.Path]::GetTempPath()) "OpenShot-MSIX-InstallerSource"
Remove-Item -Path $sourceInstallerDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -Path $sourceInstallerDir -ItemType Directory -Force | Out-Null
$sourceInstallerPath = Join-Path $sourceInstallerDir ([System.IO.Path]::GetFileName($installerPath))
Copy-Item -Path $installerPath -Destination $sourceInstallerPath -Force
Write-Information "Staged MSIX source installer: $sourceInstallerPath"

$workingTemplatePath = Join-Path $outputDir "OpenShot_template.generated.xml"
$workingTemplateText = $templateText.Replace($expectedInstallerPath, $sourceInstallerPath)
if ($workingTemplateText -eq $templateText) {
    throw "Unable to update MSIX template installer path from '$expectedInstallerPath' to '$sourceInstallerPath'"
}
Set-Content -Path $workingTemplatePath -Value $workingTemplateText -Encoding UTF8
Assert-TemplateInstallerPath -TemplatePath $workingTemplatePath -ExpectedInstallerPath $sourceInstallerPath
$msixVersion = Get-MsixVersion -ArtifactRoot $PWD.Path
$generatedPackagePath = Join-Path $sourceInstallerDir "OpenShot.generated.msix"
$generatedTemplateOutputPath = Join-Path $outputDir "OpenShot_template.output.xml"
Set-TemplateAttribute -TemplatePath $workingTemplatePath -ElementName "PackageInformation" `
    -AttributeName "Version" -Value $msixVersion | Out-Null
Set-TemplateAttribute -TemplatePath $workingTemplatePath -ElementName "SaveLocation" `
    -AttributeName "PackagePath" -Value $generatedPackagePath | Out-Null
Set-TemplateAttribute -TemplatePath $workingTemplatePath -ElementName "SaveLocation" `
    -AttributeName "TemplatePath" -Value $generatedTemplateOutputPath | Out-Null
Write-Information "Generated MSIX template version: $msixVersion"
$msixPublisher = $env:WINDOWS_MSIX_PUBLISHER
if (-not $msixPublisher) {
    $msixPublisher = 'CN="OpenShot Studios, LLC", O="OpenShot Studios, LLC", STREET="2931 Ridge Rd #101", L=Rockwall, S=Texas, C=US, PostalCode=75032'
}
Set-TemplateAttribute -TemplatePath $workingTemplatePath -ElementName "PackageInformation" `
    -AttributeName "PublisherName" -Value $msixPublisher | Out-Null
Write-Information "Generated MSIX template publisher: $msixPublisher"
$publisherDisplayName = $env:WINDOWS_MSIX_PUBLISHER_DISPLAY_NAME
if (-not $publisherDisplayName) {
    $publisherDisplayName = "OpenShot Studios"
}
Set-TemplateAttribute -TemplatePath $workingTemplatePath -ElementName "PackageInformation" `
    -AttributeName "PublisherDisplayName" -Value $publisherDisplayName | Out-Null
Write-Information "Generated MSIX template publisher display name: $publisherDisplayName"
Write-Information "Generated MSIX template: $workingTemplatePath"

Write-Information "Running MSIX Packaging Tool. Full output will be saved to: $toolLogPath"
& $ToolExe create-package --template $workingTemplatePath -v *> $toolLogPath
if ($LASTEXITCODE -ne 0) {
    if (Test-Path -Path $toolLogPath -PathType Leaf) {
        Write-Information "MSIX Packaging Tool failed. Last 120 log lines:"
        Get-Content -Path $toolLogPath -Tail 120
    }
    throw "MSIX Packaging Tool failed with exit code $LASTEXITCODE."
}
Write-Information "MSIX Packaging Tool completed successfully."

if (-not (Test-Path -Path $generatedPackagePath -PathType Leaf)) {
    throw "MSIX Packaging Tool did not create the expected package: $generatedPackagePath"
}
Assert-SourceInstallerNotPackaged -PackagePath $generatedPackagePath -SourceInstallerPath $sourceInstallerPath

$artifactName = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetFileName($installerPath), ".msix")
$artifactPath = Join-Path $outputDir $artifactName
Move-Item -Path $generatedPackagePath -Destination $artifactPath -Force
$publishedPackages = @(Get-ChildItem -Path $outputDir -Filter "*.msix" -File)
Assert-SingleArtifact -Artifacts $publishedPackages -Description "published build\msix\*.msix artifact"
Write-Information "Published MSIX artifact: $artifactPath"
