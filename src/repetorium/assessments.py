"""Library configuration and coaching for skill-aligned mock exams."""

import json
from pathlib import Path

import yaml

from repetorium.content import ContentError
from repetorium.core.db import transaction
from repetorium.generators import check
from repetorium.question_levels import question_level
from repetorium.yaml_io import safe_load

DEFAULT_QUESTION_COUNT = 10
DEFAULT_MINUTES = 20


def load_mock_tests(directory: Path, skill_ids: set[str]) -> dict:
    path = directory / "assessments" / "mock_tests.yaml"
    if not path.exists():
        return {}
    try:
        config = safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ContentError(f"Cannot read mock-test configuration: {error}") from error
    if not isinstance(config, dict) or config.get("method") != "skill_exam":
        raise ContentError("Mock-test configuration must select the skill_exam method.")
    raw_exams = config.get("exams")
    if raw_exams is None:
        selected = config.get("skills", sorted(skill_ids))
        if not isinstance(selected, list):
            raise ContentError("Skill exam skills must be a list of known skill IDs.")
        raw_exams = [{
            "id": "comprehensive",
            "title": "Skill-aligned mock exam",
            "skills": selected,
            "question_count": config.get(
                "question_count", min(DEFAULT_QUESTION_COUNT, len(selected))
            ),
            "minutes": config.get("minutes", DEFAULT_MINUTES),
        }]
    if not isinstance(raw_exams, list) or not raw_exams:
        raise ContentError("Skill exam configuration needs a nonempty exams list.")
    exams = {}
    for exam in raw_exams:
        if not isinstance(exam, dict):
            raise ContentError("Each skill exam must be a mapping.")
        exam_id, title = exam.get("id"), exam.get("title")
        if (not isinstance(exam_id, str) or not exam_id.strip()
                or not isinstance(title, str) or not title.strip() or exam_id in exams):
            raise ContentError("Every skill exam needs a distinct ID and nonempty title.")
        all_skills = exam.get("all_skills", False)
        if not isinstance(all_skills, bool):
            raise ContentError(f"{exam_id}: all_skills must be a boolean.")
        if all_skills and "skills" in exam:
            raise ContentError(f"{exam_id}: all_skills cannot be combined with an explicit skills list.")
        selected = sorted(skill_ids) if all_skills else exam.get("skills", sorted(skill_ids))
        if (not isinstance(selected, list) or not selected
                or any(not isinstance(skill_id, str) or skill_id not in skill_ids
                       for skill_id in selected)
                or len(selected) != len(set(selected))):
            raise ContentError(f"{exam_id}: skills must be distinct known skill IDs.")
        question_count = exam.get(
            "question_count",
            len(selected) if all_skills else min(DEFAULT_QUESTION_COUNT, len(selected)),
        )
        minutes = exam.get("minutes", DEFAULT_MINUTES)
        if (not isinstance(question_count, int) or isinstance(question_count, bool)
                or not 1 <= question_count <= len(selected)
                or (all_skills and question_count != len(selected))):
            raise ContentError(
                f"{exam_id}: question_count must be from 1 to the number of selected skills."
            )
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
            raise ContentError(f"{exam_id}: minutes must be a positive integer.")
        exams[exam_id] = {"id": exam_id, "title": title, "question_count": question_count,
                          "minutes": minutes, "skills": selected, "all_skills": all_skills}
    default_exam = config.get("default_exam", next(iter(exams)))
    if not isinstance(default_exam, str) or default_exam not in exams:
        raise ContentError("default_exam must identify a configured skill exam.")
    return {"method": "skill_exam", "default_exam": default_exam, "exams": exams}


class SkillExamCoach:
    def __init__(self, tutor):
        self.tutor = tutor
        self.items = []
        self.responses: list[str | None] = []
        self.hints_used: list[int] = []
        self.index = 0
        self.run_id: int | None = None
        self.run_title = ""

    def cancel(self) -> None:
        self.items = []
        self.responses = []
        self.hints_used = []
        self.index = 0
        self.run_id = None
        self.run_title = ""

    @property
    def available(self) -> bool:
        return bool(self.tutor.graph.skills)

    @property
    def eligible_skill_ids(self) -> set[str]:
        return {skill_id for skill_id, state in self.tutor.states.items() if state.mastered}

    @property
    def current_item(self):
        if not self.items or self.index >= len(self.items):
            return None
        return self.items[self.index]

    def record_hint(self) -> None:
        if self.current_item is None:
            raise RuntimeError("There is no active mock-test question to hint.")
        self.hints_used[self.index] += 1

    def start(
        self,
        skill_ids: list[str] | None = None,
        question_count: int | None = None,
        difficulty: int = 2,
    ) -> dict:
        if not self.available:
            raise ContentError("The knowledge library does not include any skills to test.")
        level = question_level(difficulty)
        rng = self.tutor.rng
        eligible = self.eligible_skill_ids
        if not eligible:
            raise ContentError("Master at least one skill before taking a mock test.")
        if skill_ids is None:
            selected = sorted(eligible)
        else:
            if (not isinstance(skill_ids, list) or not skill_ids
                    or any(not isinstance(skill_id, str)
                           or skill_id not in eligible for skill_id in skill_ids)
                    or len(skill_ids) != len(set(skill_ids))):
                raise ContentError("Choose one or more distinct mastered skills from the current library.")
            selected = list(skill_ids)
        if question_count is None:
            question_count = len(selected)
        if (
            isinstance(question_count, bool) or not isinstance(question_count, int)
            or not len(selected) <= question_count <= max(1000, len(selected))
        ):
            raise ContentError(
                "Choose at least one question per selected skill and no more than 1,000 "
                "(or the number of selected skills, if larger)."
            )
        rng.shuffle(selected)
        question_skills = selected.copy()
        for extra_index in range(question_count - len(selected)):
            question_skills.append(selected[extra_index % len(selected)])
        rng.shuffle(question_skills)
        items = []
        for skill_id in question_skills:
            seed = rng.randrange(2**31)
            item = self.tutor.generate_practice_item(skill_id, seed, difficulty)
            items.append(item)
        title = f"Custom {level['label'].lower()} mock test · {len(items)} questions"
        started = self.tutor.clock()
        with transaction(self.tutor.store.conn) as conn:
            run_id = conn.execute(
                "INSERT INTO mock_test_runs (title, started, total) VALUES (?, ?, ?)",
                (title, started, len(items)),
            ).lastrowid
        self.items = items
        self.responses = [None] * len(items)
        self.hints_used = [0] * len(items)
        self.index = 0
        self.run_id = run_id
        self.run_title = title
        return {
            "id": "custom",
            "title": title,
            "total": len(self.items),
            "skillCount": len(selected),
            "difficulty": difficulty,
            "difficultyLabel": level["label"],
        }

    def next_item(self) -> dict:
        if not self.items or self.index >= len(self.items):
            return {"done": True}
        item = self.items[self.index]
        result = item.public()
        result.update({"skillTitle": self.tutor.graph.skills[item.skill_id].title,
                       "progress": f"Question {self.index + 1} of {len(self.items)}",
                       "difficultyLabel": question_level(item.difficulty)["label"],
                       "questionXp": question_level(item.difficulty)["xp"]})
        return result

    def answer(self, response: str) -> dict:
        if not self.items or self.index >= len(self.items):
            raise RuntimeError("no active mock-test question")
        self.responses[self.index] = response
        self.index += 1
        return {"accepted": True, "done": self.index >= len(self.items)}

    def finish(self) -> dict:
        if not self.items or self.index != len(self.items) or any(
            response is None for response in self.responses
        ) or self.run_id is None:
            raise RuntimeError("answer every mock-test question before finishing")
        with self.tutor.atomic():
            result = self._finish()
        self.cancel()
        return result

    def _finish(self) -> dict:
        now = self.tutor.clock()
        correct = [check(item, response or "") for item, response in
                   zip(self.items, self.responses, strict=True)]
        touched = {}
        for index, (item, was_correct) in enumerate(zip(self.items, correct, strict=True)):
            self.tutor.store.log_attempt(now, item.skill_id, "mock_test", item.seed,
                                         item.difficulty, self.responses[index] or "",
                                         was_correct, 0)
            for state in self.tutor.record_assessment_result(
                item.skill_id, was_correct, now, weight=0.5
            ):
                touched[state.skill_id] = state
        if touched:
            self.tutor.store.save_states(list(touched.values()))
        xp = 10 + sum(
            question_level(item.difficulty)["xp"]
            for item, was_correct in zip(self.items, correct, strict=True)
            if was_correct
        )
        self.tutor.store.add_xp(now, xp, "skill mock test")
        details = [
            {"skill": self.tutor.graph.skills[item.skill_id].title, "prompt": item.prompt,
             "response": response, "correct": was_correct, "answer": item.answer_text(),
             "solution": item.solution, "hints_used": hints}
            for item, response, was_correct, hints in zip(
                self.items, self.responses, correct, self.hints_used, strict=True
            )
        ]
        if self.tutor.store.conn.execute(
            "UPDATE mock_test_runs SET finished = ?, correct = ?, results = ? WHERE id = ?",
            (now, sum(correct), json.dumps(details), self.run_id),
        ).rowcount != 1:
            raise RuntimeError("This exam no longer exists. Start a new exam.")
        result = {"title": self.run_title,
                  "correct": sum(correct),
                  "total": len(self.items), "xp": xp, "hints_used": sum(self.hints_used),
                  "results": details}
        return result

    def history(self, limit: int = 20) -> list[dict]:
        rows = self.tutor.store.conn.execute(
            "SELECT id, started, finished, correct, total, results FROM mock_test_runs "
            "WHERE finished IS NOT NULL ORDER BY started DESC LIMIT ?", (limit,)
        )
        history = []
        for row in rows:
            results = json.loads(row["results"])
            if not isinstance(results, list):
                raise ValueError(f"Mock test run {row['id']} has invalid result details.")
            history.append({
                "id": row["id"],
                "started": row["started"],
                "score": f"{row['correct']}/{row['total']}",
                "results": results,
            })
        return history
