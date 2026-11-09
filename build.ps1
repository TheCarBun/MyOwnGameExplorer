param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$distRoot = Join-Path $root "dist"
$workDir = Join-Path $root "build\pyinstaller"
$packageDir = Join-Path $distRoot "MyOwnGameExplorer"
$releaseDir = Join-Path $root "release"
$zipName = "MyOwnGameExplorer-$Version-windows-x64.zip"
$zipPath = Join-Path $releaseDir $zipName
$specPath = Join-Path $root "MyOwnGameExplorer.spec"

$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to run Python. Activate the Python 3.14 build environment first."
}
if ($pythonVersion.Trim() -ne "3.14") {
    throw "Builds require Python 3.14; found Python $($pythonVersion.Trim())."
}

$null = New-Item -ItemType Directory -Force -Path $distRoot, $workDir, $releaseDir
foreach ($path in @($packageDir, $workDir, $zipPath)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

Push-Location $root
try {
    & python -m PyInstaller --noconfirm --clean --distpath $distRoot --workpath $workDir $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$exePath = Join-Path $packageDir "MyOwnGameExplorer.exe"
$textPath = Join-Path $packageDir "config\text.json"
$themePath = Join-Path $packageDir "config\theme.json"
if (!(Test-Path -LiteralPath $exePath) -or
    !(Test-Path -LiteralPath $textPath) -or
    !(Test-Path -LiteralPath $themePath)) {
    throw "The one-folder build is missing its executable or bundled config files."
}
if (Test-Path -LiteralPath (Join-Path $packageDir "config\settings.json")) {
    throw "Refusing to package config\settings.json."
}

$null = New-Item -ItemType Directory -Force -Path `
    (Join-Path $packageDir "logs"), `
    (Join-Path $packageDir "cache")
$packageDir = (Get-Item -LiteralPath $packageDir).FullName

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open(
    $zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    $archiveRoot = "MyOwnGameExplorer-$Version"
    $null = $archive.CreateEntry("$archiveRoot/")
    foreach ($item in Get-ChildItem -LiteralPath $packageDir -Force -Recurse) {
        $relativePath = $item.FullName.Substring($packageDir.Length).TrimStart("\", "/")
        $entryName = "$archiveRoot/$($relativePath -replace '\\', '/')"
        if ($item.PSIsContainer) {
            $null = $archive.CreateEntry("$entryName/")
        }
        else {
            $null = [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, $item.FullName, $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal)
        }
    }
}
finally {
    $archive.Dispose()
}

$verificationArchive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entryNames = @($verificationArchive.Entries | ForEach-Object { $_.FullName })
    foreach ($requiredEntry in @(
        "MyOwnGameExplorer-$Version/MyOwnGameExplorer.exe",
        "MyOwnGameExplorer-$Version/config/text.json",
        "MyOwnGameExplorer-$Version/config/theme.json",
        "MyOwnGameExplorer-$Version/logs/",
        "MyOwnGameExplorer-$Version/cache/"
    )) {
        if ($entryNames -notcontains $requiredEntry) {
            throw "ZIP is missing required entry: $requiredEntry"
        }
    }
    if ($entryNames | Where-Object { $_ -match '(^|/)settings\.json$' }) {
        throw "ZIP unexpectedly contains config\settings.json."
    }
}
finally {
    $verificationArchive.Dispose()
}

Write-Host "Created $zipPath"
