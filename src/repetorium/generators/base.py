"""Item model, generator registry, number formatting/parsing and answer checking."""

import math
import random
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Item:
    prompt: str
    kind: str  # numeric | choice | order | multi_select | matching | true_false
    answer: Any
    solution: str
    choices: list[str] = field(default_factory=list)
    unit: str = ""
    tolerance: float = 0.02
    abs_tolerance: float = 0.0
    chart: dict | None = None
    table: dict | None = None
    exhibits: list[dict] = field(default_factory=list)
    follow_up_prompt: str = ""
    skill_id: str = ""
    seed: int = 0
    difficulty: int = 1
    prompts: list[str] = field(default_factory=list)

    def public(self) -> dict:
        """Item data safe to show before answering."""
        data = asdict(self)
        for key in ("answer", "solution", "tolerance", "abs_tolerance", "follow_up_prompt"):
            data.pop(key)
        data["unitHint"] = unit_hint(self.unit) if self.kind == "numeric" else ""
        return data

    def answer_text(self) -> str:
        if self.kind == "numeric":
            if (self.tolerance == 0 and self.abs_tolerance == 0
                    and self.unit not in ("$", "$M", "%")
                    and float(self.answer).is_integer()):
                return f"{int(self.answer):,} {self.unit}".strip()
            displayed = format_answer(self.answer, self.unit)
            if check(self, displayed):
                return displayed
            # A rounded model answer must still satisfy its own grading tolerance.
            decimals = max(0, 17 - math.floor(math.log10(abs(self.answer)))) if self.answer else 2
            for precision in range(2, decimals + 1):
                number = f"{self.answer:,.{precision}f}".rstrip("0").rstrip(".")
                if self.unit == "$":
                    displayed = f"${number}"
                elif self.unit in ("$K", "$M", "$B", "$T"):
                    displayed = f"${number}{self.unit[1:]}"
                else:
                    displayed = f"{number}{'%' if self.unit == '%' else ' ' + self.unit}".strip()
                if check(self, displayed):
                    return displayed
            return displayed
        if self.kind == "choice":
            return self.choices[self.answer]
        if self.kind == "true_false":
            return self.choices[self.answer]
        if self.kind == "multi_select":
            return " · ".join(self.choices[i] for i in self.answer)
        if self.kind == "matching":
            return "\n".join(
                f"{prompt} → {self.choices[index]}"
                for prompt, index in zip(self.prompts, self.answer, strict=True)
            )
        return " → ".join(self.choices[i] for i in self.answer)


GeneratorFn = Callable[[random.Random, int, dict], Item]
GENERATORS: dict[str, GeneratorFn] = {}


def generator(name: str) -> Callable[[GeneratorFn], GeneratorFn]:
    def register(fn: GeneratorFn) -> GeneratorFn:
        GENERATORS[name] = fn
        return fn

    return register


def generate(gen_id: str, skill_id: str, seed: int, difficulty: int, params: dict) -> Item:
    from repetorium import generators  # noqa: F401  ensures all generator modules are registered

    item = GENERATORS[gen_id](random.Random(seed), max(1, min(3, difficulty)), params or {})
    item.skill_id = skill_id
    item.seed = seed
    item.difficulty = difficulty
    return item


# ---------- formatting ----------

def fmt_num(x: float, decimals: int = 2) -> str:
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.{decimals}f}".rstrip("0").rstrip(".")


def fmt_big(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= div:
            return f"{sign}{fmt_num(x / div)}{suffix}"
    return sign + fmt_num(x)


def fmt_money(x: float) -> str:
    s = fmt_big(x)
    return "-$" + s[1:] if s.startswith("-") else "$" + s


def fmt_pct(x: float, decimals: int = 1) -> str:
    return f"{fmt_num(x, decimals)}%"


def format_answer(value: float, unit: str) -> str:
    if unit == "$":
        return fmt_money(value)
    if unit in ("$K", "$M", "$B", "$T"):
        return f"${fmt_num(value)}{unit[1:]}"
    if unit == "%":
        return fmt_pct(value)
    text = fmt_big(value) if abs(value) >= 1e4 else fmt_num(value)
    return f"{text} {unit}".strip()


# ---------- parsing & checking ----------

_SUFFIXES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mm": 1e6, "mn": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9,
    "t": 1e12, "tn": 1e12, "trillion": 1e12,
}
_NUM_RE = re.compile(
    r"^(-?\d*\.?\d+)(?:\s*(k|m|mm|mn|b|bn|t|tn|thousand|million|billion|trillion)(?![a-z]))?"
    r"\s*[a-z /]*$"
)


def parse_number(text: str) -> float | None:
    s = text.strip().lower().replace(",", "").replace("$", "").replace("%", "")
    m = _NUM_RE.match(s)
    if not m:
        return None
    value = float(m.group(1))
    if m.group(2):
        value *= _SUFFIXES[m.group(2)]
    return value if math.isfinite(value) else None


def interpret(text: str, unit: str) -> float | None:
    scaled_money = unit in ("$K", "$M", "$B", "$T")
    response = text.strip()
    if unit and not scaled_money and response.lower().endswith(unit.lower()):
        response = response[:-len(unit)].strip()
    value = parse_number(response)
    if value is not None:
        match = _NUM_RE.match(response.lower().replace(",", "").replace("$", "").replace("%", ""))
        suffix = match.group(2) if match else None
        if scaled_money:
            scale = _SUFFIXES[unit[1:].lower()]
            if abs(value) >= scale / 10 or suffix:
                value /= scale
        elif unit.split() and unit.split()[0].lower() in _SUFFIXES and suffix:
            value /= _SUFFIXES[unit.split()[0].lower()]
    return value


def unit_hint(unit: str) -> str:
    if unit == "$":
        return "Answer in dollars. Use K, M, B or T for scale, e.g. 450K, 1.8B"
    if unit in ("$K", "$M", "$B", "$T"):
        scale = {"$K": "thousands", "$M": "millions", "$B": "billions", "$T": "trillions"}[unit]
        return f"Answer in $ {scale}, e.g. 45 (= $45{unit[1:]})"
    if unit == "%":
        return "Answer in percent, e.g. 12.5 (negative for a decline)"
    return f"Answer in {unit}. K, M, B suffixes are accepted" if unit else "Enter a number"


def describe_response(text: str, unit: str) -> str:
    """How a typed answer was read, e.g. '180000000000' -> '$180B'."""
    value = interpret(text, unit)
    return "" if value is None else format_answer(value, unit)


def check(item: Item, response: str) -> bool:
    if item.kind == "numeric":
        value = interpret(response, item.unit)
        if value is None:
            return False
        # Percentages are judged in absolute points; relative slack grows too loose for large %s.
        allowed = item.abs_tolerance if item.unit == "%" else max(
            abs(item.answer) * item.tolerance, item.abs_tolerance)
        return abs(value - item.answer) <= allowed + 1e-9
    if item.kind in ("choice", "true_false"):
        try:
            return int(response) == item.answer
        except ValueError:
            return False
    if item.kind in ("order", "multi_select", "matching"):
        try:
            order = [int(p) for p in response.split(",") if p.strip() != ""]
        except ValueError:
            return False
        if len(order) != len(set(order)):
            return False
        if item.kind == "matching" and len(order) != len(item.prompts):
            return False
        return order == list(item.answer)
    raise ValueError(f"unknown item kind {item.kind}")


# ---------- helpers for generator authors ----------

def choice_item(rng: random.Random, prompt: str, correct: str, distractors: list[str],
                solution: str, **kw: Any) -> Item:
    options = [correct, *distractors]
    rng.shuffle(options)
    return Item(prompt=prompt, kind="choice", answer=options.index(correct),
                choices=options, solution=solution, **kw)


def order_item(rng: random.Random, prompt: str, steps: list[str], solution: str,
               **kw: Any) -> Item:
    display = list(steps)
    while len(display) > 1 and display == steps:
        rng.shuffle(display)
    answer = [display.index(s) for s in steps]
    return Item(prompt=prompt, kind="order", answer=answer, choices=display,
                solution=solution, **kw)


def multi_select_item(rng: random.Random, prompt: str, correct: list[str],
                      distractors: list[str], solution: str, **kw: Any) -> Item:
    options = [*correct, *distractors]
    rng.shuffle(options)
    answer = sorted(options.index(value) for value in correct)
    return Item(prompt=prompt, kind="multi_select", answer=answer,
                choices=options, solution=solution, **kw)


def matching_item(rng: random.Random, prompt: str, pairs: list[dict],
                  solution: str, **kw: Any) -> Item:
    prompts = [pair["left"] for pair in pairs]
    answers = [pair["right"] for pair in pairs]
    display = list(answers)
    rng.shuffle(display)
    answer = [display.index(value) for value in answers]
    return Item(prompt=prompt, kind="matching", answer=answer, choices=display,
                prompts=prompts, solution=solution, **kw)
