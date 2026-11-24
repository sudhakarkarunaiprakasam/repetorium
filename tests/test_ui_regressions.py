import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, qmlContext
from test_ui import _find
from test_ui import ui as ui_fixture

import repetorium.packs as pack_module
from repetorium.paths import QML_DIR

ui = ui_fixture


def invoke(obj, method, *args):
    arguments = [Q_ARG("QVariant", argument) for argument in args]
    assert QMetaObject.invokeMethod(obj, method, Qt.DirectConnection, *arguments)


def evaluate(obj, source):
    expression = QQmlExpression(qmlContext(obj), obj, source)
    value, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return value.toVariant() if hasattr(value, "toVariant") else value


def contrast_ratio(foreground, background):
    def luminance(color):
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _named(root, name):
    result = root.findChild(QObject, name)
    assert result is not None, f"Could not find {name}"
    return result


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_brand_palette_meets_contrast_targets(ui, qtbot, theme):
    win, _, _ = ui
    win.setProperty("theme", theme)
    qtbot.wait(30)

    palette = json.loads(evaluate(win, "JSON.stringify(brandPalette)"))
    for foreground in (
        "foreground", "mutedForeground", "accent", "teal", "green", "blue",
        "coral", "plum", "gold", "warningText", "dangerText", "successText",
    ):
        assert contrast_ratio(palette[foreground], palette["surface"]) >= 4.5, (
            f"{theme} {foreground} text has insufficient contrast on surface"
        )
    assert contrast_ratio(palette["accent"], palette["sidebar"]) >= 4.5
    assert contrast_ratio(palette["onPrimary"], palette["primary"]) >= 4.5
    assert contrast_ratio(palette["mutedForeground"], palette["rowSurface"]) >= 4.5
    assert contrast_ratio(palette["featureForeground"], palette["feature"]) >= 4.5
    assert contrast_ratio(palette["featureMutedForeground"], palette["feature"]) >= 4.5
    assert contrast_ratio(palette["onStatus"], palette["successSurface"]) >= 4.5
    assert contrast_ratio(palette["onStatus"], palette["dangerSurface"]) >= 4.5
    assert contrast_ratio(palette["legendForeground"], palette["legendBackground"]) >= 4.5
    assert contrast_ratio(palette["legendBorder"], palette["legendBackground"]) >= 3
    assert contrast_ratio(palette["legendIndicatorBorder"], palette["legendBackground"]) >= 3
    assert contrast_ratio(palette["outline"], palette["surface"]) >= 3
    assert contrast_ratio(palette["connection"], palette["surface"]) >= 3
    assert contrast_ratio(palette["outline"], palette["canvas"]) >= 3
    assert contrast_ratio(palette["outline"], palette["controlSurface"]) >= 3
    assert contrast_ratio(palette["foreground"], palette["controlSurface"]) >= 4.5

    chart_colors = json.loads(evaluate(win, "JSON.stringify(BrandColors.chartColors(theme))"))
    for color in chart_colors:
        assert contrast_ratio(color, palette["surface"]) >= 4.5, (
            f"{theme} chart color {color} has insufficient contrast on surface"
        )

    knowledge_map = _find(win, "KnowledgeMapPage")
    status_colors = json.loads(evaluate(knowledge_map, "JSON.stringify(statusColors)"))
    for status, color in status_colors.items():
        if color != "transparent":
            assert contrast_ratio("#ffffff", color) >= 4.5, (
                f"{theme} {status} labels have insufficient contrast"
            )


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_learn_lesson_button_text_contrasts_with_primary(ui, qtbot, theme):
    win, _, _ = ui
    win.setProperty("theme", theme)
    qtbot.wait(30)
    palette = json.loads(evaluate(win, "JSON.stringify(brandPalette)"))
    dashboard = _find(win, "DashboardPage")
    button = _named(dashboard, "startLessonButton")

    info = json.loads(evaluate(dashboard, "JSON.stringify(info)"))
    for learning_plan in ([], [{"id": "sample", "title": "Sample lesson"}]):
        info["learningPlan"] = learning_plan
        dashboard.setProperty("info", info)
        qtbot.wait(20)
        enabled = button.property("enabled")
        foreground = evaluate(button, "contentItem.color.toString()")
        background = palette["primary"] if enabled else palette["rowSurface"]
        expected_foreground = palette["onPrimary"] if enabled else palette["mutedForeground"]
        assert evaluate(button, "background.color.toString()") == background
        assert foreground == expected_foreground
        assert contrast_ratio(foreground, background) >= 4.5


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_secondary_button_and_card_boundaries_have_contrast(ui, qtbot, theme):
    win, _, _ = ui
    win.setProperty("theme", theme)
    win.setProperty("page", 4)
    qtbot.wait(30)

    palette = json.loads(evaluate(win, "JSON.stringify(brandPalette)"))
    library = _find(win, "KnowledgeLibraryPage")
    card = _named(library, "libraryStep1")
    button = _named(library, "downloadContentFormatInstructions")

    card_border = evaluate(card, "background.border.color.toString()")
    button_background = evaluate(button, "background.color.toString()")
    button_border = evaluate(button, "background.border.color.toString()")
    button_text = evaluate(button, "contentItem.color.toString()")

    assert evaluate(card, "background.color.toString()") == palette["surface"]
    assert contrast_ratio(card_border, palette["canvas"]) >= 3
    assert contrast_ratio(card_border, palette["surface"]) >= 3
    assert button_background == palette["controlSurface"]
    assert button_text == palette["foreground"]
    assert contrast_ratio(button_text, button_background) >= 4.5
    assert contrast_ratio(button_border, button_background) >= 3
    assert contrast_ratio(button_border, palette["surface"]) >= 3


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_mock_test_method_selection_has_contrast(ui, qtbot, theme):
    win, _, _ = ui
    win.setProperty("theme", theme)
    win.setProperty("page", 2)
    qtbot.wait(30)

    mock = _find(win, "MockTestPage")
    mock.setProperty("methods", [
        {"id": "case_practice", "title": "Case Practice"},
        {"id": "skill_exam", "title": "Mock Tests"},
    ])
    mock.setProperty("selectedMethod", "case_practice")
    qtbot.wait(30)

    palette = json.loads(evaluate(win, "JSON.stringify(brandPalette)"))
    repeater = _named(mock, "mockTestMethodRepeater")
    for index, selected in enumerate((True, False)):
        foreground = evaluate(repeater, f"itemAt({index}).contentItem.color.toString()")
        background = evaluate(repeater, f"itemAt({index}).background.color.toString()")
        expected_foreground = palette["onPrimary"] if selected else palette["foreground"]
        expected_background = palette["primary"] if selected else palette["rowSurface"]
        assert foreground == expected_foreground
        assert background == expected_background
        assert contrast_ratio(foreground, background) >= 4.5


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_map_search_placeholder_uses_accessible_muted_color(ui, qtbot, theme):
    win, _, _ = ui
    win.setProperty("theme", theme)
    qtbot.wait(30)

    palette = json.loads(evaluate(win, "JSON.stringify(brandPalette)"))
    search = _named(_find(win, "KnowledgeMapPage"), "mapSearch")
    placeholder_color = evaluate(search, "placeholderTextColor.toString()")
    assert placeholder_color == palette["mutedForeground"]
    assert contrast_ratio(placeholder_color, palette["surface"]) >= 4.5


def test_all_qml_label_surfaces_explicitly_import_safe_default():
    for path in QML_DIR.glob("*.qml"):
        source = path.read_text(encoding="utf-8")
        if path.name == "Label.qml":
            assert "textFormat: Text.PlainText" in source
        elif path.name == "MathText.qml":
            assert "textFormat: Text.RichText" in source
            assert "escapeHtml" in source
        elif "Label {" in source:
            assert 'import "."' in source, path.name
        if path.name != "MathText.qml":
            assert "Text.StyledText" not in source and "Text.RichText" not in source, path.name


def test_pack_table_and_case_text_are_rendered_as_plain_text():
    data_table = (QML_DIR / "DataTable.qml").read_text(encoding="utf-8")
    case_page = (QML_DIR / "MockCasePage.qml").read_text(encoding="utf-8")

    assert data_table.count("textFormat: Text.PlainText") == 2
    assert "textFormat: Text.PlainText" in case_page


def test_diagnostic_remains_supported_without_dashboard_action(ui):
    win, backend, messages = ui
    dashboard = _find(win, "DashboardPage")
    assert dashboard is not None
    assert dashboard.findChild(QObject, "startPlacementDiagnostic") is None
    library = _find(win, "KnowledgeLibraryPage")
    assert library.findChild(QObject, "startPlacementCheck") is not None
    assert backend.startDiagnostic()["kind"] == "diagnostic"
    assert messages == []


def test_dashboard_has_five_metric_cards_and_two_learning_lists(ui, qtbot):
    win, _, messages = ui
    dashboard = _find(win, "DashboardPage")
    qtbot.wait(30)
    assert json.loads(evaluate(win, "JSON.stringify(navItems)")) == [
        "Dashboard", "Skill Map", "Library", "Settings", "About and Credits",
    ]

    top_cards = [
        _named(dashboard, "lessonsMetricCard"),
        _named(dashboard, "practiceMetricCard"),
        _named(dashboard, "testMetricCard"),
        _named(dashboard, "lessonMasteryMetricCard"),
        _named(dashboard, "streakMetricCard"),
    ]
    assert [card.property("title") for card in top_cards] == [
        "Lessons", "Review", "Test", "Lesson Mastery", "Consistency",
    ]
    consistency_card = top_cards[4]
    assert consistency_card.property("accentColor") == \
        evaluate(dashboard, "brandPalette.mutedForeground")
    assert consistency_card.property("actionText") == ""
    columns = dashboard.property("metricColumns")
    for start in range(0, len(top_cards), columns):
        row_cards = top_cards[start:start + columns]
        assert max(card.y() for card in row_cards) - min(card.y() for card in row_cards) <= 8
    if columns == 3:
        assert abs(top_cards[0].y() - top_cards[1].y()) <= 8
        assert abs(top_cards[1].y() - top_cards[2].y()) <= 8
        assert abs(top_cards[3].y() - top_cards[4].y()) <= 8
        assert top_cards[3].y() > top_cards[0].y()

    learning = _named(dashboard, "learningPlanCard")
    reviews = _named(dashboard, "reviewDueCard")
    assert _named(learning, "learningPlanHeading").property("text") == "Learning Plan"
    assert _named(reviews, "reviewDueHeading").property("text") == "Review Due"
    review_card = _named(dashboard, "practiceMetricCard")
    info = json.loads(evaluate(dashboard, "JSON.stringify(info)"))
    assert review_card.property("value") == str(info["dueCount"])
    assert review_card.property("unit") == (
        f"{info['dueCount']} review{'s' if info['dueCount'] != 1 else ''} due now"
    )
    assert review_card.property("caption") == (
        f"{info['practiceQuizzesThisWeek']} "
        f"{'quiz' if info['practiceQuizzesThisWeek'] == 1 else 'quizzes'} · "
        f"{info['reviewsThisWeek']} "
        f"{'review' if info['reviewsThisWeek'] == 1 else 'reviews'} completed this week"
    )
    lesson_mastery_card = _named(dashboard, "lessonMasteryMetricCard")
    assert lesson_mastery_card.property("value") == str(info["mastered"])
    assert lesson_mastery_card.property("unit") == "/ " + str(info["total"])
    lesson_button = _named(_named(dashboard, "lessonsMetricCard"), "startLessonButton")
    review_button = _named(_named(dashboard, "practiceMetricCard"), "startReviewButton")
    mock_test_button = _named(_named(dashboard, "testMetricCard"), "startMockTestButton")
    assert lesson_button.property("text") == "Learn"
    assert review_button.property("text") == "Review"
    assert lesson_button.property("highlighted")
    assert not review_button.property("highlighted")
    assert not mock_test_button.property("highlighted")
    assert _named(_named(dashboard, "testMetricCard"), "startMockTestButton").property("text") == "Start"
    widths = [card.width() for card in top_cards]
    assert max(widths) - min(widths) < 1
    assert [card.height() for card in top_cards] == pytest.approx(
        [dashboard.property("metricHeight")] * 5
    )
    assert learning.findChild(QObject, "startLessonButton") is None
    assert reviews.findChild(QObject, "startReviewButton") is None
    if dashboard.property("stackPanels"):
        assert reviews.y() >= learning.y() + learning.height()
    else:
        assert abs(learning.y() - reviews.y()) < 1
        assert learning.height() == pytest.approx(360)
        assert reviews.height() == pytest.approx(360)
    assert not _named(reviews, "reviewDueHeadingBadge").isVisible()
    metric_bottom = max(
        card.mapToItem(dashboard, 0, 0).y() + card.height() for card in top_cards
    )
    learning_top = learning.mapToItem(dashboard, 0, 0).y()
    assert learning_top - metric_bottom >= 20
    assert _find(win, "StatsPage") is None
    assert messages == []


def test_inactive_dashboard_and_settings_skip_expensive_refreshes(
    ui, qtbot, monkeypatch,
):
    win, backend, messages = ui
    original_list_packs = pack_module.list_packs
    original_dashboard = backend.tutor.dashboard
    scans = []
    dashboard_calls = []

    def count_pack_scans():
        scans.append(True)
        return original_list_packs()

    def count_dashboard_calls():
        dashboard_calls.append(True)
        return original_dashboard()

    monkeypatch.setattr(pack_module, "list_packs", count_pack_scans)
    monkeypatch.setattr(backend.tutor, "dashboard", count_dashboard_calls)
    win.setProperty("page", 1)
    qtbot.wait(30)
    scans.clear()
    dashboard_calls.clear()
    backend.progressChanged.emit()
    assert scans == []
    assert dashboard_calls == []

    win.setProperty("page", 5)
    qtbot.wait(30)
    scans.clear()
    dashboard_calls.clear()
    backend.progressChanged.emit()
    assert scans == []
    assert dashboard_calls == []
    assert messages == []


def test_library_and_map_refreshes_are_active_and_coalesced(ui, qtbot, monkeypatch):
    win, backend, messages = ui
    original_list_packs = pack_module.list_packs
    original_knowledge_map = backend.tutor.knowledge_map
    scans = []
    map_calls = []

    def count_pack_scans():
        scans.append(True)
        return original_list_packs()

    def count_knowledge_map():
        map_calls.append(True)
        return original_knowledge_map()

    monkeypatch.setattr(pack_module, "list_packs", count_pack_scans)
    monkeypatch.setattr(backend.tutor, "knowledge_map", count_knowledge_map)

    win.setProperty("page", 1)
    qtbot.wait(30)
    scans.clear()
    map_calls.clear()
    backend.contentChanged.emit()
    backend.contentPacksChanged.emit()
    backend.progressChanged.emit()
    qtbot.wait(30)
    assert scans == []
    assert map_calls == []

    win.setProperty("page", 4)
    qtbot.wait(30)
    scans.clear()
    backend.contentChanged.emit()
    backend.contentPacksChanged.emit()
    qtbot.wait(30)
    assert len(scans) == 1

    win.setProperty("page", 3)
    qtbot.wait(30)
    map_calls.clear()
    backend.contentChanged.emit()
    backend.progressChanged.emit()
    qtbot.wait(30)
    assert len(map_calls) == 1

    win.setProperty("page", 1)
    qtbot.wait(30)
    map_calls.clear()
    backend.contentChanged.emit()
    backend.progressChanged.emit()
    qtbot.wait(30)
    assert map_calls == []
    assert messages == []


def test_skill_map_clears_search_when_pack_graph_changes(ui, qtbot, monkeypatch):
    win, backend, messages = ui
    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    page.setProperty("searchText", "python")
    assert page.property("matchCount") == 0

    monkeypatch.setattr(backend.tutor, "knowledge_map", lambda: {
        "nodes": [{
            "id": "finance.skill",
            "title": "Finance fundamentals",
            "category": "finance",
            "depth": 0,
            "status": "available",
            "definition": "Apply the stated financial assumptions.",
            "domains": ["finance"],
            "sources": [],
            "prerequisites": [],
            "connections": [],
            "cases": [],
            "reps": 0,
            "dueInDays": None,
        }],
        "edges": [],
    })
    backend.contentChanged.emit()
    qtbot.wait(30)

    assert page.property("searchText") == ""
    assert page.property("matchCount") == 1
    assert len(evaluate(page, "visibleNodes")) == 1
    assert messages == []


def test_learning_plan_columns_stay_aligned(ui, qtbot):
    win, _, messages = ui
    dashboard = _find(win, "DashboardPage")
    info = json.loads(evaluate(dashboard, "JSON.stringify(info)"))
    info["learningPlan"] = [
        {"id": "one", "title": "Compare business structures",
         "learningPack": "Corporate Finance Pack",
         "available": True},
        {"id": "two", "title": "Interpret cash-flow ratios",
         "learningPack": "Financial Analysis Pack",
         "available": False},
    ]
    dashboard.setProperty("info", info)
    qtbot.wait(30)

    panel = _named(dashboard, "learningPlanCard")
    assert not _named(panel, "learningPlanHeadingBadge").isVisible()
    items = [panel]
    for item in items:
        items.extend(item.childItems())
    items_by_name = {item.objectName(): item for item in items if item.objectName()}
    title_header = _named(panel, "learningPlanColumnTitle")
    pack_header = _named(panel, "learningPlanColumnPack")
    title_positions = [
        items_by_name[f"learningPlanHeadingTitle{index}"].mapToItem(panel, 0, 0).x()
        for index in range(2)
    ]
    pack_cells = [items_by_name[f"learningPlanHeadingMeta{index}"] for index in range(2)]
    pack_positions = [cell.mapToItem(panel, 0, 0).x() for cell in pack_cells]

    assert title_header.mapToItem(panel, 0, 0).x() == pytest.approx(title_positions[0])
    assert title_positions[1] == pytest.approx(title_positions[0])
    assert pack_header.property("text") == "Learning Pack"
    assert pack_header.mapToItem(panel, 0, 0).x() == pytest.approx(pack_positions[0])
    assert pack_positions[1] == pytest.approx(pack_positions[0])
    assert pack_cells[0].width() == pytest.approx(pack_cells[1].width())
    assert pack_cells[0].property("text") == "Corporate Finance Pack"
    assert pack_cells[1].property("text") == "Financial Analysis Pack"
    assert items_by_name["learningPlanHeadingLock0"].isVisible() is False
    assert items_by_name["learningPlanHeadingLock1"].isVisible() is True
    assert messages == []


def test_dashboard_renders_review_due_dates(ui, qtbot):
    win, _, messages = ui
    dashboard = _find(win, "DashboardPage")
    info = json.loads(evaluate(dashboard, "JSON.stringify(info)"))
    info["criticalReviews"] = [
        {"id": "today", "title": "Review today", "overdueDays": 0, "dueNow": True,
         "daysUntilDue": 0},
        {"id": "later-today", "title": "Review later today", "overdueDays": 0,
         "dueNow": False, "daysUntilDue": 0},
        {"id": "tomorrow", "title": "Review tomorrow", "overdueDays": 0, "dueNow": False,
         "daysUntilDue": 1},
        {"id": "later", "title": "Review later", "overdueDays": 0, "dueNow": False,
         "daysUntilDue": 3},
    ]
    dashboard.setProperty("info", info)
    qtbot.wait(30)

    panel = _named(dashboard, "reviewDueCard")
    items = [panel]
    for item in items:
        items.extend(item.childItems())
    items_by_name = {item.objectName(): item for item in items if item.objectName()}
    status_colors = json.loads(evaluate(dashboard, "JSON.stringify(statusColors)"))
    title_header = _named(panel, "reviewDueColumnTitle")
    due_header = _named(panel, "reviewDueColumnMeta")
    assert title_header.property("text") == "Skill"
    assert due_header.property("text") == "Due"
    assert title_header.mapToItem(panel, 0, 0).x() == pytest.approx(
        items_by_name["reviewDueHeadingTitle0"].mapToItem(panel, 0, 0).x()
    )
    assert due_header.mapToItem(panel, 0, 0).x() == pytest.approx(
        items_by_name["reviewDueHeadingMeta0"].mapToItem(panel, 0, 0).x()
    )
    assert items_by_name["reviewDueHeadingMeta0"].property("text") == "Due today"
    assert items_by_name["reviewDueHeadingMeta1"].property("text") == "Due later today"
    assert items_by_name["reviewDueHeadingMeta2"].property("text") == "Due tomorrow"
    assert items_by_name["reviewDueHeadingMeta3"].property("text") == "Due in 3 days"
    assert items_by_name["reviewDueHeadingIndicator0"].property("color").name() \
        == status_colors["due"]
    assert items_by_name["reviewDueHeadingIndicator1"].property("color").name() \
        == status_colors["mastered"]
    assert items_by_name["reviewDueHeadingIndicator2"].property("color").name() \
        == status_colors["mastered"]
    assert messages == []


def test_dashboard_actions_choose_lesson_review_and_test(ui, qtbot):
    win, backend, messages = ui
    dashboard = _find(win, "DashboardPage")
    assert _named(dashboard, "streakMetricCard").property("title") == "Consistency"
    assert _named(dashboard, "practiceMetricCard").property("unit") == "0 reviews due now"
    lesson_card = _named(dashboard, "lessonsMetricCard")
    review_card = _named(dashboard, "practiceMetricCard")
    test_card = _named(dashboard, "testMetricCard")
    lesson_outline = _named(lesson_card, "lessonsMetricCardBackground")
    review_outline = _named(review_card, "practiceMetricCardBackground")
    test_outline = _named(test_card, "testMetricCardBackground")
    assert lesson_outline.property("outlineWidth") == 2
    assert lesson_outline.property("outlineColor").name() \
        == evaluate(dashboard, "BrandColors.logoAmber")
    assert review_outline.property("outlineWidth") == 1
    assert test_outline.property("outlineWidth") == 1
    invoke(_named(dashboard, "startMockTestButton"), "click")
    assert win.property("page") == 2

    win.setProperty("page", 0)
    next_lesson_id = backend.dashboard()["learningPlan"][0]["id"]
    invoke(_named(dashboard, "startLessonButton"), "click")
    assert win.property("page") == 1
    assert backend.tutor.task.kind == "lesson"
    assert backend.tutor.task.skill_ids[0] == next_lesson_id

    skill_id = backend.tutor.task.skill_ids[0]
    state = backend.tutor.states[skill_id]
    state.status = "mastered"
    state.reps = max(1, state.reps)
    state.due = backend.tutor.clock() - 86_400
    backend.tutor.store.save_states([state])
    backend.progressChanged.emit()

    win.setProperty("page", 0)
    qtbot.wait(30)
    review_button = _named(dashboard, "startReviewButton")
    assert review_button.property("enabled")
    qtbot.wait(30)
    assert review_card.property("unit") == "1 review due now"
    assert review_button.property("highlighted")
    assert not _named(dashboard, "startLessonButton").property("highlighted")
    assert review_outline.property("outlineWidth") == 2
    assert review_outline.property("outlineColor").name() \
        == evaluate(dashboard, "BrandColors.logoAmber")
    assert lesson_outline.property("outlineWidth") == 1
    invoke(review_button, "click")
    assert win.property("page") == 1
    assert backend.tutor.task.kind == "review"
    assert messages == []


@pytest.mark.parametrize("size", [(980, 640), (1280, 820)])
def test_dashboard_fits_or_scrolls_without_clipping(ui, qtbot, size):
    win, _, messages = ui
    win.setWidth(size[0])
    win.setHeight(size[1])
    win.setProperty("page", 0)
    dashboard = _find(win, "DashboardPage")
    info = json.loads(evaluate(dashboard, "JSON.stringify(info)"))
    row = {"id": "x", "title": "A long skill title that must elide cleanly", "category": "Category",
           "overdueDays": 2}
    info.update(learningPlan=[row] * 7, criticalReviews=[row] * 7)
    dashboard.setProperty("info", info)
    qtbot.wait(30)

    cards = [_named(dashboard, name) for name in (
        "lessonsMetricCard", "practiceMetricCard", "testMetricCard",
        "lessonMasteryMetricCard", "streakMetricCard")]
    columns = dashboard.property("metricColumns")
    assert len({round(cards[index].y()) for index in range(5)}) == \
        dashboard.property("metricRows")
    assert all(
        abs(cards[index].y() - cards[index + 1].y()) <= 1
        for index in range(5) if index % columns != columns - 1 and index + 1 < 5
    )
    content_height = dashboard.property("contentHeight")
    metric_height = _named(dashboard, "metricCardsGrid").height()
    overview_height = _named(dashboard, "overviewPanelsGrid").height()
    assert content_height >= metric_height + overview_height
    assert messages == []


@pytest.mark.parametrize("menu_expanded", [True, False])
def test_dashboard_reflows_without_overlap_in_narrow_window(ui, qtbot, menu_expanded):
    win, _, messages = ui
    win.setProperty("menuExpanded", menu_expanded)
    win.setWidth(560)
    win.setHeight(760)
    win.setProperty("page", 0)
    dashboard = _find(win, "DashboardPage")
    qtbot.wait(30)

    cards = [_named(dashboard, name) for name in (
        "lessonsMetricCard", "practiceMetricCard", "testMetricCard",
        "lessonMasteryMetricCard", "streakMetricCard",
        "learningPlanCard", "reviewDueCard")]
    assert _named(dashboard, "metricCardsGrid").height() == pytest.approx(
        dashboard.property("metricGridHeight")
    )
    rects = [(card.mapToItem(dashboard, 0, 0), card.width(), card.height()) for card in cards]
    for index, (first, width, height) in enumerate(rects):
        assert first.x() >= 0 and first.x() + width <= dashboard.width() + 1
        for second, other_width, other_height in rects[index + 1:]:
            assert (first.x() + width <= second.x() + 1 or second.x() + other_width <= first.x() + 1
                    or first.y() + height <= second.y() + 1 or second.y() + other_height <= first.y() + 1)
    assert messages == []


def test_diagnostic_explains_guessed_answers_are_inconclusive(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    practice.setProperty("task", {"kind": "diagnostic"})
    practice.setProperty("phase", "question")
    notice = _named(practice, "diagnosticGuessNotice")
    assert notice.property("visible")
    assert '"I guessed" is inconclusive' in notice.property("text")
    assert messages == []


def test_rich_lesson_blocks_render_without_executing_code(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    assert practice is not None
    practice.setProperty("task", {
        "kind": "lesson",
        "title": "Mixed modalities",
        "guide": {"definition": "A measured relationship."},
        "lesson": [
            {"type": "math", "content": "\\sum_{i=1}^n i"},
            {"type": "code", "language": "python", "code": (
                "age_text = input('Enter your age:')\n"
                "try:\n"
                "    age = int(age_text)"
            )},
            {"type": "table", "headers": ["Trial", "Value"], "rows": [[1, 2.0]]},
            {"type": "chart", "chart": {
                "type": "scatter",
                "title": "Value by trial",
                "labels": ["1", "2"],
                "unit": "units",
                "series": [{"name": "Measurement", "values": [-2.0, 3.0]}],
            }},
        ],
    })
    practice.setProperty("phase", "intro")
    qtbot.wait(100)
    guide = _named(practice, "practiceLessonGuide")
    blocks = _named(guide, "lessonContentBlocks")
    assert evaluate(blocks, "count") == 4
    assert "∑" in evaluate(blocks, "itemAt(0).children[0].formattedText")
    code_block = evaluate(blocks, "itemAt(1).children[1]")
    assert code_block.objectName() == "lessonCodeBlock"
    assert evaluate(code_block, "isDisplayOnly")
    expected_code = "age_text = input('Enter your age:')\ntry:\n    age = int(age_text)"
    assert evaluate(code_block, "displayedCode") == expected_code
    assert _named(code_block, "codeLineNumbers").property("text") == "1\n2\n3"
    copy_button = _named(code_block, "copyCodeButton")
    evaluate(copy_button, "clicked()")
    assert copy_button.property("text") == "Copied"
    table = evaluate(blocks, "itemAt(2).children[3]")
    assert table.objectName() == "lessonDataTable"
    headers = _named(table, "tableHeaderCells")
    assert evaluate(headers, "count") == 2
    assert all(
        evaluate(headers, f"itemAt({index}).horizontalAlignment === Text.AlignLeft")
        for index in range(2)
    )
    rows = _named(table, "tableDataRows")
    assert evaluate(rows, "itemAt(0).bodyCells.count") == 2
    assert all(
        evaluate(
            rows,
            f"itemAt(0).bodyCells.itemAt({index}).horizontalAlignment === Text.AlignLeft",
        )
        for index in range(2)
    )
    assert messages == []


def test_mock_test_methods_wrap_to_content_sized_matrix(ui, qtbot):
    win, _, messages = ui
    win.setWidth(760)
    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("methods", [
        {"id": f"method_{index}", "title": title}
        for index, title in enumerate([
            "Case Practice",
            "Skill-aligned Test",
            "Structured Mock Test",
            "Full-length Comprehensive Assessment",
        ])
    ])
    qtbot.wait(50)

    matrix = win.findChild(QObject, "mockTestMethodMatrix")
    repeater = win.findChild(QObject, "mockTestMethodRepeater")
    assert evaluate(repeater, "count") == 4
    widths = [evaluate(repeater, f"itemAt({index}).width") for index in range(4)]
    rows = [evaluate(repeater, f"itemAt({index}).y") for index in range(4)]
    assert len({round(width) for width in widths}) > 1
    assert len({round(row) for row in rows}) > 1
    assert matrix.width() > 0
    assert mock.property("selectedMethod") == "case_practice"
    assert messages == []


def test_mock_exam_picker_has_no_pack_exam_presets(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    qtbot.wait(30)
    exam = _find(win, "MockExamPage")
    assert exam.findChild(QObject, "examOptionMatrix") is None
    assert exam.property("selectedSkillIds").toVariant() == []
    assert _named(exam, "examSkillSearch").property("visible")
    exam.setProperty("skills", [
        {"id": f"synthetic.{index}", "title": f"Skill {index}", "category": "Synthetic"}
        for index in range(1000)
    ])
    qtbot.wait(30)
    skill_grid = _named(exam, "examSkillRepeater")
    assert evaluate(skill_grid, "count") == 1000
    assert evaluate(skill_grid, "itemAt(0) !== null")
    assert evaluate(skill_grid, "itemAt(999) === null")
    assert messages == []


def test_mock_exam_history_shows_metadata_and_skill_breakdown(ui, qtbot):
    win, backend, messages = ui
    started = 1_800_000_000
    results = [
        {"skill": "Clear writing", "prompt": "Choose a concise summary.",
         "response": "A concise summary", "correct": True, "answer": "A concise summary",
         "solution": "Keep the summary focused.", "hints_used": 0},
        {"skill": "Evidence quality", "prompt": "Identify the stronger evidence.",
         "response": "A vague opinion", "correct": False, "answer": "Observed behavior",
         "solution": "Prefer specific examples.", "hints_used": 1},
    ]
    cursor = backend.tutor.store.conn.execute(
        "INSERT INTO mock_test_runs "
        "(title, started, finished, correct, total, elapsed_seconds, results) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Test history", started, started + 90, 1, 2, 90, json.dumps(results)),
    )
    run_id = cursor.lastrowid

    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    qtbot.wait(30)
    exam = _find(win, "MockExamPage")
    history = _named(exam, "examHistoryRepeater")
    assert evaluate(history, "count") == 1
    assert evaluate(exam, "history[0].minutes === undefined")
    entry = evaluate(history, "itemAt(0)")
    assert _named(entry, "examHistoryRunLabel").property("text") == f"Test #{run_id}"
    date_label = _named(entry, "examHistoryDateLabel")
    assert date_label.property("text") == evaluate(exam, "fmtDateTime(history[0].started)")
    assert _named(entry, "examHistoryScoreLabel").property("text") == "1/2 correct"

    invoke(_named(entry, "examHistoryDetailsButton"), "click")
    dialog = _named(exam, "examHistoryDialog")
    assert dialog.property("visible")
    correct = _named(dialog, "examHistoryCorrectSkills")
    review = _named(dialog, "examHistoryReviewSkills")
    assert evaluate(correct, "count") == 1
    assert evaluate(correct, "itemAt(0).modelData.skill") == "Clear writing"
    assert evaluate(review, "count") == 1
    assert evaluate(review, "itemAt(0).modelData.skill") == "Evidence quality"
    assert messages == []


def test_large_views_wait_until_active_after_content_change(ui, qtbot, monkeypatch):
    win, backend, messages = ui
    map_calls = []
    skill_calls = []
    original_map = backend.tutor.knowledge_map
    original_skills = backend.skillExamSkills

    def count_map():
        map_calls.append(True)
        return original_map()

    def count_skills():
        skill_calls.append(True)
        return original_skills()

    monkeypatch.setattr(backend.tutor, "knowledge_map", count_map)
    monkeypatch.setattr(backend, "skillExamSkills", count_skills)
    backend.contentChanged.emit()
    qtbot.wait(20)

    assert map_calls == []
    assert skill_calls == []

    win.setProperty("page", 3)
    qtbot.wait(30)
    assert len(map_calls) == 1

    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    qtbot.wait(30)
    assert skill_calls
    assert messages == []


def test_mock_exam_question_count_selection_and_difficulty(ui, qtbot):
    win, backend, messages = ui
    backend.tutor.states["sample.root"].status = "mastered"
    backend.tutor.states["sample.choice"].status = "mastered"
    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    qtbot.wait(40)
    exam = _find(win, "MockExamPage")
    repeater = _named(exam, "examSkillRepeater")
    assert evaluate(repeater, "count") >= 2
    initial_count = evaluate(exam, "selectedSkillIds.length")
    assert initial_count == 0
    question_count = _named(exam, "examQuestionCountSetting")
    assert question_count.property("from") == 1
    first_skill = backend.skillExamSkills()[0]
    search = _named(exam, "examSkillSearch")
    search.setProperty("text", first_skill["title"])
    exam.setProperty("skillSearch", first_skill["title"])
    assert evaluate(exam, "filteredSkills.length") == 1
    search_repeater = _named(exam, "examSkillRepeater")
    invoke(evaluate(search_repeater, "itemAt(0)"), "click")
    assert evaluate(exam, "selectedSkillIds.length") == 1
    assert evaluate(evaluate(search_repeater, "itemAt(0)"), "text") == (
        first_skill["title"] + " · " + first_skill["category"]
    )
    search.setProperty("text", "")
    exam.setProperty("skillSearch", "")
    assert evaluate(exam, "filteredSkills.length") >= 2
    invoke(evaluate(search_repeater, "itemAt(1)"), "click")
    assert evaluate(exam, "selectedSkillIds.length") == 2
    assert question_count.property("from") == 2
    assert question_count.property("value") == 2
    question_count.setProperty("value", 1)
    assert question_count.property("value") == 2
    question_count.setProperty("value", 4)
    invoke(question_count, "valueModified")
    assert exam.property("questionCount") == 4
    difficulty_repeater = _named(exam, "examDifficultyRepeater")
    assert evaluate(difficulty_repeater, "count") == 3
    assert "XP" not in evaluate(difficulty_repeater, "itemAt(0).text")
    assert evaluate(difficulty_repeater, "itemAt(0).text") == "Easy"

    invoke(evaluate(difficulty_repeater, "itemAt(0)"), "click")
    assert exam.property("difficulty") == 1

    invoke(_named(exam, "startCustomSkillExam"), "click")
    assert exam.property("phase") == "question"
    assert len(backend.skill_exam.items) == 4
    assert {item.difficulty for item in backend.skill_exam.items} == {1}
    selected_ids = set(exam.property("selectedSkillIds").toVariant())
    tested_counts = {
        skill_id: sum(item.skill_id == skill_id for item in backend.skill_exam.items)
        for skill_id in selected_ids
    }
    assert min(tested_counts.values()) >= 1
    assert max(tested_counts.values()) - min(tested_counts.values()) <= 1
    assert evaluate(exam, "exam.total") == 4
    assert evaluate(exam, "exam.minutes === undefined")
    assert messages == []


def test_advanced_learning_settings_explain_and_persist(ui, qtbot):
    win, backend, messages = ui
    win.setProperty("page", 5)
    settings = _find(win, "SettingsPage")
    tabs = _named(settings, "settingsTabs")
    assert tabs.property("currentIndex") == 0
    advanced = _named(settings, "advancedLearningSettings")
    assert not advanced.isVisible()
    pack_section = _named(settings, "contentPackSelectionSection")
    assert pack_section.isVisible()
    tabs.setProperty("currentIndex", 1)
    qtbot.wait(30)

    assert advanced.isVisible()
    assert not pack_section.isVisible()
    info_names = [
        "masteryStreakInfo",
        "reviewGrowthFactorInfo",
        "maxReviewIntervalInfo",
        "reviewRetryInfo",
        "mixedQuizFrequencyInfo",
        "mixedQuizSizeInfo",
        "adaptivePresetInfo",
    ]
    for name in info_names:
        button = _named(settings, name)
        assert button.property("infoText")
        invoke(button, "click")
        dialog = _named(win, name + "Dialog")
        assert dialog.property("visible")
        assert dialog.property("title") == button.property("infoTitle")
        invoke(dialog, "close")

    invoke(_named(settings, "easyAdaptivePreset"), "click")
    assert backend.tutor.adaptive_settings.mastery_streak == 2
    assert backend.tutor.adaptive_settings.review_growth_factor == 3.0
    assert backend.tutor.adaptive_settings.max_review_interval_days == 360
    assert backend.tutor.adaptive_settings.review_retry_hours == 8
    assert backend.tutor.adaptive_settings.mixed_quiz_every == 12
    assert backend.tutor.adaptive_settings.mixed_quiz_size == 3

    invoke(_named(settings, "hardAdaptivePreset"), "click")
    assert backend.tutor.adaptive_settings.mastery_streak == 5
    assert backend.tutor.adaptive_settings.review_growth_factor == 1.5
    assert backend.tutor.adaptive_settings.max_review_interval_days == 60
    assert backend.tutor.adaptive_settings.review_retry_hours == 1
    assert backend.tutor.adaptive_settings.mixed_quiz_every == 4
    assert backend.tutor.adaptive_settings.mixed_quiz_size == 8

    invoke(_named(settings, "balancedAdaptivePreset"), "click")
    assert backend.tutor.adaptive_settings.mastery_streak == 3
    assert backend.tutor.adaptive_settings.review_growth_factor == 2.5
    assert backend.tutor.adaptive_settings.max_review_interval_days == 180
    assert backend.tutor.adaptive_settings.review_retry_hours == 4
    assert backend.tutor.adaptive_settings.mixed_quiz_every == 8
    assert backend.tutor.adaptive_settings.mixed_quiz_size == 5

    backend.setSetting("mastery_streak", 4)
    backend.setSetting("review_growth_factor", 2.0)
    backend.setSetting("max_review_interval_days", 120)
    backend.setSetting("review_retry_hours", 6)
    backend.setSetting("mixed_quiz_every", 10)
    backend.setSetting("mixed_quiz_size", 6)
    qtbot.wait(30)
    assert backend.tutor.adaptive_settings.mastery_streak == 4
    assert backend.tutor.scheduler.settings.review_growth_factor == 2.0
    assert backend.tutor.scheduler.settings.max_review_interval_days == 120
    assert backend.tutor.scheduler.settings.review_retry_hours == 6
    assert backend.tutor.adaptive_settings.mixed_quiz_every == 10
    assert backend.tutor.adaptive_settings.mixed_quiz_size == 6
    assert _named(settings, "masteryStreakSetting").property("value") == 4
    invoke(_named(settings, "resetAdaptiveDefaults"), "click")
    assert backend.tutor.adaptive_settings.mastery_streak == 3
    assert backend.tutor.adaptive_settings.review_growth_factor == 2.5
    assert backend.tutor.adaptive_settings.max_review_interval_days == 180
    assert backend.tutor.adaptive_settings.review_retry_hours == 4
    assert backend.tutor.adaptive_settings.mixed_quiz_every == 8
    assert backend.tutor.adaptive_settings.mixed_quiz_size == 5
    assert "restored to defaults" in _named(settings, "adaptiveSettingsMessage").property("text")
    practice = _find(win, "PracticePage")
    assert "Get 3 in a row" in _named(practice, "masteryStreakExplanation").property("text")
    assert messages == []


def test_spinbox_steppers_sit_on_opposite_sides(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 5)
    qtbot.wait(30)

    setting = _named(_find(win, "SettingsPage"), "lessonsPerWeekGoalSetting")
    assert evaluate(setting, "down.indicator.x") == 0
    assert evaluate(setting, "up.indicator.x + up.indicator.width") == pytest.approx(
        evaluate(setting, "width")
    )
    assert evaluate(setting, "up.indicator.children.length") == 3
    assert evaluate(setting, "up.indicator.children[1].width") == 2
    assert evaluate(setting, "up.indicator.children[1].height") == 12
    assert evaluate(setting, "down.indicator.width") == pytest.approx(
        evaluate(setting, "up.indicator.width")
    )
    assert evaluate(setting, "down.indicator.width") < evaluate(setting, "width") / 2

    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    qtbot.wait(30)
    exam = _find(win, "MockExamPage")
    assert exam.findChild(QObject, "examDurationSetting") is None
    assert messages == []


def test_math_text_formats_notation_and_escapes_markup(ui):
    win, _, messages = ui
    math = win.findChild(QObject, "practicePrompt")
    assert math is not None

    math.setProperty(
        "text",
        r"**Learning goal.** Calculate 2*3. What is f(x)=sqrt(x-4), x^2, and $\frac{1}{2}$? $$x^2 \geq 4$$ "
        '<img src="http://127.0.0.1:1/probe.png">',
    )
    formatted = evaluate(math, "formattedText")
    assert "<b>Learning goal.</b>" in formatted
    assert "2×3" in formatted
    assert "××Learning goal" not in formatted
    assert "√(x-4)" in formatted
    assert "<sup>2</sup>" in formatted
    assert "<sup>1</sup>⁄<sub>2</sub>" in formatted
    assert "<p align=\"center\"><big>x<sup>2</sup> ≥ 4</big></p>" in formatted
    assert "&lt;img" in formatted
    assert "<img" not in formatted
    assert messages == []


def test_choice_math_text_starts_after_radio_indicator(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    evaluate(practice, 'phase = "question"; item = {kind: "choice", choices: ["x^2"], '
             'unitHint: "", skillTitle: "", prompt: "", progress: ""}')
    qtbot.wait(20)

    answer = win.findChild(QObject, "practiceAnswer")
    assert evaluate(practice, "item.kind") == "choice"
    assert evaluate(answer, "item.kind") == "choice"
    repeater = answer.findChild(QObject, "choiceRepeater")
    assert evaluate(repeater, "count") == 1
    radio = evaluate(repeater, "itemAt(0)")
    assert evaluate(radio, "contentItem.formattedText") == "x<sup>2</sup>"
    assert evaluate(radio, "contentItem.leftPadding === indicator.width + spacing")
    assert evaluate(radio, "contentItem.children[0].x >= indicator.width + spacing")
    assert messages == []


def test_answer_input_supports_mixed_response_controls(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    answer = _named(win, "practiceAnswer")

    evaluate(practice, 'phase = "question"; item = {kind: "numeric", prompt: "Calculate", '
             'unitHint: "Enter a number", progress: "", skillTitle: "", '
             'difficultyLabel: "", estimatedMinutes: 1}')
    field = _named(answer, "answerTextField")
    assert field.property("visible")
    assert not evaluate(answer, "ready")
    field.setProperty("text", "A concise answer")
    assert evaluate(answer, "ready")

    evaluate(practice, 'item = {kind: "multi_select", prompt: "Select", choices: ["A", "B", "C"], '
             'progress: "", skillTitle: "", difficultyLabel: "", estimatedMinutes: 1}')
    multi = _named(answer, "multiSelectRepeater")
    assert evaluate(multi, "count") == 3
    evaluate(answer, "toggleChoice(0, true); toggleChoice(2, true)")
    assert evaluate(answer, "response") == "0,2"

    evaluate(practice, 'item = {kind: "matching", prompt: "Match", prompts: ["A", "B"], '
             'choices: ["A concrete situation exposes constraints and shows whether the proposed '
             'learner segment is useful", "Jobs remain understandable even when interface '
             'details change", "An episode reveals the context, actions, workarounds, and friction", '
             '"Unaided problem descriptions reveal what matters without prompt effects"], '
             'progress: "", skillTitle: "", difficultyLabel: "", '
             'estimatedMinutes: 1}')
    matching = _named(answer, "matchingRepeater")
    assert evaluate(matching, "count") == 2
    assert evaluate(answer, "JSON.stringify(matchSelections)") == "[-1,-1]"
    row = evaluate(matching, "itemAt(0)")
    combo = _named(row, "matchingComboBox")
    assert evaluate(combo, "currentIndex") == -1
    assert evaluate(combo, "displayText === ''")
    second_row = evaluate(matching, "itemAt(1)")
    second_combo = _named(second_row, "matchingComboBox")
    assert evaluate(second_combo, "currentIndex") == -1
    assert evaluate(second_combo, "displayText === ''")
    evaluate(combo, "popup.open()")
    qtbot.wait(50)
    option = evaluate(combo, "popup.contentItem.itemAtIndex(2)")
    assert option is not None
    assert evaluate(option, "contentItem.wrapMode === Text.WordWrap")
    assert evaluate(option, "contentItem.text === text")
    assert evaluate(option, "contentItem.implicitHeight > font.pixelSize")
    evaluate(option, "clicked()")
    assert evaluate(combo, "currentIndex") == 2
    assert evaluate(answer, "matchSelections[0]") == 2
    assert not evaluate(answer, "ready")
    evaluate(second_combo, "popup.open()")
    qtbot.wait(50)
    second_option = evaluate(second_combo, "popup.contentItem.itemAtIndex(0)")
    evaluate(second_option, "clicked()")
    assert evaluate(second_combo, "currentIndex") == 0
    assert evaluate(answer, "matchSelections[1]") == 0
    assert evaluate(answer, "response") == "2,0"
    assert evaluate(answer, "ready")
    assert messages == []


def test_all_authored_labels_use_plain_text_without_image_requests(ui, qtbot):
    win, _, messages = ui
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    markup = f'<img src="http://127.0.0.1:{server.server_port}/probe.png">literal'
    checked = 0
    try:
        for page in range(7):
            win.setProperty("page", page)
            qtbot.wait(20)
            labels = [
                obj for obj in win.findChildren(QObject)
                if obj.metaObject().className().startswith("Label_QMLTYPE")
                and "/repetorium/qml/" in qmlContext(obj).baseUrl().toString()
            ]
            assert labels, "The shared safe Label component must be used by QML pages"
            for label in labels:
                assert evaluate(label, "textFormat === Text.PlainText"), (
                    label.property("text"), qmlContext(label).baseUrl().toString())
                label.setProperty("text", markup)
                checked += 1
            qtbot.wait(30)
        assert checked > 30
        assert requests == []
        assert messages == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("phase", ["run", "debrief", "done"])
def test_case_navigation_preserves_session(ui, qtbot, phase):
    win, _, messages = ui
    win.setProperty("page", 2)
    cases = _find(win, "MockCasePage")
    invoke(cases, "start", "sample-application")
    cases.setProperty("phase", phase)
    notes = win.findChild(QObject, "caseNotes")
    notes.setProperty("text", "keep notes")
    cases.setProperty("elapsed", 17)
    win.setProperty("page", 0)
    win.setProperty("page", 2)
    qtbot.wait(30)
    assert cases.property("phase") == phase
    assert notes.property("text") == "keep notes"
    assert cases.property("elapsed") >= 17
    assert messages == []


@pytest.mark.parametrize("phase", ["question", "finish", "debrief"])
def test_exam_navigation_preserves_session(ui, qtbot, phase):
    win, backend, messages = ui
    backend.tutor.states["sample.root"].status = "mastered"
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    win.setProperty("page", 2)
    exam = _find(win, "MockExamPage")
    exam.setProperty("selectedSkillIds", ["sample.root"])
    invoke(exam, "start")
    exam.setProperty("phase", phase)
    before = evaluate(exam, "JSON.stringify(exam)")
    win.setProperty("page", 3)
    win.setProperty("page", 2)
    qtbot.wait(30)
    assert exam.property("phase") == phase
    assert evaluate(exam, "JSON.stringify(exam)") == before
    assert messages == []


def test_sessions_reset_clears_every_session_field_and_stops_case_timer(ui, qtbot):
    win, backend, messages = ui
    practice = _find(win, "PracticePage")
    cases = _find(win, "MockCasePage")
    exam = _find(win, "MockExamPage")
    backend.tutor.states["sample.root"].status = "mastered"
    exam.setProperty("selectedSkillIds", ["sample.root"])
    invoke(practice, "begin", "next")
    invoke(cases, "start", "sample-application")
    invoke(exam, "start")
    evaluate(practice, 'summary = "old"; feedback = {correct: true, answer: "", solution: ""}')
    for name in ("caseNotes", "caseStructure", "caseRecommendation"):
        win.findChild(QObject, name).setProperty("text", "old")
    cases.setProperty("elapsed", 44)
    evaluate(exam, "result = {xp: 99}; historySelection = {id: 1, results: []}")
    backend.sessionsReset.emit()
    assert practice.property("phase") == "empty"
    assert evaluate(practice, 'Object.keys(task).length === 0 && item === null && feedback === null'
                    ' && summary === ""')
    assert win.findChild(QObject, "practiceAnswer").property("response") == ""
    assert cases.property("phase") == "pick"
    assert evaluate(cases, 'Object.keys(caseInfo).length === 0 && revealed.length === 0'
                    ' && Object.keys(requested).length === 0 && Object.keys(qResults).length === 0'
                    ' && Object.keys(debrief).length === 0 && Object.keys(scores).length === 0'
                    ' && Object.keys(result).length === 0 && selectedHistoryId === -1')
    for name in ("caseNotes", "caseStructure", "caseRecommendation"):
        assert win.findChild(QObject, name).property("text") == ""
    assert exam.property("phase") == "pick"
    assert evaluate(exam, 'Object.keys(exam).length === 0 && item === null'
                    ' && Object.keys(result).length === 0 && historySelection === null')
    assert win.findChild(QObject, "examAnswer").property("response") == ""
    qtbot.wait(1100)
    assert cases.property("elapsed") == 0
    assert messages == []


def test_refresh_reloads_skills_and_preserves_valid_selection(ui):
    win, backend, messages = ui
    backend.tutor.states["sample.root"].status = "mastered"
    win.setProperty("page", 2)
    mock = _find(win, "MockTestPage")
    mock.setProperty("selectedMethod", "skill_exam")
    exam = _find(win, "MockExamPage")
    expected = backend.skillExamSkills()
    exam.setProperty("skills", [{"id": "obsolete", "title": "Old", "category": "Old"}])
    exam.setProperty("selectedSkillIds", [expected[0]["id"]])
    exam.setProperty("phase", "debrief")
    backend.contentChanged.emit()
    assert json.loads(evaluate(exam, "JSON.stringify(skills)")) == expected
    assert evaluate(exam, "selectedSkillIds.length") == 1
    assert exam.property("phase") == "debrief"
    exam.setProperty("selectedSkillIds", ["obsolete"])
    invoke(mock, "refresh")
    assert evaluate(exam, "selectedSkillIds.length") == 0
    assert messages == []


def test_action_errors_keep_phase_and_show_plain_visible_dialog(ui, qtbot):
    win, _, messages = ui
    cases = _find(win, "MockCasePage")
    exam = _find(win, "MockExamPage")
    practice = _find(win, "PracticePage")
    invoke(cases, "start", "not-a-case")
    assert cases.property("phase") == "pick"
    dialog = win.findChild(QObject, "backendErrorDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    label = win.findChild(QObject, "backendErrorMessage")
    assert label.property("text")
    assert evaluate(label, "textFormat === Text.PlainText")
    invoke(dialog, "close")
    invoke(exam, "finish")
    assert exam.property("phase") == "pick"
    qtbot.waitUntil(lambda: dialog.property("visible"))
    invoke(dialog, "close")
    practice.setProperty("phase", "question")
    win.findChild(QObject, "practiceAnswer").setProperty("response", "42")
    invoke(practice, "submit")
    assert practice.property("phase") == "question"
    qtbot.waitUntil(lambda: dialog.property("visible"))
    assert messages == []


def test_content_pack_import_errors_can_be_copied(ui, qtbot):
    win, backend, messages = ui
    win.setProperty("page", 4)
    qtbot.wait(30)
    archive_url = "https://example.invalid/pack.zip"
    result = backend.importContentPack(archive_url)
    assert result["error"] == "Choose a local content-pack ZIP file."

    error_dialog = _named(win, "backendErrorDialog")
    qtbot.waitUntil(lambda: error_dialog.property("visible"))
    invoke(_named(error_dialog, "copyBackendError"), "click")
    assert QGuiApplication.clipboard().text() == result["error"]
    invoke(error_dialog, "close")

    page = _find(win, "KnowledgeLibraryPage")
    invoke(page, "handleImportResult", result, archive_url)
    copy_button = _named(page, "copyContentPackError")
    assert copy_button.isVisible()
    invoke(copy_button, "click")
    assert QGuiApplication.clipboard().text() == result["error"]
    assert copy_button.property("text") == "Copied"
    assert messages == []


@pytest.mark.parametrize("method", ["finish", "saveScores"])
def test_failed_case_completion_does_not_advance_phase(ui, qtbot, method):
    win, _, messages = ui
    cases = _find(win, "MockCasePage")
    invoke(cases, method)
    assert cases.property("phase") == "pick"
    dialog = win.findChild(QObject, "backendErrorDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    assert messages == []


def test_failed_exam_start_keeps_selection_phase(ui, qtbot):
    win, _, messages = ui
    exam = _find(win, "MockExamPage")
    exam.setProperty("selectedSkillIds", ["not-a-skill"])
    invoke(exam, "start")
    assert exam.property("phase") == "pick"
    dialog = win.findChild(QObject, "backendErrorDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    assert messages == []


def test_failed_case_data_request_does_not_disable_retry(ui):
    win, _, messages = ui
    cases = _find(win, "MockCasePage")
    invoke(cases, "start", "sample-application")
    invoke(cases, "request", "not-a-category")
    assert cases.property("phase") == "run"
    assert evaluate(cases, "Object.keys(requested).length === 0 && revealed.length === 0")
    assert messages == []


def test_qml_case_scores_reach_backend_as_valid_integers(ui, qtbot, monkeypatch):
    win, backend, messages = ui
    cases = _find(win, "MockCasePage")
    invoke(cases, "start", "sample-application")
    invoke(cases, "finish")
    received = []
    original = backend.coach.submit_scores

    def capture(scores):
        received.append(scores)
        return original(scores)

    monkeypatch.setattr(backend.coach, "submit_scores", capture)
    invoke(cases, "saveScores")
    assert cases.property("phase") == "done"
    assert received and received[0]
    assert all(type(score) is int and 1 <= score <= 5 for score in received[0].values())
    assert not win.findChild(QObject, "backendErrorDialog").property("visible")
    assert messages == []


def test_failed_progress_reset_keeps_confirmation_open(ui, qtbot, monkeypatch):
    win, backend, messages = ui
    dialog = win.findChild(QObject, "resetProgressDialog")
    invoke(dialog, "open")

    def fail_reset():
        raise ValueError("Reset unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(backend.tutor, "reset_progress", fail_reset)
        invoke(dialog, "reset")
        qtbot.waitUntil(lambda: win.findChild(QObject, "backendErrorDialog").property("visible"))
        assert dialog.property("visible")
    invoke(win.findChild(QObject, "backendErrorDialog"), "close")
    invoke(dialog, "reset")
    qtbot.waitUntil(lambda: not dialog.property("visible"))
    assert messages == []


def _map_page(win):
    return next(obj for obj in win.findChildren(QObject)
                if obj.metaObject().className().startswith("KnowledgeMapPage"))


def test_map_search_without_matches_clears_stale_selection(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 3)
    qtbot.wait(30)
    page = _map_page(win)
    evaluate(page, "selected = graph.nodes[0]")
    assert evaluate(page, "selected !== null")
    page.setProperty("searchText", "absent skill")
    assert evaluate(page, "selected === null")
    assert evaluate(page, "visibleNodes.length === 0 && visibleEdges.length === 0")
    page.setProperty("searchText", "")
    assert evaluate(page, "visibleEdges.length > 0")
    assert evaluate(page, "visibleEdges.every(edge => visibleNodeIds.has(edge.from)"
                    " && visibleNodeIds.has(edge.to))")
    assert messages == []


def test_map_filter_keeps_selection_that_remains_visible(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 3)
    qtbot.wait(30)
    page = _map_page(win)
    evaluate(page, "selected = graph.nodes[0]")
    title = evaluate(page, "selected.title")
    page.setProperty("searchText", title)
    assert evaluate(page, "selected !== null && selected.title === " + json.dumps(title))
    assert messages == []
