import json
import os
import zipfile

import pytest
import yaml
from PySide6.QtCore import QUrl

import repetorium.packs as pack_module
from repetorium.cases.coach import CaseCoach
from repetorium.content import ContentError
from repetorium.core.db import connect
from repetorium.engine.graph import KnowledgeGraph
from repetorium.engine.store import SkillState, Store
from repetorium.engine.tutor import Tutor
from repetorium.packs import (
    content_pack_state,
    export_pack,
    import_pack,
    list_packs,
    load_selected_library,
    make_export_snapshot,
)
from repetorium.ui.backend import Backend


def write_pack(directory, pack_id, skill_id, *, bank=False):
    directory.mkdir(parents=True)
    (directory / "graph").mkdir()
    (directory / "library.yaml").write_text(yaml.safe_dump({
        "format": 1,
        "id": pack_id,
        "name": pack_id.title(),
        "version": "1.0",
        "sources": ["User-provided content"],
    }), encoding="utf-8")
    skill = {"id": skill_id, "title": "A mapped concept",
             "generator": "bank_choice" if bank else "compound_growth"}
    if bank:
        skill["params"] = {"bank": "questions"}
        (directory / "banks").mkdir()
        (directory / "banks" / "questions.yaml").write_text(yaml.safe_dump({
            "entries": [{
                "prompt": "Mapped prompt?",
                "correct": "Mapped answer",
                "distractors": ["Mapped distractor"],
                "explain": "Mapped explanation.",
            }],
        }), encoding="utf-8")
    (directory / "graph" / "concepts.yaml").write_text(
        yaml.safe_dump([skill]), encoding="utf-8"
    )
    return directory


def zip_directory(directory, archive_path):
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory).as_posix()
            archive.write(path, relative + ("/" if path.is_dir() else ""))
    return archive_path


def test_import_export_content_pack_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    source = write_pack(tmp_path / "source", "round-trip", "sample.concept", bank=True)
    info_document = "# Round Trip\n\nThis pack teaches the mapped concept.\n"
    (source / "INFO.md").write_text(info_document, encoding="utf-8")
    source_zip = zip_directory(source, tmp_path / "source.zip")
    with zipfile.ZipFile(source_zip, "a") as archive:
        archive.writestr("repetorium-export.json", json.dumps({"format": 1}))

    imported = import_pack(source_zip)

    assert imported == {
        "id": "round-trip", "name": "Round-Trip", "skills": 1, "snapshotIncluded": True,
    }
    assert any(pack["id"] == "round-trip" for pack in list_packs())
    exported = export_pack(tmp_path / "profile" / "packs" / "round-trip", tmp_path / "export.zip")
    with zipfile.ZipFile(exported) as archive:
        assert "library.yaml" in archive.namelist()
        assert archive.read("INFO.md").decode("utf-8") == info_document
        assert "graph/concepts.yaml" in archive.namelist()
        assert "banks/questions.yaml" in archive.namelist()
        assert "repetorium-export.json" in archive.namelist()
        assert all(not name.startswith("round-trip/") for name in archive.namelist())


@pytest.mark.parametrize(
    ("info_bytes", "error_text"),
    [
        (b"\xff", "INFO.md"),
        (b"x" * (pack_module.MAX_PACK_INFO_SIZE + 1), "1 MB limit"),
    ],
)
def test_import_rejects_invalid_info_document(monkeypatch, tmp_path, info_bytes, error_text):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    source = write_pack(tmp_path / "invalid-info", "invalid-info", "sample.concept")
    (source / "INFO.md").write_bytes(info_bytes)

    with pytest.raises(ContentError, match=error_text):
        import_pack(zip_directory(source, tmp_path / "invalid-info.zip"))


def test_format_instructions_download_to_selected_folder(conn, tmp_path):
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    destination = tmp_path / "instructions"
    destination.mkdir()

    assert backend.saveKnowledgeInstructions(QUrl.fromLocalFile(str(destination)).toString())["ok"]
    instructions = destination / "RepetoriumSkills.MD"
    text = instructions.read_text(encoding="utf-8")
    assert text.startswith("---\nname: repetorium-content-format")
    assert "Do not invent concepts" in text
    assert "Naming skills, lessons, and categories" in text
    assert "Aim for 2-4 words" in text
    assert "concise `snake_case` filename" in text
    assert "error" in backend.saveKnowledgeInstructions(QUrl.fromLocalFile(str(destination)).toString())
    assert "error" in backend.saveKnowledgeInstructions("https://example.com/instructions.md")


def test_backend_import_export_and_pack_selection(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    source = write_pack(tmp_path / "backend-pack", "backend-pack", "backend.skill")
    (source / "INFO.md").write_text(
        "# Backend Pack\n\nPurpose: demonstrate pack information.\n", encoding="utf-8",
    )
    source_zip = zip_directory(source, tmp_path / "backend.zip")
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    changed = []
    backend.contentPacksChanged.connect(lambda: changed.append(True))

    imported = backend.importContentPack(QUrl.fromLocalFile(str(source_zip)).toString())

    assert imported["ok"]
    assert "progress snapshot" not in imported["message"]
    assert changed
    assert backend.contentPackInfo("backend-pack") == {
        "ok": True,
        "document": "# Backend Pack\n\nPurpose: demonstrate pack information.\n",
    }
    individual_export_path = tmp_path / "individual.zip"
    individual_export = backend.exportContentPackForId(
        "backend-pack", QUrl.fromLocalFile(str(individual_export_path)).toString(),
    )
    assert individual_export["ok"]
    with zipfile.ZipFile(individual_export_path) as archive:
        individual_manifest = yaml.safe_load(archive.read("library.yaml"))
        individual_snapshot = json.loads(archive.read("repetorium-export.json"))
    assert individual_manifest["name"] == "Backend-Pack"
    assert individual_snapshot["practice"]["includedPackIds"] == ["backend-pack"]
    assert [state["skill_id"] for state in individual_snapshot["progress"]["states"]] == [
        "backend.skill",
    ]
    mastered = backend.tutor.states["sample.root"]
    mastered.status = "mastered"
    backend.tutor.store.save_states([mastered])
    exported_path = tmp_path / "active.zip"
    assert backend.exportContentPack(QUrl.fromLocalFile(str(exported_path)).toString())["ok"]
    with zipfile.ZipFile(exported_path) as archive:
        assert "library.yaml" in archive.namelist()
        snapshot = json.loads(archive.read("repetorium-export.json"))
    assert snapshot["format"] == 1
    assert snapshot["dashboard"]["total"] == len(backend.tutor.graph.skills)
    assert snapshot["progress"]["stats"] == backend.tutor.stats()
    assert any(
        state["skill_id"] == "sample.root" and state["status"] == "mastered"
        for state in snapshot["progress"]["states"]
    )
    assert any(node["id"] == "sample.root" and node["status"] == "mastered"
               for node in snapshot["knowledgeMap"]["nodes"])
    assert any(skill["id"] == "sample.root" for skill in snapshot["learn"])
    assert "attempts" not in snapshot["progress"]
    assert backend.configureContentPacks("single", "backend-pack")["ok"]
    assert "backend.skill" in backend.tutor.graph.skills
    assert content_pack_state(backend.tutor.store)["packId"] == "backend-pack"


@pytest.mark.parametrize("include_progress", [True, False])
def test_backend_exports_all_packs_as_individual_zip_files(
    conn, monkeypatch, tmp_path, include_progress,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    for pack_id in ("batch-one", "batch-two"):
        source = write_pack(tmp_path / pack_id, pack_id, f"{pack_id}.skill")
        archive = zip_directory(source, tmp_path / f"{pack_id}.zip")
        if pack_id == "batch-one":
            with zipfile.ZipFile(archive, "a") as zip_file:
                zip_file.writestr("repetorium-export.json", json.dumps({"format": 1}))
        import_pack(archive)

    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    destination = tmp_path / "all-packs"
    destination.mkdir()
    suffix = "2026-11-16"

    result = backend.exportAllContentPacks(
        QUrl.fromLocalFile(str(destination)).toString(), suffix, include_progress,
    )

    assert result["ok"]
    installed_ids = {pack["id"] for pack in list_packs()}
    exported_paths = list(destination.glob("*.zip"))
    assert {path.name for path in exported_paths} == {
        f"{pack_id}-{suffix}.zip" for pack_id in installed_ids
    }
    for pack_id in installed_ids:
        with zipfile.ZipFile(destination / f"{pack_id}-{suffix}.zip") as archive:
            assert "library.yaml" in archive.namelist()
            if include_progress:
                snapshot = json.loads(archive.read("repetorium-export.json"))
                assert snapshot["practice"]["includedPackIds"] == [pack_id]
            else:
                assert "repetorium-export.json" not in archive.namelist()


def test_backend_export_all_refuses_existing_archive_without_overwriting(
    conn, monkeypatch, tmp_path,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    destination = tmp_path / "all-packs"
    destination.mkdir()
    first_pack_id = list_packs()[0]["id"]
    suffix = "2026-11-16"
    existing = destination / f"{first_pack_id}-{suffix}.zip"
    existing.write_text("keep this file", encoding="utf-8")

    result = backend.exportAllContentPacks(
        QUrl.fromLocalFile(str(destination)).toString(), suffix,
    )

    assert "error" in result
    assert "Choose an empty folder" in result["error"]
    assert existing.read_text(encoding="utf-8") == "keep this file"
    assert list(destination.glob("*.zip")) == [existing]


def test_backend_export_all_rejects_unsafe_suffix(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    destination = tmp_path / "all-packs"
    destination.mkdir()

    result = backend.exportAllContentPacks(
        QUrl.fromLocalFile(str(destination)).toString(), "../outside",
    )

    assert "error" in result
    assert "suffix" in result["error"]
    assert list(tmp_path.glob("outside-*.zip")) == []
    assert list(destination.iterdir()) == []


def test_individual_export_can_omit_an_existing_progress_snapshot(
    conn, monkeypatch, tmp_path,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    source = write_pack(tmp_path / "snapshot-pack", "snapshot-pack", "snapshot.skill")
    archive_path = zip_directory(source, tmp_path / "snapshot-pack.zip")
    with zipfile.ZipFile(archive_path, "a") as archive:
        archive.writestr("repetorium-export.json", json.dumps({"format": 1}))
    import_pack(archive_path)

    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    exported_path = tmp_path / "snapshot-pack-no-progress.zip"
    result = backend.exportContentPackForIdWithOptions(
        "snapshot-pack",
        QUrl.fromLocalFile(str(exported_path)).toString(),
        False,
    )

    assert result["ok"]
    with zipfile.ZipFile(exported_path) as archive:
        assert "repetorium-export.json" not in archive.namelist()


@pytest.mark.parametrize("legacy_snapshot", [False, True])
def test_exported_snapshot_restores_skill_and_daily_progress(
    monkeypatch, tmp_path, legacy_snapshot,
):
    source = write_pack(tmp_path / "source", "progress-transfer", "transfer.skill")
    source_graph = pack_module.validate_library(source)[1]
    source_conn = connect(":memory:")
    source_tutor = Tutor(source_conn, source_graph)
    source_now = source_tutor.clock()
    source_state = source_tutor.states["transfer.skill"]
    source_state.status = "mastered"
    source_state.reps = 3.5
    source_state.due = source_now + 86_400
    source_state.last_reviewed = source_now
    source_state.lesson_streak = 2
    source_tutor.store.save_states([source_state])
    source_tutor.store.log_attempt(
        source_now, "transfer.skill", "lesson", 1, 2, "private answer", True, 120
    )
    source_tutor.store.add_xp(source_now, 55, "lesson", "transfer.skill")
    for days_ago in range(1, 30):
        source_tutor.store.add_xp(source_now - days_ago * 86_400, 1, "lesson")
    assert source_tutor.store.streak_days(source_now) == 30
    snapshot = make_export_snapshot(source_tutor, {
        "mode": "single",
        "packId": "progress-transfer",
        "packs": [{"id": "progress-transfer"}],
    })
    assert "dailyProgress" in snapshot
    if legacy_snapshot:
        snapshot.pop("dailyProgress")
    archive = export_pack(source, tmp_path / "progress-transfer.zip", snapshot)
    with zipfile.ZipFile(archive) as exported:
        snapshot_text = exported.read("repetorium-export.json").decode("utf-8")
    assert "private answer" not in snapshot_text
    assert "attempts" not in snapshot["progress"]
    source_conn.close()

    target_data = tmp_path / "target-profile"
    target_content = tmp_path / "target-content"
    target_content.mkdir()
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(target_data))
    monkeypatch.setattr(pack_module, "CONTENT_DIR", target_content)
    target_conn = connect(":memory:")
    target_tutor = Tutor(target_conn, KnowledgeGraph([]))
    backend = Backend(target_tutor, CaseCoach(target_tutor))
    imported = backend.importContentPack(QUrl.fromLocalFile(str(archive)).toString())

    assert imported["ok"]
    assert imported["progressSnapshotAvailable"]
    assert imported["progressPackId"] == "progress-transfer"
    assert target_tutor.store.xp_total() == 0
    assert target_tutor.store.study_seconds_total() == 0
    local_state = backend.tutor.states["transfer.skill"]
    local_state.status = "learning"
    local_state.reps = 1
    backend.tutor.store.save_states([local_state])
    other_state = SkillState("unrelated.skill", status="mastered", reps=2)
    backend.tutor.store.save_states([other_state])

    restored = backend.restoreContentPackProgress("progress-transfer")

    assert restored["ok"]
    assert restored["restoredSkills"] == 1
    assert restored["skippedSkills"] == 0
    assert restored["xpAdded"] == 84
    assert restored["studySecondsAdded"] == 120
    assert restored["streakDays"] == 30
    assert "daily progress and study totals" in restored["message"]
    assert "XP" not in restored["message"]
    assert backend.tutor.states["transfer.skill"].status == "mastered"
    assert backend.tutor.states["transfer.skill"].reps == 3.5
    assert backend.tutor.states["transfer.skill"].lesson_streak == 2
    assert backend.tutor.store.xp_total() == 84
    assert backend.tutor.store.study_seconds_total() == 120
    assert backend.tutor.store.xp_by_day(backend.tutor.clock(), 14)[-1][1] == 55
    assert backend.tutor.store.study_seconds_by_day(backend.tutor.clock(), 14)[-1][1] == 120
    assert backend.tutor.store.streak_days(backend.tutor.clock()) == 30
    assert backend.tutor.store.load_states(["unrelated.skill"])["unrelated.skill"].mastered

    repeated = backend.restoreContentPackProgress("progress-transfer")
    assert repeated["ok"]
    assert repeated["xpAdded"] == 0
    assert repeated["studySecondsAdded"] == 0
    assert backend.tutor.store.xp_total() == 84
    assert backend.tutor.store.study_seconds_total() == 120

    backend.tutor.store.add_xp(1_900_000_000.0, 100, "local learning")
    backend.tutor.store.log_attempt(
        1_900_000_001.0, "transfer.skill", "lesson", 2, 2, "local answer", True, 200
    )
    later_restore = backend.restoreContentPackProgress("progress-transfer")
    assert later_restore["ok"]
    assert later_restore["xpAdded"] == 0
    assert later_restore["studySecondsAdded"] == 0
    assert backend.tutor.store.xp_total() == 184
    assert backend.tutor.store.study_seconds_total() == 320
    target_conn.close()


def test_import_while_mixed_adds_pack_to_active_combined_library(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    assert backend.configureContentPacks("mixed", "sample-library")["ok"]
    source = write_pack(tmp_path / "overlap", "overlap-pack", "sample.root")
    source_zip = zip_directory(source, tmp_path / "overlap.zip")

    imported = backend.importContentPack(QUrl.fromLocalFile(str(source_zip)).toString())

    assert imported["ok"]
    assert content_pack_state(backend.tutor.store)["mode"] == "mixed"
    assert "sample.root" in backend.tutor.graph.skills
    assert any(
        skill_id.endswith(".sample.root") and skill_id != "sample.root"
        for skill_id in backend.tutor.graph.skills
    )


@pytest.mark.parametrize(
    ("incoming_id", "expected_id"),
    [("shared-pack", "shared-pack-2"), ("updated-pack", "updated-pack")],
)
def test_duplicate_pack_names_prompt_suffixes_and_preserve_existing(
    conn, monkeypatch, tmp_path, incoming_id, expected_id,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))

    existing = write_pack(tmp_path / "existing", "shared-pack", "existing.skill")
    incoming = write_pack(tmp_path / "incoming", incoming_id, "incoming.skill")
    for directory in (existing, incoming):
        manifest_path = directory / "library.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["name"] = "Shared Learning Pack"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    existing_zip = zip_directory(existing, tmp_path / "existing.zip")
    incoming_zip = zip_directory(incoming, tmp_path / "incoming.zip")

    assert backend.importContentPack(QUrl.fromLocalFile(str(existing_zip)).toString())["ok"]
    old_state = backend.tutor.states["sample.root"]
    old_state.status = "mastered"
    backend.tutor.store.save_states([old_state])

    conflict = backend.importContentPack(QUrl.fromLocalFile(str(incoming_zip)).toString())
    assert conflict["duplicate"]
    assert conflict["incomingName"] == "Shared Learning Pack"
    assert conflict["conflicts"] == [{
        "id": "shared-pack",
        "name": "Shared Learning Pack",
        "builtIn": False,
    }]

    imported = backend.importContentPackWithSuffixes(
        QUrl.fromLocalFile(str(incoming_zip)).toString(), " (previous)", " (updated)"
    )
    assert imported["ok"]
    packs = {pack["id"]: pack["name"] for pack in backend.contentPackState()["packs"]}
    assert packs["shared-pack"] == "Shared Learning Pack (previous)"
    assert packs[expected_id] == "Shared Learning Pack (updated)"
    assert backend.tutor.states["sample.root"].mastered
    assert yaml.safe_load(
        (tmp_path / "profile" / "packs" / "shared-pack" / "library.yaml").read_text(
            encoding="utf-8"
        )
    )["name"] == "Shared Learning Pack"
    assert backend.configureContentPacks("single", "shared-pack")["ok"]
    exported = tmp_path / "renamed-old-pack.zip"
    assert backend.exportContentPack(QUrl.fromLocalFile(str(exported)).toString())["ok"]
    with zipfile.ZipFile(exported) as archive:
        assert yaml.safe_load(archive.read("library.yaml"))["name"] == \
            "Shared Learning Pack (previous)"


def test_import_rejects_traversal_and_invalid_zip_without_installing(monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    malicious = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../escaped.yaml", "bad")

    with pytest.raises(ContentError, match="Unsafe ZIP entry"):
        import_pack(malicious)
    assert not (tmp_path / "escaped.yaml").exists()
    assert list_packs() == [{
        "id": "sample-library",
        "name": "Sample Test Library",
        "label": "Sample Test Library (sample-library)",
        "skills": 5,
        "builtIn": True,
    }]


def test_app_can_start_without_bundled_content_and_import_first_pack(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    monkeypatch.setattr(pack_module, "CONTENT_DIR", tmp_path / "no-bundled-content")
    graph = load_selected_library(Store(conn))
    assert graph.skills == {}
    tutor = Tutor(conn, graph)
    backend = Backend(tutor, CaseCoach(tutor))
    assert backend.contentPackState()["mode"] == "none"
    assert backend.contentInfo()["name"] == "No content packs installed"

    source = write_pack(tmp_path / "first-pack", "first-pack", "first.skill")
    result = backend.importContentPack(
        QUrl.fromLocalFile(str(zip_directory(source, tmp_path / "first-pack.zip"))).toString()
    )

    assert result["ok"]
    assert "first.skill" in backend.tutor.graph.skills
    assert backend.contentPackState()["mode"] == "single"


def test_removed_saved_selection_falls_back_to_an_installed_pack(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    monkeypatch.setattr(pack_module, "CONTENT_DIR", tmp_path / "no-bundled-content")
    first = write_pack(tmp_path / "first", "first-pack", "first.skill")
    second = write_pack(tmp_path / "second", "second-pack", "second.skill")
    import_pack(zip_directory(first, tmp_path / "first.zip"))
    import_pack(zip_directory(second, tmp_path / "second.zip"))
    store = Store(conn)
    store.set("setting.content_pack_id", "deleted-pack")

    selected = load_selected_library(store)

    assert set(selected.skills) == {"first.skill"}


def test_mixed_library_namespaces_banks_and_keeps_pack_progress(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    extra = write_pack(tmp_path / "extra", "extra-practice", "extra.metric", bank=True)
    import_pack(zip_directory(extra, tmp_path / "extra.zip"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    built_in = next(pack["id"] for pack in list_packs() if pack["builtIn"])
    original_state = backend.tutor.states["sample.root"]
    original_state.status = "mastered"
    backend.tutor.store.save_states([original_state])
    backend.tutor.store.add_xp(1, 11, "test", "sample.root")

    result = backend.configureContentPacks("mixed", built_in)

    assert result["ok"]
    assert "extra.metric" in backend.tutor.graph.skills
    assert "sample.root" in backend.tutor.graph.skills
    namespaced_bank = backend.tutor.graph.skills["extra.metric"].params["bank"]
    assert namespaced_bank != "questions"
    assert namespaced_bank in backend.tutor.graph.practice_banks
    assert backend.tutor.states["sample.root"].mastered
    assert backend.tutor.store.xp_total() == 11
    assert content_pack_state(backend.tutor.store)["mode"] == "mixed"


def test_mixed_mode_namespaces_duplicate_skill_ids(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    duplicate = write_pack(tmp_path / "duplicate", "duplicate-skills", "sample.root")
    import_pack(zip_directory(duplicate, tmp_path / "duplicate.zip"))

    graph = load_selected_library(Store(conn), "mixed", "sample-library")
    assert "sample.root" in graph.skills
    assert len([
        skill_id for skill_id in graph.skills
        if skill_id != "sample.root" and skill_id.endswith(".sample.root")
    ]) == 1


def test_selected_library_reuses_validation_and_invalidates_after_edits(
    conn, monkeypatch, tmp_path,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    source = write_pack(tmp_path / "cached", "cached-pack", "cached.skill")
    validate_library = pack_module.validate_library
    validated = []

    def count_validation(directory):
        validated.append(directory)
        return validate_library(directory)

    monkeypatch.setattr(pack_module, "validate_library", count_validation)
    import_pack(zip_directory(source, tmp_path / "cached.zip"))
    assert len(validated) == 1

    safe_load = pack_module.safe_load
    parsed_for_count = []

    def count_yaml_load(stream):
        parsed_for_count.append(stream)
        return safe_load(stream)

    monkeypatch.setattr(pack_module, "safe_load", count_yaml_load)
    store = Store(conn)
    first = load_selected_library(store, "single", "cached-pack")
    assert load_selected_library(store, "single", "cached-pack") is first
    assert len(validated) == 1
    assert parsed_for_count == []

    graph_file = tmp_path / "profile" / "packs" / "cached-pack" / "graph" / "concepts.yaml"
    graph_file.write_text(
        yaml.safe_dump([{
            "id": "cached.skill",
            "title": "Updated mapped concept",
            "generator": "compound_growth",
        }]),
        encoding="utf-8",
    )
    updated = load_selected_library(store, "single", "cached-pack")

    assert len(validated) == 2
    assert len(parsed_for_count) == 1
    assert updated.skills["cached.skill"].title == "Updated mapped concept"


def test_mixed_library_cache_hit_does_not_reread_pack_contents(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    source = write_pack(tmp_path / "mixed", "mixed-pack", "mixed.skill")
    import_pack(zip_directory(source, tmp_path / "mixed.zip"))
    built_in = next(pack["id"] for pack in list_packs() if pack["builtIn"])
    store = Store(conn)
    mixed = load_selected_library(store, "mixed", built_in)

    def reject_content_read(_path):
        raise AssertionError("A cached mixed library should not reread pack file contents.")

    monkeypatch.setattr(pack_module.Path, "read_bytes", reject_content_read)

    assert load_selected_library(store, "mixed", built_in) is mixed


def test_composed_graph_cache_is_bounded(monkeypatch):
    cache = pack_module._COMPOSED_GRAPHS
    cache.clear()
    monkeypatch.setattr(pack_module, "_MAX_COMPOSED_GRAPHS", 2)

    keys = [(str(index), str(index)) for index in range(3)]
    for key in keys:
        pack_module._cache_composed_graph(key, object())

    assert list(cache) == keys[-2:]
    cache.clear()


def test_composed_library_disk_cache_keeps_recent_entries_and_active(
    monkeypatch, tmp_path,
):
    profile = tmp_path / "profile"
    libraries = profile / "libraries"
    libraries.mkdir(parents=True)
    paths = [libraries / f"{index:024x}" for index in range(6)]
    for index, path in enumerate(paths):
        path.mkdir()
        os.utime(path, ns=(index + 1, index + 1))
    monkeypatch.setattr(pack_module, "data_dir", lambda: profile)

    pack_module.prune_composed_libraries(paths[0])

    assert {path.name for path in libraries.iterdir()} == {
        paths[0].name, *[path.name for path in paths[2:]],
    }


def test_backend_switches_packs_without_losing_existing_skill_progress(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    extra = write_pack(tmp_path / "extra", "extra-practice", "extra.metric")
    import_pack(zip_directory(extra, tmp_path / "extra.zip"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    state = backend.tutor.states["sample.root"]
    state.status = "mastered"
    backend.tutor.store.save_states([state])
    built_in = next(pack["id"] for pack in list_packs() if pack["builtIn"])

    switched = backend.configureContentPacks("single", "extra-practice")
    assert switched["ok"]
    assert set(backend.tutor.states) == {"extra.metric"}
    restored = backend.configureContentPacks("single", built_in)
    assert restored["ok"]
    assert backend.tutor.states["sample.root"].mastered
    assert backend.tutor.store.get("setting.content_pack_id") == built_in


def test_backend_selects_a_subset_and_keeps_pack_goals_within_total(
    conn, monkeypatch, tmp_path,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    extra = write_pack(tmp_path / "extra", "extra-practice", "extra.metric")
    unselected = write_pack(tmp_path / "unselected", "unselected-pack", "unused.metric")
    import_pack(zip_directory(extra, tmp_path / "extra.zip"))
    import_pack(zip_directory(unselected, tmp_path / "unselected.zip"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    built_in = next(pack["id"] for pack in list_packs() if pack["builtIn"])

    selected = backend.configureContentPackSelection([built_in, "extra-practice"])

    assert selected["ok"], selected
    built_in_skills = set(load_selected_library(Store(conn), "single", built_in).skills)
    assert set(backend.tutor.graph.skills) == built_in_skills | {"extra.metric"}
    state = content_pack_state(backend.tutor.store)
    assert state["selectedPackIds"] == [built_in, "extra-practice"]
    expected_names = {pack["id"]: pack["name"] for pack in state["packs"]}
    assert backend.tutor.graph.skill_pack_ids["extra.metric"] == "extra-practice"
    assert all(
        backend.tutor.graph.skill_pack_names[skill_id] == expected_names[pack_id]
        for skill_id, pack_id in backend.tutor.graph.skill_pack_ids.items()
    )
    assert sum(pack["weeklyGoal"] for pack in state["packs"] if pack["selected"]) == 5
    snapshot = make_export_snapshot(backend.tutor, state)
    assert snapshot["practice"]["includedPackIds"] == [built_in, "extra-practice"]
    assert next(pack for pack in state["packs"] if pack["id"] == "unselected-pack")[
        "weeklyGoal"
    ] == 0

    assert backend.setPackWeeklyGoal("extra-practice", 2)["ok"]
    state = content_pack_state(backend.tutor.store)
    assert {
        pack["id"]: pack["weeklyGoal"] for pack in state["packs"] if pack["selected"]
    } == {built_in: 3, "extra-practice": 2}
    backend.setSetting("lessons_per_week_goal", 8)
    state = content_pack_state(backend.tutor.store)
    assert sum(pack["weeklyGoal"] for pack in state["packs"] if pack["selected"]) == 8
    assert backend.configureContentPackSelection([])["error"]
    assert content_pack_state(backend.tutor.store)["selectedPackIds"] == [
        built_in, "extra-practice",
    ]


def test_deleting_any_pack_switches_practice_and_preserves_progress(
    conn, monkeypatch, tmp_path,
):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path / "profile"))
    extra = write_pack(tmp_path / "extra", "deletable-pack", "deletable.skill")
    another = write_pack(tmp_path / "another", "another-pack", "another.skill")
    import_pack(zip_directory(extra, tmp_path / "deletable.zip"))
    import_pack(zip_directory(another, tmp_path / "another.zip"))
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    built_in = next(pack["id"] for pack in list_packs() if pack["builtIn"])

    assert "not installed" in backend.deleteContentPack("unknown")["error"]
    assert backend.configureContentPacks("mixed", built_in)["ok"]
    assert backend.deleteContentPack("deletable-pack")["ok"]
    assert content_pack_state(backend.tutor.store)["mode"] == "mixed"
    assert "another.skill" in backend.tutor.graph.skills
    assert "deletable.skill" not in backend.tutor.graph.skills
    another_state = backend.tutor.states["another.skill"]
    another_state.status = "mastered"
    backend.tutor.store.save_states([another_state])

    assert backend.configureContentPacks("single", "another-pack")["ok"]
    assert backend.deleteContentPack("another-pack")["ok"]
    assert content_pack_state(backend.tutor.store)["packId"] == built_in
    deleted_last = backend.deleteContentPack(built_in)
    assert deleted_last["ok"]
    assert content_pack_state(backend.tutor.store)["mode"] == "none"
    assert backend.tutor.graph.skills == {}
    assert not (tmp_path / "profile" / "packs" / "deletable-pack").exists()
    assert not (tmp_path / "profile" / "packs" / "another-pack").exists()
    assert not any(pack["id"] == "deletable-pack" for pack in list_packs())
    assert not any(pack["id"] == built_in for pack in list_packs())
    assert backend.tutor.store.load_states(["another.skill"])["another.skill"].mastered
    assert backend.contentInfo()["name"] == "No content packs installed"

    imported = backend.importContentPack(
        QUrl.fromLocalFile(str(tmp_path / "deletable.zip")).toString()
    )
    assert imported["ok"]
    assert "deletable.skill" in backend.tutor.graph.skills
    assert content_pack_state(backend.tutor.store)["mode"] == "single"


def test_renaming_pack_persists_and_updates_skill_attribution(conn):
    tutor = Tutor(conn)
    backend = Backend(tutor, CaseCoach(tutor))
    state = backend.contentPackState()
    pack_id = state["packs"][0]["id"]

    assert backend.renameContentPack(pack_id, "  Short title  ")["ok"]
    renamed_state = backend.contentPackState()
    renamed_pack = next(pack for pack in renamed_state["packs"] if pack["id"] == pack_id)
    assert renamed_pack["name"] == "Short title"
    assert backend.tutor.store.get("setting.content_pack_name_overrides")[pack_id] == \
        "Short title"
    assert all(
        name == "Short title"
        for skill_id, name in backend.tutor.graph.skill_pack_names.items()
        if backend.tutor.graph.skill_pack_ids[skill_id] == pack_id
    )
    assert "package name" in backend.renameContentPack(pack_id, "   ")["error"]
    assert "80 characters" in backend.renameContentPack(pack_id, "x" * 81)["error"]
    assert "not installed" in backend.renameContentPack("missing-pack", "Name")["error"]
