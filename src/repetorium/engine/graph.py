"""Knowledge graph: skills, prerequisite edges and weighted encompassing edges."""

from collections import deque
from dataclasses import dataclass, field
from functools import cached_property
from math import isfinite
from pathlib import Path

from repetorium.content_blocks import validate_content_block
from repetorium.paths import CONTENT_DIR
from repetorium.yaml_io import safe_load


@dataclass
class Skill:
    id: str
    title: str
    category: str
    generator: str
    params: dict = field(default_factory=dict)
    prereqs: list[str] = field(default_factory=list)
    encompasses: dict[str, float] = field(default_factory=dict)
    similar: list[str] = field(default_factory=list)
    lesson: list[str | dict] = field(default_factory=list)
    xp: int = 10
    guide: dict = field(default_factory=dict)
    domains: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class Connection:
    source: str
    target: str
    kind: str
    strength: float
    note: str


class GraphError(ValueError):
    pass


class KnowledgeGraph:
    def __init__(self, skills: list[Skill], content_dir: Path | None = None,
                 connections: list[Connection] | None = None):
        self.content_dir = content_dir or CONTENT_DIR
        self.practice_banks: dict[str, dict] | None = None
        self.case_templates: dict | None = None
        self.skill_pack_ids: dict[str, str] = {}
        self.skill_pack_names: dict[str, str] = {}
        self.connections = connections or []
        self.skills: dict[str, Skill] = {}
        for s in skills:
            if not isinstance(s.id, str) or not s.id.strip():
                raise GraphError("Skill IDs must be nonempty strings")
            if s.id in self.skills:
                raise GraphError(f"duplicate skill id {s.id}")
            self.skills[s.id] = s
            if s.domains == []:
                s.domains = [s.category]
        self.validate()

    @property
    def categories(self) -> list[str]:
        present = {skill.category for skill in self.skills.values()}
        return sorted(present)

    @staticmethod
    def category_title(category: str) -> str:
        return category.replace("_", " ").title()

    @classmethod
    def load(cls, directory: Path | None = None) -> "KnowledgeGraph":
        directory = directory or CONTENT_DIR / "graph"
        skills = []
        for path in sorted(directory.glob("*.yaml")):
            for raw in safe_load(path.read_text(encoding="utf-8")) or []:
                skills.append(Skill(category=path.stem, **raw))
        path = directory.parent / "connections.yaml"
        connections = []
        if path.exists():
            raw_connections = safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw_connections, list) or any(
                not isinstance(raw, dict) for raw in raw_connections
            ):
                raise GraphError("connections.yaml must contain a list of mappings")
            connections = [Connection(**raw) for raw in raw_connections]
        graph = cls(skills, directory.parent, connections)
        for path in sorted((directory.parent / "lessons").glob("*.yaml")):
            for skill_id, guide in (safe_load(path.read_text(encoding="utf-8")) or {}).items():
                if skill_id not in graph.skills:
                    raise GraphError(f"lesson references unknown skill {skill_id}")
                if graph.skills[skill_id].guide:
                    raise GraphError(f"duplicate guide for {skill_id}")
                cls.validate_guide(skill_id, guide)
                graph.skills[skill_id].guide = guide
        return graph

    @staticmethod
    def validate_guide(skill_id: str, guide: dict) -> None:
        if not isinstance(guide, dict):
            raise GraphError(f"{skill_id}: guide must be a mapping")
        for key in ("definition", "when_to_use"):
            if not isinstance(guide.get(key), str) or not guide[key].strip():
                raise GraphError(f"{skill_id}: guide needs {key}")
        for key in ("steps", "example", "pitfalls"):
            values = guide.get(key)
            if (not isinstance(values, list) or not values
                    or any(not isinstance(value, str) or not value.strip() for value in values)):
                raise GraphError(f"{skill_id}: guide needs nonempty {key}")
        decisions = guide.get("decision_tree")
        if not isinstance(decisions, list) or not decisions:
            raise GraphError(f"{skill_id}: guide needs a decision tree")
        for decision in decisions:
            if not isinstance(decision, dict) or any(
                not isinstance(decision.get(key), str) or not decision[key].strip()
                for key in ("question", "yes", "no")
            ):
                raise GraphError(f"{skill_id}: decision needs question, yes and no branches")

    def validate(self) -> None:
        from repetorium.generators import GENERATORS

        for s in self.skills.values():
            if (not isinstance(s.id, str) or not s.id.strip()
                    or not isinstance(s.title, str) or not s.title.strip()
                    or not isinstance(s.generator, str) or not isinstance(s.params, dict)
                    or not isinstance(s.category, str) or not s.category.strip()):
                raise GraphError("Skills need string IDs, titles, generators and mapping params")
            for label in ("prereqs", "similar", "domains", "sources"):
                values = getattr(s, label)
                if not isinstance(values, list) or any(
                    not isinstance(v, str) or not v.strip() for v in values
                ):
                    raise GraphError(f"{s.id}: {label} must be a list of strings")
            if not isinstance(s.lesson, list):
                raise GraphError(f"{s.id}: lesson must be a list.")
            for index, block in enumerate(s.lesson):
                if isinstance(block, str):
                    if not block.strip():
                        raise GraphError(f"{s.id}: lesson passages must not be empty.")
                    continue
                try:
                    validate_content_block(block, f"{s.id} lesson block {index + 1}")
                except ValueError as error:
                    raise GraphError(str(error)) from error
            if len(s.prereqs) != len(set(s.prereqs)):
                raise GraphError(f"{s.id}: duplicate prerequisites")
            if not isinstance(s.encompasses, dict):
                raise GraphError(f"{s.id}: encompasses must be a mapping")
            for ref in [*s.prereqs, *s.encompasses, *s.similar]:
                if ref not in self.skills:
                    raise GraphError(f"{s.id} references unknown skill {ref}")
            for target, w in s.encompasses.items():
                if (isinstance(w, bool) or not isinstance(w, (int, float))
                        or not isfinite(w) or not 0 < w <= 1):
                    raise GraphError(f"{s.id} → {target}: weight {w} not in (0, 1]")
                if target not in s.prereqs and target not in self.ancestors(s.id):
                    raise GraphError(f"{s.id} encompasses {target}, which is not a prerequisite")
            if s.generator not in GENERATORS:
                raise GraphError(f"{s.id} uses unknown generator {s.generator}")
        self.topological_order  # noqa: B018  raises on cycles
        seen = set()
        for link in self.connections:
            if link.source not in self.skills or link.target not in self.skills:
                raise GraphError("Connection references unknown skill")
            if link.source == link.target:
                raise GraphError("Connections must join different skills")
            if link.kind not in ("related", "analogy", "application", "contrast"):
                raise GraphError(f"Unknown connection kind {link.kind}")
            if (isinstance(link.strength, bool) or not isinstance(link.strength, (int, float))
                    or not isfinite(link.strength) or not 0 < link.strength <= 1):
                raise GraphError("Connection strength must be in (0, 1]")
            if not isinstance(link.note, str) or not link.note.strip():
                raise GraphError("Connections need a note explaining the relationship")
            identity = (tuple(sorted((link.source, link.target))), link.kind)
            if identity in seen:
                raise GraphError("Duplicate connection")
            seen.add(identity)

    def ancestors(self, skill_id: str) -> set[str]:
        seen: set[str] = set()
        stack = list(self.skills[skill_id].prereqs)
        while stack:
            cur = stack.pop()
            if cur == skill_id:
                raise GraphError(f"cycle through {skill_id}")
            if cur not in seen:
                seen.add(cur)
                stack.extend(self.skills[cur].prereqs)
        return seen

    @cached_property
    def connections_by_skill(self) -> dict[str, list[Connection]]:
        out: dict[str, list[Connection]] = {sid: [] for sid in self.skills}
        for link in self.connections:
            out[link.source].append(link)
            out[link.target].append(link)
        return out

    @cached_property
    def dependents(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {sid: [] for sid in self.skills}
        for s in self.skills.values():
            for p in s.prereqs:
                out[p].append(s.id)
        return out

    def descendants(self, skill_id: str) -> set[str]:
        seen: set[str] = set()
        stack = list(self.dependents[skill_id])
        while stack:
            cur = stack.pop()
            if cur not in seen:
                seen.add(cur)
                stack.extend(self.dependents[cur])
        return seen

    @cached_property
    def topological_order(self) -> list[str]:
        indeg = {sid: len(s.prereqs) for sid, s in self.skills.items()}
        ready = deque(sid for sid, d in indeg.items() if d == 0)
        order = []
        while ready:
            cur = ready.popleft()
            order.append(cur)
            for dep in self.dependents[cur]:
                indeg[dep] -= 1
                if indeg[dep] == 0:
                    ready.append(dep)
        if len(order) != len(self.skills):
            raise GraphError("prerequisite graph has a cycle")
        return order

    @cached_property
    def depth(self) -> dict[str, int]:
        depth: dict[str, int] = {}
        for sid in self.topological_order:
            prereqs = self.skills[sid].prereqs
            depth[sid] = 1 + max((depth[p] for p in prereqs), default=-1)
        return depth

    @cached_property
    def _reachability_bitsets(self) -> tuple[dict[str, int], dict[str, int]]:
        index = {sid: i for i, sid in enumerate(self.topological_order)}
        ancestors: dict[str, int] = {}
        for sid in self.topological_order:
            bits = 0
            for prerequisite in self.skills[sid].prereqs:
                bits |= ancestors[prerequisite] | (1 << index[prerequisite])
            ancestors[sid] = bits

        descendants: dict[str, int] = {}
        for sid in reversed(self.topological_order):
            bits = 0
            for dependent in self.dependents[sid]:
                bits |= descendants[dependent] | (1 << index[dependent])
            descendants[sid] = bits
        return ancestors, descendants

    def implicit_credit(self, skill_id: str, credit: float = 1.0,
                        floor: float = 0.05) -> dict[str, float]:
        """Fractional repetition credit flowing down encompassing edges (max over paths)."""
        result: dict[str, float] = {}
        stack = [(skill_id, credit)]
        while stack:
            cur, c = stack.pop()
            for target, w in self.skills[cur].encompasses.items():
                tc = c * w
                if tc >= floor and tc > result.get(target, 0):
                    result[target] = tc
                    stack.append((target, tc))
        return result
