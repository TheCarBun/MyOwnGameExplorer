# MyOwnGameExplorer

## Build a portable Windows ZIP

The Windows release is a PyInstaller **one-folder** build. Extract the ZIP and
run `MyOwnGameExplorer.exe`; keep the extracted folder together. The app stores
`config\settings.json`, logs, and cache beside the executable, so copy or move
the whole folder to move the app and its settings. The release includes the
default UI text and themes, but never includes the developer's
`config\settings.json`. The executable icon is generated from the selected
theme in `config\theme.json` during the build.

### Build locally

1. Make sure Git for Windows is installed.
2. From the repository root, create and activate a build environment using
   this checkout's existing Python 3.14:

   ```powershell
   .\.venv\Scripts\python.exe -m venv .venv-build
   .\.venv-build\Scripts\Activate.ps1
   ```

3. Install the pinned build dependencies and create a ZIP (replace the example
   version with the version you want to test). Confirm Python is 3.14 before
   building:

   ```powershell
   python --version
   python -m pip install -r requirements-build.txt
   .\build.ps1 -Version v0.1.0
   ```

   `python --version` should report Python 3.14. The build script rejects other
   versions. It recreates the
   one-folder output at `dist\MyOwnGameExplorer` and writes the ZIP to
   `release\MyOwnGameExplorer-v0.1.0-windows-x64.zip`.

### Test the ZIP locally

1. In PowerShell, extract the ZIP into a new writable folder outside the
   repository (for example, your Desktop):

   ```powershell
   $zip = Resolve-Path .\release\MyOwnGameExplorer-v0.1.0-windows-x64.zip
   $testDir = Join-Path $HOME "Desktop\MyOwnGameExplorer-portable-test"
   Expand-Archive -LiteralPath $zip -DestinationPath $testDir -Force
   ```

2. Confirm the archive did not include your settings, then run the extracted
   executable:

   ```powershell
   Test-Path (Join-Path $testDir "MyOwnGameExplorer-v0.1.0\config\settings.json")
   & (Join-Path $testDir "MyOwnGameExplorer-v0.1.0\MyOwnGameExplorer.exe")
   ```

   The first command must print `False`. The app opens using its default
   settings and the default games folder (`$HOME\Games`); choose a games folder
   in the app if that folder does not exist.

3. In the app, click **Choose games folder** and select an existing folder.
   This saves `config\settings.json`. Then close the app normally and check
   that the extracted folder contains that file and `logs\launcher.log`.
   `cache\` is created with the app; `cache\scan_cache.json` appears after a
   successful scan. Reopen the executable and verify your selected folder
   persists.
4. To verify portability, close the app, move the entire
   `MyOwnGameExplorer-v0.1.0` folder to another writable location, and launch
   the executable there. Confirm new settings/log/cache writes stay in that
   moved folder. Keep the whole folder together; the executable needs its
   bundled files alongside it.

### Publish the first GitHub Release

1. Commit and push the build files, workflow, and documentation to the default
   branch. The tag must point to a commit that contains
   `.github\workflows\release.yml`.

   From that branch, run:

   ```powershell
   git add .gitignore .github/workflows/release.yml MyOwnGameExplorer.spec build.ps1 requirements-build.txt README.md
   git commit -m "Add portable Windows ZIP release"
   git push origin HEAD
   ```

2. From the repository root, create and push the first version tag:

   ```powershell
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. Open the repository's **Actions** tab and wait for **Build Windows portable
   release** to finish successfully.
4. Open **Releases**. The workflow creates the `v0.1.0` release with generated
   notes and attaches
   `MyOwnGameExplorer-v0.1.0-windows-x64.zip`.

For later releases, repeat the tag and push commands with the next version
(for example, `v0.1.1`). A pushed `v*` tag triggers the Windows build and
publishes the ZIP automatically.
