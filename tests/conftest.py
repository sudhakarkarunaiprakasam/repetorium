import os
import sqlite3
from pathlib import Path

import pytest

os.environ["REPETORIUM_CONTENT_DIR"] = str(Path(__file__).parent / "fixtures" / "content")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))

from repetorium.core.db import connect
from repetorium.engine.graph import KnowledgeGraph
from repetorium.generators import Item


@pytest.fixture(scope="session")
def qt_fonts(qapp):
    if os.name == "nt":
        from PySide6.QtGui import QFont

        qapp.setFont(QFont("Arial", 10))


class FakeClock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture(scope="session")
def graph() -> KnowledgeGraph:
    return KnowledgeGraph.load()


@pytest.fixture
def conn() -> sqlite3.Connection:
    return connect(":memory:")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def correct_response(item: Item) -> str:
    if item.kind in ("order", "multi_select", "matching"):
        return ",".join(str(i) for i in item.answer)
    return str(item.answer)


def wrong_response(item: Item) -> str:
    if item.kind == "numeric":
        return str(item.answer * 3 + 1000)
    if item.kind == "choice":
        return str((item.answer + 1) % len(item.choices))
    if item.kind == "multi_select":
        replacement = [i for i in range(len(item.choices)) if i not in item.answer][:1]
        return ",".join(map(str, replacement or item.answer[1:]))
    if item.kind in ("matching", "order"):
        answer = list(item.answer)
        if len(answer) > 1:
            answer[0], answer[1] = answer[1], answer[0]
        return ",".join(map(str, answer))
    return "incorrect"
