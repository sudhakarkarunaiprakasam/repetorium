from time import perf_counter

import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QInputDevice, QPointingDevice, QWheelEvent
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from test_ui import _find
from test_ui import ui as ui


def _value(obj, name):
    value = obj.property(name)
    return value.toVariant() if hasattr(value, "toVariant") else value


def _named(root, name):
    return next(obj for obj in root.findChildren(QObject) if obj.objectName() == name)


def _invoke(obj, method):
    assert QMetaObject.invokeMethod(obj, method, Qt.DirectConnection)


def _evaluate(obj, expression):
    return QQmlExpression(qmlContext(obj), obj, expression).evaluate()[0]


def _visual_items(root: QQuickItem):
    items = [root]
    for child in root.childItems():
        if isinstance(child, QQuickItem):
            items.extend(_visual_items(child))
    return items


@pytest.fixture
def case_picker(ui, monkeypatch, qtbot):
    win, backend, messages = ui
    templates = [
        {
            "id": f"case_{index}",
            "title": f"Case {index:03d}",
            "archetype": ["Pricing", "Operations", "Market entry", "Profitability"][index % 4],
            "summary": "Coffee expansion" if index == 73 else "Assess the business opportunity",
            "minutes": 25,
            "difficulty": ["beginner", "intermediate", "hard"][index % 3],
            "skillCount": index % 8 + 1,
        }
        for index in range(100)
    ]
    monkeypatch.setattr(backend.coach, "templates", lambda: templates)
    win.setProperty("page", 2)
    page = _find(win, "MockCasePage")
    _invoke(page, "refresh")
    qtbot.wait(30)
    return win, page, messages


def test_case_picker_pages_100_backend_cases(case_picker, qtbot):
    _, page, messages = case_picker
    assert len(_value(page, "templates")) == 100
    assert page.property("resultCount") == 100
    assert page.property("pageCount") == 10
    assert len([obj for obj in _visual_items(page) if obj.objectName() == "caseCard"]) == 10
    seen = []
    for index in range(10):
        assert page.property("currentPage") == index
        seen.extend(template["id"] for template in _value(page, "pagedTemplates"))
        _invoke(page, "nextPage")
    assert seen == [f"case_{index}" for index in range(100)]
    assert page.property("currentPage") == 9
    assert len(_value(page, "pagedTemplates")) == 10
    assert not _named(page, "caseNextPage").property("enabled")
    _invoke(page, "previousPage")
    assert page.property("currentPage") == 8
    qtbot.wait(30)
    assert messages == []


def test_case_search_filter_resets_page_and_empty_results(case_picker, qtbot):
    _, page, messages = case_picker
    assert _value(page, "archetypes") == [
        "All types", "Market entry", "Operations", "Pricing", "Profitability",
    ]
    _invoke(page, "nextPage")
    search = _named(page, "caseSearch")
    search.setProperty("text", "  COFFEE  ")
    _invoke(search, "textEdited")
    assert page.property("currentPage") == 0
    assert page.property("resultCount") == 1
    assert _value(page, "pagedTemplates")[0]["id"] == "case_73"
    page.setProperty("searchText", "case 073")
    assert page.property("resultCount") == 1
    page.setProperty("searchText", "pricing")
    assert page.property("resultCount") == 25
    page.setProperty("searchText", "")
    _invoke(page, "nextPage")
    combo = _named(page, "caseArchetypeFilter")
    combo.setProperty("currentIndex", 2)
    assert QMetaObject.invokeMethod(combo, "activated", Qt.DirectConnection, Q_ARG("int", 2))
    assert page.property("archetypeFilter") == "Operations"
    assert page.property("currentPage") == 0
    assert page.property("resultCount") == 25
    difficulty = _named(page, "caseDifficultyFilter")
    difficulty.setProperty("currentIndex", 1)
    assert QMetaObject.invokeMethod(
        difficulty, "activated", Qt.DirectConnection, Q_ARG("int", 1)
    )
    assert page.property("difficultyFilter") == "Beginner"
    assert page.property("resultCount") > 0
    page.setProperty("difficultyFilter", "All levels")
    page.setProperty("searchText", "coffee")
    assert page.property("resultCount") == 1
    page.setProperty("archetypeFilter", "Pricing")
    assert page.property("resultCount") == 0
    assert page.property("pageCount") == 0
    assert _value(page, "pagedTemplates") == []
    _invoke(page, "nextPage")
    _invoke(page, "previousPage")
    assert page.property("currentPage") == 0
    qtbot.wait(30)
    assert not _named(page, "casePreviousPage").property("enabled")
    assert not _named(page, "caseNextPage").property("enabled")
    assert messages == []


def test_case_picker_responsive_columns(case_picker, qtbot):
    win, page, messages = case_picker
    win.setProperty("width", 1280)
    qtbot.wait(30)
    assert page.property("pickerColumns") == 2
    win.setProperty("width", 980)
    qtbot.wait(30)
    assert page.property("pickerColumns") == 2
    grid = _named(page, "caseGrid")
    cards = [obj for obj in _visual_items(page) if obj.objectName() == "caseCard"]
    assert all(card.width() <= grid.width() for card in cards)
    assert messages == []


@pytest.mark.parametrize("expanded", [True, False])
@pytest.mark.parametrize("size", [(980, 640), (1440, 768), (1440, 900)])
def test_case_picker_pagination_fits_without_scrolling(ui, qtbot, size, expanded):
    win, _, messages = ui
    win.setWidth(size[0])
    win.setHeight(size[1])
    win.setProperty("menuExpanded", expanded)
    win.setProperty("page", 2)
    page = _find(win, "MockCasePage")
    for _ in range(page.property("pageCount")):
        qtbot.wait(30)
        next_button = _named(page, "caseNextPage")
        bottom = next_button.mapToItem(page, QPointF(0, next_button.height())).y()
        assert bottom <= page.height()
        for card in _visual_items(page):
            if card.objectName() != "caseCard":
                continue
            assert card.height() <= 130
            for child in _visual_items(card):
                if child.property("text") is None:
                    continue
                assert child.mapToItem(card, QPointF(child.width(), child.height())).x() <= card.width()
        _invoke(page, "nextPage")
    assert messages == []


@pytest.mark.parametrize("expanded", [True, False])
def test_menu_icons_alignment_and_navigation(ui, qtbot, expanded):
    win, _, messages = ui
    win.setProperty("menuExpanded", expanded)
    qtbot.wait(30)
    menu = _named(win, "menuPane")
    toggle = _named(win, "menuToggle")
    tagline = _named(win, "appTagline")
    assert tagline.property("text") == "Practice, Review, Apply"
    assert tagline.property("visible") is expanded
    toggle_image = next(obj for obj in _visual_items(toggle)
                        if obj.metaObject().className() == "QQuickIconImage")
    assert toggle_image.property("source").toLocalFile().endswith(
        "panel-left-close.svg" if expanded else "panel-left-open.svg"
    )
    row_positions = []
    icon_positions = []
    destinations = _value(win, "navItems")
    assert destinations == [
        "Dashboard", "Skill Map", "Library", "Settings", "About and Credits",
    ]
    page_indices = _value(win, "navPageIndices")
    assert page_indices == [0, 3, 4, 5, 6]
    for index in range(len(destinations)):
        item = next(obj for obj in _visual_items(menu) if obj.objectName() == f"menuItem{index}")
        assert item.width() == menu.width() - 16
        assert item.height() == 44
        assert item.x() == 8
        image = next(obj for obj in _visual_items(item) if obj.metaObject().className() == "QQuickIconImage")
        assert image.property("source").toLocalFile().endswith(".svg")
        assert image.width() == 20
        center = image.mapToItem(menu, QPointF(image.width() / 2, image.height() / 2))
        icon_positions.append(center.x())
        assert center.y() == pytest.approx(item.y() + item.height() / 2)
        if not expanded:
            assert center.x() == pytest.approx(menu.width() / 2)
        row_positions.append(item.y())
        _invoke(item, "click")
        assert win.property("page") == page_indices[index]
        assert item.property("highlighted")
        qtbot.wait(30)
    assert len(set(icon_positions)) == 1
    assert all(row_positions[index + 1] - row_positions[index] == 48
               for index in range(len(destinations) - 1))
    assert messages == []


def test_credits_separate_learning_software_and_project_tools(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 6)
    qtbot.wait(30)
    sections = _named(win, "aboutCreditsSections")
    sections.setProperty("currentIndex", 1)
    qtbot.wait(30)
    page = _named(win, "creditsPage")
    sections = _named(page, "creditsSections")
    assert _value(sections, "count") == 2
    assert _named(page, "learningSoftwareTab").property("text") == "Learning Software"
    assert _named(page, "projectToolsTab").property("text") == "Project Tools"
    learning = _value(page, "learningSources")
    assert len(learning) == 6
    assert {entry["title"] for entry in learning} >= {
        "The Math Academy Way — Justin Skycak, advised by Jason Roberts",
        "Advice on Upskilling — Justin Skycak",
    }
    assert all("polymath" not in entry["title"].lower() for entry in learning)
    assert {entry["title"] for entry in _value(page, "softwareCredits")} == {
        "Python", "Qt / PySide6", "SQLite", "PyYAML", "platformdirs", "Lucide",
    }
    assert not any(obj.objectName() in ("creditsDisclaimer", "creditsReviewLimits")
                   for obj in page.findChildren(QObject))
    assert messages == []


@pytest.mark.parametrize("expanded", [True, False])
@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_about_page_describes_learning_software(ui, qtbot, expanded, size):
    win, _, messages = ui
    win.setWidth(size[0])
    win.setHeight(size[1])
    win.setProperty("menuExpanded", expanded)
    win.setProperty("page", 6)
    qtbot.wait(30)
    page = _named(win, "aboutPage")
    assert "learning from your own material" in _named(page, "aboutSummary").property("text")
    assert "prerequisite relationships" in _named(page, "aboutLearningFlow").property("text")
    assert "stored locally" in _named(page, "aboutLocalData").property("text")
    assert "MIT License" in _named(page, "aboutLicensePermission").property("text")
    assert "modify" in _named(page, "aboutLicensePermission").property("text")
    assert "without warranty" in _named(page, "aboutLicenseWarranty").property("text")
    assert "maximum extent permitted by law" in \
        _named(page, "aboutLicenseLiability").property("text")
    about_text = " ".join(
        str(obj.property("text") or "")
        for obj in _visual_items(page)
        if obj.property("text") is not None
    ).lower()
    assert not any(term in about_text for term in ("polymath", "munger", "da vinci", "davince"))
    assert page.property("contentWidth") <= page.width()
    assert messages == []


def test_library_page_offers_format_instructions_and_pack_controls(ui, qtbot):
    win, backend, messages = ui
    win.setProperty("page", 4)
    page = _find(win, "KnowledgeLibraryPage")
    qtbot.wait(30)
    steps = [_named(page, f"libraryStep{index}") for index in (1, 2, 3, 4)]
    assert [step.y() for step in steps] == sorted(step.y() for step in steps)
    assert _named(page, "libraryStep1Title").property("text") == "1. Download Skills.MD"
    assert _named(page, "libraryStep2Title").property("text") == "2. Import Packages"
    assert _named(page, "libraryStep3Title").property("text") == "3. Placement Check"
    assert _named(page, "libraryStep4Title").property("text") == "4. Manage Packages"
    assert _named(page, "downloadContentFormatInstructions").property("text") == \
        "Download Skills.MD"
    assert "use any tools or workflow you prefer" in \
        _named(page, "contentFormatInstructions").property("text")
    assert "Import a ZIP" in _named(page, "contentPackSetupInstructions").property("text")
    assert _named(page, "importContentPack").property("text") == "Import Package"
    assert _named(page, "contentPackDeleteList") is not None
    packs = _value(page, "packState")["packs"]
    first_pack_id = packs[0]["id"]
    info_button = next(
        item for item in _visual_items(page)
        if item.objectName() == f"contentPackInfoButton_{first_pack_id}"
    )
    assert info_button.property("text") == "Info"
    export_button = next(
        item for item in _visual_items(page)
        if item.objectName() == f"exportContentPackButton_{first_pack_id}"
    )
    assert export_button.property("text") == "Export"
    export_all_button = _named(page, "exportAllContentPacks")
    assert export_all_button.property("text") == "Export All"
    assert export_all_button.isEnabled()
    include_progress = _named(page, "includeExportProgressSnapshot")
    assert include_progress.property("checked")
    _invoke(include_progress, "click")
    assert backend.getSetting("include_export_progress_snapshot", True) is False
    _invoke(include_progress, "click")
    assert backend.getSetting("include_export_progress_snapshot", False) is True
    delete_button = next(
        item for item in _visual_items(page)
        if item.objectName() == f"deleteContentPackButton_{first_pack_id}"
    )
    export_all_right = (
        export_all_button.mapToItem(page, 0, 0).x() + export_all_button.width()
    )
    delete_right = delete_button.mapToItem(page, 0, 0).x() + delete_button.width()
    assert export_all_right == pytest.approx(delete_right)
    suffix_dialog = _named(page, "exportAllSuffixDialog")
    default_suffix = _named(suffix_dialog, "exportAllSuffix").property("text")
    assert len(default_suffix) == 10
    assert default_suffix[4] == "-" and default_suffix[7] == "-"
    progress_copy = _named(page, "contentPackProgressInfo").property("text")
    assert "choose whether to restore it" in progress_copy
    assert "raw answers" in progress_copy
    assert "XP" not in progress_copy
    use_dialog = _named(page, "contentPackUseDialog")
    declaration = _named(use_dialog, "personalUseDeclaration")
    continue_button = _named(use_dialog, "contentPackUseContinue")
    copyright_reminder = _named(use_dialog, "contentPackCopyrightReminder").property("text")
    sharing_reminder = _named(use_dialog, "contentPackSharingReminder").property("text")
    declaration_text = _named(use_dialog, "personalUseDeclaration").property("text")
    assert "copyright, license" in copyright_reminder
    assert "original material" in copyright_reminder
    assert "review the snapshot" in sharing_reminder
    assert "use or share the selected pack(s) accordingly" in declaration_text
    assert "do not share" not in declaration_text

    for action in (_named(page, "importContentPack"), export_button, export_all_button):
        _invoke(action, "click")
        qtbot.waitUntil(lambda: use_dialog.property("visible"))
        assert not declaration.property("checked")
        assert not continue_button.property("enabled")
        declaration.setProperty("checked", True)
        assert continue_button.property("enabled")
        _invoke(_named(use_dialog, "contentPackUseCancel"), "click")
        qtbot.waitUntil(lambda: not use_dialog.property("visible"))
    placement_button = _named(page, "startPlacementCheck")
    assert placement_button.property("text") == "Start Placement Check"
    assert placement_button.isEnabled()
    _invoke(placement_button, "click")
    assert win.property("page") == 1
    practice = _find(win, "PracticePage")
    assert _value(practice, "task")["kind"] == "diagnostic"
    assert messages == []


def test_export_all_prompts_for_suffix_then_folder(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 4)
    page = _find(win, "KnowledgeLibraryPage")
    _invoke(_named(page, "exportAllContentPacks"), "click")

    use_dialog = _named(page, "contentPackUseDialog")
    qtbot.waitUntil(lambda: use_dialog.property("visible"))
    _named(use_dialog, "personalUseDeclaration").setProperty("checked", True)
    _invoke(_named(use_dialog, "contentPackUseContinue"), "click")

    suffix_dialog = _named(page, "exportAllSuffixDialog")
    qtbot.waitUntil(lambda: suffix_dialog.property("visible"))
    suffix_field = _named(suffix_dialog, "exportAllSuffix")
    default_suffix = suffix_field.property("text")
    assert len(default_suffix) == 10
    assert default_suffix[4] == "-" and default_suffix[7] == "-"
    suffix_field.setProperty("text", "manual-export")
    _invoke(_named(suffix_dialog, "exportAllSuffixContinue"), "click")

    folder_dialog = _named(page, "exportAllLearningPacksFolderDialog")
    qtbot.waitUntil(lambda: folder_dialog.property("visible"))
    _invoke(folder_dialog, "close")
    assert messages == []


def test_content_pack_disclaimer_wraps_at_narrow_width(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 4)
    page = _find(win, "KnowledgeLibraryPage")
    _invoke(_named(page, "importContentPack"), "click")
    dialog = _named(page, "contentPackUseDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    dialog.setProperty("width", 320)
    qtbot.wait(50)

    text_items = [
        _named(dialog, "contentPackCopyrightReminder"),
        _named(dialog, "contentPackSharingReminder"),
        _named(dialog, "personalUseDeclarationText"),
    ]
    for text_item in text_items:
        assert text_item.width() <= dialog.property("width")
        assert text_item.height() > 30
    assert messages == []


def test_imported_progress_snapshot_offers_restore_or_keep(ui, qtbot):
    win, _, messages = ui
    win.setProperty("page", 4)
    page = _find(win, "KnowledgeLibraryPage")
    result = {
        "ok": True,
        "message": "Imported Transfer Pack (5 skills).",
        "progressSnapshotAvailable": True,
        "progressPackId": "transfer-pack",
        "progressPackName": "Transfer Pack",
    }
    assert QMetaObject.invokeMethod(
        page,
        "handleImportResult",
        Qt.DirectConnection,
        Q_ARG("QVariant", result),
        Q_ARG("QVariant", "file:///transfer-pack.zip"),
    )
    dialog = _named(page, "progressSnapshotDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    explanation = _named(dialog, "progressSnapshotExplanation").property("text")
    assert "matching skills" in explanation
    assert "raw answers" in explanation
    assert "XP" not in explanation
    assert _named(dialog, "restorePackProgress").property("text") == "Restore progress"
    _invoke(_named(dialog, "keepCurrentProgress"), "click")
    qtbot.waitUntil(lambda: not dialog.property("visible"))
    assert _value(page, "pendingProgressPackId") == ""
    assert messages == []


def test_settings_can_select_multiple_packs_and_allocate_weekly_goals(
    ui, qtbot, tmp_path,
):
    import zipfile

    import yaml

    win, backend, messages = ui
    win.setProperty("page", 5)
    page = _find(win, "SettingsPage")
    built_in = backend.contentPackState()["packs"][0]["id"]
    source = tmp_path / "ui-extra"
    (source / "graph").mkdir(parents=True)
    (source / "library.yaml").write_text(yaml.safe_dump({
        "format": 1, "id": "ui-extra", "name": "UI Extra",
        "version": "1.0", "sources": ["Test source"],
    }), encoding="utf-8")
    (source / "graph" / "concepts.yaml").write_text(yaml.safe_dump([{
        "id": "ui.extra", "title": "UI extra", "generator": "compound_growth",
    }]), encoding="utf-8")
    archive_path = tmp_path / "ui-extra.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in source.rglob("*"):
            archive.write(path, path.relative_to(source).as_posix())
    assert backend.importContentPack(QUrl.fromLocalFile(str(archive_path)).toString())["ok"]
    qtbot.wait(30)

    def pack_control(pack_id, control_name):
        state = backend.contentPackState()
        index = next(
            index for index, pack in enumerate(state["packs"]) if pack["id"] == pack_id
        )
        row = _evaluate(_named(page, "contentPackRepeater"), f"itemAt({index})")
        return row, _named(row, f"{control_name}_{pack_id}")

    pack_row, pack_check = pack_control(built_in, "contentPackSelection")
    extra_row, extra_check = pack_control("ui-extra", "contentPackSelection")
    assert pack_check.property("checked")
    assert extra_check.property("checked")
    assert "selected pack goals add up" in \
        _named(page, "contentPackModeDescription").property("text").lower()

    pack_goal_row, pack_goal = pack_control(built_in, "contentPackWeeklyGoal")
    pack_goal.setProperty("value", 3)
    _invoke(pack_goal, "valueModified")
    qtbot.wait(20)
    goals = {
        pack["id"]: pack["weeklyGoal"]
        for pack in backend.contentPackState()["packs"] if pack["selected"]
    }
    assert goals == {built_in: 3, "ui-extra": 2}

    selected_names = {
        pack["id"]: pack["name"]
        for pack in backend.contentPackState()["packs"] if pack["selected"]
    }
    win.setProperty("page", 4)
    qtbot.wait(30)
    practice_summary = _named(_find(win, "KnowledgeLibraryPage"), "activeContentPack")
    assert practice_summary.property("text") == (
        "Practice packs: " + " · ".join(selected_names[pack_id]
                                        for pack_id in (built_in, "ui-extra"))
    )

    win.setProperty("page", 5)
    qtbot.wait(20)
    total_goal = _named(page, "lessonsPerWeekGoalSetting")
    total_goal.setProperty("value", 8)
    _invoke(total_goal, "valueModified")
    qtbot.wait(20)
    assert sum(
        pack["weeklyGoal"] for pack in backend.contentPackState()["packs"]
        if pack["selected"]
    ) == 8

    extra_row, extra_check = pack_control("ui-extra", "contentPackSelection")
    _invoke(extra_check, "click")
    qtbot.wait(20)
    state = backend.contentPackState()
    assert state["selectedPackIds"] == [built_in]
    assert state["packs"][0]["weeklyGoal"] == 8
    assert messages == []


def test_weekly_lesson_goal_defaults_to_five_lessons(ui, qtbot):
    win, backend, messages = ui
    assert backend.dashboard()["weeklyLessonGoal"] == 5

    win.setProperty("page", 5)
    qtbot.wait(30)
    setting = _named(win, "lessonsPerWeekGoalSetting")
    assert setting.property("value") == 5
    setting.setProperty("value", 8)
    _invoke(setting, "valueModified")
    assert backend.dashboard()["weeklyLessonGoal"] == 8
    errors = []
    backend.errorOccurred.connect(errors.append)
    backend.setSetting("lessons_per_week_goal", 0)
    assert errors == ["The lessons per week goal must be an integer from 1 to 50."]
    assert backend.getSetting("lessons_per_week_goal", 5) == 8
    assert messages == []


def test_content_library_lists_imported_pack_delete_action(ui, qtbot, tmp_path, monkeypatch):
    import zipfile

    import yaml

    win, backend, messages = ui
    pack_dir = tmp_path / "pack"
    (pack_dir / "graph").mkdir(parents=True)
    (pack_dir / "library.yaml").write_text(yaml.safe_dump({
        "format": 1, "id": "ui-removable", "name": "UI Removable", "version": "1",
        "sources": ["Test source"],
    }), encoding="utf-8")
    info_document = (
        "# UI Removable\n\nPurpose: retain the pack's learning intent.\n\n"
        + "\n\n".join(f"Section {index}: pack details." for index in range(80))
    )
    (pack_dir / "INFO.md").write_text(info_document, encoding="utf-8")
    (pack_dir / "graph" / "test.yaml").write_text(yaml.safe_dump([{
        "id": "ui.removable", "title": "Removable skill", "generator": "unit_rates",
    }]), encoding="utf-8")
    archive_path = tmp_path / "ui-removable.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in pack_dir.rglob("*"):
            archive.write(path, path.relative_to(pack_dir).as_posix())
    assert backend.importContentPack(QUrl.fromLocalFile(str(archive_path)).toString())["ok"]
    win.setProperty("page", 4)
    page = _find(win, "KnowledgeLibraryPage")
    qtbot.wait(20)
    packs = _value(page, "packState")["packs"]
    pack_index = next(index for index, pack in enumerate(packs)
                      if pack["id"] == "ui-removable")
    row_name = f"contentPackRow_{packs[pack_index]['id']}"
    row = next(item for item in _visual_items(page) if item.objectName() == row_name)
    row_children = _visual_items(row)
    package_name = next(item for item in row_children
                        if item.objectName() == "contentPackName_ui-removable")
    assert package_name.property("text") == "UI Removable"
    delete_button = next(item for item in row_children
                         if item.objectName() == "deleteContentPackButton_ui-removable")
    export_button = next(item for item in row_children
                         if item.objectName() == "exportContentPackButton_ui-removable")
    rename_button = next(item for item in row_children
                         if item.objectName() == "renameContentPackButton_ui-removable")
    info_button = next(item for item in row_children
                       if item.objectName() == "contentPackInfoButton_ui-removable")
    assert info_button.property("text") == "Info"
    _invoke(info_button, "click")
    info_dialog = _named(page, "contentPackInfoDialog")
    qtbot.waitUntil(lambda: info_dialog.property("visible"))
    assert "Purpose: retain the pack's learning intent." in \
        _named(info_dialog, "contentPackInfoDocument").property("text")
    info_document_item = _named(info_dialog, "contentPackInfoDocument")
    assert _evaluate(info_document_item, "textFormat === Text.MarkdownText")
    info_scroll = _named(info_dialog, "contentPackInfoScroll")
    qtbot.waitUntil(lambda: info_scroll.property("contentHeight") > info_scroll.height())
    _invoke(info_dialog, "close")
    button_positions = [
        button.mapToItem(row, 0, 0).x()
        for button in (info_button, rename_button, export_button, delete_button)
    ]
    assert button_positions == sorted(button_positions)
    assert export_button.property("text") == "Export"
    assert _evaluate(delete_button, "background.color.toString()") == \
        _evaluate(page, "brandPalette.dangerSurface.toString()")
    assert _evaluate(delete_button, "contentItem.color.toString()") == \
        _evaluate(page, "brandPalette.onStatus.toString()")
    assert delete_button.isEnabled()
    assert delete_button.isVisible()
    assert delete_button.property("text") == "Delete"
    _invoke(delete_button, "click")
    dialog = _named(page, "deleteContentPackDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    assert "UI Removable" in _named(dialog, "deleteContentPackConfirmation").property("text")
    _invoke(dialog, "reject")

    assert rename_button.property("text") == "Rename"
    _invoke(rename_button, "click")
    rename_dialog = _named(page, "renameContentPackDialog")
    qtbot.waitUntil(lambda: rename_dialog.property("visible"))
    name_field = _named(rename_dialog, "renameContentPackName")
    assert name_field.property("text") == "UI Removable"
    name_field.setProperty("text", "Short name")
    _invoke(_named(rename_dialog, "saveRenameContentPack"), "click")
    qtbot.waitUntil(lambda: not rename_dialog.property("visible"))
    renamed_pack = next(pack for pack in _value(page, "packState")["packs"]
                        if pack["id"] == "ui-removable")
    assert renamed_pack["name"] == "Short name"
    assert backend.tutor.graph.skill_pack_names["ui.removable"] == "Short name"
    assert messages == []


def test_duplicate_pack_import_prompts_suffixes_for_both_packs(ui, qtbot, tmp_path):
    import zipfile

    import yaml

    win, backend, messages = ui

    def make_pack(pack_id, skill_id, output):
        source = tmp_path / f"{pack_id}-{skill_id.replace('.', '-')}"
        (source / "graph").mkdir(parents=True)
        (source / "library.yaml").write_text(yaml.safe_dump({
            "format": 1, "id": pack_id, "name": "Shared Learning Pack",
            "version": "1", "sources": ["Test source"],
        }), encoding="utf-8")
        (source / "graph" / "concepts.yaml").write_text(yaml.safe_dump([{
            "id": skill_id, "title": "A learning skill", "generator": "compound_growth",
        }]), encoding="utf-8")
        with zipfile.ZipFile(output, "w") as archive:
            for path in source.rglob("*"):
                archive.write(path, path.relative_to(source).as_posix())
        return output

    old_archive = make_pack("shared-pack", "old.skill", tmp_path / "old.zip")
    new_archive = make_pack("shared-pack", "new.skill", tmp_path / "new.zip")
    assert backend.importContentPack(QUrl.fromLocalFile(str(old_archive)).toString())["ok"]
    duplicate = backend.importContentPack(QUrl.fromLocalFile(str(new_archive)).toString())
    assert duplicate["duplicate"]

    win.setProperty("page", 4)
    qtbot.wait(30)
    page = _find(win, "KnowledgeLibraryPage")
    assert page is not None
    assert QMetaObject.invokeMethod(
        page,
        "handleImportResult",
        Qt.DirectConnection,
        Q_ARG("QVariant", duplicate),
        Q_ARG("QVariant", QUrl.fromLocalFile(str(new_archive)).toString()),
    )
    dialog = _named(page, "renameDuplicatePackDialog")
    qtbot.waitUntil(lambda: dialog.property("visible"))
    assert _named(dialog, "existingPackSuffix").property("text") == " (existing)"
    assert _named(dialog, "incomingPackSuffix").property("text") == " (new)"
    _named(dialog, "existingPackSuffix").setProperty("text", " (previous)")
    _named(dialog, "incomingPackSuffix").setProperty("text", " (updated)")
    _invoke(_named(dialog, "duplicatePackRenameImport"), "click")
    qtbot.wait(30)

    packs = {pack["id"]: pack["name"] for pack in backend.contentPackState()["packs"]}
    assert packs["shared-pack"] == "Shared Learning Pack (previous)"
    assert packs["shared-pack-2"] == "Shared Learning Pack (updated)"
    assert messages == []


def test_deleting_last_pack_leaves_importable_empty_library(ui, qtbot):
    win, backend, messages = ui
    built_in = backend.contentPackState()["packs"][0]["id"]

    assert backend.deleteContentPack(built_in)["ok"]
    qtbot.wait(20)
    assert backend.contentPackState()["mode"] == "none"
    assert backend.tutor.graph.skills == {}

    win.setProperty("page", 5)
    settings = _find(win, "SettingsPage")
    assert "No content packs are installed" in \
        _named(settings, "contentPackModeDescription").property("text")
    assert _named(settings, "contentPackSelectionSection") is not None

    win.setProperty("page", 4)
    library = _find(win, "KnowledgeLibraryPage")
    assert _named(library, "importContentPack").isEnabled()
    assert not any(
        item.objectName().startswith("exportContentPackButton_")
        for item in _visual_items(library)
    )
    assert messages == []


def test_map_reflection_saves_and_restores_for_each_concept(ui, qtbot):
    win, backend, messages = ui
    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    nodes = backend.knowledgeMap()["nodes"]
    first, second = nodes[:2]
    page.setProperty("selected", first)
    qtbot.wait(30)
    notes = _named(page, "mapReflectionNotes")
    notes.setProperty("text", "My explanation and where the analogy fails.")
    _invoke(_named(page, "saveMapReflection"), "click")
    assert backend.learningReflection(first["id"]) == "My explanation and where the analogy fails."
    page.setProperty("selected", second)
    assert notes.property("text") == ""
    page.setProperty("selected", first)
    assert notes.property("text") == "My explanation and where the analogy fails."
    assert backend.tutor.store.xp_total() == 0
    assert messages == []


@pytest.mark.parametrize("expanded", [True, False])
@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_credits_sections_render_and_scroll_at_supported_sizes(ui, qtbot, size, expanded):
    win, _, messages = ui
    win.setWidth(size[0])
    win.setHeight(size[1])
    win.setProperty("menuExpanded", expanded)
    win.setProperty("page", 6)
    qtbot.wait(30)
    _named(win, "aboutCreditsSections").setProperty("currentIndex", 1)
    qtbot.wait(30)
    page = _named(win, "creditsPage")
    sections = _named(page, "creditsSections")
    for index in (0, 1):
        sections.setProperty("currentIndex", index)
        qtbot.wait(30)
        credits = [obj for obj in _visual_items(page) if obj.objectName() == "researchCredit"]
        tools = [obj for obj in _visual_items(page) if obj.objectName() == "toolCredit"]
        assert len(credits) == (6 if index == 0 else 0)
        heading = _named(page, "creditsSectionHeading")
        assert heading.isVisible()
        assert heading.property("text") == (
            "Learning Research" if index == 0 else "Software and Icons"
        )
        assert len(tools) == (6 if index == 1 else 0)
        for item in credits:
            assert item.width() <= page.width() - 48
            for child in _visual_items(item):
                if child.property("text") is not None:
                    assert child.property("contentHeight") <= child.height()
        if index == 0:
            summary = _named(page, "creditsAlgorithmSummary").property("text").lower()
            assert "prerequisite relationships" in summary
            assert "do not guarantee long-term retention" in summary
            assert "polymath" not in summary
        else:
            assert not _named(page, "creditsAlgorithmSummary").isVisible()
        assert page.property("contentWidth") <= page.width()
    assert messages == []

@pytest.mark.parametrize("size", [(980, 640), (1440, 900)])
def test_settings_reset_button_has_padding_and_right_margin(ui, qtbot, size):
    win, _, messages = ui
    win.setWidth(size[0])
    win.setHeight(size[1])
    win.setProperty("page", 5)
    qtbot.wait(30)
    page = _find(win, "SettingsPage")
    button = _named(page, "resetProgressButton")
    right = button.mapToItem(page, QPointF(button.width(), 0)).x()
    assert page.width() - right == pytest.approx(32)
    assert button.property("leftPadding") >= 20
    assert button.property("rightPadding") >= 20
    assert messages == []


@pytest.fixture
def knowledge_map(ui, monkeypatch, qtbot):
    win, backend, messages = ui
    nodes = [
        {
            "id": f"skill_{index}",
            "title": "Target synthesis" if index == 3 else f"Foundation {index}",
            "category": "synthesis" if index == 3 else "math",
            "depth": min(index, 3),
            "status": "available",
            "reps": 7,
            "dueInDays": 2,
            "prerequisites": [{"id": f"skill_{index - 1}", "title": f"Foundation {index - 1}"}]
            if 0 < index < 4 else [],
            "guide": {},
            "lesson": {},
            "definition": "A clear recommendation supported by evidence.",
            "cases": [
                {"id": f"case_{case}", "title": f"Related case {case}", "archetype": "Pricing"}
                for case in range(30)
            ] if index == 3 else [],
        }
        for index in range(80)
    ]
    edges = [{"from": f"skill_{index}", "to": f"skill_{index + 1}"} for index in range(3)]
    edges.append({"from": "skill_0", "to": "skill_79"})
    monkeypatch.setattr(backend.tutor, "knowledge_map", lambda: {"nodes": nodes, "edges": edges})
    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    _invoke(page, "refresh")
    qtbot.wait(30)
    return page, nodes, messages


def test_map_filter_keeps_full_ancestor_context_and_visible_edges(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    assert len(_value(page, "graph")["nodes"]) == 80
    assert page.property("matchCount") == 80
    page.setProperty("categoryFilter", "synthesis")
    assert page.property("matchCount") == 1
    assert page.property("contextCount") == 3
    assert [node["id"] for node in _value(page, "visibleNodes")] == [f"skill_{index}" for index in range(4)]
    assert len(_value(page, "visibleEdges")) == 3
    page.setProperty("searchText", "  TARGET  ")
    assert page.property("matchCount") == 1
    assert page.property("contextCount") == 3
    page.setProperty("categoryFilter", "All categories")
    assert len(_value(page, "visibleNodes")) == 4
    qtbot.wait(30)
    assert len([obj for obj in _visual_items(page) if obj.objectName() == "skillNode"]) == 4
    page.setProperty("searchText", "absent skill")
    assert page.property("matchCount") == 0
    assert _value(page, "visibleNodes") == []
    assert _value(page, "visibleEdges") == []
    qtbot.wait(30)
    assert messages == []


def test_map_uses_prerequisites_without_concept_links(ui, qtbot):
    win, backend, messages = ui
    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    page.setProperty("domainFilter", "quantitative")
    matches = _value(page, "matchingNodes")
    assert matches
    assert all("quantitative" in node["domains"] for node in matches)
    page.setProperty("searchText", "base rate")
    assert page.property("matchCount") == 1
    visible = {node["id"] for node in _value(page, "visibleNodes")}
    assert "sample.related" not in visible
    assert all(edge.get("kind") in (None, "prerequisite")
               for edge in _value(page, "visibleEdges"))
    node = next(node for node in backend.knowledgeMap()["nodes"] if node["id"] == "sample.root")
    page.setProperty("selected", node)
    qtbot.wait(30)
    _invoke(_named(page, "mapOpenLesson"), "click")
    qtbot.wait(30)
    dialog = _named(page, "mapLessonDialog")
    assert dialog.property("visible")
    texts = [obj.property("text") for obj in _visual_items(_named(page, "mapLessonDialogScroll"))]
    assert node["connections"][0]["note"] not in texts
    assert page.findChild(QObject, "mapShowConnections") is None
    assert page.findChild(QObject, "mapConnectedConceptsTitle") is None
    assert page.property("domainFilter") == "quantitative"
    assert messages == []


def test_map_open_lesson_dialog_scrolls_and_preserves_stats(knowledge_map, qtbot):
    page, nodes, messages = knowledge_map
    viewport = _named(page, "mapViewport")
    qtbot.wait(60)
    expected_width = page.width() - 32
    assert viewport.width() == expected_width
    page.setProperty("selected", nodes[3])
    qtbot.wait(60)
    assert viewport.width() == expected_width
    assert _evaluate(_named(page, "mapLessonContentBlocks"), "count") == 0
    open_lesson = _named(page, "mapOpenLesson")
    assert open_lesson.property("enabled")
    assert not _named(page, "mapLessonDialog").property("visible")
    _invoke(open_lesson, "click")
    qtbot.wait(60)
    dialog = _named(page, "mapLessonDialog")
    scroll = _named(page, "mapLessonDialogScroll")
    assert dialog.property("visible")
    assert scroll.property("contentHeight") > scroll.height()
    texts = [obj.property("text") for obj in _visual_items(scroll)]
    assert "Foundation 2" in texts, str(texts)
    assert "Related case 29" in texts
    assert "Repetitions: 7" in texts
    assert "Next review in 2 days" in texts
    page.setProperty("searchText", "absent skill")
    qtbot.wait(30)
    assert _value(page, "selected") is None
    assert not dialog.property("visible")
    assert messages == []


def test_skill_map_renders_authored_code_lesson_read_only(ui, qtbot):
    win, backend, messages = ui
    code = "value = input('Value:')\nprint(value)"
    backend.tutor.graph.skills["sample.root"].lesson = [{
        "type": "code", "language": "python", "code": code,
    }]
    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    node = next(
        node for node in backend.knowledgeMap()["nodes"] if node["id"] == "sample.root"
    )
    page.setProperty("selected", node)
    _invoke(_named(page, "mapOpenLesson"), "click")
    qtbot.wait(60)

    blocks = _named(page, "mapLessonContentBlocks")
    code_block = _evaluate(blocks, "itemAt(0).children[1]")
    assert _evaluate(code_block, "isDisplayOnly")
    assert _evaluate(code_block, "displayedCode") == code
    assert _named(code_block, "codeLineNumbers").property("text") == "1\n2"
    assert messages == []


def test_map_context_from_prerequisite_payload_without_edges(knowledge_map, qtbot):
    page, nodes, messages = knowledge_map
    nodes[0]["prerequisites"] = ["skill_2"]
    page.setProperty("graph", {"nodes": nodes, "edges": []})
    page.setProperty("searchText", "target")
    assert page.property("matchCount") == 1
    assert page.property("contextCount") == 3
    assert len(_value(page, "visibleNodes")) == 4
    assert _value(page, "visibleEdges") == []
    qtbot.wait(30)
    assert messages == []


def test_map_graph_nodes_show_titles_on_hover(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    viewport = _named(page, "mapViewport")
    page.setProperty("zoom", 1.0)
    page.setProperty("autoFit", False)
    node = next(obj for obj in _visual_items(page) if obj.objectName() == "skillNode")
    node_data = _value(node, "modelData")
    title = node_data["title"]
    assert node.width() == page.property("nodeHitSize")
    assert node.height() == page.property("nodeHitSize")

    center = node.mapToScene(QPointF(node.width() / 2, node.height() / 2))
    viewport_center = viewport.mapToScene(QPointF(viewport.width() / 2, viewport.height() / 2))
    page.setProperty("panX", page.property("panX") + viewport_center.x() - center.x())
    page.setProperty("panY", page.property("panY") + viewport_center.y() - center.y())
    center = node.mapToScene(QPointF(node.width() / 2, node.height() / 2))
    QTest.mouseMove(page.window(), center.toPoint())
    qtbot.wait(300)

    assert _evaluate(_named(node, "skillNodeMouseArea"), "containsMouse"), (
        f"node hover was not received at {center.x()}, {center.y()}"
    )
    assert _evaluate(node, "ToolTip.visible")
    assert _evaluate(node, "ToolTip.text") == title
    assert messages == []


def test_map_shows_titles_when_zoomed_in_on_few_skills(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    page.setProperty("searchText", "target")
    qtbot.wait(30)
    page.setProperty("zoom", 1.3)
    page.setProperty("autoFit", False)
    viewport = _named(page, "mapViewport")
    positions = _value(page, "positions")
    target_position = positions["skill_3"]
    page.setProperty("panX", viewport.width() / 2 - target_position["x"] * 1.3)
    page.setProperty("panY", viewport.height() / 2 - target_position["y"] * 1.3)
    qtbot.wait(30)

    nodes = [obj for obj in _visual_items(page) if obj.objectName() == "skillNode"]
    target = next(obj for obj in nodes if _value(obj, "modelData")["id"] == "skill_3")
    title = target.findChild(QObject, "skillNodeTitle")
    assert page.property("nodesInViewCount") <= 24
    assert page.property("showNodeTitles") is True
    assert title is not None and title.property("visible") is True
    assert messages == []


def test_map_shows_titles_at_high_zoom(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    page.setProperty("searchText", "target")
    qtbot.wait(30)
    viewport = _named(page, "mapViewport")
    position = _value(page, "positions")["skill_3"]
    page.setProperty("zoom", 3.0)
    page.setProperty("autoFit", False)
    page.setProperty("panX", viewport.width() / 2 - position["x"] * 3)
    page.setProperty("panY", viewport.height() / 2 - position["y"] * 3)
    qtbot.wait(30)

    node = next(obj for obj in _visual_items(page) if obj.objectName() == "skillNode")
    title = node.findChild(QObject, "skillNodeTitle")
    assert page.property("nodesInViewCount") <= 24
    assert page.property("showNodeTitles") is True
    assert title is not None and title.property("visible") is True
    title_origin = title.mapToItem(node, QPointF(0, 0))
    assert abs(title_origin.x() - title.x()) <= 1
    rendered_nodes = [item for item in _visual_items(page)
                      if item.objectName() == "skillNode"]
    title_rects = []
    for item in rendered_nodes:
        item_title = item.findChild(QObject, "skillNodeTitle")
        if item_title is None or not item_title.property("visible"):
            continue
        top_left = item_title.mapToItem(viewport, QPointF(0, 0))
        bottom_right = item_title.mapToItem(
            viewport, QPointF(item_title.width(), item_title.height())
        )
        if (bottom_right.x() <= 0 or top_left.x() >= viewport.width()
                or bottom_right.y() <= 0 or top_left.y() >= viewport.height()):
            continue
        title_rects.append((item, top_left, bottom_right))

    for index, (_, first_top_left, first_bottom_right) in enumerate(title_rects):
        for _, second_top_left, second_bottom_right in title_rects[index + 1:]:
            overlaps = (
                first_top_left.x() < second_bottom_right.x()
                and second_top_left.x() < first_bottom_right.x()
                and first_top_left.y() < second_bottom_right.y()
                and second_top_left.y() < first_bottom_right.y()
            )
            assert not overlaps

    for item, top_left, bottom_right in title_rects:
        for other in rendered_nodes:
            if other is item:
                continue
            dot = other.findChild(QObject, "skillNodeDot")
            dot_top_left = dot.mapToItem(viewport, QPointF(0, 0))
            dot_bottom_right = dot.mapToItem(viewport, QPointF(dot.width(), dot.height()))
            center_x = (dot_top_left.x() + dot_bottom_right.x()) / 2
            center_y = (dot_top_left.y() + dot_bottom_right.y()) / 2
            radius = (dot_bottom_right.x() - dot_top_left.x()) / 2
            nearest_x = max(top_left.x(), min(center_x, bottom_right.x()))
            nearest_y = max(top_left.y(), min(center_y, bottom_right.y()))
            assert ((center_x - nearest_x) ** 2 + (center_y - nearest_y) ** 2) ** 0.5 >= radius - 1
    assert messages == []


def test_map_connections_become_clearer_when_zoomed_in(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    page.setProperty("searchText", "target")
    qtbot.wait(30)
    canvas = _named(page, "mapEdgesCanvas")
    assert canvas.property("edgeOpacity") == pytest.approx(0.006)

    viewport = _named(page, "mapViewport")
    position = _value(page, "positions")["skill_3"]
    page.setProperty("zoom", 1.3)
    page.setProperty("autoFit", False)
    page.setProperty("panX", viewport.width() / 2 - position["x"] * 1.3)
    page.setProperty("panY", viewport.height() / 2 - position["y"] * 1.3)
    qtbot.wait(30)

    assert _value(page, "visibleEdges")
    assert page.property("nodesInViewCount") <= 20
    assert canvas.property("edgeOpacity") == pytest.approx(0.42)
    assert canvas.property("edgeLineWidth") == pytest.approx(0.9 / 1.3)
    assert messages == []


def test_map_selection_highlights_and_labels_connected_skills(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    page.setProperty("searchText", "target")
    qtbot.wait(30)
    page.setProperty("zoom", 1.3)
    page.setProperty("autoFit", False)
    viewport = _named(page, "mapViewport")
    positions = _value(page, "positions")
    target_position = positions["skill_3"]
    page.setProperty("panX", viewport.width() / 2 - target_position["x"] * 1.3)
    page.setProperty("panY", viewport.height() / 2 - target_position["y"] * 1.3)
    nodes = [obj for obj in _visual_items(page) if obj.objectName() == "skillNode"]
    target = next(obj for obj in nodes if _value(obj, "modelData")["id"] == "skill_3")

    center = target.mapToScene(QPointF(target.width() / 2, target.height() / 2))
    QTest.mouseClick(page.window(), Qt.LeftButton, Qt.NoModifier, center.toPoint())
    qtbot.wait(30)

    nodes = [obj for obj in _visual_items(page) if obj.objectName() == "skillNode"]
    selected = next(obj for obj in nodes if _value(obj, "modelData")["id"] == "skill_3")
    connected = next(obj for obj in nodes if _value(obj, "modelData")["id"] == "skill_2")
    unrelated = next(obj for obj in nodes if _value(obj, "modelData")["id"] == "skill_1")
    assert _value(page, "selected")["id"] == "skill_3"
    assert _evaluate(page, 'selectedConnectedIds.has("skill_2")')
    assert connected.property("isConnected") is True
    assert connected.property("opacity") == 1
    assert selected.findChild(QObject, "skillNodeConnectionRing") is None
    assert connected.findChild(QObject, "skillNodeConnectionRing") is None
    assert connected.findChild(QObject, "skillNodeTitle").property("visible") is True
    assert _evaluate(page, '!selectedConnectedIds.has("skill_1")')
    assert unrelated.property("opacity") < 1
    QTest.keyClick(page.window(), Qt.Key_Escape)
    qtbot.wait(30)
    assert _value(page, "selected") is None
    assert messages == []


def test_map_node_size_reflects_skill_status(knowledge_map, qtbot):
    page, nodes, messages = knowledge_map
    statuses = ["mastered", "due", "learning", "available", "locked"]
    expected_sizes = {"mastered": 10, "due": 16, "learning": 12, "available": 14, "locked": 7}
    for node, status in zip(nodes, statuses, strict=False):
        node["status"] = status
    page.setProperty("graph", {"nodes": nodes, "edges": []})
    qtbot.wait(30)

    rendered_nodes = [obj for obj in _visual_items(page) if obj.objectName() == "skillNode"]
    nodes_by_status = {
        _value(node, "modelData")["status"]: node
        for node in rendered_nodes[:len(statuses)]
    }
    for status, expected_size in expected_sizes.items():
        node = nodes_by_status[status]
        dot = node.findChild(QObject, "skillNodeDot")
        assert dot is not None
        assert dot.width() == expected_size
        assert node.width() == page.property("nodeHitSize")
        assert node.height() == page.property("nodeHitSize")
    assert messages == []


def test_map_layout_pulls_relationship_neighbors_together(knowledge_map, qtbot):
    page, nodes, messages = knowledge_map
    edges = _value(page, "graph")["edges"] + [
        {"from": "skill_20", "to": "skill_40", "kind": "related", "strength": 1}
    ]
    page.setProperty("graph", {"nodes": nodes, "edges": edges})
    qtbot.wait(30)
    positions = _value(page, "positions")

    def distance(first, second):
        dx = positions[first]["x"] - positions[second]["x"]
        dy = positions[first]["y"] - positions[second]["y"]
        return (dx * dx + dy * dy) ** 0.5

    connected_distance = sum(
        distance(f"skill_{index}", f"skill_{index + 1}") for index in range(3)
    ) / 3
    unrelated_distance = sum(distance("skill_0", f"skill_{index}")
                             for index in (20, 30, 40, 50, 60)) / 5
    related_distance = distance("skill_20", "skill_40")
    assert connected_distance < unrelated_distance
    assert related_distance < unrelated_distance
    assert all(edge.get("kind") != "related" for edge in _value(page, "visibleEdges"))
    assert messages == []


def test_map_layout_scales_to_large_skill_graph(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    count = 638
    nodes = [
        {
            "id": f"large_skill_{index}",
            "title": f"Large skill {index}",
            "category": "test",
            "depth": 0,
            "status": "available",
            "domains": [],
            "sources": [],
            "prerequisites": [],
        }
        for index in range(count)
    ]
    edges = [
        {"from": f"large_skill_{index}", "to": f"large_skill_{index + 1}"}
        for index in range(count - 1)
    ]
    edges.extend(
        {"from": f"large_skill_{index}", "to": f"large_skill_{index + 24}",
         "kind": "related", "strength": 0.8}
        for index in range(count - 24)
        if index % 5 == 0
    )

    started = perf_counter()
    page.setProperty("graph", {"nodes": nodes, "edges": edges})
    layout_seconds = perf_counter() - started

    positions = _value(page, "positions")
    assert len(positions) == count
    assert len(_value(page, "visibleNodes")) == count
    assert layout_seconds < 3
    minimum_distance = min(
        ((positions[nodes[first]["id"]]["x"] - positions[nodes[second]["id"]]["x"]) ** 2
         + (positions[nodes[first]["id"]]["y"] - positions[nodes[second]["id"]]["y"]) ** 2) ** 0.5
        for first in range(count)
        for second in range(first + 1, count)
    )
    assert minimum_distance >= 16

    viewport = _named(page, "mapViewport")
    scene = _named(page, "mapScene")
    page.setProperty("zoom", 1.2)
    page.setProperty("autoFit", False)
    page.setProperty("panX", viewport.width() / 2 - scene.width() * 0.6)
    page.setProperty("panY", viewport.height() / 2 - scene.height() * 0.6)
    qtbot.wait(30)
    assert page.property("nodesInViewCount") > 24
    assert page.property("showNodeTitles") is False
    assert messages == []


def test_map_status_refresh_reuses_static_positions(knowledge_map, qtbot):
    page, nodes, messages = knowledge_map
    edges = _value(page, "graph")["edges"]
    sentinel_positions = dict(_value(page, "positions"))
    sentinel_positions["skill_0"] = {"x": 1234, "y": 567}
    page.setProperty("positions", sentinel_positions)
    page.setProperty("zoom", 1.5)
    page.setProperty("panX", 101)
    page.setProperty("panY", 83)
    page.setProperty("autoFit", False)
    nodes[0]["status"] = "due"

    page.setProperty("graph", {"nodes": nodes, "edges": edges})
    qtbot.wait(30)

    assert _value(page, "positions")["skill_0"] == {"x": 1234, "y": 567}
    assert page.property("zoom") == 1.5
    assert page.property("panX") == 101
    assert page.property("panY") == 83
    node = next(obj for obj in _visual_items(page) if obj.objectName() == "skillNode"
                and _value(obj, "modelData")["id"] == "skill_0")
    assert _value(node, "modelData")["status"] == "due"
    assert node.findChild(QObject, "skillNodeDot").width() == 16
    assert messages == []


@pytest.mark.parametrize("width", [980, 1440])
def test_map_fits_without_scrollbars_and_refits_after_resize(ui, qtbot, width):
    win, _, messages = ui
    win.setProperty("width", width)
    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    viewport = _named(page, "mapViewport")
    scene = _named(page, "mapScene")
    controls = _named(page, "mapControls")
    qtbot.waitUntil(lambda: viewport.width() > 200 and viewport.height() > 200, timeout=2000)
    assert viewport.y() <= 150
    assert _named(page, "mapSearch").height() <= 40
    category = _named(page, "mapCategoryFilter")
    assert category.height() <= 40
    category_text = category.property("contentItem")
    text_height = category_text.property("contentHeight")
    vertical_padding = category_text.property("topPadding") + category_text.property("bottomPadding")
    assert text_height + vertical_padding <= category_text.height()

    def assert_fitted():
        zoom = page.property("zoom")
        assert 0 < zoom <= 1
        assert scene.x() >= 0
        assert scene.y() >= 0
        assert scene.x() + scene.width() * zoom <= viewport.width() + 1
        assert scene.y() + scene.height() * zoom <= viewport.height() + 1
        assert controls.parentItem() == viewport
        assert controls.x() >= 0
        assert controls.y() >= 0
        assert controls.x() + controls.width() == pytest.approx(viewport.width() - 12)
        assert controls.y() + controls.height() == pytest.approx(viewport.height() - 12)

    def wait_for_fit():
        qtbot.waitUntil(lambda: (
            0 < page.property("zoom") <= 1
            and scene.x() >= 0
            and scene.y() >= 0
            and scene.x() + scene.width() * page.property("zoom") <= viewport.width() + 1
            and scene.y() + scene.height() * page.property("zoom") <= viewport.height() + 1
        ), timeout=2000)

    wait_for_fit()
    assert_fitted()
    assert not any("Flickable" in obj.metaObject().className() for obj in viewport.findChildren(QObject))
    win.setProperty("height", 640)
    wait_for_fit()
    assert_fitted()
    page.setProperty("searchText", "cash flow")
    wait_for_fit()
    assert_fitted()
    assert messages == []


def test_map_zoom_controls_anchor_and_limits(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    viewport = _named(page, "mapViewport")

    def click_control(name):
        button = _named(page, name)
        center = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
        QTest.mouseClick(page.window(), Qt.LeftButton, Qt.NoModifier, center.toPoint())

    original_zoom = page.property("zoom")
    click_control("mapZoomIn")
    assert page.property("zoom") == pytest.approx(original_zoom * 1.25)
    click_control("mapZoomOut")
    assert page.property("zoom") == pytest.approx(original_zoom)
    click_control("mapActualSize")
    assert page.property("zoom") == pytest.approx(1)
    anchor_x, anchor_y = viewport.width() * 0.3, viewport.height() * 0.4
    graph_x = (anchor_x - page.property("panX")) / page.property("zoom")
    graph_y = (anchor_y - page.property("panY")) / page.property("zoom")
    assert QMetaObject.invokeMethod(page, "zoomAt", Qt.DirectConnection,
                                   Q_ARG("QVariant", 1.25), Q_ARG("QVariant", anchor_x),
                                   Q_ARG("QVariant", anchor_y))
    assert (anchor_x - page.property("panX")) / page.property("zoom") == pytest.approx(graph_x)
    assert (anchor_y - page.property("panY")) / page.property("zoom") == pytest.approx(graph_y)
    for factor, expected, button in [(1000, 3, "mapZoomIn"), (0.00001, 0.05, "mapZoomOut")]:
        assert QMetaObject.invokeMethod(page, "zoomBy", Qt.DirectConnection, Q_ARG("QVariant", factor))
        assert page.property("zoom") == expected
        assert not _named(page, button).property("enabled")
    click_control("mapFit")
    assert page.property("autoFit") is True
    assert page.property("zoom") == pytest.approx(original_zoom)
    assert _value(page, "selected") is None
    node = next(obj for obj in _visual_items(page) if obj.objectName() == "skillNode")
    zoom_level = _named(page, "mapZoomLevel")
    overlay_center = zoom_level.mapToScene(QPointF(zoom_level.width() / 2, zoom_level.height() / 2))
    node_center = node.mapToScene(QPointF(node.width() / 2, node.height() / 2))
    page.setProperty("panX", page.property("panX") + overlay_center.x() - node_center.x())
    page.setProperty("panY", page.property("panY") + overlay_center.y() - node_center.y())
    QTest.mouseClick(page.window(), Qt.LeftButton, Qt.NoModifier, overlay_center.toPoint())
    assert _value(page, "selected") is None
    click_control("mapFit")
    qtbot.wait(30)
    assert messages == []


def test_map_wheel_keeps_cursor_location_fixed(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    page.setProperty("searchText", "target")
    qtbot.wait(30)
    viewport = _named(page, "mapViewport")
    node = next(obj for obj in _visual_items(page) if obj.objectName() == "skillNode")
    positions = [
        viewport.mapToScene(QPointF(viewport.width() * 0.7, viewport.height() * 0.3)),
        node.mapToScene(QPointF(node.width() / 2, node.height() / 2)),
    ]
    touchpad = QPointingDevice("Test touchpad", 1, QInputDevice.DeviceType.TouchPad,
                              QPointingDevice.PointerType.Finger, QInputDevice.Capability.Position, 2, 0)
    inputs = [
        (False, QPointingDevice.primaryPointingDevice()),
        (True, QPointingDevice.primaryPointingDevice()),
        (True, touchpad),
    ]
    for pixel_input, device in inputs:
        for position in positions:
            anchor = viewport.mapFromScene(position)
            original_zoom = page.property("zoom")
            graph_x = (anchor.x() - page.property("panX")) / original_zoom
            graph_y = (anchor.y() - page.property("panY")) / original_zoom
            for direction in [1, 1, -1, -1]:
                before = page.property("zoom")
                pixel_delta = QPoint(0, direction * 40) if pixel_input else QPoint()
                angle_delta = QPoint() if pixel_input else QPoint(0, direction * 120)
                wheel = QWheelEvent(position, position, pixel_delta, angle_delta, Qt.NoButton,
                                    Qt.NoModifier, Qt.ScrollPhase.ScrollUpdate, False, device=device)
                QCoreApplication.sendEvent(page.window(), wheel)
                after = page.property("zoom")
                assert after > before if direction > 0 else after < before
                assert (anchor.x() - page.property("panX")) / after == pytest.approx(graph_x)
                assert (anchor.y() - page.property("panY")) / after == pytest.approx(graph_y)
            assert page.property("zoom") == pytest.approx(original_zoom)
    assert _value(page, "selected") is None
    assert messages == []


def test_map_pointer_zoom_pan_and_node_selection(knowledge_map, qtbot):
    page, _, messages = knowledge_map
    viewport = _named(page, "mapViewport")
    win = page.window()
    position = viewport.mapToScene(QPointF(12, 12))
    wheel = QWheelEvent(position, position, QPoint(), QPoint(0, 120), Qt.NoButton,
                        Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    original_zoom = page.property("zoom")
    QCoreApplication.sendEvent(win, wheel)
    assert page.property("zoom") == pytest.approx(original_zoom * 1.25)
    _invoke(_named(page, "mapFit"), "click")
    drag_offsets = []
    for _ in range(2):
        start_x, start_y = page.property("panX"), page.property("panY")
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, position.toPoint())
        QTest.mouseMove(win, (position + QPointF(20, 20)).toPoint())
        QTest.mouseMove(win, (position + QPointF(60, 50)).toPoint())
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, (position + QPointF(60, 50)).toPoint())
        assert page.property("panX") > start_x
        assert page.property("panY") > start_y
        assert page.property("autoFit") is False
        drag_offsets.append((page.property("panX") - start_x, page.property("panY") - start_y))
    assert drag_offsets[1] == pytest.approx(drag_offsets[0])
    page.setProperty("searchText", "target")
    qtbot.wait(60)
    node = next(obj for obj in _visual_items(page) if obj.objectName() == "skillNode")
    center = node.mapToScene(QPointF(node.width() / 2, node.height() / 2))
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, center.toPoint())
    assert _value(page, "selected")["id"] == _value(node, "modelData")["id"]
    qtbot.wait(30)
    assert viewport.width() == pytest.approx(page.width() - 32)
    open_lesson = _named(page, "mapOpenLesson")
    assert open_lesson.property("enabled")
    _invoke(open_lesson, "click")
    qtbot.wait(30)
    assert _named(page, "mapLessonDialog").property("visible")
    assert viewport.width() == pytest.approx(page.width() - 32)
    _invoke(_named(page, "mapLessonDialog"), "close")
    qtbot.wait(30)
    QTest.keyClick(win, Qt.Key_Escape)
    qtbot.wait(30)
    assert _value(page, "selected") is None
    assert viewport.width() == pytest.approx(page.width() - 32)
    assert messages == []


@pytest.mark.parametrize("width", [980, 1440])
def test_sample_lesson_guides_render_at_supported_widths(ui, qtbot, width):
    win, backend, messages = ui
    win.setProperty("width", width)
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    assert QMetaObject.invokeMethod(practice, "begin", Qt.DirectConnection, Q_ARG("QVariant", "next"))
    qtbot.wait(60)
    task = _value(practice, "task")
    assert task["guide"]["definition"]
    guide = _named(practice, "practiceLessonGuide")
    texts = [obj.property("text") for obj in _visual_items(guide)]
    assert task["guide"]["definition"] in texts
    for decision in task["guide"]["decision_tree"]:
        assert decision["question"] in texts
        assert decision["yes"] in texts
        assert decision["no"] in texts
    assert guide.width() > 300

    win.setProperty("page", 3)
    page = _find(win, "KnowledgeMapPage")
    nodes = backend.knowledgeMap()["nodes"]
    assert all("guide" not in node and "lesson" not in node for node in nodes)
    for node in nodes:
        page.setProperty("selected", node)
        _invoke(_named(page, "mapOpenLesson"), "click")
        qtbot.wait(2)
        blocks = _named(page, "mapLessonContentBlocks")
        assert blocks is not None, node["id"]
        skill_details = backend.knowledgeMapSkillDetails(node["id"])
        lesson = _value(page, "selectedDetails")["lesson"]
        assert lesson == skill_details["lesson"]
        assert _evaluate(blocks, "count") == len(lesson)
        if lesson:
            assert _evaluate(blocks, "itemAt(0).block") == lesson[0]
    assert any(node["cases"] for node in nodes)
    dialog = _named(page, "mapLessonDialog")
    assert dialog.property("visible")
    dialog_scroll = _named(page, "mapLessonDialogScroll")
    visible_texts = [obj.property("text") for obj in _visual_items(dialog_scroll) if obj.isVisible()]
    assert not any("undefined" in str(text) for text in visible_texts)
    assert "When this comes in handy" not in visible_texts
    assert "How to work through it" not in visible_texts
    assert "Let's make it concrete" not in visible_texts
    assert messages == []


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_decision_flow_balanced_branches_in_practice_guide(ui, qtbot, theme):
    win, backend, messages = ui
    win.setProperty("theme", theme)
    win.setProperty("width", 1440)
    win.setProperty("page", 1)
    practice = _find(win, "PracticePage")
    assert QMetaObject.invokeMethod(practice, "begin", Qt.DirectConnection, Q_ARG("QVariant", "next"))
    guide = _named(practice, "practiceLessonGuide")
    flow = _find(guide, "DecisionFlow")
    decisions = [{"question": "Are annual net benefits constant and positive?",
                  "yes": "Use the simple ratio as a timing approximation, then validate the operating "
                         "assumptions and compare discounted value before choosing an investment.",
                  "no": "Accumulate actual dated cash flows."}]
    flow.setProperty("decisions", decisions)
    qtbot.wait(60)
    flow_side_by_side = flow.width() >= 560
    assert flow.property("sideBySide") is flow_side_by_side
    outcomes = [item for item in _visual_items(flow) if item.objectName() == "decisionOutcome"]
    assert len(outcomes) == 2
    assert abs(outcomes[0].width() - outcomes[1].width()) < 1
    positions = [item.mapToItem(flow, QPointF(0, 0)) for item in outcomes]
    if flow_side_by_side:
        assert abs(outcomes[0].height() - outcomes[1].height()) < 1
        assert abs(positions[0].y() - positions[1].y()) < 1
        assert positions[0].x() + outcomes[0].width() < positions[1].x()
    else:
        assert abs(positions[0].x() - positions[1].x()) < 1
        assert positions[0].y() + outcomes[0].height() < positions[1].y()
    assert messages == []
