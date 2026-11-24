import hashlib
import os
from pathlib import Path

from platformdirs import user_data_dir

PACKAGE_DIR = Path(__file__).resolve().parent
ASSET_DIR = (
    PACKAGE_DIR
    if (PACKAGE_DIR / "qml" / "Main.qml").is_file()
    else PACKAGE_DIR.parent
)


def resolve_content_dir(configured: str | None = None) -> Path:
    return Path(configured).expanduser().resolve() if configured else ASSET_DIR / "content"


QML_DIR = ASSET_DIR / "qml"


def data_dir() -> Path:
    configured = os.environ.get("REPETORIUM_DATA_DIR")
    path = (Path(configured).expanduser().resolve() if configured
            else Path(user_data_dir("repetorium", appauthor=False)))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        if path.stat().st_uid != os.getuid():
            raise PermissionError("Repetorium profile directory must be owned by the current user.")
        path.chmod(0o700)
    return path


CONTENT_DIR = resolve_content_dir(os.environ.get("REPETORIUM_CONTENT_DIR"))


def default_db_path(content_dir: Path | None = None) -> Path:
    return data_dir() / "knowledge.sqlite3"


def legacy_db_path(content_dir: Path) -> Path:
    identity = str((content_dir or CONTENT_DIR).resolve())
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    directory = data_dir() / "progress"
    directory.mkdir(exist_ok=True)
    return directory / f"{key}.sqlite3"
