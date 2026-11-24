import math

import pytest

from repetorium.cases.coach import CaseCoach
from repetorium.cases.templates import load_templates, safe_eval, validate_template
from repetorium.content import validate_library
from repetorium.engine.tutor import Tutor


def test_synthetic_content_fixture_validates_and_instantiates(graph):
    manifest, validated = validate_library(graph.content_dir)
    assert manifest["id"] == "sample-library"
    templates = load_templates(graph.content_dir / "cases")
    case = templates["sample-application"].instantiate(17)
    assert case["questions"][0]["skill"] == "sample.root"
    assert math.isfinite(case["questions"][0]["answer"])


def test_case_arithmetic_evaluator_rejects_executable_or_unbounded_input():
    assert safe_eval("amount * (1 + rate / 100)", {"amount": 10, "rate": 50}) == 15
    for bad in ["__import__('os')", "amount.__class__", "open('x')", "[1, 2]"]:
        with pytest.raises((ValueError, NameError)):
            safe_eval(bad, {"amount": 1})


def test_case_schema_rejects_invalid_questions(graph):
    template = load_templates(graph.content_dir / "cases")["sample-application"]
    raw = dict(template.raw)
    raw["questions"] = [{"prompt": "Missing a skill reference", "answer": 0}]
    with pytest.raises(ValueError, match="Case question skill"):
        validate_template(raw)


def test_case_session_records_and_removes_run_without_erasing_later_progress(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    coach = CaseCoach(tutor)
    case = coach.start("sample-application")
    assert case["questions"] and "answer" not in case["questions"][0]
    question = coach.case["questions"][0]
    feedback = coach.answer(0, str(question["answer"]))
    assert feedback["correct"]
    coach.finish("Notes", "Measure and compare", "Report the rate.")
    result = coach.submit_scores({"math": 3, "structure": 4})
    assert result["xp"] > 0
    run_id = coach.history()[0]["id"]
    assert coach.delete_history(run_id)
    assert coach.history() == []
    assert tutor.store.xp_total() == 0


def test_case_coach_rejects_unknown_template(conn, graph, clock):
    coach = CaseCoach(Tutor(conn, graph, clock))
    with pytest.raises(ValueError, match="Unknown case"):
        coach.start("missing-case")
