import configparser
import importlib.util
import json
import shlex
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def build_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
    spec = importlib.util.spec_from_file_location("repetorium_build", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("target", "host", "mode"),
    [("windows", "win32", "onefile"), ("linux", "linux", "standalone")],
)
def test_build_selects_deployment_mode(build_script, monkeypatch, tmp_path, target, host, mode):
    class StopAfterDeploy(Exception):
        pass

    deploy = Mock(side_effect=StopAfterDeploy)
    clean_bundle = Mock()
    prepare_windows = Mock()
    monkeypatch.setattr(build_script, "deploy", deploy)
    monkeypatch.setattr(build_script, "remove_previous_standalone_bundle", clean_bundle)
    monkeypatch.setattr(build_script, "prepare_windows_build", prepare_windows)
    monkeypatch.setattr(build_script.sys, "platform", host)
    monkeypatch.setattr(build_script.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(build_script.shutil, "which", lambda name: name)
    monkeypatch.setattr(build_script, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(build_script, "DIST_DIR", tmp_path / "dist")

    with pytest.raises(StopAfterDeploy):
        if target == "windows":
            monkeypatch.setattr(build_script, "find_makeappx", lambda: "makeappx.exe")
            monkeypatch.setattr(build_script, "find_manifest_tool", lambda: "mt.exe")
            build_script.build_windows("StoreIdentity", "CN=StorePublisher", "Store Publisher")
        else:
            build_script.build_linux()

    if target == "linux":
        clean_bundle.assert_called_once_with()
        prepare_windows.assert_not_called()
    else:
        prepare_windows.assert_called_once_with()
        clean_bundle.assert_not_called()
    deploy.assert_called_once_with(mode)


def test_remove_previous_standalone_bundle_removes_generated_output(build_script, tmp_path):
    build_dir = tmp_path / "build"
    bundle = build_dir / "Repetorium.dist"
    nested = bundle / "Repetorium.dist" / "old-output"
    nested.mkdir(parents=True)
    (nested / "stale.txt").write_text("stale", encoding="utf-8")
    build_dir.mkdir(exist_ok=True)
    build_script.BUILD_DIR = build_dir

    build_script.remove_previous_standalone_bundle()

    assert not bundle.exists()


def test_remove_previous_standalone_bundle_refuses_symlinks(build_script, tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    bundle = build_dir / "Repetorium.dist"
    bundle.symlink_to(tmp_path, target_is_directory=True)
    build_script.BUILD_DIR = build_dir

    with pytest.raises(SystemExit, match="Refusing to remove a symlink"):
        build_script.remove_previous_standalone_bundle()

    assert bundle.is_symlink()


def test_windows_build_creates_store_ready_msix(build_script, monkeypatch, tmp_path):
    build_dir = tmp_path / "build"
    bundle = build_dir / "Repetorium.dist"
    (bundle / "nested").mkdir(parents=True)
    (bundle / "nested" / "stale.txt").write_text("old Linux output", encoding="utf-8")
    executable = build_dir / "Repetorium.exe"
    executable.write_bytes(b"stale Windows output")
    dist_dir = tmp_path / "dist"
    monkeypatch.setattr(build_script.sys, "platform", "win32")
    monkeypatch.setattr(build_script, "BUILD_DIR", build_dir)
    monkeypatch.setattr(build_script, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build_script, "find_makeappx", lambda: "makeappx.exe")
    monkeypatch.setattr(build_script, "find_manifest_tool", lambda: "mt.exe")
    enable_dpi = Mock()
    monkeypatch.setattr(build_script, "enable_per_monitor_dpi_awareness", enable_dpi)
    monkeypatch.setattr(
        build_script,
        "write_msix_assets",
        lambda assets: assets.mkdir(parents=True),
    )

    def deploy(mode):
        assert mode == "onefile"
        assert not bundle.exists()
        assert not executable.exists()
        executable.write_bytes(b"fresh deploy output")

    def makeappx(*command, env=None):
        assert command[0:2] == ("makeappx.exe", "pack")
        package_dir = Path(command[3])
        manifest = ET.parse(package_dir / "AppxManifest.xml").getroot()
        identity = manifest.find(f"{{{build_script.APPX_NAMESPACE}}}Identity")
        assert identity is not None
        assert identity.attrib["Name"] == "StoreIdentity"
        assert identity.attrib["Publisher"] == "CN=StorePublisher"
        assert identity.attrib["Version"].count(".") == 3
        properties = manifest.find(f"{{{build_script.APPX_NAMESPACE}}}Properties")
        assert properties is not None
        assert properties.findtext(
            f"{{{build_script.APPX_NAMESPACE}}}PublisherDisplayName"
        ) == "Store Publisher"
        application = manifest.find(
            f"{{{build_script.APPX_NAMESPACE}}}Applications/"
            f"{{{build_script.APPX_NAMESPACE}}}Application"
        )
        assert application is not None
        assert application.attrib["Executable"] == "Repetorium.exe"
        assert application.attrib["EntryPoint"] == "Windows.FullTrustApplication"
        visuals = application.find(f"{{{build_script.UAP_NAMESPACE}}}VisualElements")
        assert visuals is not None
        assert visuals.attrib["Square44x44Logo"] == "Assets\\Square44x44Logo.png"
        assert visuals.attrib["Square150x150Logo"] == "Assets\\Square150x150Logo.png"
        capabilities = manifest.find(f"{{{build_script.APPX_NAMESPACE}}}Capabilities")
        assert capabilities is not None
        assert capabilities.find(
            f"{{{build_script.RESCAP_NAMESPACE}}}Capability[@Name='runFullTrust']"
        ) is not None
        output_path = Path(command[5])
        output_path.write_bytes(b"fresh MSIX package")

    monkeypatch.setattr(build_script, "deploy", deploy)
    monkeypatch.setattr(build_script, "run", makeappx)

    artifact = build_script.build_windows("StoreIdentity", "CN=StorePublisher", "Store Publisher")

    assert artifact == dist_dir / "Repetorium.msix"
    assert artifact.read_bytes() == b"fresh MSIX package"
    assert (dist_dir / "Repetorium.exe").read_bytes() == b"fresh deploy output"
    enable_dpi.assert_called_once_with(executable, "mt.exe")


def test_windows_build_reports_missing_output(build_script, monkeypatch, tmp_path):
    executable = tmp_path / "Repetorium.exe"
    executable.write_bytes(b"stale output")
    monkeypatch.setattr(build_script.sys, "platform", "win32")
    monkeypatch.setattr(build_script, "BUILD_DIR", tmp_path)
    monkeypatch.setattr(build_script, "find_makeappx", lambda: "makeappx.exe")
    monkeypatch.setattr(build_script, "find_manifest_tool", lambda: "mt.exe")
    monkeypatch.setattr(build_script, "deploy", Mock())

    with pytest.raises(SystemExit, match="Expected deploy output was not found"):
        build_script.build_windows("StoreIdentity", "CN=StorePublisher", "Store Publisher")
    assert not executable.exists()


def test_enable_per_monitor_dpi_awareness_preserves_existing_manifest(build_script, tmp_path, monkeypatch):
    executable = tmp_path / "Repetorium.exe"
    executable.write_bytes(b"executable")
    existing_manifest = (
        '<assembly xmlns="urn:schemas-microsoft-com:asm.v1" '
        'xmlns:asmv3="urn:schemas-microsoft-com:asm.v3" manifestVersion="1.0">'
        "<asmv3:application><asmv3:windowsSettings><asmv3:longPathAware>true"
        "</asmv3:longPathAware></asmv3:windowsSettings></asmv3:application></assembly>"
    )
    commands = []

    def mock_run(*command, env=None):
        commands.append(command)
        if command[1].startswith("-inputresource:"):
            manifest_path = Path(command[2][5:])
            manifest_path.write_text(existing_manifest, encoding="utf-8")
        else:
            manifest_path = Path(command[2])
            manifest = ET.parse(manifest_path).getroot()
            windows_settings = manifest.find(
                ".//{urn:schemas-microsoft-com:asm.v3}windowsSettings"
            )
            assert windows_settings is not None
            assert windows_settings.findtext(
                "{http://schemas.microsoft.com/SMI/2005/WindowsSettings}dpiAware"
            ) == "true/pm"
            assert windows_settings.findtext(
                "{http://schemas.microsoft.com/SMI/2016/WindowsSettings}dpiAwareness"
            ) == "PerMonitorV2"
            assert windows_settings.findtext(
                "{urn:schemas-microsoft-com:asm.v3}longPathAware"
            ) == "true"

    monkeypatch.setattr(build_script, "run", mock_run)

    build_script.enable_per_monitor_dpi_awareness(executable, "mt.exe")

    assert len(commands) == 2
    assert commands[0][1] == f"-inputresource:{executable};#1"
    assert commands[1][1] == "-manifest"
    assert commands[1][3] == f"-outputresource:{executable};#1"


def test_windows_build_rejects_invalid_store_identity_name(build_script, monkeypatch):
    monkeypatch.setattr(build_script.sys, "platform", "win32")
    find_makeappx = Mock()
    deploy = Mock()
    monkeypatch.setattr(build_script, "find_makeappx", find_makeappx)
    monkeypatch.setattr(build_script, "deploy", deploy)

    with pytest.raises(SystemExit, match="Invalid Store identity name"):
        build_script.build_windows(
            "Sudhakar Karunaiprakasam",
            "CN=StorePublisher",
            "Store Publisher",
        )

    find_makeappx.assert_not_called()
    deploy.assert_not_called()


def test_windows_build_requires_store_publisher_display_name(build_script, monkeypatch):
    monkeypatch.setattr(build_script.sys, "platform", "win32")
    find_makeappx = Mock()
    monkeypatch.setattr(build_script, "find_makeappx", find_makeappx)

    with pytest.raises(SystemExit, match="identity name, publisher, and publisher display name"):
        build_script.build_windows("StoreIdentity", "CN=StorePublisher")

    find_makeappx.assert_not_called()


def test_linux_build_sets_bundled_qt_paths_in_apprun(build_script, monkeypatch, tmp_path):
    build_dir = tmp_path / "build"
    bundle = build_dir / "Repetorium.dist"
    platforms = bundle / "PySide6" / "qt-plugins" / "platforms"
    qml_imports = bundle / "PySide6" / "qml"
    platforms.mkdir(parents=True)
    qml_imports.mkdir(parents=True)
    executable = bundle / "Repetorium.bin"
    executable.write_bytes(b"application")
    dist_dir = tmp_path / "dist"
    monkeypatch.setattr(build_script.sys, "platform", "linux")
    monkeypatch.setattr(build_script.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(build_script.shutil, "which", lambda name: name)
    monkeypatch.setattr(build_script, "BUILD_DIR", build_dir)
    monkeypatch.setattr(build_script, "DIST_DIR", dist_dir)

    def deploy(mode):
        assert mode == "standalone"
        platforms.mkdir(parents=True)
        qml_imports.mkdir(parents=True)
        executable.write_bytes(b"application")

    monkeypatch.setattr(build_script, "deploy", deploy)

    def check_appimage_command(*command, env=None):
        app_dir = Path(command[1])
        app_run = (app_dir / "AppRun").read_text(encoding="utf-8")
        assert 'export QT_PLUGIN_PATH="$HERE/usr/lib/repetorium/PySide6/qt-plugins"' in app_run
        assert 'export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_PATH/platforms"' in app_run
        assert 'export QML2_IMPORT_PATH="$HERE/usr/lib/repetorium/PySide6/qml"' in app_run
        assert 'exec "$HERE/usr/lib/repetorium/Repetorium.bin" "$@"' in app_run
        assert (app_dir / "AppRun").stat().st_mode & 0o111
        assert (app_dir / "Repetorium.desktop").is_file()

    monkeypatch.setattr(build_script, "run", check_appimage_command)

    artifact = build_script.build_linux()

    assert artifact == dist_dir / "Repetorium-x86_64.AppImage"


def test_linux_build_reports_missing_qt_platform_plugins(build_script, monkeypatch, tmp_path):
    build_dir = tmp_path / "build"
    bundle = build_dir / "Repetorium.dist"
    (bundle / "PySide6" / "qml").mkdir(parents=True)
    (bundle / "Repetorium.bin").write_bytes(b"application")
    monkeypatch.setattr(build_script.sys, "platform", "linux")
    monkeypatch.setattr(build_script.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(build_script.shutil, "which", lambda name: name)
    monkeypatch.setattr(build_script, "BUILD_DIR", build_dir)

    def deploy(mode):
        assert mode == "standalone"
        (bundle / "PySide6" / "qml").mkdir(parents=True)
        (bundle / "Repetorium.bin").write_bytes(b"application")

    monkeypatch.setattr(build_script, "deploy", deploy)
    run = Mock()
    monkeypatch.setattr(build_script, "run", run)

    with pytest.raises(SystemExit, match="Qt platform plugins were not found"):
        build_script.build_linux()

    run.assert_not_called()


def test_install_linux_desktop_entry(build_script, monkeypatch, tmp_path):
    artifact = tmp_path / "Repetorium build" / "Repetorium-x86_64.AppImage"
    artifact.parent.mkdir()
    artifact.write_bytes(b"AppImage")
    data_home = tmp_path / "user data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    desktop_entry = build_script.install_linux_desktop_entry(artifact)

    installed_icon = data_home / "icons" / "hicolor" / "scalable" / "apps" / "repetorium.svg"
    assert desktop_entry == data_home / "applications" / "repetorium.desktop"
    assert installed_icon.read_bytes() == (build_script.ICON_DIR / "repetorium.svg").read_bytes()
    assert (
        f'Exec="{artifact.resolve()}"\n'
        in desktop_entry.read_text(encoding="utf-8")
    )
    assert f"Icon={installed_icon}\n" in desktop_entry.read_text(encoding="utf-8")


def test_install_linux_desktop_entry_rejects_missing_artifact(build_script, tmp_path):
    with pytest.raises(SystemExit, match="Linux application bundle was not found"):
        build_script.install_linux_desktop_entry(tmp_path / "missing.AppImage")


def test_install_linux_desktop_entry_rejects_relative_data_home(
    build_script, monkeypatch, tmp_path,
):
    artifact = tmp_path / "Repetorium.AppImage"
    artifact.write_bytes(b"AppImage")
    monkeypatch.setenv("XDG_DATA_HOME", "relative-data")

    with pytest.raises(SystemExit, match="XDG_DATA_HOME must be an absolute path"):
        build_script.install_linux_desktop_entry(artifact)


def test_main_installs_desktop_entry_after_linux_build(build_script, monkeypatch, capsys):
    artifact = build_script.DIST_DIR / "Repetorium-x86_64.AppImage"
    desktop_entry = Path("/home/user/.local/share/applications/repetorium.desktop")
    build_linux = Mock(return_value=artifact)
    install_desktop_entry = Mock(return_value=desktop_entry)
    monkeypatch.setattr(build_script.sys, "argv", [
        "build.py", "--target", "linux", "--install-desktop-entry",
    ])
    monkeypatch.setattr(build_script, "build_linux", build_linux)
    monkeypatch.setattr(build_script, "install_linux_desktop_entry", install_desktop_entry)

    assert build_script.main() == 0

    build_linux.assert_called_once_with()
    install_desktop_entry.assert_called_once_with(artifact)
    assert "Installed desktop entry" in capsys.readouterr().out


def test_main_rejects_desktop_entry_for_windows(build_script, monkeypatch):
    monkeypatch.setattr(build_script.sys, "argv", [
        "build.py", "--target", "windows", "--install-desktop-entry",
    ])

    with pytest.raises(SystemExit, match="2"):
        build_script.main()


def test_main_reads_store_identity_from_environment_and_cli_overrides_it(
    build_script,
    monkeypatch,
):
    monkeypatch.setenv("REPETORIUM_STORE_IDENTITY_NAME", "EnvironmentIdentity")
    monkeypatch.setenv("REPETORIUM_STORE_PUBLISHER", "CN=EnvironmentPublisher")
    monkeypatch.setenv("REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME", "Environment Publisher")
    monkeypatch.setattr(build_script.sys, "argv", [
        "build.py",
        "--target",
        "windows",
        "--store-identity-name",
        "CommandLineIdentity",
    ])
    artifact = build_script.DIST_DIR / "Repetorium.msix"
    build_windows = Mock(return_value=artifact)
    monkeypatch.setattr(build_script, "build_windows", build_windows)

    assert build_script.main() == 0

    build_windows.assert_called_once_with(
        "CommandLineIdentity",
        "CN=EnvironmentPublisher",
        "Environment Publisher",
    )


def test_load_store_environment_reads_values_without_overwriting_environment(
    build_script,
    monkeypatch,
    tmp_path,
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Partner Center package identity\n"
        "REPETORIUM_STORE_IDENTITY_NAME='FileIdentity'\n"
        "REPETORIUM_STORE_PUBLISHER=CN=FilePublisher\n"
        'REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME="File Publisher"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("REPETORIUM_STORE_IDENTITY_NAME", raising=False)
    monkeypatch.setenv("REPETORIUM_STORE_PUBLISHER", "CN=EnvironmentPublisher")
    monkeypatch.delenv("REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME", raising=False)

    build_script.load_store_environment(env_file)

    assert build_script.os.environ["REPETORIUM_STORE_IDENTITY_NAME"] == "FileIdentity"
    assert build_script.os.environ["REPETORIUM_STORE_PUBLISHER"] == "CN=EnvironmentPublisher"
    assert build_script.os.environ["REPETORIUM_STORE_PUBLISHER_DISPLAY_NAME"] == "File Publisher"


def test_load_store_environment_reports_invalid_or_unknown_entries(build_script, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("UNEXPECTED_SETTING=value\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="Unsupported .env variable"):
        build_script.load_store_environment(env_file)

    env_file.write_text("not an assignment\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="expected KEY=VALUE"):
        build_script.load_store_environment(env_file)


@pytest.mark.parametrize("host", ["win32", "linux"])
@pytest.mark.parametrize("mode", ["onefile", "standalone"])
@pytest.mark.parametrize("existing_spec", [True, False])
def test_deploy_uses_portable_temporary_config(
    build_script, monkeypatch, tmp_path, mode, existing_spec, host,
):
    original = tmp_path / "pysidedeploy.spec"
    original_text = (
        "[app]\n"
        "project_dir = .\n"
        "exec_directory = /old/linux/output\n"
        "icon = /old/linux/PySide6/scripts/deploy_lib/pyside_icon.jpg\n"
        "[python]\n"
        "python_path = /old/linux/python\n"
        "packages = Nuitka==4.1.1\n"
        "[qt]\n"
        "modules = Core,DBus\n"
        "plugins = platforms/xcb\n"
        "qml_files = qml/Main.qml\n"
        "[nuitka]\n"
        "mode = standalone\n"
        "extra_args = --quiet --noinclude-qt-translations\n"
    )
    if existing_spec:
        original.write_text(original_text, encoding="utf-8")
    entry_point = tmp_path / "__main__.py"
    entry_point.write_text("if __name__ == '__main__':\n    pass\n", encoding="utf-8")
    qml_file = tmp_path / "qml" / "Main.qml"
    qml_file.parent.mkdir()
    qml_file.write_text("import QtQuick\nItem {}\n", encoding="utf-8")
    monkeypatch.setattr(build_script, "BUILD_DIR", tmp_path)
    monkeypatch.setattr(build_script, "ENTRY_POINT", entry_point)
    monkeypatch.setattr(build_script.sys, "platform", host)
    config_paths = []

    def check_command(*command):
        config_path = Path(command[command.index("--config-file") + 1])
        config_paths.append(config_path)
        assert command == (
            "uv", "run", "--group", "build", "pyside6-deploy", str(entry_point),
            "--config-file", str(config_path), "--mode", mode, "--name", "Repetorium", "--force",
        )
        config = configparser.ConfigParser()
        with config_path.open(encoding="utf-8") as source:
            config.read_file(source)
        project_file = Path(config["app"]["project_file"])
        assert project_file.is_file()
        project = json.loads(project_file.read_text(encoding="utf-8"))
        assert project["files"] == [str(entry_point.resolve()), str(qml_file.resolve())]
        assert config["app"]["project_dir"] == str(tmp_path)
        assert config["app"]["input_file"] == str(entry_point)
        assert config["app"]["exec_directory"] == str(tmp_path)
        assert config["app"]["title"] == "Repetorium"
        extension = "ico" if host == "win32" else "png"
        assert config["app"]["icon"] == str(build_script.ICON_DIR / f"repetorium.{extension}")
        assert Path(config["app"]["icon"]).is_file()
        assert config["python"]["python_path"] == build_script.sys.executable
        assert config["nuitka"]["mode"] == mode
        assert config["qt"]["modules"] == ""
        assert config["qt"]["plugins"] == ""
        arguments = shlex.split(config["nuitka"]["extra_args"])
        assert "--quiet" in arguments
        assert "--noinclude-qt-translations" in arguments
        resources = build_script.ROOT / "src" / "repetorium" / "resources"
        assert not any(argument.startswith(f"--include-data-dir={resources}=")
                       for argument in arguments)
        if existing_spec:
            assert config["qt"]["qml_files"] == "qml/Main.qml"
            assert config["python"]["packages"] == "Nuitka==4.1.1"

    monkeypatch.setattr(build_script, "run", check_command)

    build_script.deploy(mode)

    assert len(config_paths) == 1
    assert not config_paths[0].exists()
    if existing_spec:
        assert original.read_text(encoding="utf-8") == original_text
    else:
        assert not original.exists()


def test_deploy_retains_custom_icon_and_cleans_up_on_failure(build_script, monkeypatch, tmp_path):
    icon = tmp_path / "custom.ico"
    icon.write_bytes(b"icon")
    original = tmp_path / "pysidedeploy.spec"
    original.write_text("[app]\nicon = custom.ico\n", encoding="utf-8")
    monkeypatch.setattr(build_script, "BUILD_DIR", tmp_path)
    config_paths = []

    def fail_command(*command):
        assert command[-1] == "--dry-run"
        config_path = Path(command[command.index("--config-file") + 1])
        config_paths.append(config_path)
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        assert config["app"]["icon"] == str(icon)
        raise RuntimeError("deployment failed")

    monkeypatch.setattr(build_script, "run", fail_command)

    with pytest.raises(RuntimeError, match="deployment failed"):
        build_script.deploy("onefile", dry_run=True)

    assert len(config_paths) == 1
    assert not config_paths[0].exists()
    assert original.read_text(encoding="utf-8") == "[app]\nicon = custom.ico\n"


def test_deploy_reports_missing_custom_icon(build_script, monkeypatch, tmp_path):
    (tmp_path / "pysidedeploy.spec").write_text("[app]\nicon = missing.ico\n", encoding="utf-8")
    monkeypatch.setattr(build_script, "BUILD_DIR", tmp_path)
    run = Mock()
    monkeypatch.setattr(build_script, "run", run)

    with pytest.raises(SystemExit, match="Deployment icon was not found"):
        build_script.deploy("onefile")

    run.assert_not_called()


def test_deploy_includes_format_instructions_without_a_library(build_script, monkeypatch, tmp_path):
    (tmp_path / "pysidedeploy.spec").write_text(
        "[nuitka]\nextra_args = --quiet\n", encoding="utf-8")
    monkeypatch.setattr(build_script, "BUILD_DIR", tmp_path)
    def check_command(*command):
        config = configparser.ConfigParser()
        config.read(command[command.index("--config-file") + 1], encoding="utf-8")
        arguments = shlex.split(config["nuitka"]["extra_args"])
        resources = build_script.ROOT / "src" / "repetorium" / "resources"
        assert not any(argument.startswith(f"--include-data-dir={resources}=")
                       for argument in arguments)
    monkeypatch.setattr(build_script, "run", check_command)
    build_script.deploy("onefile")
