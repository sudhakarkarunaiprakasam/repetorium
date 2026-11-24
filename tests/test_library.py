import math
import os
import stat

import pytest
import yaml

from repetorium.cases.coach import CaseCoach
from repetorium.content import ContentError, validate_library
from repetorium.core.db import connect
from repetorium.engine.graph import Connection, GraphError, KnowledgeGraph, Skill
from repetorium.engine.tutor import Tutor
from repetorium.library import load_library, open_progress
from repetorium.paths import PACKAGE_DIR, data_dir, default_db_path, legacy_db_path
from repetorium.ui.backend import Backend


def write_library(directory):
    directory.mkdir()
    (directory / "library.yaml").write_text(yaml.safe_dump({
        "format": 1, "id": "personal", "name": "Personal library", "version": "1",
        "sources": ["An original source"],
    }), encoding="utf-8")
    (directory / "graph").mkdir()
    (directory / "graph" / "sample.yaml").write_text(yaml.safe_dump([
        {"id": "sample.growth", "title": "Compound growth", "generator": "compound_growth",
         "domains": ["sample", "quantitative"], "sources": ["An original source"]},
    ]), encoding="utf-8")
    return directory


def test_application_source_has_no_default_learning_library():
    directory = PACKAGE_DIR / "content"
    assert not (directory / "library.yaml").exists()
    assert KnowledgeGraph.load(directory / "graph").skills == {}


def test_single_profile_has_one_progress_database(monkeypatch, tmp_path):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path))
    assert data_dir() == tmp_path
    assert default_db_path(tmp_path / "first") == default_db_path(tmp_path / "second")
    assert default_db_path() == tmp_path / "knowledge.sqlite3"


@pytest.mark.skipif(os.name != "posix", reason="POSIX profile permissions")
def test_profile_directory_is_private(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o755)
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(profile))

    assert stat.S_IMODE(data_dir().stat().st_mode) == 0o700


@pytest.mark.parametrize("legacy", ["current", "original"])
def test_migration_preserves_history_and_original(monkeypatch, tmp_path, legacy):
    monkeypatch.setenv("REPETORIUM_DATA_DIR", str(tmp_path))
    directory = tmp_path / "content"
    source = {"current": legacy_db_path(directory),
              "original": tmp_path / "repetorium.sqlite3"}[legacy]
    previous = connect(source)
    previous.execute("INSERT INTO meta VALUES ('setting.theme', '\"light\"')")
    previous.execute("INSERT INTO xp_ledger (ts, amount, reason) VALUES (10, 30, 'lesson')")
    previous.commit()
    previous.close()
    connection = open_progress(directory)
    assert connection.execute("SELECT value FROM meta WHERE key='setting.theme'").fetchone()[0] == '"light"'
    assert connection.execute("SELECT amount FROM xp_ledger").fetchone()[0] == 30
    connection.close()
    assert source.exists()
    again = open_progress(directory)
    assert again.execute("SELECT COUNT(*) FROM xp_ledger").fetchone()[0] == 1
    again.close()


def test_manifest_needs_no_license_and_loads_source_metadata(tmp_path):
    _, graph = validate_library(write_library(tmp_path / "library"))
    assert graph.skills["sample.growth"].sources == ["An original source"]


def test_bad_content_reload_is_explicit_and_preserves_session(tmp_path, conn):
    directory = write_library(tmp_path / "library")
    tutor = Tutor(conn, load_library(directory))
    backend = Backend(tutor, CaseCoach(tutor))
    tutor.select_task()
    task = tutor.task
    (directory / "graph" / "sample.yaml").write_text("not a skill list", encoding="utf-8")
    assert "error" in backend.reloadContent()
    assert backend.tutor is tutor
    assert backend.tutor.task is task


def test_expanding_library_preserves_mastery_and_adds_new_skills(tmp_path, conn):
    directory = write_library(tmp_path / "library")
    tutor = Tutor(conn, load_library(directory))
    backend = Backend(tutor, CaseCoach(tutor))
    state = tutor.states["sample.growth"]
    state.status = "mastered"
    tutor.store.save_states([state])
    (directory / "graph" / "adjacent.yaml").write_text(yaml.safe_dump([
        {"id": "adjacent.rates", "title": "Rates", "generator": "unit_rates",
         "domains": ["adjacent"], "prereqs": ["sample.growth"]},
    ]), encoding="utf-8")
    assert backend.reloadContent()["ok"]
    assert backend.tutor.states["sample.growth"].mastered
    assert backend.tutor.is_available("adjacent.rates")
    assert backend.tutor.store.conn is conn


def simple_skills():
    return [Skill("sample.rates", "Rates", "sample", "unit_rates"),
            Skill("adjacent.rates", "Related rates", "adjacent", "unit_rates")]


def test_connections_are_bidirectional_navigation_not_mastery_or_gating(conn):
    graph = KnowledgeGraph(simple_skills(), connections=[
        Connection("sample.rates", "adjacent.rates", "analogy", 0.5, "Both express change per unit.")
    ])
    tutor = Tutor(conn, graph)
    assert set(tutor.frontier()) == {"sample.rates", "adjacent.rates"}
    assert graph.ancestors("adjacent.rates") == set()
    assert graph.implicit_credit("adjacent.rates") == {}
    nodes = {node["id"]: node for node in tutor.knowledge_map()["nodes"]}
    assert nodes["sample.rates"]["connections"][0]["id"] == "adjacent.rates"
    assert nodes["adjacent.rates"]["connections"][0]["id"] == "sample.rates"


@pytest.mark.parametrize("strength", [0, -1, 2, math.nan, math.inf, True, "strong"])
def test_connection_strength_is_validated(strength):
    with pytest.raises(GraphError, match="strength"):
        KnowledgeGraph(simple_skills(), connections=[
            Connection("sample.rates", "adjacent.rates", "analogy", strength, "Rates relate.")
        ])


@pytest.mark.parametrize("connection", [
    Connection("sample.rates", "missing", "analogy", 0.5, "Note"),
    Connection("sample.rates", "sample.rates", "related", 0.5, "Note"),
    Connection("sample.rates", "adjacent.rates", "unknown", 0.5, "Note"),
    Connection("sample.rates", "adjacent.rates", "related", 0.5, ""),
])
def test_invalid_connections_are_rejected(connection):
    with pytest.raises(GraphError):
        KnowledgeGraph(simple_skills(), connections=[connection])


def test_duplicate_reverse_connections_are_rejected():
    with pytest.raises(GraphError, match="Duplicate"):
        KnowledgeGraph(simple_skills(), connections=[
            Connection("sample.rates", "adjacent.rates", "analogy", 0.5, "Note"),
            Connection("adjacent.rates", "sample.rates", "analogy", 0.6, "Another note"),
        ])


@pytest.mark.parametrize("mutation", ["cycle", "unknown-generator", "reserved-params", "bad-xp",
                                     "bad-domain", "bad-source", "bad-assessment"])
def test_invalid_library_is_rejected(tmp_path, mutation):
    directory = write_library(tmp_path / "library")
    path = directory / "graph" / "sample.yaml"
    skills = yaml.safe_load(path.read_text(encoding="utf-8"))
    skill = skills[0]
    if mutation == "cycle":
        skill["prereqs"] = [skill["id"]]
    elif mutation == "unknown-generator":
        skill["generator"] = "missing"
    elif mutation == "reserved-params":
        skill["params"] = {"_content_dir": "elsewhere"}
    elif mutation == "bad-xp":
        skill["xp"] = True
    elif mutation == "bad-domain":
        skill["domains"] = "sample"
    elif mutation == "bad-source":
        skill["sources"] = [""]
    else:
        (directory / "assessments").mkdir()
        (directory / "assessments" / "mock_tests.yaml").write_text(
            "method: skill_exam\nskills: [missing]\n", encoding="utf-8")
    path.write_text(yaml.safe_dump(skills), encoding="utf-8")
    with pytest.raises(ContentError):
        validate_library(directory)
