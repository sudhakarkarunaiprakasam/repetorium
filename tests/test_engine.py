import pytest

from repetorium.engine.graph import GraphError, KnowledgeGraph, Skill
from repetorium.engine.learning_settings import ADAPTIVE_PRESETS, AdaptiveSettings
from repetorium.engine.scheduler import DAY, Scheduler, interval_days
from repetorium.engine.store import SkillState


def test_graph_is_valid(graph):
    assert graph.skills
    assert set(graph.topological_order) == set(graph.skills)


def test_cycle_detected():
    with pytest.raises(GraphError):
        KnowledgeGraph([
            Skill("a", "A", "sample", "pct_of", prereqs=["b"]),
            Skill("b", "B", "sample", "pct_of", prereqs=["a"]),
        ])


def test_encompassing_must_be_ancestor():
    with pytest.raises(GraphError):
        KnowledgeGraph([
            Skill("a", "A", "sample", "pct_of"),
            Skill("b", "B", "sample", "pct_of", encompasses={"a": 0.5}),
        ])


def test_implicit_credit_flows_transitively(graph):
    credit = graph.implicit_credit("sample.followup")
    assert credit["sample.root"] == pytest.approx(0.5)
    assert all(c >= 0.05 for c in credit.values())


def _mastered_states(graph, now):
    states = {sid: SkillState(sid) for sid in graph.skills}
    for st in states.values():
        st.status, st.reps, st.due, st.last_reviewed = "mastered", 1.0, now + DAY, now
    return states


def test_review_of_advanced_skill_pushes_back_simpler_reviews(graph):
    now = 1_000_000.0
    review_graph = KnowledgeGraph([
        Skill("sample.base", "Base", "sample", "unit_rates"),
        Skill("sample.advanced", "Advanced", "sample", "unit_rates",
              prereqs=["sample.base"], encompasses={"sample.base": 0.5}),
        Skill("sample.other", "Other", "other", "unit_rates"),
    ])
    states = _mastered_states(review_graph, now)
    sched = Scheduler(review_graph, states)
    before = states["sample.base"].due
    sched.review("sample.advanced", True, now + DAY)
    assert states["sample.base"].due > before
    assert states["sample.base"].reps > 1.0
    assert states["sample.other"].due == before


def test_failed_review_comes_back_soon(graph):
    now = 1_000_000.0
    states = _mastered_states(graph, now)
    states["sample.root"].reps = 4
    Scheduler(graph, states).review("sample.root", False, now)
    assert states["sample.root"].due - now < DAY
    assert states["sample.root"].reps == 2
    assert states["sample.followup"].due <= now + DAY


def test_adaptive_review_settings_control_growth_cap_and_retry(graph):
    now = 1_000_000.0
    states = _mastered_states(graph, now)
    settings = AdaptiveSettings(
        review_growth_factor=1.5,
        max_review_interval_days=60,
        review_retry_hours=2,
    )
    scheduler = Scheduler(graph, states, settings)

    scheduler.review("sample.root", True, now)
    assert states["sample.root"].due == now + 1.5 * DAY
    states["sample.followup"].reps = 100
    scheduler.review("sample.followup", True, now)
    assert states["sample.followup"].due == now + 60 * DAY
    scheduler.review("sample.root", False, now + DAY)
    assert states["sample.root"].due == now + DAY + 2 * 3600


def test_learning_presets_have_consistent_difficulty_order():
    easy, balanced, hard = (
        ADAPTIVE_PRESETS[name] for name in ("easy", "balanced", "hard")
    )

    assert easy["mastery_streak"] <= balanced["mastery_streak"] <= hard["mastery_streak"]
    for key in ("review_retry_hours", "mixed_quiz_every"):
        assert easy[key] >= balanced[key] >= hard[key]
    for key in ("review_growth_factor", "max_review_interval_days"):
        assert easy[key] >= balanced[key] >= hard[key]
    assert easy["mixed_quiz_size"] <= balanced["mixed_quiz_size"] <= hard["mixed_quiz_size"]

    for reps in (1, 2, 3, 5, 10):
        intervals = [
            interval_days(reps, preset["review_growth_factor"],
                          preset["max_review_interval_days"])
            for preset in (easy, balanced, hard)
        ]
        assert intervals[0] >= intervals[1] >= intervals[2]
