# Desktop Builds

Builds are host-native: create the Linux AppImage on Linux and the Windows executable on Windows. Install the project environment first with `uv sync`.

These builds contain no preinstalled learning library. Users import a pack
through Library or set `REPETORIUM_CONTENT_DIR`. Existing executables
are not updated by source edits; rebuild to include code changes.

The build script automatically selects the `build` dependency group when running `pyside6-deploy`. This provides `pip`, which the deploy tool uses to install Nuitka and its supporting packages. A plain `uv sync` does not install this build-only dependency; do not invoke `pyside6-deploy` with plain `uv run`. For direct deploy commands, use `uv run --group build pyside6-deploy ...`.

For each build, the script uses a temporary deployment spec based on PySide6's defaults and the existing `src/repetorium/pysidedeploy.spec`, if present. It sets the current interpreter, source/output paths, application name, and target mode, and rediscovers Qt modules and plugins for the current host. The project icon is selected by default (ICO on Windows, PNG on Linux); custom icons must exist (relative paths are resolved from `src/repetorium`). Other settings are retained, and the original spec is not modified. This prevents a saved Linux configuration or standalone mode from overriding a Windows onefile build.

## Linux AppImage

Install `appimagetool` and make it available on `PATH`, then run:

```bash
uv run python scripts/build.py --target linux
```

The output is `dist/Repetorium-x86_64.AppImage` (or the matching architecture name on AArch64). Build on an older supported Linux distribution when broad compatibility matters; an AppImage does not bundle the host's glibc.
Before deployment, the build script removes its previous `Repetorium.dist`
output so a rebuild cannot include stale deployment files recursively.

The AppImage launcher points Qt to the bundled platform plugins and QML imports.
Launch the `.AppImage` directly or through the installed desktop entry; do not
launch the inner binary from the deployment bundle.

To install a per-user desktop menu entry that launches the AppImage, run:

```bash
uv run python scripts/build.py --target linux --install-desktop-entry
```

This builds the AppImage and installs `repetorium.desktop` and its icon under
`$XDG_DATA_HOME` (or `~/.local/share` when unset). The desktop entry is not
installed system-wide.

## Windows MSIX for Microsoft Store

On Windows, install `uv`, the Visual Studio C++ Build Tools with `dumpbin` available on `PATH`, and the Windows 10/11 SDK (for `MakeAppx.exe`). In Partner Center, open **Product identity** and copy the package **Identity name**, **Publisher**, and **Publisher display name** exactly. Do not use the Store product ID or your personal name as the identity name: it must contain only letters, numbers, periods, and hyphens. The publisher and publisher display name are separate values.

```powershell
uv sync
uv run --group build python scripts/build.py --target windows
```

The build reads these settings from `.env` in the repository root:

```dotenv
REPETORIUM_STORE_IDENTITY_NAME=YourPartnerCenterIdentityName
REPETORIUM_STORE_PUBLISHER=CN=YourPartnerCenterPublisher
REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME=YourPublisherDisplayName
```

Copy `.env.example` to `.env` and replace the example values. The local `.env`
file is ignored by Git; do not commit it. The build reads simple `KEY=VALUE`
lines and does not overwrite environment variables already set in PowerShell.
You may also pass `--store-identity-name`, `--store-publisher`, and
`--store-publisher-display-name`; command-line arguments take precedence over
environment variables and `.env`. These values appear in package metadata and
are public, not secrets.

The build produces `dist\Repetorium.msix` for Store submission and keeps
`dist\Repetorium.exe` as a portable executable. It creates a package manifest
with an application entry point, Windows Desktop targeting, app logos, and the
`runFullTrust` capability required by this desktop app. The executable manifest
declares Per-Monitor V2 DPI awareness. A Windows build must be performed on
Windows; this script does not cross-compile.

To run the Windows App Certification Kit (included in the Windows SDK), open
an elevated PowerShell window and run:

```powershell
$kit = "${env:ProgramFiles(x86)}\Windows Kits\10\App Certification Kit\appcert.exe"
$report = "$env:TEMP\Repetorium-AppCert-Report.xml"
& $kit reset
& $kit test -appxpackagepath (Resolve-Path "dist\Repetorium.msix").Path -reportoutputpath $report
```

Review the generated report before submission. WACK is a local preflight, not a
guarantee of Store certification; some tests use static analysis and can flag
references in bundled runtimes that need investigation.

Upload the MSIX to Partner Center; the Store signs packages for Store
distribution. The `runFullTrust` restricted-capability warning is expected for
a desktop executable and requires approval in Partner Center. Keep the app's
Store identity name and publisher unchanged between submissions, and increase
the project version for each update. For local installation outside the Store,
sign the MSIX with a certificate trusted by the test machine.

Before building, the script removes stale `Repetorium.dist` and
`Repetorium.exe` outputs from the package directory. This prevents an earlier
Linux standalone bundle from being included as Windows data and ensures a
failed/no-output deploy cannot be mistaken for a successful fresh build.

The app sets a stable Windows taskbar identity (`Repetorium.Desktop`) before
creating its windows and explicitly assigns the multi-resolution project ICO to
the main window. This keeps its running taskbar icon separate from Python's icon
when launched from source, as well as branding the packaged app. After rebuilding,
close any older running copy and launch the new executable. If a pinned shortcut
still shows an older icon, unpin it and pin the newly running app again.

If deployment warns that `dumpbin` cannot be found, run the build from a Visual Studio Developer PowerShell or a developer command prompt with the C++ tools initialized. This warning is separate from a fatal `No module named pip` error, which the build dependency group addresses.
