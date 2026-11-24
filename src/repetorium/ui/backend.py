"""QObject bridge exposing the tutor and case coach to QML."""

import re
import sqlite3
import tempfile
from functools import wraps
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from repetorium.assessments import SkillExamCoach
from repetorium.cases.coach import CaseCoach
from repetorium.content import ContentError, read_manifest
from repetorium.core.db import transaction
from repetorium.engine.learning_settings import ADAPTIVE_PRESETS, ADAPTIVE_SETTING_DEFAULTS
from repetorium.engine.tutor import Tutor
from repetorium.generators.base import describe_response
from repetorium.library import load_library
from repetorium.packs import (
    DuplicatePackError,
    allocate_pack_weekly_goals,
    content_pack_state,
    delete_pack,
    export_pack,
    import_pack,
    list_packs,
    load_selected_library,
    make_export_snapshot,
    prune_composed_libraries,
    read_pack_info,
    remove_imported_pack,
    restore_pack_progress,
)
from repetorium.paths import ASSET_DIR
from repetorium.question_levels import (
    QUESTION_LEVELS,
    question_level,
)


def report_errors(fallback=None):
    def decorate(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except (ContentError, OSError, sqlite3.Error, ValueError, RuntimeError) as error:
                result = self._error(error)
                return fallback() if fallback is not None else result
        return wrapped
    return decorate


class Backend(QObject):
    progressChanged = Signal()
    contentChanged = Signal()
    sessionsReset = Signal()
    errorOccurred = Signal(str)
    contentPacksChanged = Signal()

    def __init__(self, tutor: Tutor, coach: CaseCoach, parent: QObject | None = None):
        super().__init__(parent)
        self.tutor = tutor
        self.coach = coach
        self.skill_exam = SkillExamCoach(tutor)

    def _error(self, error: Exception | str) -> dict:
        message = str(error)
        self.errorOccurred.emit(message)
        return {"error": message}

    @Slot(str, result="QVariantMap")
    @report_errors()
    def copyToClipboard(self, text: str) -> dict:
        if not text:
            raise ValueError("There is no message to copy.")
        application = QGuiApplication.instance()
        if application is None:
            raise RuntimeError("The clipboard is unavailable without a GUI application.")
        application.clipboard().setText(text)
        return {"ok": True}

    @Slot(result="QVariantMap")
    def contentInfo(self) -> dict:
        directory = self.tutor.graph.content_dir
        try:
            manifest = read_manifest(directory) if any(
                (directory / name).exists() for name in ("library.yaml", "pack.yaml")) else {}
            default_name = "Personal Knowledge Library" if self.tutor.graph.skills \
                else "No content packs installed"
            return {"name": manifest.get("name", default_name),
                    "sources": manifest.get("sources", []), "directory": str(directory),
                    "skills": len(self.tutor.graph.skills),
                    "connections": len(self.tutor.graph.connections),
                    "domains": sorted({domain for skill in self.tutor.graph.skills.values()
                                       for domain in skill.domains})}
        except ContentError as error:
            return self._error(error)

    @Slot(result="QVariantMap")
    def reloadContent(self) -> dict:
        try:
            selection = content_pack_state(self.tutor.store)
            direct_library = any(
                (self.tutor.graph.content_dir / name).is_file()
                for name in ("library.yaml", "pack.yaml")
            )
            graph = (
                load_library(self.tutor.graph.content_dir)
                if direct_library and selection["mode"] == "single"
                else load_selected_library(self.tutor.store)
            )
            tutor = Tutor(self.tutor.store.conn, graph, clock=self.tutor.clock)
            coach = CaseCoach(tutor)
            skill_exam = SkillExamCoach(tutor)
        except (ContentError, OSError, sqlite3.Error) as error:
            return self._error(error)
        self.tutor, self.coach, self.skill_exam = tutor, coach, skill_exam
        self.sessionsReset.emit()
        self.contentChanged.emit()
        self.progressChanged.emit()
        return {"ok": True, "message": "Library reloaded. Study sessions ended; progress is preserved."}

    @Slot(result="QVariantMap")
    def contentPackState(self) -> dict:
        try:
            return content_pack_state(self.tutor.store)
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)

    @Slot(str, result="QVariantMap")
    def contentPackInfo(self, pack_id: str) -> dict:
        try:
            document = read_pack_info(pack_id)
            return {"ok": True, "document": document or ""}
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)

    def _packNameOverrides(self) -> dict[str, str]:
        overrides = self.tutor.store.get("setting.content_pack_name_overrides", {})
        if not isinstance(overrides, dict) or any(
            not isinstance(pack_id, str) or not isinstance(name, str) or not name.strip()
            for pack_id, name in overrides.items()
        ):
            raise ContentError("Saved content-pack name overrides are invalid.")
        return overrides

    @Slot(str, str, result="QVariantMap")
    def renameContentPack(self, pack_id: str, name: str) -> dict:
        try:
            state = content_pack_state(self.tutor.store)
            pack = next(
                (entry for entry in state["packs"] if entry["id"].casefold() == pack_id.casefold()),
                None,
            )
            if pack is None:
                raise ContentError(f"Content pack {pack_id!r} is not installed.")
            name = name.strip()
            if not name or len(name) > 80:
                raise ContentError("Enter a package name between 1 and 80 characters.")
            name_overrides = self._packNameOverrides()
            name_overrides[pack["id"]] = name
            self.tutor.store.set("setting.content_pack_name_overrides", name_overrides)
            pack["name"] = name
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)
        pack_names = {
            entry["id"]: name if entry["id"] == pack["id"] else entry["name"]
            for entry in state["packs"]
        }
        self.tutor.graph.skill_pack_names = {
            skill_id: pack_names[assigned_pack_id]
            for skill_id, assigned_pack_id in self.tutor.graph.skill_pack_ids.items()
            if assigned_pack_id in pack_names
        }
        self.contentPacksChanged.emit()
        self.contentChanged.emit()
        return {"ok": True, "message": f'Renamed package to "{name}".'}

    @Slot(str, result="QVariantMap")
    def importContentPack(self, archive_url: str) -> dict:
        try:
            url = QUrl(archive_url)
            if not url.isLocalFile():
                raise ContentError("Choose a local content-pack ZIP file.")
            current = content_pack_state(self.tutor.store)
            pack = import_pack(
                Path(url.toLocalFile()),
                existing_name_overrides=self._packNameOverrides(),
            )
        except DuplicatePackError as error:
            return self._packNameConflict(error)
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)
        try:
            return self._finishPackImport(pack, current)
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)

    @Slot(str, str, str, result="QVariantMap")
    def importContentPackWithSuffixes(
        self, archive_url: str, existing_suffix: str, incoming_suffix: str
    ) -> dict:
        try:
            url = QUrl(archive_url)
            if not url.isLocalFile():
                raise ContentError("Choose a local content-pack ZIP file.")
            if not existing_suffix.strip() or not incoming_suffix.strip():
                raise ContentError("Enter a suffix for both learning pack names.")
            current = content_pack_state(self.tutor.store)
            pack = import_pack(
                Path(url.toLocalFile()),
                conflict_suffixes=(existing_suffix, incoming_suffix),
                existing_name_overrides=self._packNameOverrides(),
            )
        except DuplicatePackError as error:
            return self._packNameConflict(error)
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)
        try:
            return self._finishPackImport(pack, current)
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)

    def _packNameConflict(self, error: DuplicatePackError) -> dict:
        try:
            name_overrides = self._packNameOverrides()
        except ContentError as override_error:
            return self._error(override_error)
        return {
            "duplicate": True,
            "incomingName": error.incoming["name"],
            "conflicts": [
                {
                    "id": pack["id"],
                    "name": name_overrides.get(pack["id"], pack["name"]),
                    "builtIn": pack["builtIn"],
                }
                for pack in error.conflicts
            ],
            "message": str(error),
        }

    def _finishPackImport(self, pack: dict, current: dict) -> dict:
        if current["mode"] == "none" or (
            len(current["selectedPackIds"]) == len(current["packs"])
        ):
            selected_ids = (
                [pack["id"]]
                if current["mode"] == "none"
                else [*current["selectedPackIds"], pack["id"]]
            )
            result = self.configureContentPackSelection(selected_ids)
            if "error" in result:
                try:
                    remove_imported_pack(pack["id"])
                except (ContentError, OSError) as error:
                    return self._error(error)
                self.contentPacksChanged.emit()
                return result
        renamed_existing = pack.get("renamedExisting", [])
        if renamed_existing:
            name_overrides = self._packNameOverrides()
            name_overrides.update({
                entry["id"]: entry["name"] for entry in renamed_existing
            })
            self.tutor.store.set("setting.content_pack_name_overrides", name_overrides)
        self.contentPacksChanged.emit()
        message = f"Imported {pack['name']} ({pack['skills']} skills)."
        if pack["snapshotIncluded"]:
            message += " A saved progress snapshot is available to restore."
        result = {"ok": True, "message": message}
        if pack["snapshotIncluded"]:
            result.update({
                "progressSnapshotAvailable": True,
                "progressPackId": pack["id"],
                "progressPackName": pack["name"],
            })
        return result

    @Slot(str, result="QVariantMap")
    @report_errors()
    def restoreContentPackProgress(self, pack_id: str) -> dict:
        restored = restore_pack_progress(self.tutor.store, pack_id)
        self.tutor.states.update(self.tutor.store.load_states(list(self.tutor.graph.skills)))
        self.progressChanged.emit()
        restored_count = restored["restoredSkills"]
        streak = self.tutor.store.streak_days(self.tutor.clock())
        message = (
            f"Restored progress for {restored_count} matching skills, a {streak}-day streak, "
            "and daily progress and study totals. "
            "Updated lifetime progress totals and added "
            f"{restored['studySecondsAdded']} seconds of lifetime study time."
        )
        if restored["skippedSkills"]:
            message += f" Skipped {restored['skippedSkills']} skills not in this pack."
        message += " Attempt history, raw answers, and personal notes are not included."
        return {"ok": True, "message": message, "streakDays": streak, **restored}

    @Slot(str, result="QVariantMap")
    def exportContentPack(self, destination_url: str) -> dict:
        return self._exportContentPack(destination_url)

    @Slot(str, str, result="QVariantMap")
    def exportContentPackForId(self, pack_id: str, destination_url: str) -> dict:
        return self._exportContentPack(destination_url, pack_id)

    @Slot(str, str, bool, result="QVariantMap")
    def exportContentPackForIdWithOptions(
        self, pack_id: str, destination_url: str, include_progress: bool
    ) -> dict:
        return self._exportContentPack(destination_url, pack_id, include_progress)

    @Slot(str, str, bool, result="QVariantMap")
    def exportAllContentPacks(
        self, destination_url: str, suffix: str, include_progress: bool = True,
    ) -> dict:
        try:
            url = QUrl(destination_url)
            if not url.isLocalFile():
                raise ContentError("Choose a local folder for the learning-pack ZIP files.")
            suffix = suffix.strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", suffix):
                raise ContentError(
                    "Use a suffix of 1-40 letters, numbers, hyphens, or underscores."
                )
            destination = Path(url.toLocalFile())
            if not destination.is_dir():
                raise ContentError("Choose an existing folder for the learning-pack ZIP files.")
            packs = content_pack_state(self.tutor.store)["packs"]
            if not packs:
                raise ContentError("There are no installed learning packs to export.")
            outputs = [destination / f"{pack['id']}-{suffix}.zip" for pack in packs]
            conflicts = [
                path.name for path in outputs if path.exists() or path.is_symlink()
            ]
            if conflicts:
                raise ContentError(
                    "Export would overwrite existing files: "
                    f"{', '.join(conflicts)}. Choose an empty folder."
                )

            published = []
            with tempfile.TemporaryDirectory(
                prefix=".repetorium-export-", dir=destination,
            ) as temporary_directory:
                staged = []
                for pack in packs:
                    archive = Path(temporary_directory) / f"{pack['id']}-{suffix}.zip"
                    result = self._exportContentPack(
                        QUrl.fromLocalFile(str(archive)).toString(),
                        pack["id"],
                        include_progress,
                    )
                    if "error" in result:
                        return result
                    staged.append(archive)

                try:
                    for archive, output in zip(staged, outputs, strict=True):
                        if output.exists() or output.is_symlink():
                            raise ContentError(
                                f"Export would overwrite {output.name}; "
                                "choose an empty folder."
                            )
                        archive.replace(output)
                        published.append(output)
                except (ContentError, OSError) as error:
                    for output in reversed(published):
                        output.unlink(missing_ok=True)
                    raise ContentError(
                        f"Could not complete the batch export; partial files were removed: {error}"
                    ) from error
        except (ContentError, OSError, sqlite3.Error, ValueError, RuntimeError) as error:
            return self._error(error)
        return {
            "ok": True,
            "message": (
                f"Exported {len(packs)} learning packs as individual ZIP files "
                f"in {destination}."
            ),
        }

    def _exportContentPack(
        self,
        destination_url: str,
        pack_id: str | None = None,
        include_progress: bool = True,
    ) -> dict:
        try:
            url = QUrl(destination_url)
            if not url.isLocalFile():
                raise ContentError("Choose a local destination for the content-pack ZIP.")
            if pack_id is None:
                selection = content_pack_state(self.tutor.store)
                export_tutor = self.tutor
                directory = export_tutor.graph.content_dir
                name_override = None
                if selection["mode"] == "single":
                    active_pack = next(
                        pack for pack in selection["packs"]
                        if pack["id"] == selection["packId"]
                    )
                    name_override = active_pack["name"]
            else:
                state = content_pack_state(self.tutor.store)
                selected_pack = next(
                    (pack for pack in state["packs"]
                     if pack["id"].casefold() == pack_id.casefold()),
                    None,
                )
                if selected_pack is None:
                    raise ContentError(f"Content pack {pack_id!r} is not installed.")
                selection = content_pack_state(
                    self.tutor.store, selected_ids=[selected_pack["id"]],
                )
                graph = load_selected_library(
                    self.tutor.store, selected_ids=[selected_pack["id"]],
                )
                export_tutor = Tutor(self.tutor.store.conn, graph, clock=self.tutor.clock)
                directory = graph.content_dir
                name_override = selected_pack["name"]

            snapshot = (
                make_export_snapshot(export_tutor, selection)
                if include_progress else None
            )
            if snapshot is not None and name_override is not None:
                snapshot["library"]["name"] = name_override
            destination = export_pack(
                directory,
                Path(url.toLocalFile()),
                snapshot,
                name_override=name_override,
                include_snapshot=include_progress,
            )
            return {
                "ok": True,
                "message": (
                    f"Exported content and learner snapshot to {destination}."
                    if include_progress else f"Exported content to {destination}."
                ),
            }
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)

    @Slot(str, result="QVariantMap")
    def deleteContentPack(self, pack_id: str) -> dict:
        try:
            state = content_pack_state(self.tutor.store)
            pack = next(
                (entry for entry in state["packs"] if entry["id"].casefold() == pack_id.casefold()),
                None,
            )
            if pack is None:
                raise ContentError(f"Content pack {pack_id!r} is not installed.")
            selected_ids = [
                selected_id for selected_id in state["selectedPackIds"]
                if selected_id.casefold() != pack_id.casefold()
            ]
            was_selected = len(selected_ids) != len(state["selectedPackIds"])
            delete_pack(pack["id"])
            name_overrides = self._packNameOverrides()
            if pack["id"] in name_overrides:
                del name_overrides[pack["id"]]
                self.tutor.store.set("setting.content_pack_name_overrides", name_overrides)
            weekly_goals = self.tutor.store.get("setting.content_pack_weekly_goals", {})
            if pack["id"] in weekly_goals:
                del weekly_goals[pack["id"]]
                self.tutor.store.set("setting.content_pack_weekly_goals", weekly_goals)
            remaining = list_packs()
            if not remaining:
                result = self.configureContentPacks("none", "")
            elif was_selected:
                if not selected_ids:
                    selected_ids = [remaining[0]["id"]]
                result = self.configureContentPackSelection(selected_ids)
            else:
                result = {"ok": True}
            self.contentPacksChanged.emit()
            if "error" in result:
                return result
        except (ContentError, OSError, ValueError, RuntimeError) as error:
            return self._error(error)
        return {
            "ok": True,
            "message": (
                f"Deleted {pack['name']}. Learner progress is retained in the profile."
                if remaining else f"Deleted {pack['name']}. Import a content pack to start practicing."
            ),
        }

    @Slot(str, str, result="QVariantMap")
    @report_errors()
    def configureContentPacks(self, mode: str, pack_id: str) -> dict:
        if mode == "mixed":
            packs = list_packs()
            if not packs:
                raise ContentError(
                    "No content packs are installed. Import a pack before selecting practice."
                )
            selected_ids = [pack["id"] for pack in packs]
        elif mode == "single":
            selected_ids = [pack_id]
        elif mode == "none":
            selected_ids = []
        else:
            return self._error(f"Unknown content-pack practice mode: {mode!r}")
        return self.configureContentPackSelection(selected_ids)

    @Slot("QVariantList", result="QVariantMap")
    @report_errors()
    def configureContentPackSelection(self, selected_ids: list) -> dict:
        try:
            state = content_pack_state(self.tutor.store, selected_ids=selected_ids)
            selected_ids = state["selectedPackIds"]
            total_goal = self.tutor.store.get("setting.lessons_per_week_goal", 5)
            previous_goals = self.tutor.store.get("setting.content_pack_weekly_goals", {})
            goals = allocate_pack_weekly_goals(total_goal, selected_ids, previous_goals)
            saved_goals = {**previous_goals, **goals}
            mode = "single" if len(selected_ids) == 1 else "mixed"
            pack_id = selected_ids[0] if selected_ids else ""
            graph = load_selected_library(self.tutor.store, selected_ids=selected_ids)
            tutor = Tutor(self.tutor.store.conn, graph, clock=self.tutor.clock)
            coach = CaseCoach(tutor)
            skill_exam = SkillExamCoach(tutor)
            with transaction(self.tutor.store.conn):
                self.tutor.store.set_many({
                    "setting.content_pack_ids": selected_ids,
                    "setting.content_pack_mode": "none" if not selected_ids else mode,
                    "setting.content_pack_id": pack_id,
                    "setting.content_pack_weekly_goals": saved_goals,
                })
        except (ContentError, OSError, sqlite3.Error, ValueError, RuntimeError) as error:
            return self._error(error)
        self.tutor, self.coach, self.skill_exam = tutor, coach, skill_exam
        message = "Practice library updated. Progress is preserved."
        try:
            prune_composed_libraries(self.tutor.graph.content_dir)
        except (ContentError, OSError) as error:
            message += f" Unused-library cache cleanup failed: {error}"
        self.sessionsReset.emit()
        self.contentChanged.emit()
        self.progressChanged.emit()
        return {"ok": True, "message": message}

    @Slot(str, int, result="QVariantMap")
    @report_errors()
    def setPackWeeklyGoal(self, pack_id: str, goal: int) -> dict:
        state = content_pack_state(self.tutor.store)
        total_goal = self.tutor.store.get("setting.lessons_per_week_goal", 5)
        previous_goals = self.tutor.store.get("setting.content_pack_weekly_goals", {})
        goals = allocate_pack_weekly_goals(
            total_goal,
            state["selectedPackIds"],
            previous_goals,
            pack_id,
            goal,
        )
        self.tutor.store.set_many({
            "setting.content_pack_weekly_goals": {**previous_goals, **goals},
        })
        self.progressChanged.emit()
        return {"ok": True, "goals": goals}

    def _setWeeklyLessonGoal(self, goal: int) -> None:
        state = content_pack_state(self.tutor.store)
        previous_goals = self.tutor.store.get("setting.content_pack_weekly_goals", {})
        goals = allocate_pack_weekly_goals(goal, state["selectedPackIds"], previous_goals)
        self.tutor.store.set_many({
            "setting.lessons_per_week_goal": goal,
            "setting.content_pack_weekly_goals": {**previous_goals, **goals},
        })

    @Slot(str, result="QVariantMap")
    def saveKnowledgeInstructions(self, destination_folder: str) -> dict:
        try:
            instructions = ASSET_DIR / "resources" / "RepetoriumSkills.MD"
            if not instructions.is_file():
                raise ContentError("The content-pack instructions could not be found.")
            folder_url = QUrl(destination_folder)
            folder = Path(folder_url.toLocalFile())
            if not folder_url.isLocalFile() or not folder.is_dir():
                raise ContentError("Choose an existing local folder for the instructions.")
            target = folder / "RepetoriumSkills.MD"
            if target.exists():
                raise ContentError(f"{target.name} already exists in the selected folder.")
            target.write_bytes(instructions.read_bytes())
            return {"ok": True, "message": f"Instructions saved to {target}."}
        except (ContentError, OSError) as error:
            return self._error(error)

    @Slot(str, result=str)
    @report_errors(str)
    def learningReflection(self, skill_id: str) -> str:
        return self.tutor.store.get(f"reflection.{skill_id}", "")

    @Slot(str, str, result="QVariantMap")
    def saveLearningReflection(self, skill_id: str, notes: str) -> dict:
        if skill_id not in self.tutor.graph.skills:
            return self._error("Select a concept in the current knowledge library.")
        try:
            self.tutor.store.set(f"reflection.{skill_id}", notes)
            return {
                "ok": True,
                "message": "Reflection saved privately. It does not affect progress or mastery.",
            }
        except sqlite3.Error as error:
            return self._error(error)

    def _task_dict(self) -> dict:
        task = self.tutor.task
        if task is None:
            return {}
        out = {"kind": task.kind, "title": task.title, "lesson": [], "guide": {}, "category": ""}
        if task.skill_ids and task.kind in ("lesson", "review"):
            skill = self.tutor.graph.skills[task.skill_ids[0]]
            out["category"] = skill.category
            if task.kind == "lesson":
                out["lesson"] = skill.lesson
                out["guide"] = skill.guide
        return out

    # ----- practice -----
    @Slot(result="QVariantMap")
    @report_errors()
    def dashboard(self) -> dict:
        return self.tutor.dashboard()

    @Slot(result="QVariantMap")
    @report_errors()
    def nextTask(self) -> dict:
        self.tutor.select_task()
        return self._task_dict()

    @Slot(str, result="QVariantMap")
    @report_errors()
    def startFocusedTask(self, mode: str) -> dict:
        self.tutor.select_task(mode)
        return self._task_dict()

    @Slot(result="QVariantMap")
    @report_errors()
    def startDiagnostic(self) -> dict:
        self.tutor.start_diagnostic()
        return self._task_dict()

    @Slot(result="QVariantMap")
    @report_errors()
    def nextItem(self) -> dict:
        task = self.tutor.task
        item = self.tutor.next_item()
        if task is None or item is None:
            if task is not None and task.kind == "diagnostic" and task.done:
                self.progressChanged.emit()
            return {"done": True, "summary": task.summary if task else "", "xp": task.xp if task else 0}
        data = item.public()
        skill = self.tutor.graph.skills[item.skill_id]
        data["skillTitle"] = skill.title
        data["lesson"] = skill.lesson
        data["guide"] = skill.guide
        if task.kind == "lesson":
            streak = self.tutor.states[task.skill_ids[0]].lesson_streak
            data["progress"] = f"{streak}/{self.tutor.adaptive_settings.mastery_streak} correct in a row"
        elif task.kind == "quiz":
            data["progress"] = f"Question {task.index + 1} of {len(task.skill_ids)}"
        elif task.kind == "diagnostic":
            data["progress"] = f"Question {task.answered + 1}"
        else:
            data["progress"] = ""
        if task.kind == "quiz":
            level = question_level(item.difficulty)
            data["difficultyLabel"] = level["label"]
            data["estimatedMinutes"] = level["minutes"]
            data["questionXp"] = level["xp"]
        data["done"] = False
        return data

    @Slot(int, bool, result="QVariantMap")
    @report_errors()
    def lessonHint(self, requested_level: int, for_exam: bool = False) -> dict:
        if for_exam:
            item = self.skill_exam.current_item
        else:
            item = self.tutor.item
        if item is None:
            raise RuntimeError("There is no active question to hint.")
        hint = self.tutor.lesson_hint(item.skill_id, item.difficulty, requested_level)
        if for_exam:
            self.skill_exam.record_hint()
        return hint

    @Slot(str, result="QVariantMap")
    @Slot(str, str, result="QVariantMap")
    @Slot(str, str, bool, result="QVariantMap")
    @report_errors()
    def submit(self, response: str, confidence: str = "", lesson_opened: bool = False) -> dict:
        item = self.tutor.item
        your = describe_response(response, item.unit) if item and item.kind == "numeric" else ""
        skill = self.tutor.graph.skills[item.skill_id] if item else None
        fb = self.tutor.submit(
            response, confidence=confidence, lesson_opened=lesson_opened,
        )
        task = self.tutor.task
        self.progressChanged.emit()
        feedback = {
            "correct": fb.correct,
            "answer": fb.answer,
            "solution": fb.solution,
            "xp": fb.xp,
            "taskDone": fb.task_done,
            "summary": fb.summary,
            "taskXp": task.xp if task else 0,
            "yourAnswer": your,
            "guide": skill.guide if skill else {},
            "skillTitle": skill.title if skill else "",
            "followUpPrompt": item.follow_up_prompt if item else "",
            "confidence": confidence,
        }
        if item is not None and task is not None and task.kind == "lesson":
            target = self.tutor.adaptive_settings.mastery_streak
            streak = (
                target
                if fb.correct and fb.task_done
                else self.tutor.states[item.skill_id].lesson_streak
            )
            feedback["progress"] = f"{streak}/{target} correct in a row"
        return feedback

    @Slot(str, str, result=str)
    def describeNumber(self, text: str, unit: str) -> str:
        return describe_response(text, unit)

    # ----- mock cases -----
    @Slot(result="QVariantList")
    @report_errors(list)
    def caseTemplates(self) -> list:
        return self.coach.templates()

    @Slot(result="QVariantList")
    @report_errors(list)
    def mockTestMethods(self) -> list:
        methods = []
        if self.coach.templates():
            methods.append({"id": "case_practice", "title": "Case-Based Practice"})
        if self.skill_exam.available:
            methods.append({"id": "skill_exam", "title": "Mock Tests"})
        return methods

    @Slot(result="QVariantList")
    def skillExamSkills(self) -> list:
        eligible = self.skill_exam.eligible_skill_ids
        return [
            {"id": skill.id, "title": skill.title, "category": skill.category}
            for skill in sorted(self.tutor.graph.skills.values(), key=lambda skill: skill.title.casefold())
            if skill.id in eligible
        ]

    @Slot(result="QVariantList")
    def questionDifficultyOptions(self) -> list:
        return [
            {"difficulty": difficulty, "label": details["label"]}
            for difficulty, details in QUESTION_LEVELS.items()
        ]

    @Slot("QVariantList", int, int, result="QVariantMap")
    @report_errors()
    def startSkillExam(self, skill_ids: list, question_count: int, difficulty: int) -> dict:
        return self.skill_exam.start(skill_ids, question_count, difficulty)

    @Slot(result="QVariantMap")
    @report_errors()
    def nextSkillExamItem(self) -> dict:
        return self.skill_exam.next_item()

    @Slot(str, result="QVariantMap")
    @report_errors()
    def answerSkillExamQuestion(self, response: str) -> dict:
        return self.skill_exam.answer(response)

    @Slot(result="QVariantMap")
    @report_errors()
    def finishSkillExam(self) -> dict:
        result = self.skill_exam.finish()
        self.progressChanged.emit()
        return result

    @Slot(result="QVariantList")
    @report_errors(list)
    def skillExamHistory(self) -> list:
        return self.skill_exam.history()

    @Slot(str, result="QVariantMap")
    @report_errors()
    def startCase(self, template_id: str) -> dict:
        return self.coach.start(template_id)

    @Slot(str, result="QVariantList")
    @report_errors(list)
    def requestCaseData(self, category: str) -> list:
        return self.coach.request_data(category)

    @Slot(int, str, result="QVariantMap")
    @report_errors()
    def answerCaseQuestion(self, index: int, response: str) -> dict:
        return self.coach.answer(index, response)

    @Slot(str, str, str, result="QVariantMap")
    @report_errors()
    def finishCase(self, notes: str, structure: str, recommendation: str) -> dict:
        return self.coach.finish(notes, structure, recommendation)

    @Slot("QVariantMap", result="QVariantMap")
    @report_errors()
    def submitCaseScores(self, scores: dict) -> dict:
        result = self.coach.submit_scores(scores)
        self.progressChanged.emit()
        return result

    @Slot(result="QVariantList")
    @report_errors(list)
    def caseHistory(self) -> list:
        return self.coach.history()

    @Slot(int, result=bool)
    @report_errors(bool)
    def deleteCaseHistory(self, run_id: int) -> bool:
        deleted = self.coach.delete_history(run_id)
        if deleted:
            self.progressChanged.emit()
        return deleted

    # ----- insight & settings -----
    @Slot(result="QVariantMap")
    @report_errors(lambda: {"nodes": [], "edges": []})
    def knowledgeMap(self) -> dict:
        graph = self.tutor.knowledge_map()
        for node in graph["nodes"]:
            node.pop("guide", None)
            node.pop("lesson", None)
        return graph

    @Slot(str, result="QVariantMap")
    @report_errors()
    def knowledgeMapSkillDetails(self, skill_id: str) -> dict:
        skill = self.tutor.graph.skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Unknown skill: {skill_id}")
        return {"guide": skill.guide, "lesson": skill.lesson}

    @Slot(result="QVariantMap")
    @report_errors()
    def stats(self) -> dict:
        return self.tutor.stats()

    @Slot(str, "QVariant", result="QVariant")
    @report_errors(lambda: None)
    def getSetting(self, key: str, default):
        return self.tutor.store.get(f"setting.{key}", default)

    @Slot(result="QVariantMap")
    def adaptivePresets(self) -> dict:
        return {name: values.copy() for name, values in ADAPTIVE_PRESETS.items()}

    @Slot(str, "QVariant")
    @report_errors(lambda: None)
    def setSetting(self, key: str, value) -> None:
        if key in ADAPTIVE_SETTING_DEFAULTS:
            self.tutor.set_adaptive_setting(key, value)
        elif key == "theme" and value not in ("dark", "light"):
            raise ValueError("Choose the light or dark theme.")
        elif key == "lessons_per_week_goal" and (
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 50
        ):
            raise ValueError("The lessons per week goal must be an integer from 1 to 50.")
        elif key == "lessons_per_week_goal":
            self._setWeeklyLessonGoal(value)
        else:
            self.tutor.store.set(f"setting.{key}", value)
        self.progressChanged.emit()

    @Slot("QVariantMap", result="QVariantMap")
    @report_errors()
    def setAdaptiveSettings(self, values: dict) -> dict:
        self.tutor.set_adaptive_settings(values)
        self.progressChanged.emit()
        return {"ok": True}

    @Slot(result="QVariantMap")
    @report_errors()
    def resetProgress(self) -> dict:
        self.tutor.reset_progress()
        self.coach.cancel()
        self.skill_exam.cancel()
        self.sessionsReset.emit()
        self.progressChanged.emit()
        return {"ok": True}
