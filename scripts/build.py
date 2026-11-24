from __future__ import annotations

import argparse
import configparser
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path, PureWindowsPath
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = ROOT / "src" / "repetorium" / "__main__.py"
BUILD_DIR = ENTRY_POINT.parent
DIST_DIR = ROOT / "dist"
APP_NAME = "Repetorium"
ICON_DIR = ROOT / "src" / "repetorium" / "qml" / "icons"
APPX_NAMESPACE = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP_NAMESPACE = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
RESCAP_NAMESPACE = "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
STORE_ENV_KEYS = {
    "REPETORIUM_STORE_IDENTITY_NAME",
    "REPETORIUM_STORE_PUBLISHER",
    "REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME",
}

ET.register_namespace("", APPX_NAMESPACE)
ET.register_namespace("uap", UAP_NAMESPACE)
ET.register_namespace("rescap", RESCAP_NAMESPACE)


def load_store_environment(env_file: Path = ROOT / ".env") -> None:
    if not env_file.is_file():
        return

    for line_number, line in enumerate(env_file.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise SystemExit(f"Invalid .env entry on line {line_number}: expected KEY=VALUE.")
        key, value = (part.strip() for part in stripped.split("=", 1))
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
            raise SystemExit(f"Invalid .env variable name on line {line_number}: {key!r}.")
        if key not in STORE_ENV_KEYS:
            raise SystemExit(f"Unsupported .env variable on line {line_number}: {key}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def run(*command: str, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def deploy(mode: Literal["onefile", "standalone"], *, dry_run: bool = False) -> None:
    import PySide6

    deploy_lib = Path(PySide6.__file__).parent / "scripts" / "deploy_lib"
    config = configparser.ConfigParser(interpolation=None)
    with (deploy_lib / "default.spec").open(encoding="utf-8") as source:
        config.read_file(source)
    original = BUILD_DIR / "pysidedeploy.spec"
    if original.is_file():
        with original.open(encoding="utf-8") as source:
            config.read_file(source)

    config["app"]["project_dir"] = str(BUILD_DIR)
    config["app"]["input_file"] = str(ENTRY_POINT)
    config["app"]["exec_directory"] = str(BUILD_DIR)
    config["app"]["title"] = APP_NAME
    config["python"]["python_path"] = sys.executable
    config["nuitka"]["mode"] = mode
    extra_args = shlex.split(config["nuitka"]["extra_args"])
    config["nuitka"]["extra_args"] = shlex.join(extra_args)
    # These are discovery results cached by pyside6-deploy, not portable across hosts.
    config["qt"]["modules"] = ""
    config["qt"]["plugins"] = ""

    icon = config["app"]["icon"].strip()
    icon_path = PureWindowsPath(icon)
    if not icon or (icon_path.parent.name == "deploy_lib" and icon_path.stem == "pyside_icon"):
        icon = str(ICON_DIR / ("repetorium.ico" if sys.platform == "win32" else "repetorium.png"))
    if icon:
        resolved_icon = Path(icon)
        if not resolved_icon.is_absolute():
            resolved_icon = BUILD_DIR / resolved_icon
        if not resolved_icon.is_file():
            raise SystemExit(f"Deployment icon was not found: {resolved_icon}")
        config["app"]["icon"] = str(resolved_icon)

    with tempfile.TemporaryDirectory(prefix="repetorium-deploy-") as temporary:
        project_file = Path(temporary) / "repetorium.pyproject"
        excluded_directories = {"__pycache__", "deployment", f"{APP_NAME}.dist"}
        project_files = sorted(
            str(path.resolve())
            for pattern in ("*.py", "*.qml")
            for path in BUILD_DIR.rglob(pattern)
            if excluded_directories.isdisjoint(path.relative_to(BUILD_DIR).parts)
        )
        project_file.write_text(
            json.dumps({"files": project_files}),
            encoding="utf-8",
        )
        config["app"]["project_file"] = str(project_file)
        config_file = Path(temporary) / "pysidedeploy.spec"
        with config_file.open("w", encoding="utf-8") as destination:
            config.write(destination)
        run(
            "uv",
            "run",
            "--group",
            "build",
            "pyside6-deploy",
            str(ENTRY_POINT),
            "--config-file",
            str(config_file),
            "--mode",
            mode,
            "--name",
            APP_NAME,
            "--force",
            *(("--dry-run",) if dry_run else ()),
        )


def find_makeappx() -> str:
    makeappx = shutil.which("makeappx.exe") or shutil.which("makeappx")
    if makeappx is not None:
        return makeappx

    windows_kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    sdk_bin = windows_kits / "Windows Kits" / "10" / "bin"
    candidates = sorted(sdk_bin.glob("*/x64/makeappx.exe"), reverse=True)
    if candidates:
        return str(candidates[0])
    raise SystemExit(
        "MakeAppx.exe was not found. Install the Windows 10/11 SDK or add its x64 bin directory to PATH."
    )


def find_manifest_tool() -> str:
    manifest_tool = shutil.which("mt.exe") or shutil.which("mt")
    if manifest_tool is not None:
        return manifest_tool

    windows_kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    sdk_bin = windows_kits / "Windows Kits" / "10" / "bin"
    candidates = sorted(sdk_bin.glob("*/x64/mt.exe"), reverse=True)
    if candidates:
        return str(candidates[0])
    raise SystemExit(
        "mt.exe was not found. Install the Windows 10/11 SDK or add its x64 bin directory to PATH."
    )


def enable_per_monitor_dpi_awareness(executable: Path, manifest_tool: str) -> None:
    application_namespace = "urn:schemas-microsoft-com:asm.v3"
    settings_2005_namespace = "http://schemas.microsoft.com/SMI/2005/WindowsSettings"
    settings_2016_namespace = "http://schemas.microsoft.com/SMI/2016/WindowsSettings"
    with tempfile.TemporaryDirectory(prefix="repetorium-manifest-") as temporary:
        manifest_path = Path(temporary) / "Repetorium.manifest"
        run(manifest_tool, f"-inputresource:{executable};#1", f"-out:{manifest_path}")
        manifest = ET.parse(manifest_path)
        root = manifest.getroot()
        application = root.find(f"{{{application_namespace}}}application")
        if application is None:
            application = ET.SubElement(root, f"{{{application_namespace}}}application")
        settings = application.find(f"{{{application_namespace}}}windowsSettings")
        if settings is None:
            settings = ET.SubElement(application, f"{{{application_namespace}}}windowsSettings")
        for namespace, name, value in (
            (settings_2005_namespace, "dpiAware", "true/pm"),
            (settings_2016_namespace, "dpiAwareness", "PerMonitorV2"),
        ):
            dpi_setting = settings.find(f"{{{namespace}}}{name}")
            if dpi_setting is None:
                dpi_setting = ET.SubElement(settings, f"{{{namespace}}}{name}")
            dpi_setting.text = value
        ET.indent(root)
        manifest.write(manifest_path, encoding="utf-8", xml_declaration=True)
        run(manifest_tool, "-manifest", str(manifest_path), f"-outputresource:{executable};#1")


def make_msix_manifest(
    identity_name: str,
    publisher: str,
    publisher_display_name: str,
) -> ET.Element:
    version = importlib.metadata.version("repetorium")
    version_parts = version.split(".")
    if len(version_parts) > 4 or any(not part.isdecimal() or int(part) > 65535 for part in version_parts):
        raise SystemExit(f"Project version is not valid for an MSIX package: {version}")
    version = ".".join((*version_parts, *("0" for _ in range(4 - len(version_parts)))))
    architecture = platform.machine().lower()
    architectures = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86": "x86",
    }
    package_architecture = architectures.get(architecture)
    if package_architecture is None:
        raise SystemExit(f"MSIX builds are not configured for {platform.machine()}.")

    package = ET.Element(f"{{{APPX_NAMESPACE}}}Package")
    ET.SubElement(
        package,
        f"{{{APPX_NAMESPACE}}}Identity",
        {
            "Name": identity_name,
            "Publisher": publisher,
            "Version": version,
            "ProcessorArchitecture": package_architecture,
        },
    )
    properties = ET.SubElement(package, f"{{{APPX_NAMESPACE}}}Properties")
    ET.SubElement(properties, f"{{{APPX_NAMESPACE}}}DisplayName").text = APP_NAME
    ET.SubElement(properties, f"{{{APPX_NAMESPACE}}}PublisherDisplayName").text = publisher_display_name
    ET.SubElement(properties, f"{{{APPX_NAMESPACE}}}Logo").text = "Assets\\StoreLogo.png"

    dependencies = ET.SubElement(package, f"{{{APPX_NAMESPACE}}}Dependencies")
    ET.SubElement(
        dependencies,
        f"{{{APPX_NAMESPACE}}}TargetDeviceFamily",
        {
            "Name": "Windows.Desktop",
            "MinVersion": "10.0.19041.0",
            "MaxVersionTested": "10.0.26100.0",
        },
    )
    resources = ET.SubElement(package, f"{{{APPX_NAMESPACE}}}Resources")
    ET.SubElement(resources, f"{{{APPX_NAMESPACE}}}Resource", {"Language": "en-us"})
    applications = ET.SubElement(package, f"{{{APPX_NAMESPACE}}}Applications")
    application = ET.SubElement(
        applications,
        f"{{{APPX_NAMESPACE}}}Application",
        {
            "Id": "Repetorium",
            "Executable": "Repetorium.exe",
            "EntryPoint": "Windows.FullTrustApplication",
        },
    )
    ET.SubElement(
        application,
        f"{{{UAP_NAMESPACE}}}VisualElements",
        {
            "DisplayName": APP_NAME,
            "Description": APP_NAME,
            "BackgroundColor": "transparent",
            "Square44x44Logo": "Assets\\Square44x44Logo.png",
            "Square150x150Logo": "Assets\\Square150x150Logo.png",
        },
    )
    capabilities = ET.SubElement(package, f"{{{APPX_NAMESPACE}}}Capabilities")
    ET.SubElement(capabilities, f"{{{RESCAP_NAMESPACE}}}Capability", {"Name": "runFullTrust"})
    return package


def write_msix_assets(assets_dir: Path) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    icon_path = ICON_DIR / "repetorium.svg"
    renderer = QSvgRenderer(str(icon_path))
    if not renderer.isValid():
        raise SystemExit(f"Could not load the MSIX icon: {icon_path}")
    assets_dir.mkdir(parents=True, exist_ok=True)
    for filename, size in (
        ("StoreLogo.png", 50),
        ("Square44x44Logo.png", 44),
        ("Square150x150Logo.png", 150),
    ):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        if not image.save(str(assets_dir / filename), "PNG"):
            raise SystemExit(f"Could not write the MSIX logo: {assets_dir / filename}")


def build_windows(
    identity_name: str | None = None,
    publisher: str | None = None,
    publisher_display_name: str | None = None,
) -> Path:
    if sys.platform != "win32":
        raise SystemExit("Windows executables must be built on Windows.")
    if not identity_name or not publisher or not publisher_display_name:
        raise SystemExit(
            "Store MSIX builds require the exact identity name, publisher, and publisher display name "
            "from Partner Center."
        )
    if re.fullmatch(r"[-.A-Za-z0-9]+", identity_name) is None:
        raise SystemExit(
            "Invalid Store identity name. Copy the package Identity name from Partner Center; "
            "it may contain only letters, numbers, periods, and hyphens (no spaces)."
        )
    makeappx = find_makeappx()
    manifest_tool = find_manifest_tool()

    prepare_windows_build()
    deploy("onefile")

    executable = BUILD_DIR / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise SystemExit(f"Expected deploy output was not found: {executable}")
    enable_per_monitor_dpi_awareness(executable, manifest_tool)
    DIST_DIR.mkdir(exist_ok=True)
    executable_destination = DIST_DIR / f"{APP_NAME}.exe"
    shutil.copy2(executable, executable_destination)
    destination = DIST_DIR / f"{APP_NAME}.msix"
    if destination.is_symlink():
        raise SystemExit(f"Refusing to overwrite a symlink at the MSIX output: {destination}")
    if destination.exists():
        destination.unlink()

    with tempfile.TemporaryDirectory(prefix="repetorium-msix-", dir=DIST_DIR) as temporary:
        package_dir = Path(temporary)
        shutil.copy2(executable_destination, package_dir / executable_destination.name)
        write_msix_assets(package_dir / "Assets")
        manifest = make_msix_manifest(identity_name, publisher, publisher_display_name)
        ET.indent(manifest)
        ET.ElementTree(manifest).write(
            package_dir / "AppxManifest.xml",
            encoding="utf-8",
            xml_declaration=True,
        )
        run(makeappx, "pack", "/d", str(package_dir), "/p", str(destination), "/o")
    if not destination.is_file():
        raise SystemExit(f"MakeAppx did not create the expected MSIX package: {destination}")
    return destination


def find_linux_bundle() -> tuple[Path, Path]:
    bundles = sorted(BUILD_DIR.glob(f"{APP_NAME}.dist"))
    if len(bundles) != 1:
        raise SystemExit(
            f"Expected Nuitka output {BUILD_DIR / f'{APP_NAME}.dist'}, found {len(bundles)} matches."
        )

    bundle = bundles[0]
    executable_names = (f"{APP_NAME}.bin", APP_NAME, "__main__.bin", "__main__")
    executable = next(
        (bundle / name for name in executable_names if (bundle / name).is_file()),
        None,
    )
    if executable is None:
        raise SystemExit(f"Could not find the application executable in {bundle}.")
    return bundle, executable


def remove_previous_standalone_bundle() -> None:
    bundle = BUILD_DIR / f"{APP_NAME}.dist"
    if bundle.is_symlink():
        raise SystemExit(f"Refusing to remove a symlink at the deployment output: {bundle}")
    if bundle.is_dir():
        shutil.rmtree(bundle)
    elif bundle.exists():
        bundle.unlink()


def prepare_windows_build() -> None:
    remove_previous_standalone_bundle()
    executable = BUILD_DIR / f"{APP_NAME}.exe"
    if executable.is_symlink():
        raise SystemExit(f"Refusing to remove a symlink at the deployment output: {executable}")
    if executable.is_dir():
        raise SystemExit(f"Expected a file at the deployment output, found a directory: {executable}")
    if executable.exists():
        executable.unlink()


def build_linux() -> Path:
    if not sys.platform.startswith("linux"):
        raise SystemExit("Linux AppImages must be built on Linux.")
    architecture = platform.machine()
    if architecture not in {"x86_64", "aarch64"}:
        raise SystemExit(f"AppImage builds are not configured for {architecture}.")
    appimagetool = shutil.which("appimagetool")
    if appimagetool is None:
        raise SystemExit("Install appimagetool and ensure it is available on PATH.")

    remove_previous_standalone_bundle()
    deploy("standalone")
    bundle, executable = find_linux_bundle()
    qt_plugins = bundle / "PySide6" / "qt-plugins"
    qml_imports = bundle / "PySide6" / "qml"
    if not (qt_plugins / "platforms").is_dir():
        raise SystemExit(f"Qt platform plugins were not found in the deployment bundle: {qt_plugins}")
    if not qml_imports.is_dir():
        raise SystemExit(f"Qt QML imports were not found in the deployment bundle: {qml_imports}")

    DIST_DIR.mkdir(exist_ok=True)
    destination = DIST_DIR / f"{APP_NAME}-{architecture}.AppImage"

    with tempfile.TemporaryDirectory(prefix="repetorium-appimage-") as temporary:
        app_dir = Path(temporary) / f"{APP_NAME}.AppDir"
        library_dir = app_dir / "usr" / "lib" / "repetorium"
        library_dir.parent.mkdir(parents=True)
        shutil.copytree(bundle, library_dir)

        relative_executable = executable.relative_to(bundle)
        (app_dir / "AppRun").write_text(
            "#!/bin/sh\n"
            'HERE="$(dirname "$(readlink -f "$0")")"\n'
            'export QT_PLUGIN_PATH="$HERE/usr/lib/repetorium/PySide6/qt-plugins"\n'
            'export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_PATH/platforms"\n'
            'export QML2_IMPORT_PATH="$HERE/usr/lib/repetorium/PySide6/qml"\n'
            f'exec "$HERE/usr/lib/repetorium/{relative_executable.as_posix()}" "$@"\n',
            encoding="utf-8",
        )
        (app_dir / "AppRun").chmod(0o755)
        icon_source = ICON_DIR / "repetorium.svg"
        icon_path = app_dir / f"{APP_NAME}.svg"
        shutil.copy2(icon_source, icon_path)
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer

        icon_image = QImage(256, 256, QImage.Format.Format_ARGB32)
        icon_image.fill(Qt.GlobalColor.transparent)
        icon_renderer = QSvgRenderer(str(icon_path))
        painter = QPainter(icon_image)
        icon_renderer.render(painter)
        painter.end()
        if not icon_renderer.isValid() or not icon_image.save(str(app_dir / ".DirIcon"), "PNG"):
            raise SystemExit("Could not create the AppImage icon from the bundled SVG.")
        (app_dir / f"{APP_NAME}.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            f"Icon={APP_NAME}\n"
            "Exec=AppRun\n"
            "Terminal=false\n"
            "Categories=Education;\n",
            encoding="utf-8",
        )
        run(
            appimagetool,
            str(app_dir),
            str(destination),
            env={**os.environ, "ARCH": architecture},
        )

    return destination


def install_linux_desktop_entry(artifact: Path) -> Path:
    if not artifact.is_file():
        raise SystemExit(f"Linux application bundle was not found: {artifact}")

    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    if not data_home.is_absolute():
        raise SystemExit("XDG_DATA_HOME must be an absolute path.")
    applications_dir = data_home / "applications"
    icons_dir = data_home / "icons" / "hicolor" / "scalable" / "apps"
    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    installed_icon = icons_dir / "repetorium.svg"
    shutil.copy2(ICON_DIR / "repetorium.svg", installed_icon)
    escaped_artifact = str(artifact.resolve())
    escaped_artifact = (
        escaped_artifact.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
    )
    desktop_entry = applications_dir / "repetorium.desktop"
    desktop_entry.write_text(
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f'Exec="{escaped_artifact}"\n'
        f"Icon={installed_icon}\n"
        "Terminal=false\n"
        "Categories=Education;\n",
        encoding="utf-8",
    )
    return desktop_entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Repetorium for the current host OS.")
    parser.add_argument(
        "--target",
        choices=("linux", "windows"),
        default="linux" if sys.platform.startswith("linux") else "windows",
        help="Target platform (must match the build host).",
    )
    parser.add_argument(
        "--install-desktop-entry",
        action="store_true",
        help="After a Linux build, add Repetorium to the current user's desktop menu.",
    )
    parser.add_argument(
        "--store-identity-name",
        help="Exact package identity name from Partner Center (required for Windows MSIX builds).",
    )
    parser.add_argument(
        "--store-publisher",
        help="Exact package publisher from Partner Center (required for Windows MSIX builds).",
    )
    parser.add_argument(
        "--store-publisher-display-name",
        help="Exact publisher display name from Partner Center (required for Windows MSIX builds).",
    )
    args = parser.parse_args()

    if args.install_desktop_entry and args.target != "linux":
        parser.error("--install-desktop-entry can only be used with --target linux.")
    if args.target == "linux" and any(
        value is not None
        for value in (args.store_identity_name, args.store_publisher, args.store_publisher_display_name)
    ):
        parser.error("Store identity options can only be used with --target windows.")

    if args.target == "windows":
        load_store_environment()

    artifact = (
        build_linux()
        if args.target == "linux"
        else build_windows(
            args.store_identity_name
            if args.store_identity_name is not None
            else os.environ.get("REPETORIUM_STORE_IDENTITY_NAME"),
            args.store_publisher
            if args.store_publisher is not None
            else os.environ.get("REPETORIUM_STORE_PUBLISHER"),
            args.store_publisher_display_name
            if args.store_publisher_display_name is not None
            else os.environ.get("REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME"),
        )
    )
    print(f"Built {artifact.relative_to(ROOT)}")
    if args.install_desktop_entry:
        desktop_entry = install_linux_desktop_entry(artifact)
        print(f"Installed desktop entry {desktop_entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
