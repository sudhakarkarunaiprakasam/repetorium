import pytest

from repetorium.generators import check, generate
from repetorium.generators.base import describe_response, format_answer, parse_number


@pytest.mark.parametrize("text,value", [
    ("1,200", 1200), ("$3.5M", 3.5e6), ("2.4 bn", 2.4e9), ("12.5%", 12.5), ("-20", -20),
    ("450k", 450e3), ("1.5 million", 1.5e6), ("2x", 2), ("abc", None), ("", None),
    ("24,000 visits/year", 24000), ("3/4", None),
])
def test_parse_number(text, value):
    assert parse_number(text) == value


def test_every_skill_generates_valid_gradable_items(graph):
    for sid, skill in graph.skills.items():
        for d in (1, 2, 3):
            for seed in range(25):
                item = generate(skill.generator, sid, seed, d, skill.params)
                assert item.prompt and item.solution, sid
                if item.kind == "numeric":
                    assert check(item, repr(item.answer)), (sid, item.prompt)
                    assert check(item, format_answer(item.answer, item.unit)), (
                        sid, item.answer, format_answer(item.answer, item.unit))
                elif item.kind == "choice":
                    assert len(set(item.choices)) == len(item.choices), (sid, item.choices)
                    assert check(item, str(item.answer))
                else:
                    assert sorted(item.answer) == list(range(len(item.choices)))
                    assert check(item, ",".join(map(str, item.answer)))


def test_generation_is_deterministic(graph):
    for sid, skill in graph.skills.items():
        a = generate(skill.generator, sid, 42, 2, skill.params)
        b = generate(skill.generator, sid, 42, 2, skill.params)
        assert a.public() == b.public()


def test_public_hides_answer(graph):
    item = generate("pct_of", "sample.percent", 1, 1, {})
    assert "answer" not in item.public() and "solution" not in item.public()
    assert "dollars" in item.public()["unitHint"]


def test_authored_follow_up_is_revealed_only_after_answer():
    bank = {
        "entries": [{
            "prompt": "Question",
            "correct": "A",
            "distractors": ["B"],
            "explain": "Reason",
            "follow_up_prompt": "What if the assumption changed?",
        }]
    }
    item = generate("bank_choice", "test.skill", 1, 1,
                    {"bank": "test", "_banks": {"test": bank}})
    assert item.follow_up_prompt == "What if the assumption changed?"
    assert "follow_up_prompt" not in item.public()


@pytest.mark.parametrize(("difficulty", "prompt"), [
    (1, "Easy question"), (2, "Medium question"), (3, "Hard question"),
])
def test_bank_choice_selects_question_at_requested_difficulty(difficulty, prompt):
    bank = {
        "entries": [
            {"prompt": label + " question", "correct": "A", "distractors": ["B"],
             "difficulty": level}
            for level, label in enumerate(("Easy", "Medium", "Hard"), start=1)
        ]
    }
    item = generate("bank_choice", "test.skill", 1, difficulty,
                    {"bank": "test", "_banks": {"test": bank}})
    assert item.prompt == prompt


@pytest.mark.parametrize(("entry", "response", "kind", "answer"), [
    ({"type": "true_false", "prompt": "True?", "answer": True},
     "0", "true_false", 0),
    ({"type": "numeric", "prompt": "Calculate", "answer": 2.5, "unit": "kg"},
     "2.5 kg", "numeric", 2.5),
])
def test_bank_mixed_generates_boolean_and_numeric_items(entry, response, kind, answer):
    entry["explain"] = "Source-grounded explanation."
    item = generate("bank_mixed", "test.skill", 42, 2,
                    {"bank": "test", "_banks": {"test": {"entries": [entry]}}})
    assert item.kind == kind
    assert item.answer == answer
    assert check(item, response)
    assert item.solution == "Source-grounded explanation."


def test_bank_mixed_grades_multi_select_matching_and_orders():
    cases = [
        ({"type": "multi_select", "prompt": "Select all", "correct": ["A", "B"],
          "distractors": ["C"]}, None, "multi_select"),
        ({"type": "matching", "prompt": "Match", "pairs": [
            {"left": "A", "right": "1"}, {"left": "B", "right": "2"},
        ]}, None, "matching"),
        ({"type": "order", "prompt": "Order", "steps": ["First", "Second"]},
         None, "order"),
    ]
    for seed, (entry, response, kind) in enumerate(cases):
        entry["explain"] = "Source-grounded explanation."
        item = generate("bank_mixed", "test.skill", seed, 2,
                        {"bank": "test", "_banks": {"test": {"entries": [entry]}}})
        assert item.kind == kind
        if response is None:
            response = ",".join(map(str, item.answer))
        assert check(item, response)
        assert item.answer_text()
        assert "answer" not in item.public()


def test_bank_mixed_prefers_a_less_recently_used_format():
    bank = {"entries": [
        {"type": "choice", "prompt": "Choice", "correct": "A",
         "distractors": ["B"], "explain": "Reason."},
        {"type": "true_false", "prompt": "True?", "answer": True, "explain": "Reason."},
    ]}
    item = generate("bank_mixed", "test.skill", 1, 2,
                    {"bank": "test", "_banks": {"test": bank},
                     "_recent_kinds": ["choice", "choice", "choice"]})
    assert item.kind == "true_false"
    assert item.prompt == "True?"


@pytest.mark.parametrize("text,unit,shown", [
    ("180000000000", "$", "$180B"), ("1.8b", "$", "$1.8B"), ("450k", "$", "$450K"),
    ("45", "$M", "$45M"), ("$45M", "$M", "$45M"), ("12.5", "%", "12.5%"), ("oops", "$", ""),
])
def test_describe_response(text, unit, shown):
    assert describe_response(text, unit) == shown


def test_wrong_numeric_rejected():
    item = generate("breakeven", "sample.threshold", 3, 2, {})
    assert not check(item, str(item.answer * 1.5))
    assert not check(item, "not a number")


def test_percentage_answers_reject_off_by_one_point(graph):
    for sid, skill in graph.skills.items():
        for seed in range(25):
            item = generate(skill.generator, sid, seed, 2, skill.params)
            if item.kind == "numeric" and item.unit == "%":
                assert not check(item, str(item.answer + 1)), (sid, item.answer)
                assert not check(item, str(item.answer - 1)), (sid, item.answer)
