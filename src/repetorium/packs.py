"""Import, export and compose validated Repetorium content libraries."""

import hashlib
import json
import math
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from collections import OrderedDict
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath

import yaml

from repetorium.content import ContentError, identifier, read_manifest, validate_library
from repetorium.core.db import transaction
from repetorium.engine.graph import KnowledgeGraph
from repetorium.engine.store import IMPORTED_PROGRESS_REASON, SkillState
from repetorium.paths import CONTENT_DIR, data_dir
from repetorium.yaml_io import safe_dump, safe_load

MAX_PACK_FILES = 5000
MAX_PACK_SIZE = 100 * 1024 * 1024
MAX_PACK_INFO_SIZE = 1024 * 1024
MAX_SQLITE_INTEGER = 2**63 - 1
MAX_DISK_COMPOSED_GRAPHS = 4
_PACK_DIRS = {"assessments", "banks", "cases", "graph", "lessons"}
_PACK_INFO_FILE = "INFO.md"
_SNAPSHOT_FILE = "repetorium-export.json"
_ROOT_FILES = {
    "connections.yaml", "library.yaml", "pack.yaml", _PACK_INFO_FILE, _SNAPSHOT_FILE,
}
_MAX_COMPOSED_GRAPHS = 4
_COMPOSED_GRAPHS: OrderedDict[tuple[str, str], KnowledgeGraph] = OrderedDict()
_LIBRARY_GRAPHS: dict[
    str, tuple[tuple[tuple[str, int, int], ...], KnowledgeGraph]
] = {}
_SKILL_COUNTS: dict[str, tuple[tuple[tuple[str, int, int], ...], int]] = {}


class DuplicatePackError(ContentError):
    def __init__(self, incoming: dict, conflicts: list[dict]):
        self.incoming = incoming
        self.conflicts = conflicts
        names = ", ".join(pack["name"] for pack in conflicts)
        super().__init__(
            f"{incoming['name']!r} conflicts with installed content pack(s): {names}."
        )


def _read_progress_snapshot(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ContentError("This content pack does not contain a progress snapshot.")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ContentError(f"Invalid Repetorium export snapshot: {error}") from error
    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("format")) is not int
        or snapshot["format"] != 1
    ):
        raise ContentError("Repetorium export snapshot must declare format: 1.")
    return snapshot


def _finite_number(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _snapshot_states(snapshot: dict, skill_ids: set[str]) -> tuple[list[SkillState], int]:
    progress = snapshot.get("progress")
    raw_states = progress.get("states") if isinstance(progress, dict) else None
    if not isinstance(raw_states, list):
        raise ContentError("Repetorium export snapshot does not contain skill progress.")

    required = {
        "skill_id", "status", "reps", "due", "last_reviewed", "lesson_streak",
        "lesson_errors", "fail_streak", "placed",
    }
    allowed_statuses = {"new", "learning", "mastered"}
    seen: set[str] = set()
    states = []
    skipped = 0
    for raw in raw_states:
        if not isinstance(raw, dict) or not required.issubset(raw):
            raise ContentError("Repetorium export snapshot contains an invalid skill state.")
        skill_id = raw["skill_id"]
        if not isinstance(skill_id, str) or not skill_id or skill_id in seen:
            raise ContentError("Repetorium export snapshot contains an invalid or duplicate skill ID.")
        seen.add(skill_id)
        if not isinstance(raw["status"], str) or raw["status"] not in allowed_statuses:
            raise ContentError(f"Repetorium export snapshot has an invalid status for {skill_id}.")
        reps = raw["reps"]
        if not _finite_number(reps) or reps < 0:
            raise ContentError(f"Repetorium export snapshot has invalid repetitions for {skill_id}.")
        reps = float(reps)
        dates = {}
        for field in ("due", "last_reviewed"):
            value = raw[field]
            if value is not None and (
                not _finite_number(value)
            ):
                raise ContentError(f"Repetorium export snapshot has an invalid {field} for {skill_id}.")
            dates[field] = None if value is None else float(value)
        counts = {}
        for field in ("lesson_streak", "lesson_errors", "fail_streak", "placed"):
            value = raw[field]
            if (
                isinstance(value, bool) or not isinstance(value, int)
                or not 0 <= value <= MAX_SQLITE_INTEGER
            ):
                raise ContentError(f"Repetorium export snapshot has an invalid {field} for {skill_id}.")
            counts[field] = value
        if skill_id not in skill_ids:
            skipped += 1
            continue
        states.append(SkillState(
            skill_id=skill_id,
            status=raw["status"],
            reps=reps,
            due=dates["due"],
            last_reviewed=dates["last_reviewed"],
            **counts,
        ))
    return states, skipped


def _snapshot_daily_totals(
    entries: object,
    value_key: str,
    *,
    exported_date: date,
    allow_negative: bool,
) -> dict[str, int]:
    if not isinstance(entries, list):
        raise ContentError(f"Repetorium export snapshot has invalid daily {value_key} data.")
    legacy_days = {
        (exported_date - timedelta(days=offset)).strftime("%m-%d"):
        (exported_date - timedelta(days=offset)).isoformat()
        for offset in range(-1, 16)
    }
    totals = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("day"), str):
            raise ContentError(f"Repetorium export snapshot has invalid daily {value_key} data.")
        raw_day = entry["day"]
        try:
            day = date.fromisoformat(raw_day).isoformat()
        except ValueError:
            day = legacy_days.get(raw_day, "")
        value = entry.get(value_key)
        if (
            not day or isinstance(value, bool) or not isinstance(value, int)
            or not -(2**63) <= value <= MAX_SQLITE_INTEGER
            or (not allow_negative and value < 0)
        ):
            raise ContentError(f"Repetorium export snapshot has invalid daily {value_key} data.")
        if day in totals:
            raise ContentError(f"Repetorium export snapshot has duplicate daily {value_key} data.")
        totals[day] = value
    return totals


def _snapshot_daily_progress(
    snapshot: dict, dashboard: dict, exported_at: datetime
) -> tuple[dict[str, int], set[str], dict[str, int], dict]:
    exported_date = exported_at.astimezone().date()
    daily = snapshot.get("dailyProgress")
    if daily is None:
        progress = snapshot.get("progress")
        stats = progress.get("stats") if isinstance(progress, dict) else None
        if not isinstance(stats, dict):
            raise ContentError("Repetorium export snapshot does not contain daily progress.")
        xp_by_day = _snapshot_daily_totals(
            stats.get("xpByDay"), "xp", exported_date=exported_date, allow_negative=True
        )
        study_by_day = _snapshot_daily_totals(
            stats.get("studyTimeByDay"), "seconds",
            exported_date=exported_date, allow_negative=False,
        )
        active_days = {day for day, amount in xp_by_day.items() if amount > 0}
        streak = dashboard.get("streak")
        if isinstance(streak, bool) or not isinstance(streak, int) or streak < 0:
            raise ContentError("Repetorium export snapshot has an invalid streak.")
        if streak and not active_days:
            last_active = (
                exported_date.isoformat()
                if dashboard.get("xpToday", 0) > 0
                else (exported_date - timedelta(days=1)).isoformat()
            )
            active_days.add(last_active)
        last_active_day = max(active_days) if active_days else None
    else:
        if not isinstance(daily, dict):
            raise ContentError("Repetorium export snapshot has invalid daily progress.")
        xp_by_day = _snapshot_daily_totals(
            daily.get("xpByDay"), "xp", exported_date=exported_date, allow_negative=True
        )
        study_by_day = _snapshot_daily_totals(
            daily.get("studyTimeByDay"), "seconds",
            exported_date=exported_date, allow_negative=False,
        )
        raw_active_days = daily.get("xpActiveDays")
        if not isinstance(raw_active_days, list):
            raise ContentError("Repetorium export snapshot has invalid progress activity days.")
        active_days = set()
        for day in raw_active_days:
            try:
                valid_day = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
            except ValueError:
                valid_day = False
            if not valid_day:
                raise ContentError("Repetorium export snapshot has an invalid progress activity day.")
            active_days.add(day)
        raw_streak = daily.get("streak")
        if not isinstance(raw_streak, dict):
            raise ContentError("Repetorium export snapshot has invalid streak information.")
        streak = raw_streak.get("count")
        last_active_day = raw_streak.get("lastActiveDay")
        if isinstance(streak, bool) or not isinstance(streak, int) or streak < 0:
            raise ContentError("Repetorium export snapshot has an invalid streak.")
        if last_active_day is not None:
            try:
                valid_day = (
                    isinstance(last_active_day, str)
                    and date.fromisoformat(last_active_day).isoformat() == last_active_day
                )
            except ValueError:
                valid_day = False
            if not valid_day:
                raise ContentError("Repetorium export snapshot has an invalid last active day.")
        if last_active_day is not None and last_active_day not in active_days:
            raise ContentError("Repetorium export snapshot streak does not match its progress activity.")
    streak_baseline = {
        "count": streak,
        "lastActiveDay": last_active_day,
        "exportedAt": exported_at.isoformat(),
    }
    return xp_by_day, active_days, study_by_day, streak_baseline


def restore_pack_progress(store, pack_id: str) -> dict:
    directory = pack_directory(pack_id)
    snapshot_path = directory / _SNAPSHOT_FILE
    snapshot = _read_progress_snapshot(snapshot_path)
    dashboard = snapshot.get("dashboard")
    if not isinstance(dashboard, dict):
        raise ContentError("Repetorium export snapshot does not contain dashboard totals.")
    xp_total, study_seconds = dashboard.get("xpTotal"), dashboard.get("studySecondsTotal")
    for value, label in ((xp_total, "progress points"), (study_seconds, "study time")):
        if (
            isinstance(value, bool) or not isinstance(value, int)
            or not 0 <= value <= MAX_SQLITE_INTEGER
        ):
            raise ContentError(f"Repetorium export snapshot has an invalid {label} total.")
    exported_at = snapshot.get("exportedAt")
    if not isinstance(exported_at, str):
        raise ContentError("Repetorium export snapshot does not contain an export timestamp.")
    try:
        exported_time = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContentError("Repetorium export snapshot has an invalid export timestamp.") from error
    if exported_time.tzinfo is None:
        exported_time = exported_time.replace(tzinfo=UTC)

    graph = _load_validated_library(directory)
    states, skipped = _snapshot_states(snapshot, set(graph.skills))
    xp_by_day, active_days, study_by_day, streak_baseline = _snapshot_daily_progress(
        snapshot, dashboard, exported_time
    )
    with transaction(store.conn):
        store.save_states(states)
        current_xp = store.xp_total()
        xp_added = max(0, xp_total - current_xp)
        if xp_added > MAX_SQLITE_INTEGER:
            raise ContentError("Merged progress points exceed the supported range.")
        if xp_added:
            store.add_xp(exported_time.timestamp(), xp_added, IMPORTED_PROGRESS_REASON)
        study_added = store.merge_imported_study_seconds(study_seconds)
        store.merge_imported_daily_progress(
            xp_by_day, active_days, study_by_day, streak_baseline
        )
    return {
        "packId": pack_id,
        "restoredSkills": len(states),
        "skippedSkills": skipped,
        "xpAdded": xp_added,
        "studySecondsAdded": study_added,
    }


def _directory_signature(directory: Path) -> tuple[tuple[str, int, int], ...]:
    signature = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.is_symlink():
            stat = path.stat()
            signature.append((
                path.relative_to(directory).as_posix(),
                stat.st_size,
                stat.st_mtime_ns,
            ))
    return tuple(signature)


def _graph_signature(graph_files: list[Path]) -> tuple[tuple[str, int, int], ...]:
    signature = []
    for path in graph_files:
        stat = path.stat()
        signature.append((path.name, stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


def _load_validated_library(directory: Path) -> KnowledgeGraph:
    signature = _directory_signature(directory)
    cache_key = str(directory.resolve())
    cached = _LIBRARY_GRAPHS.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    graph = validate_library(directory)[1]
    _LIBRARY_GRAPHS[cache_key] = (signature, graph)
    return graph


def _pack_root() -> Path:
    root = data_dir() / "packs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _unique_pack_id(pack_id: str) -> str:
    used = {pack["id"].casefold() for pack in list_packs()}
    suffix = 2
    while True:
        tail = f"-{suffix}"
        candidate = f"{pack_id[:80 - len(tail)]}{tail}"
        if candidate.casefold() not in used:
            return candidate
        suffix += 1


def _disabled_pack_path(pack_id: str) -> Path:
    return data_dir() / "disabled-packs" / f"{pack_id}.disabled"


def list_packs() -> list[dict]:
    packs = []
    has_bundled_manifest = any(
        (CONTENT_DIR / filename).is_file() for filename in ("library.yaml", "pack.yaml")
    )
    default_id = None
    default_enabled = False
    if has_bundled_manifest:
        manifest = read_manifest(CONTENT_DIR)
        default_id = identifier(manifest["id"], "Library ID")
        default_enabled = not _disabled_pack_path(default_id).is_file()
        if default_enabled:
            packs.append({
                "id": default_id,
                "name": manifest["name"],
                "label": f"{manifest['name']} ({default_id})",
                "skills": _skill_count(CONTENT_DIR),
                "builtIn": True,
            })
    for directory in sorted(_pack_root().iterdir(), key=lambda path: path.name.casefold()):
        if directory.name.startswith("."):
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ContentError(f"Invalid content-pack entry: {directory.name}")
        pack_manifest = read_manifest(directory)
        pack_id = identifier(pack_manifest["id"], "Library ID")
        if directory.name != pack_id:
            raise ContentError(f"Content pack folder {directory.name} does not match ID {pack_id}.")
        if (default_enabled and pack_id.casefold() == default_id.casefold()) or any(
            pack["id"].casefold() == pack_id.casefold() for pack in packs
        ):
            raise ContentError(f"Duplicate content-pack ID: {pack_id}")
        packs.append({
            "id": pack_id,
            "name": pack_manifest["name"],
            "label": f"{pack_manifest['name']} ({pack_id})",
            "skills": _skill_count(directory),
            "builtIn": False,
        })
    return packs


def _skill_count(directory: Path) -> int:
    graph_files = sorted((directory / "graph").glob("*.yaml"))
    signature = _graph_signature(graph_files)
    cache_key = str(directory.resolve())
    cached = _SKILL_COUNTS.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    count = 0
    try:
        for path in graph_files:
            skills = safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(skills, list):
                raise ContentError(f"{path.name} must contain a list of skills.")
            count += len(skills)
    except (OSError, yaml.YAMLError) as error:
        raise ContentError(f"Cannot list skills in {directory}: {error}") from error
    _SKILL_COUNTS[cache_key] = (signature, count)
    return count


def pack_directory(pack_id: str) -> Path:
    pack_id = identifier(pack_id, "Content-pack ID")
    for pack in list_packs():
        if pack["id"] == pack_id:
            return _directory_for_pack(pack)
    raise ContentError(f"Content pack {pack_id!r} is not installed.")


def _read_pack_info(path: Path) -> str | None:
    if path.is_symlink():
        raise ContentError("Content-pack INFO.md must not be a symbolic link.")
    if not path.exists():
        return None
    if not path.is_file():
        raise ContentError("Content-pack INFO.md must be a regular file.")
    if path.stat().st_size > MAX_PACK_INFO_SIZE:
        raise ContentError("Content-pack INFO.md exceeds the 1 MB limit.")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ContentError(f"Cannot read content-pack INFO.md: {error}") from error
    if not content.strip():
        raise ContentError("Content-pack INFO.md must not be empty.")
    return content


def read_pack_info(pack_id: str) -> str | None:
    return _read_pack_info(pack_directory(pack_id) / _PACK_INFO_FILE)


def _directory_for_pack(pack: dict) -> Path:
    return CONTENT_DIR if pack["builtIn"] else _pack_root() / pack["id"]


def _zip_member_path(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    if not name or "\\" in name or "\x00" in name or ":" in name:
        raise ContentError(f"Unsafe ZIP entry: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ContentError(f"Unsafe ZIP entry: {name!r}")
    if len(path.parts) == 1:
        if info.is_dir():
            if path.name not in _PACK_DIRS:
                raise ContentError(f"Unsupported content-pack directory: {name}")
        elif path.name not in _ROOT_FILES:
            raise ContentError(f"Unsupported content-pack file: {name}")
    elif len(path.parts) == 2 and path.parts[0] in _PACK_DIRS:
        if info.is_dir() or not path.name.endswith(".yaml"):
            raise ContentError(f"Unsupported content-pack file: {name}")
    else:
        raise ContentError(f"Unsupported content-pack path: {name}")
    if (not info.is_dir() and path.parts[0] == "assessments"
            and path.name != "mock_tests.yaml"):
        raise ContentError(f"Unsupported assessment file: {name}")
    if any(len(part) > 180 for part in path.parts):
        raise ContentError(f"ZIP entry name is too long: {name}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ContentError(f"ZIP entries must not be symbolic links: {name}")
    if info.flag_bits & 1:
        raise ContentError(f"Encrypted ZIP entry is not supported: {name}")
    return path


def import_pack(
    archive: Path,
    *,
    conflict_suffixes: tuple[str, str] | None = None,
    existing_name_overrides: dict[str, str] | None = None,
) -> dict:
    archive = Path(archive)
    if not archive.is_file():
        raise ContentError("Select a content-pack ZIP file.")
    if archive.suffix.casefold() != ".zip":
        raise ContentError("Content packs must use the .zip file extension.")
    if archive.stat().st_size > MAX_PACK_SIZE:
        raise ContentError("Content-pack ZIP exceeds the 100 MB limit.")
    root = _pack_root()
    staging = Path(tempfile.mkdtemp(prefix=".import-", dir=root))
    try:
        try:
            with zipfile.ZipFile(archive) as source:
                entries = source.infolist()
                if not entries or len(entries) > MAX_PACK_FILES:
                    raise ContentError(f"ZIP must contain between 1 and {MAX_PACK_FILES} entries.")
                total_size = sum(info.file_size for info in entries)
                if total_size > MAX_PACK_SIZE:
                    raise ContentError("Uncompressed content pack exceeds the 100 MB limit.")
                seen = set()
                extracted_size = 0
                for info in entries:
                    relative = _zip_member_path(info)
                    normalized = relative.as_posix().casefold()
                    if normalized in seen:
                        raise ContentError(f"Duplicate ZIP entry: {info.filename}")
                    seen.add(normalized)
                    target = staging.joinpath(*relative.parts)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(info) as input_file, target.open("xb") as output_file:
                        while chunk := input_file.read(1024 * 1024):
                            extracted_size += len(chunk)
                            if extracted_size > MAX_PACK_SIZE:
                                raise ContentError(
                                    "Uncompressed content pack exceeds the 100 MB limit."
                                )
                            output_file.write(chunk)
        except zipfile.BadZipFile as error:
            raise ContentError(f"Invalid content-pack ZIP: {error}") from error
        if not any((staging / name).is_file() for name in ("library.yaml", "pack.yaml")):
            raise ContentError("Content pack must include library.yaml or pack.yaml at its ZIP root.")
        info_path = staging / _PACK_INFO_FILE
        if info_path.exists() or info_path.is_symlink():
            _read_pack_info(info_path)
        snapshot_path = staging / _SNAPSHOT_FILE
        snapshot_included = snapshot_path.is_file()
        if snapshot_included:
            _read_progress_snapshot(snapshot_path)
        manifest, graph = validate_library(staging)
        pack_id = identifier(manifest["id"], "Library ID")
        installed = list_packs()
        name_overrides = existing_name_overrides if existing_name_overrides is not None else {}
        if not isinstance(name_overrides, dict) or any(
            not isinstance(pack_id, str) or not isinstance(name, str) or not name.strip()
            for pack_id, name in name_overrides.items()
        ):
            raise ContentError("Saved content-pack name overrides are invalid.")

        def installed_name(pack: dict) -> str:
            return name_overrides.get(pack["id"], pack["name"])

        conflicts = [
            pack for pack in installed
            if pack["id"].casefold() == pack_id.casefold()
            or installed_name(pack).strip().casefold() == manifest["name"].strip().casefold()
        ]
        renamed_existing = []
        if conflicts:
            if conflict_suffixes is None:
                raise DuplicatePackError(
                    {"id": pack_id, "name": manifest["name"]}, conflicts
                )
            old_suffix, new_suffix = conflict_suffixes
            if (not isinstance(old_suffix, str) or not old_suffix.strip()
                    or not isinstance(new_suffix, str) or not new_suffix.strip()):
                raise ContentError("Enter a nonempty suffix for both content pack names.")

            if any(pack["id"].casefold() == pack_id.casefold() for pack in conflicts):
                manifest["id"] = _unique_pack_id(pack_id)
            manifest["name"] = manifest["name"].strip() + new_suffix
            pack_id = identifier(manifest["id"], "Library ID")
            renamed_existing = [
                {"id": pack["id"], "name": installed_name(pack).strip() + old_suffix}
                for pack in conflicts
            ]

            manifest_path = staging / ("library.yaml" if (staging / "library.yaml").is_file()
                                       else "pack.yaml")
            manifest_path.write_text(
                safe_dump(manifest, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            manifest = read_manifest(staging)
            remaining = [
                pack for pack in list_packs()
                if pack["id"].casefold() == pack_id.casefold()
                or name_overrides.get(pack["id"], pack["name"]).strip().casefold()
                == manifest["name"].strip().casefold()
            ]
            if remaining:
                raise DuplicatePackError(
                    {"id": pack_id, "name": manifest["name"]}, remaining
                )
            pack_id = identifier(manifest["id"], "Library ID")
        destination = root / pack_id
        if destination.exists():
            raise ContentError(f"Content-pack destination already exists: {destination}")
        directory_signature = _directory_signature(staging)
        graph_signature = _graph_signature(sorted((staging / "graph").glob("*.yaml")))
        cache_key = str(destination.resolve())
        os.replace(staging, destination)
        graph.content_dir = destination
        _LIBRARY_GRAPHS[cache_key] = (directory_signature, graph)
        _SKILL_COUNTS[cache_key] = (graph_signature, len(graph.skills))
        _COMPOSED_GRAPHS.clear()
        result = {
            "id": pack_id,
            "name": manifest["name"],
            "skills": len(graph.skills),
            "snapshotIncluded": snapshot_included,
        }
        if renamed_existing:
            result["renamedExisting"] = renamed_existing
        return result
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as error:
        if isinstance(error, ContentError):
            raise
        raise ContentError(f"Could not import content pack: {error}") from error
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def remove_imported_pack(pack_id: str) -> None:
    pack_id = identifier(pack_id, "Content-pack ID")
    path = _pack_root() / pack_id
    installed = next(
        (pack for pack in list_packs() if pack["id"].casefold() == pack_id.casefold()),
        None,
    )
    if installed is None or installed["builtIn"]:
        raise ContentError("The built-in library cannot be deleted.")
    if (path.is_symlink() or not path.is_dir()
            or path.resolve().parent != _pack_root().resolve()):
        raise ContentError(f"Imported content pack {pack_id!r} is unavailable for rollback.")
    cache_key = str(path.resolve())
    shutil.rmtree(path)
    _LIBRARY_GRAPHS.pop(cache_key, None)
    _SKILL_COUNTS.pop(cache_key, None)
    _COMPOSED_GRAPHS.clear()


def delete_pack(pack_id: str) -> None:
    pack_id = identifier(pack_id, "Content-pack ID")
    installed = next(
        (pack for pack in list_packs() if pack["id"].casefold() == pack_id.casefold()),
        None,
    )
    if installed is None:
        raise ContentError(f"Content pack {pack_id!r} is not installed.")
    if not installed["builtIn"]:
        remove_imported_pack(installed["id"])
        return
    disabled_path = _disabled_pack_path(installed["id"])
    disabled_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = disabled_path.with_name(f".{disabled_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(installed["id"], encoding="utf-8")
        temporary.replace(disabled_path)
    finally:
        temporary.unlink(missing_ok=True)


def _export_files(directory: Path) -> list[Path]:
    files = []
    for name in _ROOT_FILES:
        path = directory / name
        if path.is_symlink():
            raise ContentError(f"Invalid content file: {path}")
        if path.is_file():
            files.append(path)
    for subdirectory in sorted(_PACK_DIRS):
        current = directory / subdirectory
        if not current.exists():
            continue
        if current.is_symlink() or not current.is_dir():
            raise ContentError(f"Invalid content directory: {current}")
        for path in sorted(current.glob("*.yaml")):
            if path.is_symlink() or not path.is_file():
                raise ContentError(f"Invalid content file: {path}")
            if subdirectory == "assessments" and path.name != "mock_tests.yaml":
                continue
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(directory).as_posix())


def export_pack(
    directory: Path,
    destination: Path,
    snapshot: dict | None = None,
    *,
    name_override: str | None = None,
    include_snapshot: bool = True,
) -> Path:
    directory = Path(directory)
    destination = Path(destination)
    if destination.suffix.casefold() != ".zip":
        raise ContentError("Export the content pack with a .zip filename.")
    validate_library(directory)
    files = _export_files(directory)
    manifest_path = directory / (
        "library.yaml" if (directory / "library.yaml").is_file() else "pack.yaml"
    )
    if name_override is not None and (
        not isinstance(name_override, str) or not name_override.strip()
    ):
        raise ContentError("Exported content-pack name must be a nonempty string.")
    if snapshot is not None or not include_snapshot:
        files = [path for path in files if path.name != _SNAPSHOT_FILE]
    if not files:
        raise ContentError("The selected library has no exportable content files.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                relative = path.relative_to(directory).as_posix()
                if name_override is not None and path == manifest_path:
                    manifest = _yaml_file(path)
                    manifest["name"] = name_override
                    archive.writestr(
                        relative,
                        safe_dump(manifest, sort_keys=False, allow_unicode=True).encode("utf-8"),
                    )
                else:
                    archive.write(path, relative)
            if snapshot is not None and include_snapshot:
                archive.writestr(
                    _SNAPSHOT_FILE,
                    json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
                )
        temporary.replace(destination)
    except (OSError, TypeError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        raise ContentError(f"Could not export content pack: {error}") from error
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def make_export_snapshot(tutor, selection: dict) -> dict:
    manifest = read_manifest(tutor.graph.content_dir)
    skill_ids = tutor.graph.topological_order
    now = tutor.clock()
    dashboard = tutor.dashboard()
    dashboard.update({
        "xpToday": tutor.store.xp_by_day(now, 1)[-1][1],
        "xpTotal": tutor.store.xp_total(),
        "studySecondsTotal": tutor.store.study_seconds_total(),
        "streak": tutor.store.streak_days(now),
    })
    stats = tutor.stats()
    active_days = tutor.store.xp_active_days()
    today = datetime.fromtimestamp(now).date().isoformat()
    last_active_day = max((day for day in active_days if day <= today), default=None)
    return {
        "format": 1,
        "exportedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "library": {
            "id": manifest["id"],
            "name": manifest["name"],
            "version": manifest["version"],
        },
        "practice": {
            "mode": selection["mode"],
            "selectedPackId": selection["packId"],
            "includedPackIds": (
                selection["selectedPackIds"]
                if selection["mode"] == "mixed"
                else [selection["packId"]]
            ),
        },
        "dashboard": dashboard,
        "progress": {
            "states": [asdict(tutor.states[skill_id]) for skill_id in skill_ids],
            "stats": stats,
        },
        "dailyProgress": {
            "xpByDay": [
                {"day": day, "xp": amount}
                for day, amount in sorted(tutor.store.xp_history_by_day().items())
            ],
            "xpActiveDays": sorted(active_days),
            "studyTimeByDay": [
                {"day": day, "seconds": seconds}
                for day, seconds in tutor.store.study_seconds_by_day(now, 14)
            ],
            "streak": {
                "count": dashboard["streak"],
                "lastActiveDay": last_active_day,
            },
        },
        "knowledgeMap": tutor.knowledge_map(),
        "learn": [
            {
                "id": skill_id,
                "title": tutor.graph.skills[skill_id].title,
                "category": tutor.graph.skills[skill_id].category,
                "domains": tutor.graph.skills[skill_id].domains,
                "prerequisites": tutor.graph.skills[skill_id].prereqs,
                "lesson": tutor.graph.skills[skill_id].lesson,
                "guide": tutor.graph.skills[skill_id].guide,
                "sources": tutor.graph.skills[skill_id].sources,
            }
            for skill_id in skill_ids
        ],
    }


def _yaml_file(path: Path):
    try:
        return safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ContentError(f"Cannot read {path}: {error}") from error


def _write_yaml(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _namespace(pack_id: str, item_id: str) -> str:
    prefix = f"p{hashlib.sha256(pack_id.encode('utf-8')).hexdigest()[:8]}."
    return prefix + item_id[:80 - len(prefix)]


def _map_pack_skill_ids(pack_id: str, skill_ids, used_skill_ids: set[str]) -> dict[str, str]:
    id_map = {}
    for skill_id in skill_ids:
        mapped_id = skill_id
        if mapped_id in used_skill_ids:
            mapped_id = _namespace(pack_id, skill_id)
            suffix = 1
            while mapped_id in used_skill_ids:
                tail = f".{suffix}"
                mapped_id = _namespace(pack_id, skill_id)[:80 - len(tail)] + tail
                suffix += 1
        id_map[skill_id] = mapped_id
        used_skill_ids.add(mapped_id)
    return id_map


def _selected_skill_pack_ids(state: dict) -> dict[str, str]:
    packs_by_id = {pack["id"]: pack for pack in state["packs"]}
    used_skill_ids: set[str] = set()
    skill_pack_ids = {}
    for pack_id in state["selectedPackIds"]:
        graph = _load_validated_library(_directory_for_pack(packs_by_id[pack_id]))
        id_map = _map_pack_skill_ids(pack_id, graph.skills, used_skill_ids)
        skill_pack_ids.update({
            mapped_id: pack_id for mapped_id in id_map.values()
        })
    return skill_pack_ids


def _cache_composed_graph(
    cache_id: tuple[str, str], graph: KnowledgeGraph
) -> None:
    _COMPOSED_GRAPHS[cache_id] = graph
    _COMPOSED_GRAPHS.move_to_end(cache_id)
    while len(_COMPOSED_GRAPHS) > _MAX_COMPOSED_GRAPHS:
        _COMPOSED_GRAPHS.popitem(last=False)


def prune_composed_libraries(active_content_dir: Path) -> None:
    libraries = data_dir() / "libraries"
    if not libraries.exists():
        return
    if libraries.is_symlink() or not libraries.is_dir():
        raise ContentError("The composed-library cache directory is invalid.")
    candidates = [
        path for path in libraries.iterdir()
        if not path.is_symlink()
        and path.is_dir()
        and len(path.name) == 24
        and all(character in "0123456789abcdef" for character in path.name)
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
    keep = set(candidates[:MAX_DISK_COMPOSED_GRAPHS])
    active = active_content_dir.resolve()
    if active.parent == libraries.resolve() and active in candidates:
        keep.add(active)
    for path in candidates:
        if path not in keep:
            shutil.rmtree(path)
            _COMPOSED_GRAPHS.pop((str(path), path.name), None)


def _compose_libraries(pack_dirs: list[Path]) -> KnowledgeGraph:
    manifests = [(directory, read_manifest(directory)) for directory in pack_dirs]
    signatures = [
        (manifest, _directory_signature(directory))
        for directory, manifest in manifests
    ]
    digest = hashlib.sha256()
    for manifest, signature in signatures:
        digest.update(manifest["id"].encode("utf-8"))
        for relative_path, size, modified in signature:
            digest.update(relative_path.encode("utf-8"))
            digest.update(f"{size}:{modified}".encode("ascii"))
    cache_key = digest.hexdigest()[:24]
    libraries = data_dir() / "libraries"
    libraries.mkdir(parents=True, exist_ok=True)
    destination = libraries / cache_key
    cache_id = (str(destination), cache_key)
    cached = _COMPOSED_GRAPHS.get(cache_id)
    if cached is not None:
        _COMPOSED_GRAPHS.move_to_end(cache_id)
        return cached
    if destination.exists():
        graph = validate_library(destination)[1]
        _cache_composed_graph(cache_id, graph)
        return graph

    pack_data = []
    used_skill_ids: set[str] = set()
    for directory, manifest in manifests:
        cached = _LIBRARY_GRAPHS.get(str(directory.resolve()))
        graph = (
            cached[1]
            if cached is not None and cached[0] == _directory_signature(directory)
            else KnowledgeGraph.load(directory / "graph")
        )
        id_map = _map_pack_skill_ids(manifest["id"], graph.skills, used_skill_ids)
        pack_data.append((directory, manifest, graph, id_map))

    staging = Path(tempfile.mkdtemp(prefix=".compose-", dir=libraries))
    try:
        combined_manifest = {
            "format": 1,
            "id": f"mixed-{cache_key}",
            "name": "Mixed Content Library",
            "version": "1.0.0",
            "sources": [
                f"Content pack: {manifest['name']} (version {manifest['version']})."
                for _, manifest, _, _ in pack_data
            ],
        }
        _write_yaml(staging / "library.yaml", combined_manifest)

        graph_by_category = {}
        combined_connections = []
        combined_guides = {}
        combined_cases = []
        for directory, manifest, _graph, id_map in pack_data:
            pack_id = manifest["id"]
            for path in sorted((directory / "graph").glob("*.yaml")):
                skills = _yaml_file(path) or []
                for skill in skills:
                    skill_id = skill["id"]
                    skill["id"] = id_map[skill_id]
                    for reference_list in ("prereqs", "similar"):
                        if reference_list in skill:
                            skill[reference_list] = [
                                id_map[reference] for reference in skill[reference_list]
                            ]
                    if "encompasses" in skill:
                        skill["encompasses"] = {
                            id_map[reference]: weight
                            for reference, weight in skill["encompasses"].items()
                        }
                    if skill.get("generator", "").startswith("bank_"):
                        params = skill.get("params") or {}
                        old_bank = identifier(params.get("bank"), f"{skill_id} bank")
                        new_bank = _namespace(pack_id, old_bank).replace(".", "_")
                        params["bank"] = new_bank
                        if params.get("skill") in id_map:
                            params["skill"] = id_map[params["skill"]]
                        bank_path = directory / "banks" / f"{old_bank}.yaml"
                        bank_target = staging / "banks" / f"{new_bank}.yaml"
                        bank = _yaml_file(bank_path)
                        entries = bank.get(
                            "items" if skill["generator"] == "bank_classify" else "entries", []
                        )
                        for entry in entries:
                            if entry.get("skill") in id_map:
                                entry["skill"] = id_map[entry["skill"]]
                        _write_yaml(bank_target, bank)
                        skill["params"] = params
                graph_by_category.setdefault(path.stem, []).extend(skills)

            links_path = directory / "connections.yaml"
            if links_path.exists():
                for link in _yaml_file(links_path) or []:
                    link["source"] = id_map[link["source"]]
                    link["target"] = id_map[link["target"]]
                    combined_connections.append(link)

            for path in sorted((directory / "lessons").glob("*.yaml")):
                guides = _yaml_file(path) or {}
                guides = {id_map[skill_id]: guide for skill_id, guide in guides.items()}
                overlap = set(combined_guides).intersection(guides)
                if overlap:
                    raise ContentError(f"Duplicate guide for skill {sorted(overlap)[0]}.")
                combined_guides.update(guides)

            for path in sorted((directory / "cases").glob("*.yaml")):
                case = _yaml_file(path)
                case["id"] = _namespace(pack_id, case["id"])
                for question in case.get("questions", []):
                    question["skill"] = id_map[question["skill"]]
                for rubric in case.get("rubric_skills", {}).values():
                    for index, skill_id in enumerate(rubric):
                        rubric[index] = id_map[skill_id]
                case["case_skills"] = [
                    id_map[skill_id] for skill_id in case.get("case_skills", [])
                ]
                combined_cases.append(case)

        for category, skills in graph_by_category.items():
            _write_yaml(staging / "graph" / f"{category}.yaml", skills)
        if combined_connections:
            _write_yaml(staging / "connections.yaml", combined_connections)
        if combined_guides:
            _write_yaml(staging / "lessons" / "combined.yaml", combined_guides)
        for case in combined_cases:
            _write_yaml(staging / "cases" / f"{case['id']}.yaml", case)
        _, graph = validate_library(staging)
        os.replace(staging, destination)
        graph.content_dir = destination
        graph.skill_pack_ids = {
            mapped_id: manifest["id"]
            for _, manifest, _, id_map in pack_data
            for mapped_id in id_map.values()
        }
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        if isinstance(error, ContentError):
            raise
        raise ContentError(f"Could not combine content packs: {error}") from error
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    _cache_composed_graph(cache_id, graph)
    return graph


def allocate_pack_weekly_goals(
    total: int,
    selected_ids: list[str],
    previous: dict[str, int],
    fixed_pack_id: str | None = None,
    fixed_goal: int | None = None,
) -> dict[str, int]:
    if isinstance(total, bool) or not isinstance(total, int) or not 1 <= total <= 50:
        raise ContentError("The lessons per week goal must be an integer from 1 to 50.")
    if not isinstance(previous, dict) or any(
        not isinstance(key, str)
        or isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 50
        for key, value in previous.items()
    ):
        raise ContentError("Saved learning-pack weekly goals are invalid.")
    if fixed_pack_id is not None:
        if not selected_ids or fixed_pack_id not in selected_ids:
            raise ContentError("Choose a selected learning pack to set its weekly goal.")
        if (
            isinstance(fixed_goal, bool) or not isinstance(fixed_goal, int)
            or not 0 <= fixed_goal <= total
        ):
            raise ContentError(f"A learning-pack goal must be an integer from 0 to {total}.")
        others = [pack_id for pack_id in selected_ids if pack_id != fixed_pack_id]
        if not others:
            if fixed_goal != total:
                raise ContentError("The only selected learning pack must use the total weekly goal.")
            return {fixed_pack_id: total}
        weights = [previous.get(pack_id, 1) for pack_id in others]
        remainder = total - fixed_goal
        allocation = {fixed_pack_id: fixed_goal}
    else:
        if not selected_ids:
            return {}
        weights = [previous.get(pack_id, 1) for pack_id in selected_ids]
        others = selected_ids
        remainder = total
        allocation = {}
    weight_total = sum(weights)
    if weight_total == 0:
        weights = [1] * len(others)
        weight_total = len(others)
    shares = [remainder * weight / weight_total for weight in weights]
    goals = [int(share) for share in shares]
    remaining = remainder - sum(goals)
    order = sorted(
        range(len(others)),
        key=lambda index: (-(shares[index] - goals[index]), index),
    )
    for index in order[:remaining]:
        goals[index] += 1
    allocation.update(dict(zip(others, goals, strict=True)))
    if sum(allocation.values()) != total:
        raise RuntimeError("Learning-pack goals do not add up to the total weekly goal.")
    return allocation


def content_pack_state(
    store,
    mode: str | None = None,
    pack_id: str | None = None,
    selected_ids: list[str] | None = None,
) -> dict:
    packs = list_packs()
    if not packs:
        if (
            (mode is not None and mode != "none")
            or (pack_id is not None and pack_id != "")
            or (selected_ids is not None and selected_ids)
        ):
            raise ContentError("No content packs are installed. Import a pack before selecting practice.")
        return {
            "packs": [], "mode": "none", "packId": "", "selectedPackIds": [],
            "activeName": "No content packs installed",
        }
    name_overrides = store.get("setting.content_pack_name_overrides", {})
    if not isinstance(name_overrides, dict) or any(
        not isinstance(pack_id, str) or not isinstance(name, str) or not name.strip()
        for pack_id, name in name_overrides.items()
    ):
        raise ContentError("Saved content-pack name overrides are invalid.")
    for pack in packs:
        name = name_overrides.get(pack["id"])
        if name is not None:
            pack["name"] = name
            pack["label"] = f"{name} ({pack['id']})"
    valid_ids = {pack["id"] for pack in packs}
    if selected_ids is not None:
        requested = selected_ids
    elif mode is not None:
        if mode == "mixed":
            requested = [pack["id"] for pack in packs]
        elif mode == "single":
            requested = [pack_id] if pack_id is not None else []
        else:
            raise ContentError(f"Unknown content-pack practice mode: {mode!r}")
    else:
        requested = store.get("setting.content_pack_ids")
        if requested is None:
            saved_mode = store.get("setting.content_pack_mode", "single")
            if saved_mode == "mixed":
                requested = [pack["id"] for pack in packs]
            else:
                legacy_id = store.get("setting.content_pack_id", packs[0]["id"])
                requested = [legacy_id]
        elif not isinstance(requested, list):
            raise ContentError("Saved learning-pack selection is invalid.")
    if (
        not isinstance(requested, list)
        or any(not isinstance(value, str) for value in requested)
        or len(set(requested)) != len(requested)
    ):
        raise ContentError("Choose one or more valid learning packs.")
    if selected_ids is not None and any(value not in valid_ids for value in requested):
        unknown = next(value for value in requested if value not in valid_ids)
        raise ContentError(f"Selected content pack {unknown!r} is not installed.")
    chosen_ids = [pack["id"] for pack in packs if pack["id"] in requested]
    if not chosen_ids:
        if selected_ids is not None or mode is not None:
            raise ContentError("Select at least one installed learning pack.")
        chosen_ids = [packs[0]["id"]]
    total = store.get("setting.lessons_per_week_goal", 5)
    if isinstance(total, bool) or not isinstance(total, int) or not 1 <= total <= 50:
        raise ContentError("Saved lessons per week goal is invalid.")
    saved_goals = store.get("setting.content_pack_weekly_goals", {})
    if not isinstance(saved_goals, dict) or any(
        not isinstance(key, str)
        or isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 50
        for key, value in saved_goals.items()
    ):
        raise ContentError("Saved learning-pack weekly goals are invalid.")
    goals = allocate_pack_weekly_goals(total, chosen_ids, saved_goals)
    for pack in packs:
        pack["selected"] = pack["id"] in chosen_ids
        pack["weeklyGoal"] = goals.get(pack["id"], 0)
    selected_mode = "single" if len(chosen_ids) == 1 else "mixed"
    primary_id = chosen_ids[0]
    active = (
        next(pack["label"] for pack in packs if pack["id"] == primary_id)
        if selected_mode == "single" else "Selected Learning Packs"
    )
    return {
        "packs": packs,
        "mode": selected_mode,
        "packId": primary_id,
        "selectedPackIds": chosen_ids,
        "activeName": active,
    }


def load_selected_library(
    store,
    mode: str | None = None,
    pack_id: str | None = None,
    selected_ids: list[str] | None = None,
) -> KnowledgeGraph:
    state = content_pack_state(store, mode, pack_id, selected_ids)
    if state["mode"] == "none":
        return KnowledgeGraph([], data_dir() / "empty-library")
    packs_by_id = {pack["id"]: pack for pack in state["packs"]}
    directories = [
        _directory_for_pack(packs_by_id[selected_id])
        for selected_id in state["selectedPackIds"]
    ]
    if len(directories) == 1:
        graph = _load_validated_library(directories[0])
        graph.skill_pack_ids = {
            skill_id: state["selectedPackIds"][0] for skill_id in graph.skills
        }
    else:
        graph = _compose_libraries(directories)
        if not graph.skill_pack_ids:
            graph.skill_pack_ids = _selected_skill_pack_ids(state)
    pack_names = {pack["id"]: pack["name"] for pack in state["packs"]}
    graph.skill_pack_names = {
        skill_id: pack_names[pack_id]
        for skill_id, pack_id in graph.skill_pack_ids.items()
        if pack_id in pack_names
    }
    return graph
