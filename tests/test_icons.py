import importlib.util
import struct
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QIcon, QImage
from PySide6.QtSvg import QSvgRenderer

from repetorium import app
from repetorium.paths import QML_DIR

ICON_DIR = QML_DIR / "icons"


def load_generator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_icons.py"
    spec = importlib.util.spec_from_file_location("repetorium_icons", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_brand_assets_are_valid(qapp):
    assert QSvgRenderer(str(ICON_DIR / "repetorium.svg")).isValid()
    image = QImage(str(ICON_DIR / "repetorium.png"))
    assert (image.width(), image.height()) == (512, 512)
    icon = QIcon(str(ICON_DIR / "repetorium.ico"))
    assert not icon.isNull()
    assert {size.width() for size in icon.availableSizes()} == {16, 24, 32, 48, 64, 128, 256}


def test_icon_generator_matches_committed_assets(qapp, tmp_path):
    generator = load_generator()
    (tmp_path / "repetorium.svg").write_bytes((ICON_DIR / "repetorium.svg").read_bytes())
    generator.generate_icons(tmp_path)
    for extension in ("png", "ico"):
        generated = (tmp_path / f"repetorium.{extension}").read_bytes()
        assert generated == (ICON_DIR / f"repetorium.{extension}").read_bytes()

    data = (tmp_path / "repetorium.ico").read_bytes()
    assert struct.unpack_from("<HHH", data) == (0, 1, 7)
    for index, size in enumerate(generator.ICON_SIZES):
        width, height, _, _, planes, depth, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * index,
        )
        assert (width or 256, height or 256, planes, depth) == (size, size, 1, 32)
        frame = QImage.fromData(data[offset:offset + length], "PNG")
        assert (frame.width(), frame.height()) == (size, size)


def test_store_tile_matches_logo_source(qapp, tmp_path):
    generator = load_generator()
    (tmp_path / "repetorium.svg").write_bytes((ICON_DIR / "repetorium.svg").read_bytes())
    output = tmp_path / "repetorium-app-tile-300x300.png"
    generator.generate_store_tile(tmp_path, output)

    image = QImage(str(output))
    assert (image.width(), image.height()) == (300, 300)
    assert output.read_bytes() == generator.STORE_TILE_PATH.read_bytes()


def test_store_icon_1024_matches_logo_source(qapp, tmp_path):
    generator = load_generator()
    (tmp_path / "repetorium.svg").write_bytes((ICON_DIR / "repetorium.svg").read_bytes())
    output = tmp_path / "repetorium-app-icon-1024x1024.png"
    generator.generate_store_icon_1024(tmp_path, output)

    image = QImage(str(output))
    assert (image.width(), image.height()) == (1024, 1024)
    assert output.read_bytes() == generator.STORE_ICON_1024_PATH.read_bytes()


def test_icon_generator_reports_invalid_source(tmp_path):
    (tmp_path / "repetorium.svg").write_text("not an SVG", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Could not load"):
        load_generator().generate_icons(tmp_path)


def test_main_sets_project_window_icon(qapp, monkeypatch):
    application = Mock()
    application.exec.return_value = 0
    monkeypatch.setattr(app, "QGuiApplication", Mock(return_value=application))
    configure_taskbar = Mock()
    monkeypatch.setattr(app, "configure_windows_taskbar", configure_taskbar)
    monkeypatch.setattr(app, "open_progress", Mock())
    monkeypatch.setattr(app, "load_selected_library", Mock())
    monkeypatch.setattr(app, "Tutor", Mock())
    monkeypatch.setattr(app, "CaseCoach", Mock())
    monkeypatch.setattr(app, "Backend", Mock())
    monkeypatch.setattr(app, "create_engine", Mock(return_value=Mock(rootObjects=lambda: [Mock()])))

    assert app.main() == 0
    configure_taskbar.assert_called_once()
    application.setWindowIcon.assert_called_once()
    icon = application.setWindowIcon.call_args.args[0]
    assert not icon.isNull()
    assert icon.pixmap(32, 32).toImage() == QIcon(str(ICON_DIR / "repetorium.ico")).pixmap(32, 32).toImage()


def test_windows_taskbar_identity_is_set(monkeypatch):
    monkeypatch.setattr(app.sys, "platform", "win32")
    set_app_id = Mock(return_value=0)
    load_library = Mock(return_value=Mock(SetCurrentProcessExplicitAppUserModelID=set_app_id))
    monkeypatch.setattr(app.ctypes, "WinDLL", load_library, raising=False)

    app.configure_windows_taskbar()

    load_library.assert_called_once_with("shell32", use_last_error=True)
    set_app_id.assert_called_once_with("Repetorium.Desktop")
    assert set_app_id.argtypes == [app.ctypes.c_wchar_p]
    assert set_app_id.restype == app.ctypes.c_long


def test_windows_taskbar_identity_failure_is_reported(monkeypatch):
    monkeypatch.setattr(app.sys, "platform", "win32")
    set_app_id = Mock(return_value=-2147467259)
    monkeypatch.setattr(
        app.ctypes, "WinDLL",
        Mock(return_value=Mock(SetCurrentProcessExplicitAppUserModelID=set_app_id)),
        raising=False,
    )
    with pytest.raises(OSError, match="HRESULT 0x80004005"):
        app.configure_windows_taskbar()


def test_taskbar_identity_is_windows_only(monkeypatch):
    monkeypatch.setattr(app.sys, "platform", "linux")
    load_library = Mock()
    monkeypatch.setattr(app.ctypes, "WinDLL", load_library, raising=False)
    app.configure_windows_taskbar()
    load_library.assert_not_called()
