"""Parametric case templates: YAML + a restricted arithmetic expression language."""

import ast
import math
import operator
import random
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from repetorium.generators.base import fmt_big, fmt_money, fmt_num, fmt_pct
from repetorium.paths import CONTENT_DIR
from repetorium.yaml_io import safe_load

_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.FloorDiv: operator.floordiv,
           ast.Mod: operator.mod}
_CMPOPS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
           ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
_FUNCS = {"round": round, "min": min, "max": max, "abs": abs, "ceil": math.ceil,
          "floor": math.floor}


def safe_eval(expr: str, env: dict):
    """Evaluate arithmetic over `env` without exposing Python's eval."""

    def bounded(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Case expressions must produce finite numbers.")
        if isinstance(value, int) and value.bit_length() > 1024:
            raise ValueError("Case expression integer is too large.")
        if isinstance(value, str) and len(value) > 4096:
            raise ValueError("Case expression string is too long.")
        if not isinstance(value, int | float | str):
            raise ValueError("Case expressions support only numbers and strings.")
        return value

    def ev(node):
        return bounded(evaluate(node))

    def evaluate(node):
        match node:
            case ast.Expression(body=body):
                return ev(body)
            case ast.Constant(value=v) if isinstance(v, int | float | str):
                return v
            case ast.Name(id=name):
                if name not in env:
                    raise NameError(f"unknown variable {name!r} in {expr!r}")
                return env[name]
            case ast.BinOp(left=l, op=op, right=r) if type(op) in _BINOPS:
                left, right = ev(l), ev(r)
                if not isinstance(left, int | float) or not isinstance(right, int | float):
                    raise ValueError("Case arithmetic requires numeric operands.")
                if isinstance(op, ast.Pow):
                    if abs(right) > 1024:
                        raise ValueError("Case expression exponent is too large.")
                    if (isinstance(left, int) and isinstance(right, int) and right > 0
                            and max(0, abs(left).bit_length() - 1) * right > 1024):
                        raise ValueError("Case expression power is too large.")
                return _BINOPS[type(op)](left, right)
            case ast.UnaryOp(op=ast.USub(), operand=o):
                return -ev(o)
            case ast.UnaryOp(op=ast.UAdd(), operand=o):
                return ev(o)
            case ast.Compare(left=l, ops=[op], comparators=[r]) if type(op) in _CMPOPS:
                return _CMPOPS[type(op)](ev(l), ev(r))
            case ast.IfExp(test=t, body=b, orelse=o):
                return ev(b) if ev(t) else ev(o)
            case ast.Call(func=ast.Name(id=fn), args=args, keywords=[]) if fn in _FUNCS:
                return _FUNCS[fn](*(ev(a) for a in args))
        raise ValueError(f"unsupported expression {expr!r}")

    if len(expr) > 4096:
        raise ValueError("Case expression is too long.")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as error:
        raise ValueError(f"Invalid case expression {expr!r}") from error
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise ValueError("Case expression is too complex.")
    return ev(tree)


_FORMATTERS = {
    "money": fmt_money, "pct": fmt_pct, "num": fmt_num, "big": fmt_big,
    "int": lambda x: f"{round(x):,}",
}
_PLACEHOLDER = re.compile(r"\{([^{}|]+)(?:\|(\w+))?\}")
_SOFT_BREAK = re.compile(r"(?<!\n)\n(?!\n)")


def prose(text: str) -> str:
    return _SOFT_BREAK.sub(" ", text.strip())


def render(text: str, env: dict) -> str:
    def sub(m: re.Match) -> str:
        value = safe_eval(m.group(1), env)
        fmt = m.group(2)
        if fmt:
            return _FORMATTERS[fmt](value)
        if isinstance(value, int | float):
            decimals = max(2, 2 - math.floor(math.log10(abs(value)))) if 0 < abs(value) < 1 else 2
            return fmt_num(value, decimals)
        return str(value)

    return _PLACEHOLDER.sub(sub, text)


def _string(value, label: str, *, empty: bool = False) -> None:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{label} must be a {'string' if empty else 'nonempty string'}.")


def _number(value, label: str, *, nonnegative: bool = False) -> float:
    if (isinstance(value, bool) or not isinstance(value, int | float)
            or not math.isfinite(value) or (nonnegative and value < 0)):
        raise ValueError(f"{label} must be a finite {'nonnegative ' if nonnegative else ''}number.")
    return float(value)


def validate_template(raw) -> None:
    """Check every authored field, including alternatives not chosen by a seed."""
    if not isinstance(raw, dict):
        raise ValueError("Case template must be a mapping.")
    for key in ("id", "title", "archetype", "prompt"):
        _string(raw.get(key), f"Case {key}")
    for key in ("summary", "model_structure", "model_recommendation"):
        _string(raw.get(key, ""), f"Case {key}", empty=True)
    minutes = raw.get("minutes", 25)
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
        raise ValueError("Case minutes must be a positive integer.")
    variants = raw.get("variants", [{}])
    if not isinstance(variants, list) or not variants:
        raise ValueError("Case variants must be a nonempty list.")
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError("Each case variant must be a mapping.")
        for name, value in variant.items():
            _string(name, "Case variable name")
            if isinstance(value, str):
                _string(value, "Case variant value")
            else:
                _number(value, "Case variant value")
    params, derived = raw.get("params", {}), raw.get("derived", {})
    if not isinstance(params, dict) or not isinstance(derived, dict):
        raise ValueError("Case params and derived must be mappings.")
    for name, values in params.items():
        _string(name, "Case parameter name")
        if not isinstance(values, list) or not values:
            raise ValueError("Case parameters need nonempty candidate lists.")
        for value in values:
            if isinstance(value, str):
                _string(value, "Case parameter value")
            else:
                _number(value, "Case parameter value")
    for name, expression in derived.items():
        _string(name, "Derived variable name")
        if isinstance(expression, str):
            _string(expression, "Derived expression")
        else:
            _number(expression, "Derived expression")
    questions, data = raw.get("questions", []), raw.get("data", [])
    if not isinstance(questions, list) or not isinstance(data, list):
        raise ValueError("Case questions and data must be lists.")
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("Each case question must be a mapping.")
        for key in ("prompt", "skill"):
            _string(question.get(key), f"Case question {key}")
        for key in ("unit", "solution"):
            _string(question.get(key, ""), f"Case question {key}", empty=True)
        answer = question.get("answer")
        if isinstance(answer, str):
            _string(answer, "Case question answer")
        else:
            _number(answer, "Case question answer")
        for key in ("tolerance", "abs_tolerance"):
            if key in question:
                _number(question[key], f"Case question {key}", nonnegative=True)
    for block in data:
        if not isinstance(block, dict):
            raise ValueError("Each case data block must be a mapping.")
        for key in ("category", "title"):
            _string(block.get(key), f"Case data {key}")
        _string(block.get("text", ""), "Case data text", empty=True)
        if "table" in block:
            table = block["table"]
            if not isinstance(table, dict):
                raise ValueError("Case table must be a mapping.")
            headers, rows = table.get("headers"), table.get("rows")
            if not isinstance(headers, list) or not headers or not isinstance(rows, list):
                raise ValueError("Case tables need headers and rows.")
            for header in headers:
                if isinstance(header, str):
                    _string(header, "Case table header", empty=True)
                else:
                    _number(header, "Case table header")
            for row in rows:
                if not isinstance(row, list) or len(row) != len(headers):
                    raise ValueError("Case table rows must match the headers.")
                for cell in row:
                    if isinstance(cell, str):
                        _string(cell, "Case table cell", empty=True)
                    elif not isinstance(cell, bool):
                        _number(cell, "Case table cell")
        if "chart" in block:
            chart = block["chart"]
            if not isinstance(chart, dict) or chart.get("type", "bar") not in ("bar", "line"):
                raise ValueError("Case chart must be a bar or line chart mapping.")
            _string(chart.get("title"), "Case chart title")
            _string(chart.get("unit", ""), "Case chart unit", empty=True)
            labels, series = chart.get("labels"), chart.get("series")
            if not isinstance(labels, list) or not labels or not isinstance(series, list) or not series:
                raise ValueError("Case charts need labels and series.")
            for label in labels:
                _string(label, "Case chart label")
            for entry in series:
                if not isinstance(entry, dict):
                    raise ValueError("Case chart series must be mappings.")
                _string(entry.get("name"), "Case chart series name")
                values = entry.get("values")
                if not isinstance(values, list) or len(values) != len(labels):
                    raise ValueError("Case chart values must match the labels.")
                for value in values:
                    if isinstance(value, str):
                        _string(value, "Case chart expression")
                    else:
                        _number(value, "Case chart value")
    rubric = raw.get("rubric_skills", {})
    if not isinstance(rubric, dict):
        raise ValueError("Case rubric skills must be a mapping.")
    for key, skills in rubric.items():
        _string(key, "Case rubric key")
        if not isinstance(skills, list):
            raise ValueError("Case rubric skills must be lists.")
        for skill in skills:
            _string(skill, "Case rubric skill")
    case_skills = raw.get("case_skills", [])
    if not isinstance(case_skills, list):
        raise ValueError("Case skills must be a list.")
    for skill in case_skills:
        _string(skill, "Case skill")


@dataclass
class CaseTemplate:
    id: str
    title: str
    archetype: str
    summary: str
    minutes: int
    raw: dict

    def difficulty(self, graph) -> str:
        """Classify by prerequisite depth and breadth of numerically tested skills."""
        skill_ids = {question["skill"] for question in self.raw.get("questions", [])}
        if not skill_ids:
            return "beginner"
        max_depth = max(graph.depth[skill_id] for skill_id in skill_ids)
        categories = {graph.skills[skill_id].category for skill_id in skill_ids}
        score = max_depth + 0.5 * (len(categories) - 1) + 0.2 * min(len(skill_ids) - 1, 8)
        if score <= 3:
            return "beginner"
        if score <= 6.5:
            return "intermediate"
        return "hard"

    def instantiate(self, seed: int) -> dict:
        rng = random.Random(seed)
        raw = self.raw
        env: dict = dict(rng.choice(raw.get("variants") or [{}]))
        for name, spec in (raw.get("params") or {}).items():
            env[name] = rng.choice(spec)
        for name, expr in (raw.get("derived") or {}).items():
            env[name] = safe_eval(str(expr), env)

        def data_block(block: dict) -> dict:
            out = {"category": block["category"], "title": render(block["title"], env),
                   "text": prose(render(block.get("text", ""), env))}
            if "table" in block:
                t = block["table"]
                out["table"] = {"headers": t["headers"],
                                "rows": [[render(str(c), env) for c in row] for row in t["rows"]]}
            if "chart" in block:
                c = block["chart"]
                out["chart"] = {
                    "type": c.get("type", "bar"), "title": render(c["title"], env),
                    "unit": c.get("unit", ""), "labels": c["labels"],
                    "series": [{"name": s["name"],
                                "values": [_number(safe_eval(str(v), env), "Case chart value")
                                           for v in s["values"]]}
                               for s in c["series"]],
                }
            return out

        questions = []
        for q in raw.get("questions", []):
            questions.append({
                "prompt": render(q["prompt"], env),
                "answer": _number(safe_eval(str(q["answer"]), env), "Case question answer"),
                "unit": q.get("unit", ""),
                "tolerance": q.get("tolerance", 0.03),
                "abs_tolerance": q.get("abs_tolerance", 0.05 if q.get("unit") == "%" else 0.0),
                "skill": q["skill"],
                "solution": render(q.get("solution", ""), env).strip(),
            })
        return {
            "id": self.id, "title": self.title, "archetype": self.archetype,
            "minutes": self.minutes, "seed": seed,
            "prompt": prose(render(raw["prompt"], env)),
            "data": [data_block(b) for b in raw.get("data", [])],
            "questions": questions,
            "modelStructure": render(raw.get("model_structure", ""), env).rstrip(),
            "modelRecommendation": prose(render(raw.get("model_recommendation", ""), env)),
            "rubricSkills": raw.get("rubric_skills", {}),
            "caseSkills": sorted({
                *raw.get("case_skills", []),
                *(question["skill"] for question in raw.get("questions", [])),
                *(sid for skills in raw.get("rubric_skills", {}).values() for sid in skills),
            }),
        }


@cache
def load_templates(directory: Path | None = None) -> dict[str, CaseTemplate]:
    directory = directory or CONTENT_DIR / "cases"
    out = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = safe_load(path.read_text(encoding="utf-8"))
        validate_template(raw)
        if raw["id"] in out:
            raise ValueError(f"Duplicate case ID: {raw['id']}")
        out[raw["id"]] = CaseTemplate(raw["id"], raw["title"], raw["archetype"],
                                      raw.get("summary", ""), raw.get("minutes", 25), raw)
    return out
