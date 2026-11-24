"""Render store screenshots: scripts/screenshots.py OUT_DIR [WIDTH HEIGHT [light|dark]]."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("REPETORIUM_CONTENT_DIR", str(
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "content"
))

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from repetorium.app import create_engine  # noqa: E402
from repetorium.cases.coach import CaseCoach  # noqa: E402
from repetorium.core.db import connect  # noqa: E402
from repetorium.engine.tutor import Tutor  # noqa: E402
from repetorium.ui.backend import Backend  # noqa: E402


def find(root, name):
    stack = [root]
    while stack:
        obj = stack.pop()
        if obj.metaObject().className().startswith(name):
            return obj
        stack.extend(obj.findChildren(QObject))
    return None


def main(out: Path, width: int = 1280, height: int = 820, theme: str = "light") -> None:
    if theme not in ("light", "dark"):
        raise ValueError("Choose the light or dark theme.")
    out.mkdir(parents=True, exist_ok=True)
    QQuickStyle.setStyle("Repetorium")
    app = QGuiApplication(sys.argv)
    tutor = Tutor(connect(":memory:"), seed=4)
    backend = Backend(tutor, CaseCoach(tutor))
    backend.setSetting("theme", theme)
    engine = create_engine(backend)
    win = engine.rootObjects()[0]
    win.setWidth(width)
    win.setHeight(height)

    def shot(name):
        for _ in range(10):
            app.processEvents()
        win.grabWindow().save(str(out / f"{name}.png"))

    shot("dashboard")
    win.setProperty("page", 1)
    practice = find(win, "PracticePage")
    QMetaObject.invokeMethod(practice, "begin", Qt.DirectConnection, Q_ARG("QVariant", "next"))
    lesson_guide = win.findChild(QObject, "practiceLessonGuide")
    if lesson_guide is None:
        raise RuntimeError("The practice lesson guide was not found.")
    if height <= 768:
        lesson_guide.setProperty("lesson", [])
    shot("lesson_guide")
    QMetaObject.invokeMethod(practice, "loadItem", Qt.DirectConnection)
    shot("practice")
    if "sample-application" in tutor.graph.case_templates:
        win.setProperty("page", 2)
        cases = find(win, "MockCasePage")
        shot("case_library")
        QMetaObject.invokeMethod(cases, "start", Qt.DirectConnection,
                                 Q_ARG("QVariant", "sample-application"))
        for cat in ("Observation",):
            QMetaObject.invokeMethod(cases, "request", Qt.DirectConnection, Q_ARG("QVariant", cat))
        shot("mock_case")
    win.setProperty("page", 3)
    knowledge_map = find(win, "KnowledgeMapPage")
    map_search = os.environ.get("REPETORIUM_SCREENSHOT_MAP_SEARCH", "")
    if map_search:
        graph = backend.knowledgeMap()
        nodes = graph["nodes"]
        query = map_search.strip().casefold()
        matches = [
            node for node in nodes
            if any(
                query in str(node.get(key, "")).casefold()
                for key in ("title", "category", "description", "definition", "domains", "sources")
            )
        ]
        if not matches:
            raise RuntimeError(f"No knowledge-map skills match {map_search!r}.")
        included = {node["id"] for node in matches}
        map_nodes = matches
        map_edges = [
            edge for edge in graph["edges"]
            if edge.get("kind") in (None, "prerequisite")
            and edge["from"] in included and edge["to"] in included
        ]
        knowledge_map.setProperty("autoFit", False)
        knowledge_map.setProperty("graph", {"nodes": map_nodes, "edges": map_edges})
        knowledge_map.setProperty("searchText", map_search)
        for _ in range(10):
            app.processEvents()
        QMetaObject.invokeMethod(knowledge_map, "fitGraph", Qt.DirectConnection)
        for _ in range(10):
            app.processEvents()
        zoom = float(knowledge_map.property("zoom"))
        QMetaObject.invokeMethod(
            knowledge_map, "zoomBy", Qt.DirectConnection, Q_ARG("QVariant", 1.2 / zoom)
        )
        if len(map_nodes) <= 9:
            columns = min(3, len(map_nodes))
            rows = (len(map_nodes) + columns - 1) // columns
            x_positions = {1: [480], 2: [250, 710], 3: [100, 500, 900]}[columns]
            canvas_height = 640
            positions = {
                node["id"]: {
                    "x": x_positions[index % columns],
                    "y": canvas_height * (index // columns + 1) / (rows + 1),
                }
                for index, node in enumerate(map_nodes)
            }
            knowledge_map.setProperty("positions", positions)
            map_canvas = knowledge_map.findChild(QObject, "mapEdgesCanvas")
            if map_canvas is None:
                raise RuntimeError("The knowledge map canvas was not found.")
            QMetaObject.invokeMethod(map_canvas, "requestPaint", Qt.DirectConnection)
    else:
        knowledge_map.setProperty("autoFit", False)
        knowledge_map.setProperty("zoom", 1.2)
    shot("knowledge_map")
    win.setProperty("page", 4)
    library = find(win, "KnowledgeLibraryPage")
    if library is None:
        raise RuntimeError("The knowledge library page was not found.")
    library.setProperty("packState", backend.contentPackState())
    shot("library")
    win.setProperty("page", 5)
    settings_tabs = win.findChild(QObject, "settingsTabs")
    if settings_tabs is None:
        raise RuntimeError("The settings tabs were not found.")
    settings_tabs.setProperty("currentIndex", 0)
    shot("settings")
    settings_tabs.setProperty("currentIndex", 1)
    shot("advanced_settings")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots"),
         int(sys.argv[2]) if len(sys.argv) > 2 else 1280,
         int(sys.argv[3]) if len(sys.argv) > 3 else 820,
         sys.argv[4] if len(sys.argv) > 4 else "light")
