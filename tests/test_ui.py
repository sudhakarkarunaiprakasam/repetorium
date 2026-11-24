import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    Q_ARG,
    QCoreApplication,
    QEvent,
    QMetaObject,
    QObject,
    Qt,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtQml import QQmlExpression, qmlContext  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from repetorium.app import create_engine  # noqa: E402
from repetorium.cases.coach import CaseCoach  # noqa: E402
from repetorium.engine.tutor import Task, Tutor  # noqa: E402
from repetorium.paths import QML_DIR  # noqa: E402
from repetorium.ui.backend import Backend  # noqa: E402


@pytest.fixture
def ui(qapp, qt_fonts, conn, graph, clock, tmp_path, monkeypatch):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    if QQuickStyle.name() != "Repetorium":
        QQuickStyle.setStyle("Repetorium")
    messages: list[str] = []

    def handler(mode, ctx, msg):
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            messages.append(msg)

    qInstallMessageHandler(handler)
    tutor = Tutor(conn, graph, clock, seed=1)
    backend = Backend(tutor, CaseCoach(tutor))
    engine = create_engine(backend)
    assert engine.rootObjects(), messages
    yield engine.rootObjects()[0], backend, messages
    qInstallMessageHandler(None)
    engine.rootObjects()[0].close()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _find(root, name):
    stack = [root]
    while stack:
        obj = stack.pop()
        if type(obj).__name__.startswith(name) or obj.metaObject().className().startswith(name):
            return obj
        stack.extend(obj.findChildren(QObject))
    return None


def test_all_pages_load_without_qml_warnings(ui, qtbot):
    win, backend, messages = ui
    for page in range(7):
        win.setProperty("page", page)
        qtbot.wait(30)
        assert messages == [], f"Page {page}: {messages}"


def test_lesson_hints_remain_available_in_mock_exam(ui):
    _, backend, messages = ui
    backend.tutor.states["sample.choice"].status = "mastered"
    backend.startSkillExam(["sample.choice"], 1, 2)
    exam_item = backend.nextSkillExamItem()
    assert exam_item["prompt"]
    exam_hint = backend.lessonHint(1, True)
    assert exam_hint["text"]
    assert exam_hint["guide"]["definition"]
    assert messages == []


def test_opening_lesson_prevents_mastery_credit(ui, qtbot):
    win, backend, messages = ui
    backend.setSetting("mastery_streak", 2)
    skill_id = "sample.choice"
    skill = backend.tutor.graph.skills[skill_id]
    state = backend.tutor.states[skill_id]
    state.lesson_streak = 1
    backend.tutor.task = Task("lesson", [skill_id], "Lesson")
    item = backend.tutor.next_item()
    public_item = backend.nextItem()
    assert public_item["lesson"] == skill.lesson
    assert public_item["guide"] == skill.guide

    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    practice.setProperty("task", {"kind": "lesson", "title": "Lesson"})
    practice.setProperty("item", public_item)
    practice.setProperty("phase", "question")
    open_lesson = win.findChild(QObject, "openLessonButton")
    assert open_lesson is not None and open_lesson.isVisible()
    assert QMetaObject.invokeMethod(open_lesson, "click", Qt.DirectConnection)

    dialog = win.findChild(QObject, "practiceLessonDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    assert practice.property("lessonOpened")
    assert dialog.property("visible")
    assert QMetaObject.invokeMethod(dialog, "close", Qt.DirectConnection)

    practice.setProperty("confidence", "explained")
    win.findChild(QObject, "practiceAnswer").setProperty("response", str(item.answer))
    assert QMetaObject.invokeMethod(practice, "submit", Qt.DirectConnection)

    assert state.lesson_streak == 0
    assert not state.mastered
    assert not backend.tutor.task.done
    notice = win.findChild(QObject, "confidenceMasteryNotice")
    assert notice.property("visible")
    assert "opening the lesson" in notice.property("text").lower()
    attempt = backend.tutor.store.conn.execute(
        "SELECT confidence FROM attempts"
    ).fetchone()
    assert attempt["confidence"] == "explained"
    assert messages == []


def test_backend_submit_returns_skill_guide_follow_up_and_confidence(ui):
    _, backend, messages = ui
    skill_id = "sample.choice"
    skill = backend.tutor.graph.skills[skill_id]
    bank = backend.tutor.graph.practice_banks[skill.params["bank"]]
    bank["entries"] = [{
        "prompt": "What is the weighted cost?",
        "correct": "8.95%",
        "distractors": ["9.4%"],
        "explain": "Weight each component and adjust usable debt for tax.",
        "follow_up_prompt": "What if the tax shield were unavailable?",
    }]
    backend.tutor.task = Task("lesson", [skill_id], "Lesson")
    item = backend.tutor.next_item()

    feedback = backend.submit(str(item.answer), "unsure")

    assert feedback["correct"]
    assert feedback["guide"]["definition"] == skill.guide["definition"]
    assert feedback["followUpPrompt"] == "What if the tax shield were unavailable?"
    assert feedback["confidence"] == "unsure"
    attempt = backend.tutor.store.conn.execute(
        "SELECT confidence FROM attempts"
    ).fetchone()
    assert attempt["confidence"] == "unsure"
    assert messages == []


@pytest.mark.parametrize("target", [2, 3, 5])
def test_practice_mastery_counter_reaches_target(ui, qtbot, target):
    win, backend, messages = ui
    backend.setSetting("mastery_streak", target)
    skill_id = "sample.choice"
    backend.tutor.states[skill_id].lesson_streak = target - 1
    backend.tutor.task = Task("lesson", [skill_id], "Lesson")
    item = backend.tutor.next_item()
    public_item = backend.nextItem()

    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    practice.setProperty("task", {"kind": "lesson", "title": "Lesson"})
    practice.setProperty("item", public_item)
    practice.setProperty("phase", "question")
    win.findChild(QObject, "practiceAnswer").setProperty("response", str(item.answer))

    assert QMetaObject.invokeMethod(practice, "submit", Qt.DirectConnection)
    progress = win.findChild(QObject, "practiceProgress")
    assert progress.property("text") == f"{target}/{target} correct in a row"
    assert backend.tutor.states[skill_id].mastered

    assert QMetaObject.invokeMethod(practice, "proceed", Qt.DirectConnection)
    assert practice.property("phase") == "summary"
    assert progress.property("text") == f"{target}/{target} correct in a row"
    assert messages == []


def test_practice_feedback_shows_concept_transfer_and_confidence(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    practice.setProperty("item", {
        "skillTitle": "WACC",
        "kind": "numeric",
        "unit": "%",
        "unitHint": "%",
        "choices": [],
        "prompt": "Calculate WACC.",
        "progress": "Question 1",
    })
    practice.setProperty("feedback", {
        "correct": True,
        "answer": "8.95%",
        "solution": "Weight the capital costs and adjust usable debt tax shields.",
        "skillTitle": "WACC",
        "confidence": "guessed",
        "followUpPrompt": "What if the debt deduction were unusable?",
        "guide": {
            "definition": "The weighted required return for all capital providers.",
            "when_to_use": "Discounting cash flows to all capital providers.",
            "steps": ["Weight each funding source.", "Adjust usable debt for tax."],
        },
    })
    practice.setProperty("phase", "feedback")
    qtbot.wait(30)

    concept = win.findChild(QObject, "practiceUnderlyingConcept")
    transfer = win.findChild(QObject, "practiceTransferPrompt")
    assert concept is not None and concept.isVisible()
    assert "weighted required return" in concept.property("text")
    assert transfer is not None and transfer.isVisible()
    assert "debt deduction" in transfer.property("text")
    assert messages == []


def test_lesson_dialog_content_uses_available_width(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    practice.setProperty("item", {
        "skillTitle": "Sample skill",
        "kind": "choice",
        "choices": ["One", "Two"],
        "unitHint": "",
        "prompt": "Choose the best answer.",
        "progress": "1/3 correct in a row",
        "lesson": ["Read the complete lesson."],
        "guide": {
            "definition": "The Capital Asset Pricing Model estimates the required return on equity.",
            "when_to_use": "Estimate a risk-based required return.",
            "steps": ["Use a risk-free rate, beta, and market risk premium."],
            "example": ["The lesson content should use the full dialog width."],
            "pitfalls": ["Do not treat a required return as guaranteed."],
            "decision_tree": [
                {"question": "Estimate it?", "yes": "Use CAPM.", "no": "Choose another model."},
            ],
        },
    })
    practice.setProperty("phase", "question")
    assert QMetaObject.invokeMethod(practice, "openLesson", Qt.DirectConnection)
    dialog = win.findChild(QObject, "practiceLessonDialog")
    assert dialog.property("visible")
    guide = win.findChild(QObject, "practiceDialogLessonGuide")
    scroll = win.findChild(QObject, "practiceLessonDialogScroll")
    qtbot.wait(100)
    assert guide is not None and scroll is not None
    available_width = scroll.property("availableWidth")
    assert available_width > 0
    assert guide.width() >= available_width - 2
    assert messages == []


def test_empty_library_has_clear_ui(ui, qtbot, tmp_path):
    from repetorium.engine.graph import KnowledgeGraph

    win, backend, messages = ui
    backend.tutor = Tutor(backend.tutor.store.conn, KnowledgeGraph([], tmp_path / "empty"))
    backend.coach = CaseCoach(backend.tutor)
    backend.contentChanged.emit()
    backend.progressChanged.emit()
    assert backend.dashboard()["total"] == 0
    assert backend.caseTemplates() == []
    assert backend.knowledgeMap() == {"nodes": [], "edges": []}
    assert backend.nextTask() == {}
    for page in range(7):
        win.setProperty("page", page)
        qtbot.wait(30)
    assert backend.contentInfo()["name"] == "No content packs installed"
    assert messages == []


def test_library_reload_resets_sessions_and_preserves_progress(ui, qtbot):
    win, backend, messages = ui
    win.setProperty("page", 4)
    practice = _find(win, "PracticePage")
    QMetaObject.invokeMethod(practice, "begin", Qt.DirectConnection, Q_ARG("QVariant", "next"))
    previous_phase = practice.property("phase")
    mock = _find(win, "MockCasePage")
    QMetaObject.invokeMethod(mock, "start", Qt.DirectConnection, Q_ARG("QVariant", "sample-application"))
    assert practice.property("phase") == previous_phase
    assert mock.property("phase") == "run"
    state = backend.tutor.states["sample.root"]
    state.status = "mastered"
    backend.tutor.store.save_states([state])
    assert backend.reloadContent()["ok"]
    assert backend.tutor.states["sample.root"].mastered
    assert practice.property("phase") == "empty"
    assert mock.property("phase") == "pick"
    assert {method["id"] for method in backend.mockTestMethods()} == {"skill_exam", "case_practice"}
    exam = _find(win, "MockExamPage")
    exam.setProperty("selectedSkillIds", ["sample.root"])
    QMetaObject.invokeMethod(exam, "start", Qt.DirectConnection)
    assert exam.property("phase") == "question"
    map_data = backend.knowledgeMap()
    assert len(map_data["nodes"]) == 5
    assert all("guide" not in node and "lesson" not in node for node in map_data["nodes"])
    details = backend.knowledgeMapSkillDetails("sample.root")
    root_skill = backend.tutor.graph.skills["sample.root"]
    assert details == {"guide": root_skill.guide, "lesson": root_skill.lesson}
    assert next(method for method in backend.mockTestMethods()
                if method["id"] == "case_practice")["title"] == "Case-Based Practice"
    assert next(method for method in backend.mockTestMethods()
                if method["id"] == "skill_exam")["title"] == "Mock Tests"
    assert {skill["id"] for skill in backend.skillExamSkills()} == {"sample.root"}
    assert backend.knowledgeMap()["nodes"][0]["definition"]
    qtbot.wait(30)
    assert messages == []


def test_main_window_has_project_taskbar_icon(ui):
    win, _, messages = ui
    expected = QIcon(str(QML_DIR / "icons" / "repetorium.ico"))
    assert not win.icon().isNull()
    for size in (16, 32, 48, 256):
        assert win.icon().pixmap(size, size).toImage() == expected.pixmap(size, size).toImage()
    assert messages == []


def test_navigation_menu_collapses_and_expands_across_pages(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 3)
    menu = next(obj for obj in win.findChildren(QObject)
                if obj.objectName() == "menuPane")
    toggle = next(obj for obj in win.findChildren(QObject)
                  if obj.objectName() == "menuToggle")

    assert menu.width() == 220
    QMetaObject.invokeMethod(toggle, "click", Qt.DirectConnection)
    qtbot.wait(30)
    assert win.property("menuExpanded") is False
    assert menu.width() == 56
    assert win.property("page") == 3

    QMetaObject.invokeMethod(toggle, "click", Qt.DirectConnection)
    qtbot.wait(30)
    assert win.property("menuExpanded") is True
    assert menu.width() == 220
    assert messages == []


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_project_logo_loads_in_expanded_and_collapsed_menu(ui, qtbot, theme):
    win, _, messages = ui
    win.setProperty("theme", theme)
    logo = next(obj for obj in win.findChildren(QObject) if obj.objectName() == "brandIcon")
    menu = next(obj for obj in win.findChildren(QObject) if obj.objectName() == "menuPane")
    for expanded in (True, False):
        win.setProperty("menuExpanded", expanded)
        qtbot.wait(30)
        ready = QQmlExpression(qmlContext(logo), logo, "status === Image.Ready")
        assert ready.evaluate()[0] is True
        assert logo.isVisible()
        assert logo.x() >= 0
        assert logo.x() + logo.width() <= menu.width()
        assert logo.y() + logo.height() <= 96
    assert messages == []


def test_practice_and_case_flow_in_ui(ui, qtbot):
    win, backend, messages = ui

    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    assert practice is not None
    QMetaObject.invokeMethod(practice, "begin", Qt.DirectConnection, Q_ARG("QVariant", "next"))
    qtbot.wait(30)
    assert practice.property("phase") == "intro"
    QMetaObject.invokeMethod(practice, "loadItem", Qt.DirectConnection)
    qtbot.wait(30)
    assert practice.property("phase") == "question"

    win.setProperty("page", 2)
    cases = _find(win, "MockCasePage")
    QMetaObject.invokeMethod(cases, "start", Qt.DirectConnection,
                             Q_ARG("QVariant", "sample-application"))
    QMetaObject.invokeMethod(cases, "request", Qt.DirectConnection,
                             Q_ARG("QVariant", "Observation"))
    qtbot.wait(30)
    QMetaObject.invokeMethod(cases, "finish", Qt.DirectConnection)
    qtbot.wait(30)
    assert cases.property("phase") == "debrief"
    assert messages == []


def test_mock_case_history_delete_updates_progress(ui, qtbot):
    win, backend, messages = ui
    backend.coach.start("sample-application")
    backend.coach.finish("", "", "")
    backend.coach.submit_scores({})
    assert backend.tutor.store.xp_total() == 20
    run_id = backend.coach.history()[0]["id"]
    assert backend.deleteCaseHistory(run_id)
    assert backend.caseHistory() == []
    assert backend.tutor.store.xp_total() == 0
    assert messages == []


def test_mock_case_editors_and_table_use_available_width(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 2)
    cases = _find(win, "MockCasePage")
    QMetaObject.invokeMethod(cases, "start", Qt.DirectConnection,
                             Q_ARG("QVariant", "sample-application"))
    QMetaObject.invokeMethod(cases, "request", Qt.DirectConnection,
                             Q_ARG("QVariant", "Observation"))
    qtbot.wait(60)

    structure = next(
        obj for obj in cases.findChildren(QObject)
        if (obj.property("placeholderText") or "").startswith("Build your issue tree")
    )
    assert structure.width() > 300
    assert structure.height() > 500
    frame = next(obj for obj in cases.findChildren(QObject)
                 if obj.objectName() == "structureEditorFrame")
    assert structure.x() == 0
    assert structure.y() == 0
    assert abs(frame.width() - structure.width()) <= 2
    assert abs(frame.height() - structure.height()) <= 2
    assert structure.property("text") == ""
    assert structure.property("placeholderText").startswith("Build your issue tree")
    structure.setProperty("text", "K")
    assert structure.property("placeholderText") == ""
    structure.setProperty("text", "")
    assert structure.property("placeholderText").startswith("Build your issue tree")
    scroll_view = structure.parent()
    structure.setProperty("text", "\n".join(f"Issue branch {index}" for index in range(100)))
    qtbot.wait(30)
    assert structure.width() <= scroll_view.width()
    assert structure.height() > scroll_view.height()

    revealed = cases.property("revealed").toVariant()
    table = revealed[0]["table"]
    assert all(len(row) == len(table["headers"]) for row in table["rows"])
    assert messages == []
