"""Candidate-led mock case sessions with self-assessment that feeds the skill scheduler."""

import json
from dataclasses import asdict

from repetorium.core.db import transaction
from repetorium.engine.scheduler import DAY
from repetorium.engine.tutor import Tutor
from repetorium.generators import Item, check
from repetorium.generators.base import describe_response, unit_hint

RUBRIC = [
    {"key": "structure", "title": "Structure",
     "anchors": ["Generic or no framework", "Tailored buckets with some gaps/overlap",
                 "Tailored, MECE, prioritised, with hypotheses per branch"]},
    {"key": "hypothesis", "title": "Hypothesis-driven",
     "anchors": ["Asked for data at random", "Stated a hypothesis but didn't update it",
                 "Each data request tested a hypothesis that evolved with evidence"]},
    {"key": "math", "title": "Math",
     "anchors": ["Errors or no stated approach", "Correct but needed rework",
                 "Approach stated first, accurate, quick, sanity-checked"]},
    {"key": "insight", "title": "Insight",
     "anchors": ["Read numbers back without implications", "Some 'so whats'",
                 "Every result linked to the client question and next step"]},
    {"key": "synthesis", "title": "Synthesis",
     "anchors": ["Recapped the process; no clear answer", "Clear answer, weak support or no risks",
                 "Answer first, 2–3 quantified reasons, risks, next steps"]},
    {"key": "communication", "title": "Communication",
     "anchors": ["Rambling, hard to follow", "Mostly clear, occasionally lost the thread",
                 "Signposted, concise and confident throughout"]},
]

DEFAULT_RUBRIC_SKILLS = {
    "structure": ["struct.mece", "struct.issue_tree", "struct.case_types"],
    "hypothesis": ["struct.hypothesis", "struct.next_data"],
    "math": [],
    "insight": ["charts.insight"],
    "synthesis": ["synth.answer_first", "synth.structure", "synth.risks"],
    "communication": ["synth.answer_first"],
}
CASE_XP = 20
CASE_QUESTION_XP = 2


class CaseCoach:
    def __init__(self, tutor: Tutor):
        self.tutor = tutor
        self.case: dict | None = None
        self.run_id: int | None = None
        self.started = 0.0
        self.results: dict[int, bool] = {}
        self.finished = False

    def cancel(self) -> None:
        self.case = None
        self.run_id = None
        self.results = {}
        self.started = 0.0
        self.finished = False

    def _active_case(self) -> dict:
        if self.case is None or self.run_id is None:
            raise RuntimeError("Start a case before continuing.")
        return self.case

    def templates(self) -> list[dict]:
        out = []
        for template in self.tutor.graph.case_templates.values():
            skill_ids = {
                *template.raw.get("case_skills", []),
                *(question["skill"] for question in template.raw.get("questions", [])),
                *(sid for skills in template.raw.get("rubric_skills", {}).values() for sid in skills),
            }
            out.append({
                "id": template.id, "title": template.title, "archetype": template.archetype,
                "summary": template.summary, "minutes": template.minutes,
                "difficulty": template.difficulty(self.tutor.graph),
                "skillCount": len(skill_ids),
            })
        return out

    def start(self, template_id: str) -> dict:
        seed = self.tutor.rng.randrange(2**31)
        templates = self.tutor.graph.case_templates
        if template_id not in templates:
            raise ValueError(f"Unknown case: {template_id}")
        case = templates[template_id].instantiate(seed)
        started = self.tutor.clock()
        with transaction(self.tutor.store.conn) as conn:
            run_id = conn.execute(
                "INSERT INTO case_runs (template_id, seed, started, math_total) VALUES (?, ?, ?, ?)",
                (template_id, seed, started, len(case["questions"])),
            ).lastrowid
        self.case, self.run_id, self.started = case, run_id, started
        self.results = {}
        self.finished = False
        return self.public_case()

    def public_case(self) -> dict:
        c = self._active_case()
        return {
            "title": c["title"], "archetype": c["archetype"], "minutes": c["minutes"],
            "difficulty": self.tutor.graph.case_templates[c["id"]].difficulty(self.tutor.graph),
            "focusSkills": [
                self.tutor.graph.skills[sid].title for sid in c["caseSkills"]
            ],
            "prompt": c["prompt"],
            "categories": sorted({d["category"] for d in c["data"]}),
            "questions": [{"prompt": q["prompt"], "unit": q["unit"], "unitHint": unit_hint(q["unit"])}
                          for q in c["questions"]],
        }

    def request_data(self, category: str) -> list[dict]:
        case = self._active_case()
        if category not in {d["category"] for d in case["data"]}:
            raise ValueError(f"Unknown case data category: {category}")
        return [d for d in case["data"] if d["category"] == category]

    def answer(self, index: int, response: str) -> dict:
        case = self._active_case()
        if not 0 <= index < len(case["questions"]):
            raise ValueError("Select a valid case question.")
        q = case["questions"][index]
        item = Item(prompt=q["prompt"], kind="numeric", answer=q["answer"], unit=q["unit"],
                    tolerance=q["tolerance"], abs_tolerance=q["abs_tolerance"],
                    solution=q["solution"], skill_id=q["skill"])
        correct = check(item, response)
        if not self.finished:
            self.results.setdefault(index, correct)  # first attempt counts
        return {"correct": correct, "answer": item.answer_text(), "solution": q["solution"],
                "yourAnswer": describe_response(response, q["unit"])}

    def finish(self, notes: str, structure: str, recommendation: str) -> dict:
        self._active_case()
        now = self.tutor.clock()
        correct = sum(self.results.values())
        result = {
            "elapsedMinutes": round((now - self.started) / 60, 1),
            "targetMinutes": self.case["minutes"],
            "mathCorrect": correct, "mathTotal": len(self.case["questions"]),
            "questions": [{"prompt": q["prompt"], "answer": Item(
                "", "numeric", q["answer"], "", unit=q["unit"],
                tolerance=q["tolerance"], abs_tolerance=q["abs_tolerance"]).answer_text(),
                "solution": q["solution"], "correct": self.results.get(i)}
                for i, q in enumerate(self.case["questions"])],
            "modelStructure": self.case["modelStructure"],
            "modelRecommendation": self.case["modelRecommendation"],
            "yourStructure": structure, "yourRecommendation": recommendation,
            "rubric": RUBRIC,
        }
        with transaction(self.tutor.store.conn) as conn:
            if conn.execute(
                "UPDATE case_runs SET finished = ?, notes = ?, structure = ?, recommendation = ?, "
                "math_correct = ? WHERE id = ?",
                (now, notes, structure, recommendation, correct, self.run_id),
            ).rowcount != 1:
                raise RuntimeError("This case no longer exists. Start a new case.")
        self.finished = True
        return result

    def submit_scores(self, scores: dict[str, int]) -> dict:
        """Low self-scores pull the related skills' reviews forward; math results act as reviews."""
        self._active_case()
        if not self.finished:
            raise RuntimeError("Finish the case before submitting its scores.")
        allowed = {entry["key"] for entry in RUBRIC}
        if any(key not in allowed or isinstance(score, bool) or not isinstance(score, int)
               or not 1 <= score <= 5 for key, score in scores.items()):
            raise ValueError("Case scores must use known rubric keys and integers from 1 to 5.")
        tutor, now = self.tutor, self.tutor.clock()
        with tutor.atomic():
            result = self._apply_scores(scores, now)
        self.cancel()
        return result

    def _apply_scores(self, scores: dict[str, int], now: float) -> dict:
        tutor = self.tutor
        state_before = {sid: asdict(state) for sid, state in tutor.states.items()}
        state_before["__remediation_queue__"] = tutor.store.get("remediation", [])
        state_before["__skill_revisions__"] = tutor.store.skill_revisions()
        sched, states = tutor.scheduler, tutor.states
        touched = []
        for i, q in enumerate(self.case["questions"]):
            sid = q["skill"]
            if sid in states and i in self.results:
                touched += tutor.record_assessment_result(
                    sid, self.results[i], now, weight=0.5
                )
        mapping = {**DEFAULT_RUBRIC_SKILLS, **self.case["rubricSkills"]}
        flagged = []
        for key, score in scores.items():
            for sid in mapping.get(key, []):
                st = states.get(sid)
                if st is None or not st.mastered:
                    continue
                if score <= 2:
                    st.due = now
                    flagged.append(tutor.graph.skills[sid].title)
                elif score == 3:
                    st.due = min(st.due or now, now + DAY)
                else:
                    touched += sched.review(sid, True, now, weight=0.3)
                    continue
                touched.append(st)
        tutor.store.save_states(touched)
        xp = CASE_XP + CASE_QUESTION_XP * sum(self.results.values())
        tutor.store.add_xp(now, xp, "mock case", case_run_id=self.run_id)
        state_after = {sid: asdict(state) for sid, state in states.items()}
        state_after["__remediation_queue__"] = tutor.store.get("remediation", [])
        state_after["__skill_revisions__"] = tutor.store.skill_revisions()
        if tutor.store.conn.execute(
            "UPDATE case_runs SET scores = ?, state_before = ?, state_after = ? WHERE id = ?",
            (json.dumps(scores), json.dumps(state_before), json.dumps(state_after), self.run_id),
        ).rowcount != 1:
            raise RuntimeError("This case no longer exists. Start a new case.")
        return {"xp": xp, "flagged": sorted(set(flagged))}

    def history(self, limit: int = 20) -> list[dict]:
        rows = self.tutor.store.conn.execute(
            "SELECT id, template_id, started, finished, math_correct, math_total, scores "
            "FROM case_runs WHERE finished IS NOT NULL ORDER BY started DESC LIMIT ?", (limit,))
        templates = self.tutor.graph.case_templates
        out = []
        for r in rows:
            scores = json.loads(r["scores"])
            out.append({
                "id": r["id"],
                "title": templates[r["template_id"]].title if r["template_id"] in templates
                else r["template_id"],
                "minutes": round((r["finished"] - r["started"]) / 60, 1),
                "math": f"{r['math_correct']}/{r['math_total']}",
                "avgScore": round(sum(scores.values()) / len(scores), 1) if scores else None,
            })
        return out

    def delete_history(self, run_id: int) -> bool:
        with self.tutor.atomic():
            return self._delete_history(run_id)

    def _delete_history(self, run_id: int) -> bool:
        row = self.tutor.store.conn.execute(
            "SELECT state_before, state_after, finished FROM case_runs "
            "WHERE id = ? AND finished IS NOT NULL", (run_id,)
        ).fetchone()
        if row is None:
            return False

        before = json.loads(row["state_before"])
        after = json.loads(row["state_after"])
        before_queue = before.pop("__remediation_queue__", None)
        after_queue = after.pop("__remediation_queue__", None)
        before_revisions = before.pop("__skill_revisions__", {})
        after_revisions = after.pop("__skill_revisions__", None)
        current_revisions = self.tutor.store.skill_revisions()
        queue_changed = before_queue is not None and before_queue != after_queue
        if queue_changed and after_revisions is not None:
            queue_evidence = set(after_queue or []) - set(before_queue or [])
            queue_evidence.update(
                sid for sid, revision in after_revisions.items()
                if revision != before_revisions.get(sid, 0)
            )
            if any(current_revisions.get(sid, 0) != after_revisions.get(sid, 0)
                   for sid in queue_evidence):
                raise ValueError(
                    "Cannot undo this case because later learning supports its remediation queue. "
                    "Your progress and case history have been kept."
                )
        if after_revisions is None and any(
            self.tutor.store.conn.execute(sql, parameters).fetchone() is not None
            for sql, parameters in (
                ("SELECT 1 FROM attempts WHERE ts >= ? LIMIT 1", (row["finished"],)),
                ("SELECT 1 FROM case_runs WHERE id > ? AND finished IS NOT NULL LIMIT 1", (run_id,)),
                ("SELECT 1 FROM mock_test_runs WHERE finished >= ? LIMIT 1", (row["finished"],)),
            )
        ):
            raise ValueError("Cannot undo a legacy case after later learning. Your progress has been kept.")
        restored = []
        persisted = self.tutor.store.load_states(list(after))
        for sid, after_state in after.items():
            if sid not in before or after_state == before[sid]:
                continue
            current = self.tutor.states.get(sid, persisted[sid])
            if (asdict(current) != after_state or (
                after_revisions is not None
                and current_revisions.get(sid, 0) != after_revisions.get(sid, 0)
            )):
                raise ValueError(
                    "Cannot undo this case because later learning involved its affected skills. "
                    "Your progress and case history have been kept."
                )
            restored.append((current, before[sid]))
        current_queue = self.tutor.store.get("remediation", [])
        if queue_changed and current_queue != after_queue:
            raise ValueError(
                "Cannot undo this case because later learning changed its remediation queue. "
                "Your progress and case history have been kept."
            )
        for state, values in restored:
            vars(state).update(values)
        self.tutor.store.save_states([state for state, _ in restored])
        if queue_changed:
            self.tutor.store.set("remediation", before_queue)
        self.tutor.store.conn.execute("DELETE FROM xp_ledger WHERE case_run_id = ?", (run_id,))
        self.tutor.store.conn.execute("DELETE FROM case_runs WHERE id = ?", (run_id,))
        return True
