from collections import Counter

import pytest
from conftest import correct_response, wrong_response

from repetorium.engine.graph import Connection, KnowledgeGraph, Skill
from repetorium.engine.scheduler import DAY, RETRY_DELAY
from repetorium.engine.tutor import (
    DIAGNOSTIC_MAX,
    LESSON_MAX_ERRORS,
    LESSON_STREAK_TO_MASTER,
    Task,
    Tutor,
)


def run_task(tutor, answer):
    task = tutor.select_task()
    while (item := tutor.next_item()) is not None:
        fb = tutor.submit(answer(item), seconds=20)
        if fb.task_done:
            break
    return task


def _tutor_with_pack_goals(conn, clock, goals, total_goal):
    skills = []
    skill_pack_ids = {}
    skill_pack_names = {}
    for pack_id in goals:
        for index in range(3):
            skill_id = f"{pack_id}.skill-{index}"
            skills.append(Skill(skill_id, f"{pack_id} skill {index}", pack_id, "unit_rates"))
            skill_pack_ids[skill_id] = pack_id
            skill_pack_names[skill_id] = pack_id
    graph = KnowledgeGraph(skills)
    graph.skill_pack_ids = skill_pack_ids
    graph.skill_pack_names = skill_pack_names
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.store.set("setting.content_pack_ids", list(goals))
    tutor.store.set("setting.content_pack_weekly_goals", goals)
    tutor.store.set("setting.lessons_per_week_goal", total_goal)
    return tutor


def test_first_task_is_a_root_lesson(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    task = tutor.select_task()
    assert task.kind == "lesson"
    assert graph.skills[task.skill_ids[0]].prereqs == []


def test_adaptive_mastery_streak_persists_and_changes_completion(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.set_adaptive_setting("mastery_streak", 2)

    task = tutor.select_task()
    for _ in range(2):
        item = tutor.next_item()
        feedback = tutor.submit(correct_response(item), seconds=20)

    assert feedback.task_done
    assert tutor.states[task.skill_ids[0]].mastered
    assert Tutor(conn, graph, clock, seed=1).adaptive_settings.mastery_streak == 2


def test_adaptive_quiz_settings_control_cadence_and_size(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.set_adaptive_setting("mixed_quiz_every", 4)
    tutor.set_adaptive_setting("mixed_quiz_size", 3)
    for sid in list(tutor.states)[:3]:
        tutor.states[sid].status = "mastered"

    tutor.store.set("tasks_since_quiz", 3)
    assert tutor._quiz_task() is None
    tutor.store.set("tasks_since_quiz", 4)
    quiz = tutor._quiz_task()
    assert quiz is not None
    assert len(quiz.skill_ids) == 3
    assert quiz.difficulty == 1
    assert quiz.title == "Mixed quiz · Easy"
    tutor.task = quiz
    item = tutor.next_item()
    assert item.difficulty == 1
    assert tutor.submit(correct_response(item), seconds=20).xp == 1
    for state in tutor.states.values():
        state.reps = 4
    assert tutor._quiz_task().difficulty == 3


@pytest.mark.parametrize(
    ("key", "value", "default"),
    [
        ("mastery_streak", 1, 3),
        ("mixed_quiz_size", True, 5),
        ("review_growth_factor", 1.1, 2.5),
    ],
)
def test_invalid_adaptive_settings_are_rejected_without_persisting(
    conn, graph, clock, key, value, default,
):
    tutor = Tutor(conn, graph, clock, seed=1)

    with pytest.raises(ValueError):
        tutor.set_adaptive_setting(key, value)

    assert tutor.store.get(f"setting.{key}") is None
    assert getattr(tutor.adaptive_settings, key) == default


def test_lesson_selection_interleaves_recently_connected_subjects(conn, clock):
    graph = KnowledgeGraph(
        [
            Skill("sample.rates", "Rates", "sample", "unit_rates"),
            Skill("related.demand", "Demand", "related", "unit_rates"),
            Skill("other.cells", "Cells", "other", "unit_rates"),
        ],
        connections=[
            Connection("sample.rates", "related.demand", "application", 0.9,
                       "Rates quantify how quantity responds to price.")
        ],
    )
    tutor = Tutor(conn, graph, clock, seed=4)
    tutor.store.log_attempt(clock(), "sample.rates", "lesson", 1, 2, "correct", True, 20)

    task = tutor.select_task()

    assert task.kind == "lesson"
    assert task.skill_ids == ["related.demand"]


def test_mixed_bank_practice_rotates_response_types_per_skill(conn, clock):
    graph = KnowledgeGraph([
        Skill("mixed.skill", "Mixed skill", "sample", "bank_mixed", {"bank": "mixed"})
    ])
    graph.practice_banks = {"mixed": {"entries": [
        {"type": "choice", "prompt": "Choose", "correct": "A",
         "distractors": ["B"], "explain": "Reason."},
        {"type": "true_false", "prompt": "True?", "answer": True,
         "explain": "Reason."},
    ]}}
    graph.case_templates = {}
    tutor = Tutor(conn, graph, clock, seed=3)

    first = tutor.generate_practice_item("mixed.skill", 1, 2)
    second = tutor.generate_practice_item("mixed.skill", 2, 2)

    assert {first.kind, second.kind} == {"choice", "true_false"}
    assert tutor.store.get("practice_kinds.mixed.skill") == [first.kind, second.kind]


def test_recent_session_history_stays_bounded_and_preserves_lesson_recency(conn, clock):
    graph = KnowledgeGraph([
        Skill(f"skill.{index}", f"Skill {index}", "sample", "pct_of")
        for index in range(12)
    ])
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.set_adaptive_setting("mastery_streak", 2)
    tutor.set_adaptive_setting("mixed_quiz_every", 20)
    completed = []

    for _ in range(12):
        task = tutor.select_task()
        assert task.kind == "lesson"
        completed.append(task.skill_ids[0])
        while not task.done:
            item = tutor.next_item()
            tutor.submit(correct_response(item), seconds=20)

    assert tutor.history == [("lesson", sid) for sid in completed[-2:]]
    assert tutor.recent_lesson_skills == list(reversed(completed[-8:]))


def test_diagnostic_bitset_selection_matches_graph_traversal(conn, clock):
    graph = KnowledgeGraph([
        Skill(
            f"skill.{index}", f"Skill {index}", "sample", "pct_of",
            prereqs=[f"skill.{index - 1}"] if index else [],
        )
        for index in range(128)
    ])
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.start_diagnostic()
    unclassified = set(graph.skills)

    def old_score(skill_id):
        ancestors = len(graph.ancestors(skill_id) & unclassified)
        descendants = len(graph.descendants(skill_id) & unclassified)
        return min(ancestors, descendants), ancestors + descendants, -tutor._topo_index[skill_id]

    assert tutor._diagnostic_pick() == max(unclassified, key=old_score)
    tutor.task.uncertain.add("skill.64")
    unclassified.remove("skill.64")
    assert tutor._diagnostic_pick() == max(unclassified, key=old_score)


def test_failed_assessment_queues_prerequisites_and_target(conn, clock):
    graph = KnowledgeGraph([
        Skill("sample.rates", "Rates", "sample", "unit_rates"),
        Skill("related.demand", "Demand", "related", "unit_rates",
              prereqs=["sample.rates"]),
        Skill("other.pricing", "Pricing", "other", "unit_rates",
              prereqs=["related.demand"]),
    ])
    tutor = Tutor(conn, graph, clock, seed=4)

    tutor.record_assessment_result("other.pricing", False, clock())
    assert tutor.store.get("remediation") == [
        "sample.rates", "related.demand", "other.pricing"
    ]

    first = tutor.select_task()
    assert first.kind == "lesson" and first.skill_ids == ["sample.rates"]
    run_task_existing(tutor, correct_response)
    second = tutor.select_task()
    assert second.kind == "lesson" and second.skill_ids == ["related.demand"]
    assert tutor.store.get("remediation") == ["other.pricing"]


def test_correct_assessment_does_not_master_an_unlearned_skill(conn, clock):
    graph = KnowledgeGraph([Skill("sample.rates", "Rates", "sample", "unit_rates")])
    tutor = Tutor(conn, graph, clock, seed=4)

    touched = tutor.record_assessment_result("sample.rates", True, clock())

    assert touched == [tutor.states["sample.rates"]]
    assert tutor.states["sample.rates"].status == "learning"
    assert not tutor.states["sample.rates"].mastered
    assert tutor.store.get("remediation", []) == []


def test_reporting_includes_new_library_categories(conn, clock):
    graph = KnowledgeGraph([Skill(id="sample.cells", title="Cells", category="sample",
                                  generator="bank_choice")])
    tutor = Tutor(conn, graph, clock, seed=1)

    assert tutor.dashboard()["categories"] == [
        {"key": "sample", "title": "Sample", "mastered": 0, "total": 1}
    ]
    assert tutor.stats()["categories"] == [{"title": "Sample", "correct": 0, "total": 0}]


def test_lesson_mastery_after_streak(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    task = run_task(tutor, correct_response)
    sid = task.skill_ids[0]
    assert tutor.states[sid].mastered
    assert task.answered == LESSON_STREAK_TO_MASTER
    assert tutor.store.xp_total() > 0


def test_opening_lesson_does_not_advance_mastery_streak(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    skill_id = "sample.choice"
    tutor.states[skill_id].lesson_streak = LESSON_STREAK_TO_MASTER - 1
    tutor.task = Task("lesson", [skill_id], "Lesson")
    item = tutor.next_item()

    feedback = tutor.submit(
        correct_response(item),
        seconds=20,
        confidence="explained",
        lesson_opened=True,
    )

    assert feedback.correct and not feedback.task_done
    assert tutor.states[skill_id].lesson_streak == 0
    assert not tutor.states[skill_id].mastered
    attempt = tutor.store.conn.execute(
        "SELECT confidence FROM attempts"
    ).fetchone()
    assert attempt["confidence"] == "explained"


def test_lesson_does_not_repeat_questions_within_a_streak(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    skill_id = "sample.choice"
    tutor.task = Task("lesson", [skill_id], "Lesson")
    prompts = []

    for _ in range(LESSON_STREAK_TO_MASTER):
        item = tutor.next_item()
        prompts.append(item.prompt)
        tutor.submit(str(item.answer), seconds=20)

    assert len(set(prompts)) == LESSON_STREAK_TO_MASTER


def test_bank_lesson_avoids_recent_prompts_after_restarting_tutor(conn, graph, clock):
    skill_id = "sample.choice"
    first_tutor = Tutor(conn, graph, clock, seed=1)
    first_tutor.task = Task("lesson", [skill_id], "Lesson")
    first_item = first_tutor.next_item()
    first_tutor.submit(correct_response(first_item), seconds=20)

    next_tutor = Tutor(conn, graph, clock, seed=1)
    next_tutor.task = Task("lesson", [skill_id], "Lesson")
    next_item = next_tutor.next_item()

    assert next_item.prompt != first_item.prompt


def test_bank_lesson_rebuilds_prompt_history_from_older_attempts(conn, graph, clock):
    skill_id = "sample.choice"
    first_tutor = Tutor(conn, graph, clock, seed=1)
    first_tutor.task = Task("lesson", [skill_id], "Lesson")
    first_item = first_tutor.next_item()
    first_tutor.submit(correct_response(first_item), seconds=20)
    conn.execute("DELETE FROM meta WHERE key IN (?, ?)",
                  (f"practice_prompts.{skill_id}", f"practice_prompts_migrated.{skill_id}"))

    next_tutor = Tutor(conn, graph, clock, seed=1)
    next_tutor.task = Task("lesson", [skill_id], "Lesson")
    next_item = next_tutor.next_item()

    assert next_item.prompt != first_item.prompt


def test_lesson_hints_progress_and_adapt_to_difficulty_or_misses(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    skill_id = "sample.choice"
    tutor.task = Task("lesson", [skill_id], "Lesson")
    item = tutor.next_item()

    first = tutor.lesson_hint(skill_id, item.difficulty, 1)
    second = tutor.lesson_hint(skill_id, item.difficulty, 2)
    tutor.states[skill_id].lesson_errors = 1
    adapted = tutor.lesson_hint(skill_id, item.difficulty, 1)

    assert first["text"] != second["text"]
    assert adapted["level"] > first["level"]
    assert adapted["guide"] == graph.skills[skill_id].guide
    assert item.answer_text() not in adapted["text"]


def test_failed_lesson_ends_without_mastery(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    task = run_task(tutor, wrong_response)
    assert task.answered == LESSON_MAX_ERRORS
    assert not tutor.states[task.skill_ids[0]].mastered


def test_never_serves_locked_skills_and_eventually_masters_all(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=7)
    kinds = set()
    for _ in range(len(graph.skills) * 6):
        task = tutor.select_task()
        if task is None:
            break
        if task.kind == "lesson":
            assert tutor.is_available(task.skill_ids[0])
        kinds.add(task.kind)
        run_task_existing(tutor, correct_response)
        clock.advance(DAY / 4)
    assert len(tutor.mastered()) == len(graph.skills)
    assert {"lesson", "review", "quiz"} <= kinds


def run_task_existing(tutor, answer):
    while (item := tutor.next_item()) is not None:
        if tutor.submit(answer(item), seconds=20).task_done:
            break


def test_due_review_is_prioritised(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=3)
    first = run_task(tutor, correct_response).skill_ids[0]
    clock.advance(10 * DAY)
    task = tutor.select_task()
    assert task.kind == "review" and task.skill_ids == [first]


def test_correct_but_unsure_review_is_scheduled_again_soon(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=3)
    sid = next(iter(tutor.states))
    state = tutor.states[sid]
    state.status, state.reps, state.due = "mastered", 4.0, clock()
    tutor.task = Task("review", [sid], f"Review: {graph.skills[sid].title}")
    item = tutor.next_item()

    feedback = tutor.submit(correct_response(item), confidence="unsure")

    assert feedback.correct and feedback.task_done
    assert feedback.xp == 0
    assert "self-check was unsure" in feedback.summary
    assert state.reps == 2.0
    assert state.fail_streak == 1
    assert state.due == clock() + RETRY_DELAY


def test_completed_quiz_at_existing_mastery_threshold_counts_as_mastered(
    conn, graph, clock,
):
    tutor = Tutor(conn, graph, clock, seed=3)
    skill_ids = list(tutor.states)[:5]
    for skill_id in skill_ids:
        tutor.states[skill_id].status = "mastered"
    tutor.task = Task("quiz", skill_ids, "Mixed quiz")

    for index in range(len(skill_ids)):
        item = tutor.next_item()
        answer = correct_response(item) if index < 4 else wrong_response(item)
        tutor.submit(answer)

    dashboard = tutor.dashboard()
    assert dashboard["totalQuizzes"] == 1
    assert dashboard["masteredQuizzes"] == 1


def test_completed_reviews_are_tracked_separately_from_weekly_practice_quizzes(
    conn, graph, clock,
):
    tutor = Tutor(conn, graph, clock, seed=3)
    sid = next(iter(tutor.states))
    state = tutor.states[sid]
    state.status, state.reps, state.due = "mastered", 4.0, clock()
    tutor.task = Task("review", [sid], f"Review: {graph.skills[sid].title}")

    item = tutor.next_item()
    feedback = tutor.submit(correct_response(item))

    assert feedback.task_done
    assert tutor.dashboard()["practiceQuizzesThisWeek"] == 0
    assert tutor.dashboard()["reviewsThisWeek"] == 1


def test_dashboard_includes_locked_lessons_and_upcoming_reviews(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=3)

    dashboard = tutor.dashboard()
    assert dashboard["recommendedAction"] == "lesson"
    assert dashboard["learningPlan"][0]["available"]
    assert any(not lesson["available"] for lesson in dashboard["learningPlan"])
    plan_indexes = {
        lesson["id"]: index for index, lesson in enumerate(dashboard["learningPlan"])
    }
    for lesson_id, index in plan_indexes.items():
        assert all(
            prerequisite not in plan_indexes or plan_indexes[prerequisite] < index
            for prerequisite in graph.skills[lesson_id].prereqs
        )

    sid = next(iter(tutor.states))
    state = tutor.states[sid]
    state.status, state.reps, state.due = "mastered", 4.0, clock() + DAY
    dashboard = tutor.dashboard()
    assert dashboard["dueCount"] == 0
    assert any(
        review["id"] == sid and review["daysUntilDue"] == 1 and not review["dueNow"]
        for review in dashboard["criticalReviews"]
    )

    state.due = clock() + 3600
    dashboard = tutor.dashboard()
    assert dashboard["dueCount"] == 0
    assert any(
        review["id"] == sid and review["daysUntilDue"] == 0 and not review["dueNow"]
        for review in dashboard["criticalReviews"]
    )

    state.due = clock()
    dashboard = tutor.dashboard()
    assert dashboard["recommendedAction"] == "review"
    assert any(review["id"] == sid and review["dueNow"]
               for review in dashboard["criticalReviews"])


def test_dashboard_learning_plan_respects_pack_goals_at_seven_lessons(conn, clock):
    goals = {
        "computer-science": 2,
        "finance": 2,
        "humanities": 1,
        "product": 1,
        "software": 1,
    }
    tutor = _tutor_with_pack_goals(conn, clock, goals, total_goal=7)

    plan = tutor.dashboard()["learningPlan"]
    counts = Counter(tutor.graph.skill_pack_ids[lesson["id"]] for lesson in plan)

    assert len(plan) == 7
    assert counts == goals


def test_dashboard_learning_plan_fills_to_seven_in_pack_goal_proportions(conn, clock):
    goals = {"computer-science": 2, "finance": 1, "humanities": 1}
    tutor = _tutor_with_pack_goals(conn, clock, goals, total_goal=4)

    plan = tutor.dashboard()["learningPlan"]
    counts = Counter(tutor.graph.skill_pack_ids[lesson["id"]] for lesson in plan)

    assert len(plan) == 7
    assert counts["computer-science"] >= goals["computer-science"]
    assert counts["finance"] >= goals["finance"]
    assert counts["humanities"] >= goals["humanities"]
    assert counts == {"computer-science": 3, "finance": 2, "humanities": 2}


def test_dashboard_learning_plan_covers_every_pack_when_goal_exceeds_seven(
    conn, clock,
):
    goals = {
        "computer-science": 8,
        "finance": 1,
        "humanities": 1,
        "product": 0,
        "software": 0,
    }
    tutor = _tutor_with_pack_goals(conn, clock, goals, total_goal=10)

    plan = tutor.dashboard()["learningPlan"]
    shown_packs = {tutor.graph.skill_pack_ids[lesson["id"]] for lesson in plan}

    assert len(plan) == 7
    assert shown_packs == set(goals)


def test_correct_but_guessed_quiz_answer_schedules_review(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=3)
    sid = next(iter(tutor.states))
    state = tutor.states[sid]
    state.status, state.reps, state.due = "mastered", 4.0, clock() + DAY
    tutor.task = Task("quiz", [sid], "Mixed quiz")
    item = tutor.next_item()

    feedback = tutor.submit(correct_response(item), confidence="guessed")

    assert feedback.correct and feedback.task_done
    assert state.reps == 2.0
    assert state.fail_streak == 1
    assert state.due == clock() + RETRY_DELAY
    assert tutor.dashboard()["totalQuizzes"] == 1
    assert tutor.dashboard()["masteredQuizzes"] == 1


def test_diagnostic_perfect_learner_places_everything(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()
    while (item := tutor.next_item()) is not None:
        tutor.submit(correct_response(item), seconds=20)
    assert tutor.task.done
    assert len(tutor.mastered()) >= len(graph.skills) * 0.5
    assert tutor.store.get("diagnostic_done")


def test_diagnostic_novice_places_nothing(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()
    while (item := tutor.next_item()) is not None:
        tutor.submit(wrong_response(item), seconds=20)
    assert tutor.mastered() == []


def test_diagnostic_confirms_a_skill_and_only_credits_its_prerequisites(conn, clock):
    graph = KnowledgeGraph([
        Skill("base", "Base", "sample", "pct_of"),
        Skill("middle", "Middle", "sample", "pct_of", prereqs=["base"]),
        Skill("advanced", "Advanced", "sample", "pct_of", prereqs=["middle"]),
    ])
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()

    first = tutor.next_item()
    assert first.skill_id == "middle"
    assert first.difficulty == 2
    tutor.submit(correct_response(first), seconds=20)

    confirmation = tutor.next_item()
    assert confirmation.skill_id == first.skill_id
    assert confirmation.difficulty == 3
    assert confirmation.prompt != first.prompt
    tutor.submit(correct_response(confirmation), seconds=20)

    assert tutor.task.known == {"base", "middle"}
    assert tutor.task.unknown == set()
    assert tutor.task.uncertain == set()


@pytest.mark.parametrize("confidence", ["unsure", "guessed"])
def test_diagnostic_low_confidence_correct_answer_is_inconclusive(
    conn, clock, confidence,
):
    graph = KnowledgeGraph([
        Skill("base", "Base", "sample", "pct_of"),
        Skill("middle", "Middle", "sample", "pct_of", prereqs=["base"]),
        Skill("advanced", "Advanced", "sample", "pct_of", prereqs=["middle"]),
    ])
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()

    first = tutor.next_item()
    feedback = tutor.submit(
        correct_response(first), seconds=20, confidence=confidence,
    )
    assert feedback.correct
    confirmation = tutor.next_item()
    assert confirmation.skill_id == first.skill_id
    assert confirmation.difficulty == 2
    tutor.submit(correct_response(confirmation), seconds=20, confidence="explained")

    assert tutor.task.known == set()
    assert tutor.task.unknown == set()
    assert tutor.task.uncertain == {first.skill_id}
    assert tutor.mastered() == []


def test_diagnostic_mixed_evidence_is_inconclusive_and_does_not_skip_descendants(
    conn, clock,
):
    graph = KnowledgeGraph([
        Skill("base", "Base", "sample", "pct_of"),
        Skill("middle", "Middle", "sample", "pct_of", prereqs=["base"]),
        Skill("advanced", "Advanced", "sample", "pct_of", prereqs=["middle"]),
    ])
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()

    first = tutor.next_item()
    assert first.skill_id == "middle"
    tutor.submit(wrong_response(first), seconds=20)
    easier = tutor.next_item()
    assert easier.skill_id == first.skill_id
    assert easier.difficulty == 1
    tutor.submit(correct_response(easier), seconds=20)

    assert tutor.task.uncertain == {"middle"}
    assert tutor.task.unknown == set()
    assert tutor.task.known == set()
    assert tutor.next_item().skill_id == "base"


def test_diagnostic_failure_does_not_classify_descendants_as_unknown(conn, clock):
    graph = KnowledgeGraph([
        Skill("base", "Base", "sample", "pct_of"),
        Skill("middle", "Middle", "sample", "pct_of", prereqs=["base"]),
        Skill("advanced", "Advanced", "sample", "pct_of", prereqs=["middle"]),
    ])
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()

    first = tutor.next_item()
    tutor.submit(wrong_response(first), seconds=20)
    easier = tutor.next_item()
    tutor.submit(wrong_response(easier), seconds=20)

    assert tutor.task.unknown == {"middle"}
    assert "advanced" not in tutor.task.unknown
    assert tutor.next_item().skill_id == "base"


def test_diagnostic_never_exceeds_fifteen_and_reports_unassessed_skills(conn, clock):
    graph = KnowledgeGraph([
        Skill(f"skill-{index}", f"Skill {index}", "sample", "pct_of")
        for index in range(20)
    ])
    tutor = Tutor(conn, graph, clock, seed=5)
    tutor.start_diagnostic()

    while (item := tutor.next_item()) is not None:
        tutor.submit(correct_response(item), seconds=20)

    assert tutor.task.answered == DIAGNOSTIC_MAX == 15
    assert tutor.task.done
    assert "were not assessed" in tutor.task.summary
    assert "not proof of mastery" in tutor.task.summary


def test_rushed_wrong_answer_costs_xp(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.select_task()
    item = tutor.next_item()
    fb = tutor.submit(wrong_response(item), seconds=1)
    assert fb.xp == -1


def test_progress_persists(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    sid = run_task(tutor, correct_response).skill_ids[0]
    again = Tutor(conn, graph, clock, seed=1)
    assert again.states[sid].mastered
