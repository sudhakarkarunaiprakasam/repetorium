import sqlite3
from dataclasses import asdict
from datetime import datetime

import pytest

from repetorium.assessments import SkillExamCoach
from repetorium.cases.coach import CaseCoach
from repetorium.content import ContentError
from repetorium.core import db
from repetorium.engine.graph import Connection, GraphError, KnowledgeGraph, Skill
from repetorium.engine.scheduler import DAY, MAX_INTERVAL_DAYS, interval_days
from repetorium.engine.store import SkillState, Store
from repetorium.engine.tutor import Tutor
from repetorium.library import load_library
from repetorium.question_levels import question_level
from repetorium.ui.backend import Backend


def table_count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_failed_migration_rolls_back_schema_and_version(monkeypatch, tmp_path):
    path = tmp_path / "progress.sqlite3"
    monkeypatch.setattr(db, "MIGRATIONS", [
        "CREATE TABLE first (id INTEGER);",
        "CREATE TABLE partial (id INTEGER); INSERT INTO missing VALUES (1);",
    ])
    with pytest.raises(sqlite3.OperationalError, match="missing"):
        db.connect(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchone() is None
    monkeypatch.setattr(db, "MIGRATIONS", [
        "CREATE TABLE first (id INTEGER);",
        "CREATE TABLE partial (id INTEGER);",
    ])
    conn = db.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    conn.close()


def test_newer_database_is_not_opened_as_compatible(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute(f"PRAGMA user_version = {len(db.MIGRATIONS) + 1}")
    with pytest.raises(sqlite3.DatabaseError, match="newer"):
        db.connect(path)


def test_latest_migration_preserves_existing_attempts_and_quiz_completions():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for version, migration in enumerate(db.MIGRATIONS[:-1], start=1):
        conn.executescript(
            f"BEGIN IMMEDIATE;\n{migration}\nPRAGMA user_version = {version};\nCOMMIT;"
        )
    conn.execute(
        "INSERT INTO attempts (ts, skill_id, task_kind, seed, difficulty, response, correct, seconds) "
        "VALUES (1, 'old.skill', 'review', 1, 1, 'answer', 1, 5)"
    )
    conn.execute("INSERT INTO quiz_completions (completed_at) VALUES (1)")
    conn.commit()

    db.migrate(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    attempt = conn.execute("SELECT correct, confidence FROM attempts").fetchone()
    assert tuple(attempt) == (1, "")
    quiz = conn.execute("SELECT correct, total FROM quiz_completions").fetchone()
    assert tuple(quiz) == (0, 0)
    conn.close()


def test_store_savepoints_do_not_commit_callers_transaction(conn):
    conn.execute("INSERT INTO meta VALUES ('outer', '1')")
    Store(conn).add_xp(1, 20, "test")
    Store(conn).set("inner", True)
    assert conn.in_transaction
    conn.rollback()
    assert table_count(conn, "xp_ledger") == 0
    assert table_count(conn, "meta") == 0


def test_study_time_excludes_mock_test_time(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    store = tutor.store
    today = clock()
    store.log_attempt(today, "sample.root", "lesson", 1, 1, "1", True, 90)
    store.log_attempt(today, "sample.root", "quiz", 4, 1, "1", True, 40)
    store.log_quiz_completion(today, 4, 5)
    store.log_attempt(today, "sample.root", "mock_test", 2, 1, "1", True, 50)
    store.log_attempt(today - 86400, "sample.root", "review", 3, 1, "1", True, 30)
    conn.execute(
        "INSERT INTO mock_test_runs (title, started, finished, total, elapsed_seconds) "
        "VALUES (?, ?, ?, ?, ?)", ("Exam", today - 120, today, 1, 120)
    )
    conn.execute(
        "INSERT INTO case_runs (template_id, seed, started, finished) VALUES (?, ?, ?, ?)",
        ("case", 1, today - 300, today)
    )
    store.add_xp(today, 15, "practice")

    dashboard = tutor.dashboard()
    stats = tutor.stats()
    times = {entry["day"]: entry["seconds"] for entry in stats["studyTimeByDay"]}
    today_day = datetime.fromtimestamp(today).date().isoformat()
    yesterday_day = datetime.fromtimestamp(today - 86400).date().isoformat()

    assert dashboard["lessonsThisWeek"] == 1
    assert dashboard["practiceQuizzesThisWeek"] == 1
    assert dashboard["reviewsThisWeek"] == 1
    assert dashboard["totalQuizzes"] == 1
    assert dashboard["masteredQuizzes"] == 1
    assert dashboard["mockTestsThisWeek"] == 1
    assert dashboard["activeDaysLastSeven"] == 2
    assert times[today_day[5:]] == 430
    assert times[yesterday_day[5:]] == 30
    assert tutor.store.xp_total() == 15


def test_imported_lifetime_study_time_merges_without_reducing_and_resets(conn):
    store = Store(conn)
    store.log_attempt(100, "sample.root", "lesson", 1, 1, "answer", True, 30)

    assert store.merge_imported_study_seconds(100) == 70
    assert store.study_seconds_total() == 100
    store.log_attempt(101, "sample.root", "review", 2, 1, "answer", True, 20)
    assert store.study_seconds_total() == 120
    assert store.merge_imported_study_seconds(90) == 0
    assert store.study_seconds_total() == 120

    store.reset_progress()
    assert store.study_seconds_total() == 0


def test_load_states_filters_and_chunks_requested_skills(conn):
    store = Store(conn)
    store.save_states([
        SkillState(f"skill.{index}", status="learning")
        for index in range(1_100)
    ])

    states = store.load_states(["skill.0", "skill.599", "skill.1099", "missing"])

    assert states["skill.0"].status == "learning"
    assert states["skill.599"].status == "learning"
    assert states["skill.1099"].status == "learning"
    assert states["missing"].status == "new"


def test_recent_skills_returns_newest_distinct_skills(conn, clock):
    store = Store(conn)
    for index, skill_id in enumerate(("a", "b", "a", "c", "b")):
        store.log_attempt(clock() + index, skill_id, "lesson", index, 1, "", True, 1)

    assert store.recent_skills("lesson", 2) == ["b", "c"]
    assert store.recent_skills("lesson", 0) == []


@pytest.mark.parametrize("confidence", ["unsure", "guessed"])
def test_low_confidence_correct_answer_does_not_advance_mastery(
    conn, graph, clock, confidence,
):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.select_task()
    item = tutor.next_item()

    response = (",".join(map(str, item.answer)) if item.kind == "order"
                else str(item.answer))
    feedback = tutor.submit(response, confidence=confidence)

    assert feedback.correct
    attempt = conn.execute("SELECT correct, confidence FROM attempts").fetchone()
    assert tuple(attempt) == (1, confidence)
    category = next(
        entry for entry in tutor.stats()["confidenceByCategory"]
        if entry["title"] == tutor.graph.category_title(tutor.graph.skills[item.skill_id].category)
    )
    assert category["confidenceLow"] == 1
    assert category["confidenceRated"] == 1
    assert tutor.states[item.skill_id].lesson_streak == 0
    assert tutor.states[item.skill_id].lesson_errors == 0


def test_explained_correct_answer_advances_mastery(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.select_task()
    item = tutor.next_item()
    response = (",".join(map(str, item.answer)) if item.kind == "order"
                else str(item.answer))

    feedback = tutor.submit(response, confidence="explained")

    assert feedback.correct
    assert tutor.states[item.skill_id].lesson_streak == 1


def test_unrated_attempts_are_not_counted_as_confidence(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.select_task()
    item = tutor.next_item()
    response = (",".join(map(str, item.answer)) if item.kind == "order"
                else str(item.answer))
    tutor.submit(response)

    category = next(
        entry for entry in tutor.stats()["confidenceByCategory"]
        if entry["title"] == tutor.graph.category_title(tutor.graph.skills[item.skill_id].category)
    )
    assert category["confidenceLow"] == 0
    assert category["confidenceRated"] == 0
    assert tutor.states[item.skill_id].lesson_streak == 1


def test_invalid_confidence_does_not_record_or_consume_attempt(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.select_task()
    item = tutor.next_item()

    with pytest.raises(ValueError, match="Confidence must be"):
        response = (",".join(map(str, item.answer)) if item.kind == "order"
                    else str(item.answer))
        tutor.submit(response, confidence="certain")

    assert table_count(conn, "attempts") == 0
    assert tutor.item is item


def test_practice_failure_rolls_back_attempt_state_and_session(conn, clock):
    graph = KnowledgeGraph([Skill("sample.test", "Test", "sample", "pct_of")])
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.select_task()
    for _ in range(2):
        item = tutor.next_item()
        tutor.submit(str(item.answer), seconds=20)
    item = tutor.next_item()
    state = asdict(tutor.states[item.skill_id])
    answered = tutor.task.answered
    conn.execute(
        "CREATE TRIGGER fail_xp BEFORE INSERT ON xp_ledger "
        "BEGIN SELECT RAISE(ABORT, 'cannot save xp'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="cannot save xp"):
        tutor.submit(str(item.answer), seconds=20)
    assert table_count(conn, "attempts") == 2
    assert asdict(tutor.states[item.skill_id]) == state
    assert tutor.task.answered == answered
    assert tutor.item is item
    assert not tutor.task.done
    assert Store(conn).load_states([item.skill_id])[item.skill_id].lesson_streak == 2
    conn.execute("DROP TRIGGER fail_xp")
    assert tutor.submit(str(item.answer), seconds=20).task_done
    assert table_count(conn, "attempts") == 3


def test_repeated_next_item_does_not_replace_question(conn, clock):
    tutor = Tutor(conn, KnowledgeGraph([Skill("test", "Test", "sample", "pct_of")]), clock, seed=1)
    tutor.start_diagnostic()
    item = tutor.next_item()
    clock.advance(20)
    assert tutor.next_item() is item
    assert tutor.task.skill_ids == ["test"]
    assert tutor.item_started == clock() - 20


def test_exam_finish_is_atomic_and_retryable(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.states["sample.root"].status = "mastered"
    tutor.store.save_states([tutor.states["sample.root"]])
    exam = SkillExamCoach(tutor)
    exam.start(["sample.root"], 1, 2)
    exam.answer(str(exam.items[0].answer))
    before = asdict(tutor.states["sample.root"])
    conn.execute(
        "CREATE TRIGGER fail_exam BEFORE UPDATE ON mock_test_runs "
        "BEGIN SELECT RAISE(ABORT, 'cannot finish exam'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="cannot finish exam"):
        exam.finish()
    assert table_count(conn, "attempts") == table_count(conn, "xp_ledger") == 0
    assert asdict(tutor.states["sample.root"]) == before
    assert exam.run_id is not None
    assert exam.responses[0] is not None
    conn.execute("DROP TRIGGER fail_exam")
    assert exam.finish()["correct"] == 1
    assert table_count(conn, "attempts") == 1
    assert len(exam.history()) == 1
    with pytest.raises(RuntimeError):
        exam.finish()


def test_mock_test_uses_selected_skills_and_difficulty_without_timing(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    skill_ids = ["sample.root", "sample.followup"]
    for skill_id in skill_ids:
        tutor.states[skill_id].status = "mastered"
    exam = SkillExamCoach(tutor)
    question_count = 5
    started = exam.start(skill_ids, question_count, 3)

    assert started["total"] == question_count
    assert started["skillCount"] == len(skill_ids)
    assert "minutes" not in started
    assert started["difficultyLabel"] == "Hard"
    skill_counts = {
        skill_id: sum(item.skill_id == skill_id for item in exam.items)
        for skill_id in skill_ids
    }
    assert set(skill_counts) == set(skill_ids)
    assert min(skill_counts.values()) >= 1
    assert max(skill_counts.values()) - min(skill_counts.values()) <= 1
    assert len(exam.items) == question_count
    assert {item.difficulty for item in exam.items} == {3}
    assert exam.next_item()["questionXp"] == 3
    for item in exam.items:
        exam.answer(str(item.answer))
    result = exam.finish()

    assert result["total"] == question_count
    assert result["xp"] == 10 + question_count * 3
    assert "minutes" not in result
    assert conn.execute(
        "SELECT elapsed_seconds FROM mock_test_runs WHERE id = ?", (exam.history()[0]["id"],)
    ).fetchone()[0] == 0
    assert question_level(1) == {"label": "Easy", "minutes": 2, "xp": 1}
    assert question_level(2) == {"label": "Medium", "minutes": 3, "xp": 2}
    assert question_level(3) == {"label": "Hard", "minutes": 5, "xp": 3}

    with pytest.raises(ContentError, match="at least one question per selected skill"):
        exam.start(skill_ids, 1, 2)
    with pytest.raises(ValueError, match="Question difficulty"):
        exam.start(skill_ids, 2, 4)


def test_mock_tests_work_without_pack_exam_configuration(conn, tmp_path, clock):
    graph = KnowledgeGraph(
        [Skill("custom.skill", "Custom skill", "custom", "pct_of")],
        content_dir=tmp_path,
    )
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.states["custom.skill"].status = "mastered"
    backend = Backend(tutor, CaseCoach(tutor))

    assert backend.mockTestMethods() == [{"id": "skill_exam", "title": "Mock Tests"}]
    started = backend.startSkillExam(["custom.skill"], 1, 2)
    assert started["total"] == 1
    assert backend.nextSkillExamItem()["skillTitle"] == "Custom skill"


def test_mock_test_picker_and_start_only_allow_mastered_skills(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.states["sample.choice"].status = "mastered"
    tutor.states["sample.choice"].due = clock() - 1
    tutor.states["sample.related"].status = "mastered"
    tutor.states["sample.related"].due = clock() + DAY
    tutor.states["sample.root"].status = "learning"
    backend = Backend(tutor, CaseCoach(tutor))

    assert {skill["id"] for skill in backend.skillExamSkills()} == {
        "sample.choice", "sample.related",
    }
    assert "error" in backend.startSkillExam(["sample.root"], 1, 2)
    assert backend.skill_exam.run_id is None
    assert backend.startSkillExam(["sample.choice"], 1, 2)["total"] == 1


def test_reset_cancels_every_backend_session(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.states["sample.root"].status = "mastered"
    backend = Backend(tutor, CaseCoach(tutor))
    backend.startCase("sample-application")
    backend.startSkillExam(["sample.root"], 1, 2)
    backend.nextTask()
    backend.nextItem()
    resets = []
    backend.sessionsReset.connect(lambda: resets.append(True))
    assert backend.resetProgress() == {"ok": True}
    assert resets == [True]
    assert backend.coach.case is None
    assert backend.coach.results == {}
    assert backend.skill_exam.items == []
    assert backend.skill_exam.run_id is None
    assert tutor.task is tutor.item is None
    assert "error" in backend.finishSkillExam()
    assert "error" in backend.submitCaseScores({})
    for table in ("attempts", "xp_ledger", "case_runs", "mock_test_runs", "skill_state"):
        assert table_count(conn, table) == 0


def test_failed_reset_preserves_sessions_and_reports_error(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    tutor.states["sample.root"].status = "mastered"
    backend = Backend(tutor, CaseCoach(tutor))
    backend.startCase("sample-application")
    backend.startSkillExam(["sample.root"], 1, 2)
    tutor.select_task()
    task, case = tutor.task, backend.coach.case
    errors, resets = [], []
    backend.errorOccurred.connect(errors.append)
    backend.sessionsReset.connect(lambda: resets.append(True))
    conn.execute(
        "CREATE TRIGGER fail_reset BEFORE DELETE ON case_runs "
        "BEGIN SELECT RAISE(ABORT, 'cannot reset'); END"
    )
    assert backend.resetProgress() == {"error": "cannot reset"}
    assert errors == ["cannot reset"]
    assert resets == []
    assert tutor.task is task
    assert backend.coach.case is case
    assert backend.skill_exam.run_id is not None
    assert table_count(conn, "case_runs") == table_count(conn, "mock_test_runs") == 1
    assert table_count(conn, "skill_state") == 1


def test_backend_action_errors_are_explicit_and_do_not_mutate_session(conn, graph, clock):
    tutor = Tutor(conn, graph, clock)
    backend = Backend(tutor, CaseCoach(tutor))
    errors = []
    backend.errorOccurred.connect(errors.append)
    assert "error" in backend.startSkillExam(["missing"], 1, 2)
    assert "error" in backend.startCase("missing")
    assert "error" in backend.submit("1")
    assert len(errors) == 3
    assert backend.tutor.item is None
    assert backend.skill_exam.run_id is None
    assert backend.coach.run_id is None
    assert table_count(conn, "attempts") == table_count(conn, "xp_ledger") == 0


def test_case_scores_and_undo_restore_full_state_atomically(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    coach = CaseCoach(tutor)
    coach.start("sample-application")
    question = coach.case["questions"][0]
    sid = question["skill"]
    before = asdict(tutor.states[sid])
    coach.answer(0, str(question["answer"]))
    coach.finish("", "", "")
    conn.execute(
        "CREATE TRIGGER fail_case BEFORE UPDATE ON case_runs "
        "BEGIN SELECT RAISE(ABORT, 'cannot save case'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="cannot save case"):
        coach.submit_scores({})
    assert asdict(tutor.states[sid]) == before
    assert table_count(conn, "xp_ledger") == 0
    assert coach.run_id is not None
    conn.execute("DROP TRIGGER fail_case")
    coach.submit_scores({})
    assert tutor.states[sid].status == "learning"
    run_id = coach.history()[0]["id"]
    conn.execute(
        "CREATE TRIGGER fail_delete BEFORE DELETE ON case_runs "
        "BEGIN SELECT RAISE(ABORT, 'cannot delete case'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="cannot delete case"):
        coach.delete_history(run_id)
    assert tutor.states[sid].status == "learning"
    assert table_count(conn, "xp_ledger") == 1
    conn.execute("DROP TRIGGER fail_delete")
    assert coach.delete_history(run_id)
    assert asdict(tutor.states[sid]) == before
    assert Store(conn).load_states([sid])[sid].status == "new"
    assert table_count(conn, "xp_ledger") == 0


def test_case_undo_rejects_nonlinear_later_learning(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    coach = CaseCoach(tutor)
    coach.start("sample-application")
    question = coach.case["questions"][0]
    sid = question["skill"]
    tutor.states[sid].status, tutor.states[sid].reps = "mastered", 4.0
    tutor.store.save_states([tutor.states[sid]])
    coach.answer(0, str(question["answer"]))
    coach.finish("", "", "")
    coach.submit_scores({})
    run_id = coach.history()[0]["id"]
    tutor.store.save_states(tutor.scheduler.review(sid, False, clock()))
    before = asdict(tutor.states[sid])
    xp = tutor.store.xp_total()
    with pytest.raises(ValueError, match="later learning"):
        coach.delete_history(run_id)
    assert asdict(tutor.states[sid]) == before
    assert tutor.store.xp_total() == xp
    assert coach.history()[0]["id"] == run_id


def test_case_undo_rejects_later_evidence_with_identical_state(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    coach = CaseCoach(tutor)
    ids = []
    snapshots = []
    for _ in range(2):
        coach.start("sample-application")
        question = coach.case["questions"][0]
        coach.answer(0, str(question["answer"]))
        coach.finish("", "", "")
        coach.submit_scores({})
        ids.append(coach.history()[0]["id"])
        snapshots.append(asdict(tutor.states[question["skill"]]))
    assert snapshots[0] == snapshots[1]
    with pytest.raises(ValueError, match="later learning"):
        coach.delete_history(ids[0])
    assert len(coach.history()) == 2
    assert tutor.states[question["skill"]].status == "learning"


def test_case_undo_rejects_later_practice_without_state_change(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    coach = CaseCoach(tutor)
    coach.start("sample-application")
    question = coach.case["questions"][0]
    coach.answer(0, str(question["answer"]))
    coach.finish("", "", "")
    coach.submit_scores({})
    run_id = coach.history()[0]["id"]
    tutor.store.log_attempt(clock(), question["skill"], "lesson", 1, 1, "1", True, 10)
    with pytest.raises(ValueError, match="later learning"):
        coach.delete_history(run_id)


def test_case_undo_keeps_remediation_supported_by_identical_later_evidence(conn, graph, clock):
    tutor = Tutor(conn, graph, clock, seed=1)
    coach = CaseCoach(tutor)
    run_ids = []
    for _ in range(2):
        coach.start("sample-application")
        coach.answer(0, "not a number")
        coach.finish("", "", "")
        coach.submit_scores({})
        run_ids.append(coach.history()[0]["id"])
    queue = tutor.store.get("remediation")
    assert queue
    with pytest.raises(ValueError, match="later learning"):
        coach.delete_history(run_ids[0])
    assert tutor.store.get("remediation") == queue
    assert len(coach.history()) == 2


def test_failed_reload_preserves_bank_and_case_snapshots(conn, tmp_path, clock):
    import yaml

    directory = tmp_path / "library"
    for name in ("graph", "banks", "cases"):
        (directory / name).mkdir(parents=True)
    (directory / "library.yaml").write_text(yaml.safe_dump({
        "format": 1, "id": "test", "name": "Test", "version": "1",
    }), encoding="utf-8")
    (directory / "graph" / "sample.yaml").write_text(yaml.safe_dump([
        {"id": "test.bank", "title": "Test", "generator": "bank_choice", "params": {"bank": "test"}},
    ]), encoding="utf-8")
    bank_path = directory / "banks" / "test.yaml"
    valid_bank = {"entries": [{
        "prompt": "Old question", "correct": "Yes", "distractors": ["No"],
        "explain": "The evidence supports Yes.",
    }]}
    bank_path.write_text(yaml.safe_dump(valid_bank), encoding="utf-8")
    from repetorium.cases.templates import load_templates
    from repetorium.paths import CONTENT_DIR

    template = next(iter(load_templates(CONTENT_DIR / "cases").values()))
    case = dict(template.raw)
    case["questions"] = [{**question, "skill": "test.bank"} for question in case["questions"]]
    case["rubric_skills"] = {}
    case["case_skills"] = ["test.bank"]
    case_path = directory / "cases" / "test.yaml"
    case_path.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")
    tutor = Tutor(conn, load_library(directory), clock, seed=1)
    backend = Backend(tutor, CaseCoach(tutor))
    backend.nextTask()
    assert backend.nextItem()["prompt"] == "Old question"
    current_item = tutor.item
    bank_path.write_text("entries: []", encoding="utf-8")
    case_path.write_text("invalid", encoding="utf-8")
    assert "error" in backend.reloadContent()
    assert backend.tutor is tutor
    assert "error" not in backend.submit(str(current_item.answer))
    assert backend.nextItem()["prompt"] == "Old question"
    assert backend.startCase(template.id)["title"] == template.title
    bank_path.write_text(yaml.safe_dump({
        "entries": [{
            "prompt": "New question", "correct": "Yes", "distractors": ["No"],
            "explain": "The evidence supports Yes.",
        }],
    }), encoding="utf-8")
    case_path.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")
    assert backend.reloadContent()["ok"]
    backend.nextTask()
    assert backend.nextItem()["prompt"] == "New question"


def test_case_inputs_are_validated_before_updates(conn, graph, clock):
    coach = CaseCoach(Tutor(conn, graph, clock))
    with pytest.raises(ValueError, match="Unknown case"):
        coach.start("missing")
    coach.start("sample-application")
    with pytest.raises(ValueError, match="valid case question"):
        coach.answer(-1, "1")
    with pytest.raises(RuntimeError, match="Finish"):
        coach.submit_scores({})
    coach.finish("", "", "")
    for scores in ({"structure": 0}, {"structure": True}, {"structure": 1.5}, {"unknown": 5}):
        with pytest.raises(ValueError, match="scores"):
            coach.submit_scores(scores)
    assert table_count(conn, "xp_ledger") == 0


def test_case_debrief_answers_cannot_change_scored_evidence(conn, graph, clock):
    coach = CaseCoach(Tutor(conn, graph, clock, seed=1))
    coach.start("sample-application")
    question = coach.case["questions"][0]
    result = coach.finish("", "", "")
    assert result["mathCorrect"] == 0
    assert coach.answer(0, str(question["answer"]))["correct"]
    assert coach.results == {}
    assert coach.submit_scores({})["xp"] == 20
    assert coach.history()[0]["math"].startswith("0/")


def test_archived_skill_statistics_preserve_attempt_totals(conn, clock):
    graph = KnowledgeGraph([Skill("current", "Current", "sample", "pct_of")])
    tutor = Tutor(conn, graph, clock)
    tutor.store.log_attempt(clock(), "removed", "lesson", 1, 1, "1", True, 10)
    tutor.store.log_attempt(clock(), "current", "lesson", 1, 1, "1", False, 10)
    assert tutor.stats()["categories"] == [
        {"title": "Sample", "correct": 0, "total": 1},
        {"title": "Archived skills", "correct": 1, "total": 1},
    ]
    assert tutor.stats()["attempts"] == 2


def test_daily_xp_ignores_future_days_and_streak_aggregates_days(conn, clock):
    store = Store(conn)
    store.add_xp(clock(), 2, "today")
    store.add_xp(clock(), 3, "today again")
    store.add_xp(clock() - DAY, 1, "yesterday")
    store.add_xp(clock() + 2 * DAY, 50, "future")
    assert store.xp_by_day(clock(), 1)[0][1] == 5
    assert store.streak_days(clock()) == 2


def test_streak_days_starts_yesterday_and_stops_at_a_gap(conn, clock):
    store = Store(conn)
    store.add_xp(clock() - DAY, 2, "yesterday")
    store.add_xp(clock() - 2 * DAY, 1, "two days ago")
    store.add_xp(clock() + 1_000, 1, "future today")
    assert store.streak_days(clock()) == 2

    conn.execute("DELETE FROM xp_ledger")
    store.add_xp(clock(), 1, "today")
    store.add_xp(clock() - 2 * DAY, 1, "after a gap")
    assert store.streak_days(clock()) == 1


def test_connection_index_is_bidirectional_and_preserves_order(conn, tmp_path):
    skills = [Skill(str(i), str(i), "sample", "pct_of") for i in range(20)]
    links = [Connection(str(i), str(i + 1), "related", 1.0, "Note") for i in range(19)]
    graph = KnowledgeGraph(skills, tmp_path, connections=links)
    assert graph.connections_by_skill["1"] == links[:2]
    tutor = Tutor(conn, graph)
    node = tutor.knowledge_map()["nodes"][1]
    assert [link["id"] for link in node["connections"]] == ["0", "2"]


def test_scheduler_caps_before_exponentiation():
    assert interval_days(1_000_000) == MAX_INTERVAL_DAYS
    for bad in (float("inf"), float("nan"), -1):
        with pytest.raises(ValueError, match="finite"):
            interval_days(bad)


@pytest.mark.parametrize("weight", [True, "strong", float("inf"), float("nan"), 0, -1, 2])
def test_encompassing_weights_fail_with_explicit_graph_errors(weight):
    with pytest.raises(GraphError, match="weight"):
        KnowledgeGraph([
            Skill("parent", "Parent", "sample", "pct_of"),
            Skill("child", "Child", "sample", "pct_of",
                  prereqs=["parent"], encompasses={"parent": weight}),
        ])
