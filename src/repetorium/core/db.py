import sqlite3
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS: list[str] = [
    """
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE skill_state (
        skill_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'new',
        reps REAL NOT NULL DEFAULT 0,
        due REAL,
        last_reviewed REAL,
        lesson_streak INTEGER NOT NULL DEFAULT 0,
        lesson_errors INTEGER NOT NULL DEFAULT 0,
        fail_streak INTEGER NOT NULL DEFAULT 0,
        placed INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE attempts (
        id INTEGER PRIMARY KEY,
        ts REAL NOT NULL,
        skill_id TEXT NOT NULL,
        task_kind TEXT NOT NULL,
        seed INTEGER NOT NULL,
        difficulty INTEGER NOT NULL,
        response TEXT NOT NULL,
        correct INTEGER NOT NULL,
        seconds REAL NOT NULL
    );
    CREATE INDEX attempts_ts ON attempts(ts);
    CREATE TABLE xp_ledger (
        id INTEGER PRIMARY KEY,
        ts REAL NOT NULL,
        amount INTEGER NOT NULL,
        reason TEXT NOT NULL,
        skill_id TEXT
    );
    CREATE INDEX xp_ts ON xp_ledger(ts);
    CREATE TABLE case_runs (
        id INTEGER PRIMARY KEY,
        template_id TEXT NOT NULL,
        seed INTEGER NOT NULL,
        started REAL NOT NULL,
        finished REAL,
        notes TEXT NOT NULL DEFAULT '',
        structure TEXT NOT NULL DEFAULT '',
        recommendation TEXT NOT NULL DEFAULT '',
        math_correct INTEGER NOT NULL DEFAULT 0,
        math_total INTEGER NOT NULL DEFAULT 0,
        scores TEXT NOT NULL DEFAULT '{}'
    );
    """,
    """
    ALTER TABLE case_runs ADD COLUMN state_before TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE case_runs ADD COLUMN state_after TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE xp_ledger ADD COLUMN case_run_id INTEGER;

    WITH ranked_cases AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS seq
        FROM case_runs WHERE scores != '{}'
    ), ranked_xp AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS seq
        FROM xp_ledger WHERE reason = 'mock case'
    )
    UPDATE xp_ledger SET case_run_id = (
        SELECT ranked_cases.id FROM ranked_cases
        JOIN ranked_xp ON ranked_xp.seq = ranked_cases.seq
        WHERE ranked_xp.id = xp_ledger.id
    ) WHERE reason = 'mock case';
    """,
    """
    CREATE TABLE mock_test_runs (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        started REAL NOT NULL,
        finished REAL,
        correct INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL,
        elapsed_seconds INTEGER NOT NULL DEFAULT 0,
        results TEXT NOT NULL DEFAULT '[]'
    );
    """,
    "SELECT 1;",
    """
    CREATE TABLE skill_activity (
        skill_id TEXT PRIMARY KEY,
        revision INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    ALTER TABLE attempts ADD COLUMN confidence TEXT NOT NULL DEFAULT ''
        CHECK (confidence IN ('', 'explained', 'unsure', 'guessed'));
    """,
    """
    CREATE INDEX attempts_skill_id ON attempts(skill_id, id, seed, difficulty);
    CREATE INDEX attempts_kind_recent ON attempts(task_kind, id DESC, skill_id);
    CREATE INDEX xp_positive_ts ON xp_ledger(ts DESC) WHERE amount > 0;
    """,
    """
    CREATE TABLE quiz_completions (
        id INTEGER PRIMARY KEY,
        completed_at REAL NOT NULL
    );
    CREATE INDEX quiz_completions_at ON quiz_completions(completed_at);
    """,
    """
    ALTER TABLE quiz_completions
        ADD COLUMN correct INTEGER NOT NULL DEFAULT 0 CHECK (correct >= 0);
    ALTER TABLE quiz_completions
        ADD COLUMN total INTEGER NOT NULL DEFAULT 0 CHECK (total >= 0);
    """,
]


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:
        raise sqlite3.ProgrammingError("Migrations require a connection with no active transaction.")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if not 0 <= version <= len(MIGRATIONS):
        raise sqlite3.DatabaseError("This progress database was created by a newer application version.")
    for i, script in enumerate(MIGRATIONS[version:], start=version + 1):
        try:
            conn.executescript(f"BEGIN IMMEDIATE;\n{script}\nPRAGMA user_version = {i};\nCOMMIT;")
        except BaseException:
            conn.rollback()
            raise


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Savepoints compose without committing a caller's transaction."""
    conn.execute("SAVEPOINT repetorium_write")
    try:
        yield conn
        conn.execute("RELEASE SAVEPOINT repetorium_write")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT repetorium_write")
        conn.execute("RELEASE SAVEPOINT repetorium_write")
        raise
