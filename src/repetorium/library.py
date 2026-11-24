"""Personal library loading and non-destructive progress migration."""

import sqlite3
from contextlib import closing
from pathlib import Path

from repetorium.content import validate_library
from repetorium.core.db import connect
from repetorium.engine.graph import KnowledgeGraph
from repetorium.paths import CONTENT_DIR, data_dir, default_db_path, legacy_db_path


def load_library(directory: Path = CONTENT_DIR) -> KnowledgeGraph:
    return validate_library(directory)[1]


def open_progress(directory: Path = CONTENT_DIR) -> sqlite3.Connection:
    destination = default_db_path()
    if destination.exists():
        return connect(destination)
    candidates = [legacy_db_path(directory)]
    candidates.append(data_dir() / "repetorium.sqlite3")
    source = next((path for path in candidates if path.is_file()), None)
    if source is not None:
        temporary = destination.with_suffix(".migrating")
        try:
            with closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as previous:
                with closing(sqlite3.connect(temporary)) as copied:
                    previous.backup(copied)
            # Do not publish an unusable profile if its schema cannot be migrated.
            with closing(connect(temporary)):
                pass
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return connect(destination)
