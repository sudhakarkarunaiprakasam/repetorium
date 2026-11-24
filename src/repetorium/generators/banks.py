"""Generic generators backed by YAML banks in a content pack."""

import random
from collections import Counter
from functools import cache
from pathlib import Path

from repetorium.generators.base import (
    Item,
    choice_item,
    generator,
    matching_item,
    multi_select_item,
    order_item,
)
from repetorium.paths import CONTENT_DIR
from repetorium.yaml_io import safe_load


@cache
def load_bank(name: str, content_dir: str | Path = CONTENT_DIR) -> dict:
    with open(Path(content_dir) / "banks" / f"{name}.yaml", encoding="utf-8") as f:
        return safe_load(f)


def _bank(params: dict) -> dict:
    if "_banks" in params:
        return params["_banks"][params["bank"]]
    return load_bank(params["bank"], params.get("_content_dir", CONTENT_DIR))


def _at_difficulty(entries: list[dict], difficulty: int, bank_name: str) -> list[dict]:
    assigned = [entry for entry in entries if "difficulty" in entry]
    if not assigned:
        return entries
    matching = [entry for entry in assigned if entry["difficulty"] == difficulty]
    unassigned = [entry for entry in entries if "difficulty" not in entry]
    candidates = matching or unassigned
    if not candidates:
        label = ("easy", "medium", "hard")[difficulty - 1]
        raise ValueError(f"Practice bank {bank_name!r} has no {label} questions.")
    return candidates


@generator("bank_choice")
def bank_choice(rng: random.Random, d: int, p: dict) -> Item:
    entries = _bank(p)["entries"]
    if "skill" in p:
        entries = [entry for entry in entries if entry.get("skill") == p["skill"]]
        if not entries:
            raise ValueError(f"Practice bank {p['bank']!r} has no entries for skill {p['skill']!r}.")
    entries = _at_difficulty(entries, d, p["bank"])
    unseen = [entry for entry in entries if entry["prompt"] not in p.get("_exclude_prompts", ())]
    if unseen:
        entries = unseen
    entry = rng.choice(entries)
    n_distractors = min(len(entry["distractors"]), 1 + d)
    return choice_item(rng, entry["prompt"], entry["correct"],
                       rng.sample(entry["distractors"], n_distractors),
                       solution=entry.get("explain", ""),
                       follow_up_prompt=entry.get("follow_up_prompt", ""),
                       exhibits=entry.get("exhibits", []))


@generator("bank_classify")
def bank_classify(rng: random.Random, d: int, p: dict) -> Item:
    bank = _bank(p)
    excluded = p.get("_exclude_prompts", ())
    items = _at_difficulty(bank["items"], d, p["bank"])
    items = [entry for entry in items
             if f'{bank["prompt"]}\n\n“{entry["text"]}”' not in excluded]
    entry = rng.choice(items or _at_difficulty(bank["items"], d, p["bank"]))
    others = [c for c in bank["categories"] if c != entry["category"]]
    return choice_item(
        rng, f"{bank['prompt']}\n\n“{entry['text']}”", entry["category"],
        rng.sample(others, min(len(others), 1 + d)),
        solution=entry.get("explain", f"This belongs under {entry['category']}."),
        follow_up_prompt=entry.get("follow_up_prompt", ""),
        exhibits=entry.get("exhibits", []),
    )


@generator("bank_order")
def bank_order(rng: random.Random, d: int, p: dict) -> Item:
    entries = _at_difficulty(_bank(p)["entries"], d, p["bank"])
    unseen = [entry for entry in entries if entry["prompt"] not in p.get("_exclude_prompts", ())]
    entry = rng.choice(unseen or entries)
    return order_item(rng, entry["prompt"], entry["steps"], solution=entry.get("explain", ""),
                      follow_up_prompt=entry.get("follow_up_prompt", ""),
                      exhibits=entry.get("exhibits", []))


@generator("bank_mixed")
def bank_mixed(rng: random.Random, d: int, p: dict) -> Item:
    entries = _at_difficulty(_bank(p)["entries"], d, p["bank"])
    recent = Counter(p.get("_recent_kinds", [])[-8:])
    available = sorted({entry["type"] for entry in entries})
    least_used = min(recent[kind] for kind in available)
    preferred = [kind for kind in available if recent[kind] == least_used]
    kind = rng.choice(preferred)
    candidates = [entry for entry in entries if entry["type"] == kind]
    unseen = [entry for entry in candidates if entry["prompt"] not in p.get("_exclude_prompts", ())]
    entry = rng.choice(unseen or candidates)
    common = {
        "solution": entry["explain"],
        "follow_up_prompt": entry.get("follow_up_prompt", ""),
        "exhibits": entry.get("exhibits", []),
    }

    if kind == "choice":
        return choice_item(rng, entry["prompt"], entry["correct"], entry["distractors"],
                           **common)
    if kind == "numeric":
        return Item(
            prompt=entry["prompt"], kind="numeric", answer=entry["answer"],
            unit=entry.get("unit", ""), tolerance=entry.get("tolerance", 0.02),
            abs_tolerance=entry.get("abs_tolerance", 0.0), **common,
        )
    if kind == "order":
        return order_item(rng, entry["prompt"], entry["steps"], **common)
    if kind == "multi_select":
        return multi_select_item(
            rng, entry["prompt"], entry["correct"], entry["distractors"], **common,
        )
    if kind == "matching":
        return matching_item(rng, entry["prompt"], entry["pairs"], **common)
    if kind == "true_false":
        choices = ["True", "False"]
        answer = 0 if entry["answer"] else 1
        return Item(prompt=entry["prompt"], kind="true_false", answer=answer,
                    choices=choices, **common)
    raise ValueError(f"Unknown mixed-bank question type {kind!r}.")
