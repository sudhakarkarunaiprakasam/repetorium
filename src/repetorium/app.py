import ctypes
import sys

from PySide6.QtGui import QGuiApplication, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from repetorium.cases.coach import CaseCoach
from repetorium.engine.store import Store
from repetorium.engine.tutor import Tutor
from repetorium.library import open_progress
from repetorium.packs import load_selected_library
from repetorium.paths import CONTENT_DIR, QML_DIR
from repetorium.ui.backend import Backend


def configure_windows_taskbar() -> None:
    if sys.platform != "win32":
        return
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    set_app_id = shell32.SetCurrentProcessExplicitAppUserModelID
    set_app_id.argtypes = [ctypes.c_wchar_p]
    set_app_id.restype = ctypes.c_long
    result = set_app_id("Repetorium.Desktop")
    if result < 0:
        raise OSError(f"Could not set Windows taskbar identity (HRESULT 0x{result & 0xFFFFFFFF:08X}).")


def create_engine(backend: Backend) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    # The unified control style lives in QML_DIR/Repetorium and is resolved
    # by style name through the engine's import path.
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QML_DIR / "Main.qml")
    icon = QIcon(str(QML_DIR / "icons" / "repetorium.ico"))
    if icon.isNull():
        raise RuntimeError("Could not load the Repetorium window icon.")
    for root in engine.rootObjects():
        if isinstance(root, QWindow):
            root.setIcon(icon)
    return engine


def main() -> int:
    configure_windows_taskbar()
    QQuickStyle.setStyle("Repetorium")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Repetorium")
    app.setOrganizationName("Repetorium")
    app.setWindowIcon(QIcon(str(QML_DIR / "icons" / "repetorium.ico")))

    connection = open_progress(CONTENT_DIR)
    try:
        graph = load_selected_library(Store(connection))
        tutor = Tutor(connection, graph)
        backend = Backend(tutor, CaseCoach(tutor))
        engine = create_engine(backend)
        if not engine.rootObjects():
            return 1
        return app.exec()
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
