import pytest

from repetorium.content import ContentError, validate_bank, validate_library
from repetorium.engine.graph import GraphError, KnowledgeGraph, Skill
from repetorium.generators import generate


def _blocks():
    return [
        {"type": "text", "text": "Read the evidence before drawing a conclusion."},
        {"type": "math", "content": "y = mx + b"},
        {"type": "code", "language": "python", "code": "mean = sum(values) / len(values)"},
        {"type": "table", "headers": ["Trial", "Result"], "rows": [[1, 2.1]]},
        {"type": "chart", "chart": {
            "type": "scatter", "title": "Result by trial", "labels": ["1", "2"],
            "series": [{"name": "Measurement", "values": [2.1, 3.9]}],
        }},
    ]


def test_graph_accepts_typed_lesson_blocks_and_legacy_prose():
    skill = Skill(
        "sample.blocks", "Evidence", "sample", "pct_of",
        lesson=["A prose passage.", *_blocks()],
    )
    graph = KnowledgeGraph([skill])
    assert graph.skills["sample.blocks"].lesson == ["A prose passage.", *_blocks()]


@pytest.mark.parametrize("block", [
    {"type": "table", "headers": ["A", "B"], "rows": [[1]]},
    {"type": "chart", "chart": {
        "type": "scatter", "title": "Invalid labels", "labels": ["first"],
        "series": [{"name": "Series", "values": [1]}],
    }},
    {"type": "code", "language": "python", "code": ""},
    {"type": "unknown", "text": "No renderer"},
])
def test_graph_rejects_malformed_typed_lesson_blocks(block):
    with pytest.raises(GraphError):
        KnowledgeGraph([Skill("sample.blocks", "Evidence", "sample", "pct_of",
                              lesson=[block])])


def test_bank_exhibits_validate_and_explanations_are_required():
    bank = {
        "entries": [{
            "prompt": "What does the evidence support?",
            "correct": "A supported conclusion",
            "distractors": ["An unsupported conclusion"],
            "explain": "The table and stated relationship support the conclusion.",
            "exhibits": _blocks(),
        }]
    }
    validate_bank(bank, "bank_choice")
    with pytest.raises(ContentError, match="needs an explanation"):
        validate_bank({"entries": [{
            "prompt": "Question", "correct": "Answer", "distractors": ["Other"],
        }]}, "bank_choice")


def test_bank_generator_exposes_display_only_exhibits():
    exhibits = _blocks()
    bank = {
        "entries": [{
            "prompt": "Which conclusion fits the plot?",
            "correct": "The values increase",
            "distractors": ["The values decrease"],
            "explain": "Each plotted value is larger than the previous one.",
            "exhibits": exhibits,
        }]
    }
    item = generate("bank_choice", "sample.blocks", 1, 1,
                    {"bank": "test", "_banks": {"test": bank}})
    public = item.public()
    assert public["exhibits"] == exhibits
    assert "answer" not in public and "solution" not in public


def test_mixed_bank_validates_every_supported_response_type():
    bank = {"entries": [
        {"type": "choice", "prompt": "Choose", "correct": "A",
         "distractors": ["B"], "explain": "Reason."},
        {"type": "numeric", "prompt": "Calculate", "answer": 2.5,
         "unit": "kg", "explain": "Reason."},
        {"type": "order", "prompt": "Order", "steps": ["A", "B"],
         "explain": "Reason."},
        {"type": "multi_select", "prompt": "Select all", "correct": ["A", "B"],
         "distractors": ["C"], "explain": "Reason."},
        {"type": "matching", "prompt": "Match", "pairs": [
            {"left": "A", "right": "1"}, {"left": "B", "right": "2"},
        ], "explain": "Reason."},
        {"type": "true_false", "prompt": "True?", "answer": False,
         "explain": "Reason."},
    ]}
    validate_bank(bank, "bank_mixed")


@pytest.mark.parametrize("entry", [
    {"type": "essay", "prompt": "Unsupported", "explain": "Reason."},
    {"type": "short_answer", "prompt": "Text answer", "answer": "Term",
     "explain": "Reason."},
    {"type": "fill_blank", "prompt": "Complete", "answer": "word",
     "explain": "Reason."},
    {"type": "numeric", "prompt": "Not finite", "answer": float("inf"),
     "explain": "Reason."},
    {"type": "true_false", "prompt": "Not a boolean", "answer": "true",
     "explain": "Reason."},
    {"type": "matching", "prompt": "Duplicate", "pairs": [
        {"left": "A", "right": "1"}, {"left": "A", "right": "2"},
    ], "explain": "Reason."},
])
def test_mixed_bank_rejects_unsupported_or_malformed_entries(entry):
    with pytest.raises(ContentError):
        validate_bank({"entries": [entry]}, "bank_mixed")


def test_bank_validation_reports_each_invalid_entry():
    bank = {"entries": [
        {"prompt": "Untyped choice", "correct": "A", "distractors": ["B"],
         "explain": "Reason."},
        {"type": "choice", "prompt": "Missing answer", "distractors": ["B"],
         "explain": "Reason."},
    ]}

    with pytest.raises(ContentError) as error:
        validate_bank(bank, "bank_mixed")

    assert "entry 1" in str(error.value)
    assert "Missing required 'type'" in str(error.value)
    assert "entry 2" in str(error.value)
    assert "Correct answer must be a nonempty string" in str(error.value)


def test_choice_generator_reports_mixed_response_type():
    bank = {"entries": [{
        "type": "multi_select", "prompt": "Select all", "correct": ["A", "B"],
        "distractors": ["C"], "explain": "Reason.",
    }]}

    with pytest.raises(ContentError, match="use bank_mixed"):
        validate_bank(bank, "bank_choice")


def test_difficulty_tags_allow_untagged_fallback():
    bank = {"entries": [
        {"prompt": "Easy", "correct": "A", "distractors": ["B"],
         "difficulty": 1, "explain": "Reason."},
        {"prompt": "Medium", "correct": "A", "distractors": ["B"],
         "difficulty": 2, "explain": "Reason."},
        {"prompt": "Fallback", "correct": "A", "distractors": ["B"],
         "explain": "Reason."},
    ]}

    validate_bank(bank, "bank_choice")
    item = generate("bank_choice", "sample.fallback", 1, 3,
                    {"bank": "fallback", "_banks": {"fallback": bank}})

    assert item.prompt == "Fallback"


def test_difficulty_tags_without_fallback_need_all_three_levels():
    bank = {"entries": [
        {"prompt": "Easy", "correct": "A", "distractors": ["B"],
         "difficulty": 1, "explain": "Reason."},
        {"prompt": "Medium", "correct": "A", "distractors": ["B"],
         "difficulty": 2, "explain": "Reason."},
    ]}

    with pytest.raises(ContentError, match="Hard"):
        validate_bank(bank, "bank_choice")


def test_library_validator_generates_mixed_bank_exercises_at_each_level(tmp_path):
    (tmp_path / "library.yaml").write_text(
        "format: 1\nid: mixed-test\nname: Mixed test\nversion: '1.0'\n",
        encoding="utf-8",
    )
    (tmp_path / "graph").mkdir()
    (tmp_path / "banks").mkdir()
    (tmp_path / "graph" / "sample.yaml").write_text(
        "- id: sample.outcome\n"
        "  title: Explain the outcome\n"
        "  generator: bank_mixed\n"
        "  params: {bank: sample}\n",
        encoding="utf-8",
    )
    (tmp_path / "banks" / "sample.yaml").write_text(
        "entries:\n"
        "  - type: choice\n"
        "    prompt: Which outcome is supported?\n"
        "    correct: result\n"
        "    distractors: [unrelated]\n"
        "    explain: The source defines the result.\n",
        encoding="utf-8",
    )
    manifest, graph = validate_library(tmp_path)
    assert manifest["id"] == "mixed-test"
    assert graph.skills["sample.outcome"].generator == "bank_mixed"
