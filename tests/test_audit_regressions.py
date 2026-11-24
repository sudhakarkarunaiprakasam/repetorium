import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from repetorium import app, library
from repetorium.cases.templates import load_templates, render, safe_eval
from repetorium.content import ContentError, read_manifest, validate_library
from repetorium.core.db import connect
from repetorium.generators.banks import load_bank
from repetorium.generators.base import Item, check, describe_response, interpret, parse_number
from repetorium.paths import default_db_path, legacy_db_path


def write_library(directory, *, bank=False):
    directory.mkdir(parents=True)
    (directory / "library.yaml").write_text(yaml.safe_dump({
        "format": 1, "id": "audit", "name": "Audit library", "version": "1",
    }), encoding="utf-8")
    (directory / "graph").mkdir()
    skill = {"id": "audit.skill", "title": "Audit skill", "generator": "pct_of"}
    if bank:
        skill.update(generator="bank_choice", params={"bank": "audit"})
        (directory / "banks").mkdir()
        (directory / "banks" / "audit.yaml").write_text(yaml.safe_dump({
            "entries": [{"prompt": "Choose", "correct": "Right", "distractors": ["Wrong"]}],
        }), encoding="utf-8")
    (directory / "graph" / "audit.yaml").write_text(yaml.safe_dump([skill]), encoding="utf-8")
    return directory


def template():
    return {
        "id": "audit_case", "title": "Audit case", "archetype": "Math",
        "prompt": "Calculate an answer.",
        "questions": [{"prompt": "How much?", "answer": "2 + 3", "skill": "audit.skill"}],
    }


def write_case(directory, raw):
    cases = directory / "cases"
    cases.mkdir(exist_ok=True)
    (cases / "audit.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return cases


@pytest.mark.parametrize("response", [
    "9" * 400, "-" + "9" * 400, "9" * 300 + "T", "-" + "9" * 300 + " trillion",
])
@pytest.mark.parametrize("unit", ["", "$", "$M", "%"])
def test_nonfinite_numeric_responses_are_invalid(response, unit):
    item = Item("Calculate", "numeric", 5, "Five", unit=unit)
    assert parse_number(response) is None
    assert interpret(response, unit) is None
    assert describe_response(response, unit) == ""
    assert not check(item, response)


@pytest.mark.parametrize("response,value", [
    ("$0.05M", 0.05), ("$-0.03M", -0.03), ("18K", 0.018), ("0.018 million", 0.018),
    ("0.018", 0.018), ("45", 45), ("45000000", 45),
])
def test_million_units_respect_explicit_small_scales(response, value):
    assert interpret(response, "$M") == pytest.approx(value)


@pytest.mark.parametrize("answer,unit,tolerance", [
    (0.018, "$M", 0.03), (0.000018, "$M", 0.03), (1.234567, "$", 0),
    (0.018, "%", 0), (1.234567, "years", 0),
])
def test_displayed_model_answer_meets_its_own_tolerance(answer, unit, tolerance):
    item = Item("Calculate", "numeric", answer, "Solution", unit=unit, tolerance=tolerance)
    assert check(item, item.answer_text())


def test_small_case_values_keep_meaningful_solution_precision():
    shown = render("Expected saving: {saving}M.", {"saving": 0.01799999999999999})
    assert shown == "Expected saving: 0.018M."


@pytest.mark.parametrize("answer,unit,response", [
    (10, "million cubic meters", "10 million cubic meters"),
    (10, "million cubic meters", "10 million"),
    (16, "$B", "$16B"), (16, "$B", "16"),
    (624, "$M^2", "624 $M^2"),
    (0.3, "expected illnesses/$1000", "0.3 expected illnesses/$1000"),
    (8000, "unit-days", "8K unit-days"),
])
def test_declared_units_do_not_corrupt_numeric_values(answer, unit, response):
    item = Item("Calculate", "numeric", answer, "Solution", unit=unit)
    assert check(item, response)
    assert check(item, item.answer_text())


@pytest.mark.parametrize("expression", [
    "2 ** (2 ** 40)", "2 ** 10000", "10 ** 1000", "'x' * 1000000000",
    "1e309", "1e308 * 10", "(-1) ** 0.5", "+".join(["1"] * 200), "1+" * 3000,
    "(", "__import__('os')", "a.__class__",
])
def test_case_expressions_reject_unbounded_or_unsupported_results(expression):
    with pytest.raises(ValueError):
        safe_eval(expression, {"a": 1})


def test_case_expression_language_preserves_supported_arithmetic():
    assert safe_eval("round(a * (1 + b / 100), 2)", {"a": 10, "b": 50}) == 15
    assert safe_eval("max(ceil(a / 3), 1) if a > 0 else 0", {"a": 10}) == 4
    assert safe_eval("client", {"client": "A company"}) == "A company"
    assert safe_eval("2 ** 20", {}) == 1048576


@pytest.mark.parametrize("mutation", [
    "negative-tolerance", "infinite-tolerance", "bool-minutes", "string-minutes",
    "empty-params", "bad-param-alternative", "bad-variant-alternative",
    "bad-rubric", "bad-table", "bad-chart", "infinite-answer", "invalid-expression",
])
def test_invalid_case_content_is_rejected(tmp_path, mutation):
    directory = write_library(tmp_path / "library")
    raw = template()
    if mutation == "negative-tolerance":
        raw["questions"][0]["tolerance"] = -0.1
    elif mutation == "infinite-tolerance":
        raw["questions"][0]["abs_tolerance"] = float("inf")
    elif mutation == "bool-minutes":
        raw["minutes"] = True
    elif mutation == "string-minutes":
        raw["minutes"] = "25"
    elif mutation == "empty-params":
        raw["params"] = {"a": []}
    elif mutation == "bad-param-alternative":
        raw["params"] = {"a": [1, float("nan")]}
    elif mutation == "bad-variant-alternative":
        raw["variants"] = [{}, {"a": []}]
    elif mutation == "bad-rubric":
        raw["rubric_skills"] = {"math": "audit.skill"}
    elif mutation == "bad-table":
        raw["data"] = [{
            "category": "Data", "title": "Table", "table": {"headers": ["One"], "rows": [[1, 2]]},
        }]
    elif mutation == "bad-chart":
        raw["data"] = [{
            "category": "Data", "title": "Chart",
            "chart": {"title": "Trend", "labels": ["One"], "series": [{"name": "Values", "values": []}]},
        }]
    elif mutation == "infinite-answer":
        raw["questions"][0]["answer"] = "1e308 * 10"
    else:
        raw["derived"] = {"a": "("}
    write_case(directory, raw)
    with pytest.raises(ContentError):
        validate_library(directory)


def test_manifest_format_cannot_be_boolean(tmp_path):
    directory = write_library(tmp_path / "library")
    manifest = yaml.safe_load((directory / "library.yaml").read_text(encoding="utf-8"))
    manifest["format"] = True
    (directory / "library.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    with pytest.raises(ContentError, match="format"):
        read_manifest(directory)


def test_library_reload_validates_current_bank_file(tmp_path):
    directory = write_library(tmp_path / "library", bank=True)
    load_bank("audit", directory)
    (directory / "banks" / "audit.yaml").write_text("entries: []", encoding="utf-8")
    with pytest.raises(ContentError, match="nonempty"):
        validate_library(directory)


def test_library_validation_reports_all_invalid_banks_with_context(tmp_path):
    directory = write_library(tmp_path / "library")
    (directory / "banks").mkdir()
    (directory / "graph" / "audit.yaml").write_text(yaml.safe_dump([
        {
            "id": "first.skill", "title": "First skill", "generator": "bank_mixed",
            "params": {"bank": "first"},
        },
        {
            "id": "second.skill", "title": "Second skill", "generator": "bank_choice",
            "params": {"bank": "second"},
        },
    ]), encoding="utf-8")
    (directory / "banks" / "first.yaml").write_text(yaml.safe_dump({
        "entries": [{
            "prompt": "Untyped choice", "correct": "A", "distractors": ["B"],
            "explain": "Reason.",
        }],
    }), encoding="utf-8")
    (directory / "banks" / "second.yaml").write_text(yaml.safe_dump({
        "entries": [{
            "type": "multi_select", "prompt": "Select all", "correct": ["A", "B"],
            "distractors": ["C"], "explain": "Reason.",
        }],
    }), encoding="utf-8")

    with pytest.raises(ContentError) as error:
        validate_library(directory)

    message = str(error.value)
    assert "banks/first.yaml (first.skill, bank_mixed)" in message
    assert "entry 1" in message
    assert "Missing required 'type'" in message
    assert "banks/second.yaml (second.skill, bank_choice)" in message
    assert "bank_choice only accepts choice items" in message


def test_library_reload_validates_current_case_file(tmp_path):
    directory = write_library(tmp_path / "library")
    cases = write_case(directory, template())
    load_templates(cases)
    (cases / "audit.yaml").write_text("id: broken", encoding="utf-8")
    with pytest.raises(ContentError, match="title"):
        validate_library(directory)


def test_case_tables_allow_blank_and_numeric_column_headers(tmp_path):
    directory = write_library(tmp_path / "library")
    raw = template()
    raw["data"] = [{
        "category": "Data", "title": "Table",
        "table": {"headers": ["", 0, "Value"], "rows": [["Metric", 1, 2]]},
    }]
    write_case(directory, raw)
    validate_library(directory)


def add_progress(path, amount):
    connection = connect(path)
    connection.execute("INSERT INTO xp_ledger (ts, amount, reason) VALUES (10, ?, 'lesson')", (amount,))
    connection.commit()
    connection.close()


def test_failed_legacy_schema_migration_does_not_publish_destination(tmp_path, monkeypatch):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path))
    directory = tmp_path / "library"
    source = legacy_db_path(directory)
    add_progress(source, 30)

    def fail_migration(path):
        assert path.suffix == ".migrating"
        raise sqlite3.DatabaseError("Migration failed")

    monkeypatch.setattr(library, "connect", fail_migration)
    with pytest.raises(sqlite3.DatabaseError, match="Migration failed"):
        library.open_progress(directory)
    assert not default_db_path().exists()
    assert not default_db_path().with_suffix(".migrating").exists()
    original = sqlite3.connect(source)
    assert original.execute("SELECT amount FROM xp_ledger").fetchone()[0] == 30
    original.close()


@pytest.mark.parametrize("phase", ["tutor", "backend", "engine", "no-root", "exec"])
def test_application_closes_progress_on_startup_and_runtime_failures(monkeypatch, phase):
    connection = Mock()
    failure = RuntimeError("Startup failure")
    gui = Mock()
    gui.exec.side_effect = failure
    monkeypatch.setattr(app, "configure_windows_taskbar", lambda: None)
    monkeypatch.setattr(app.QQuickStyle, "setStyle", lambda style: None)
    monkeypatch.setattr(app, "QGuiApplication", lambda args: gui)
    monkeypatch.setattr(app, "QIcon", lambda path: object())
    monkeypatch.setattr(app, "load_selected_library", lambda store: object())
    monkeypatch.setattr(app, "open_progress", lambda directory: connection)
    monkeypatch.setattr(app, "Tutor", Mock(side_effect=failure if phase == "tutor" else None))
    monkeypatch.setattr(app, "CaseCoach", Mock())
    monkeypatch.setattr(app, "Backend", Mock(side_effect=failure if phase == "backend" else None))
    engine = SimpleNamespace(rootObjects=lambda: [] if phase == "no-root" else [object()])
    monkeypatch.setattr(app, "create_engine", Mock(
        side_effect=failure if phase == "engine" else None, return_value=engine,
    ))
    if phase == "no-root":
        assert app.main() == 1
    else:
        with pytest.raises(RuntimeError, match="Startup failure"):
            app.main()
    connection.close.assert_called_once()
