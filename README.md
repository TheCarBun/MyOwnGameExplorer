# MyOwnGameExplorer

A lightweight, portable Windows game launcher that scans a games folder,
builds a searchable library, and lets you launch your games from one place.

> I made this because these games were just unzipped files and not installed so windows wasn't returning anything when searched.
>
> - I also wanted to try the github releases and workflows. Glad I could do it both in the same project.

[![Latest release](https://img.shields.io/github/v/release/TheCarBun/MyOwnGameExplorer?display_name=tag)](https://github.com/TheCarBun/MyOwnGameExplorer/releases/latest)
[![Windows x64](https://img.shields.io/badge/platform-Windows%20x64-blue)](#download-and-run)
[![Release workflow](https://github.com/TheCarBun/MyOwnGameExplorer/actions/workflows/release.yml/badge.svg)](https://github.com/TheCarBun/MyOwnGameExplorer/actions/workflows/release.yml)
[![Downloads](https://img.shields.io/github/downloads/TheCarBun/MyOwnGameExplorer/total)](https://github.com/TheCarBun/MyOwnGameExplorer/releases)
[![Built with Python 3.14](https://img.shields.io/badge/build-Python%203.14-3776AB?logo=python&logoColor=white)](#build-from-source)

## Features

- Scans your selected games folder in the background so the window stays
  responsive.
- Shows a library of game cards with extracted game icons and folder sizes.
- Searches the library and sorts by name (ascending or descending) or folder
  size (largest or smallest).
- Opens a details panel with the game folder, executable, file sizes, and
  modified time.
- Launches a game or opens its folder from the card or details panel.
- Remembers your selected games folder, window size, sort order, and theme.
- Includes multiple themes and keeps settings, logs, and cache beside the app
  for portable use.

## Use the launcher

- **Choose games folder** selects the parent folder to scan. The default is
  `%USERPROFILE%\Games`.
- **Refresh library** rescans that folder. Scanning runs in the background.
- Type in the search box to filter the game cards. Press **Ctrl+F** to focus
  the search box and **Esc** to clear the search.
- Use **Sort by** to change the order of the library, and **Theme** to change
  the app's appearance.
- Select **Details** on a game card to see its paths and file information.
  From the details panel, choose **Play game** or **Open folder**.

## Download and run

1. Open [the latest GitHub Release](https://github.com/TheCarBun/MyOwnGameExplorer/releases/latest).
2. Download `MyOwnGameExplorer-<version>-windows-x64.zip`.
3. Extract the ZIP to a folder where you have write access. Keep the extracted
   folder intact; the executable needs its bundled files beside it.
4. Open `MyOwnGameExplorer.exe`.
5. On first run, the app scans `%USERPROFILE%\Games`. If your games are
   somewhere else, click **Choose games folder** and select the folder that
   contains them.

The portable ZIP contains the app; you do not need to install Python to run a
released build.

## How scanning works

The launcher treats each immediate subfolder of the selected games folder as a
game folder, then searches within it for `.exe` files. It ignores common
installer, uninstaller, redistributable, and crash-handler executables and
directories. When it finds multiple candidates, it chooses the largest
non-ignored executable. A folder named `Installers n Zips` is treated as a
container, so its game subfolders are scanned individually.

The launcher caches scan results to make later scans faster. Use **Refresh
library** to rescan after adding or changing games.

### Recommended Games folder structure

```text
Games/                   # Your games folder
├── Installers n Zips/   # Optional container for installers and ZIPs(ignored by the launcher)
├── Game1/
│   ├── game1.exe        # executable detected by the launcher
│   └── ...              # Other game files
├── Game2/
│   ├── game2.exe        # executable detected by the launcher
|   └──...               # Other game files
└── ...                  # Other games
```

## Portable data and configuration

The app writes its data into the extracted app folder:

```text
MyOwnGameExplorer/
├── MyOwnGameExplorer.exe
├── config/
│   ├── settings.json   # Created by the app; not included in the release
│   ├── text.json      # Default interface text
│   └── theme.json     # Available themes and selected theme
├── logs/
│   └── launcher.log
└── cache/
    ├── scan_cache.json
    └── icons/
```

Because data is stored beside the executable, the app folder must be writable.
To move the app and its preferences, close it and move the **entire extracted
folder**. The release intentionally does not contain a developer's
`settings.json`; the app creates one for you as needed.

You can change the theme from the theme selector in the app. Advanced users can
customize `config\theme.json` or `config\text.json`; make a backup before
editing these JSON files. The app uses defaults for missing or invalid values.

## Troubleshooting

- **No games appear:** Use **Choose games folder** to select the parent folder
  containing your installed game folders, then click **Refresh library**.
- **A game was not detected or the wrong executable was chosen:** The launcher
  selects the largest non-ignored `.exe` found in each game folder. Check that
  the game's main executable is present and not under a directory used for
  redistributables or installers.
- **Settings or logs cannot be saved:** Extract the ZIP to a normal folder you
  can write to, rather than a protected Windows folder or a read-only
  location.
- **The app closes or scanning fails:** Check `logs\launcher.log` beside the
  executable.

## Build from source

Portable releases are built for Windows x64 with PyInstaller in **one-folder**
mode. Build with Python 3.14 (the build script checks the Python version).

1. Install Git for Windows and 64-bit Python 3.14.
2. Open PowerShell in the cloned repository and create an isolated Python
   3.14 environment:

   ```powershell
   py -3.14 -m venv .venv-build
   .\.venv-build\Scripts\Activate.ps1
   python --version
   ```

   Confirm the active Python reports version 3.14. If `py -3.14` is not
   available, use the full path to your Python 3.14 executable to create the
   virtual environment.

3. Install the pinned build dependencies and create the ZIP:

   ```powershell
   python -m pip install -r requirements-build.txt
   .\build.ps1 -Version v0.1.0
   ```

The build produces:

- One-folder app: `dist\MyOwnGameExplorer\`
- Portable ZIP: `release\MyOwnGameExplorer-v0.1.0-windows-x64.zip`

The packaging spec includes the default text and theme files but excludes
`config\settings.json`. The build script verifies the ZIP contents.

### Test a local build

Extract the generated ZIP somewhere outside the repository and confirm the
release starts without relying on your development files:

```powershell
$zip = Resolve-Path .\release\MyOwnGameExplorer-v0.1.0-windows-x64.zip
$testDir = Join-Path $HOME "Desktop\MyOwnGameExplorer-portable-test"
Expand-Archive -LiteralPath $zip -DestinationPath $testDir -Force
Test-Path (Join-Path $testDir "MyOwnGameExplorer-v0.1.0\config\settings.json")
& (Join-Path $testDir "MyOwnGameExplorer-v0.1.0\MyOwnGameExplorer.exe")
```

`Test-Path` should print `False` before the first run. In the app, choose an
existing games folder and then close the app. Verify that `config\settings.json`
and `logs\launcher.log` appear beside the executable. Move the entire extracted
folder to another writable location and launch it again to check portability.

## Releases

Pushing a version tag such as `v0.1.1` starts the GitHub Actions workflow. It
builds the Windows x64 ZIP and attaches it to the matching GitHub Release. To
publish a new release, first push the commit containing the changes to the
default branch, then create and push a new tag:

```powershell
git tag v0.1.1
git push origin v0.1.1
```

Check the [Actions page](https://github.com/TheCarBun/MyOwnGameExplorer/actions)
for the build result and the [Releases page](https://github.com/TheCarBun/MyOwnGameExplorer/releases)
for the published ZIP.
