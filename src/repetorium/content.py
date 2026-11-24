"""Validation for Repetorium content libraries."""

import re
from copy import deepcopy
from math import isfinite
from pathlib import Path

import yaml

from repetorium.cases.templates import load_templates
from repetorium.content_blocks import validate_content_block
from repetorium.engine.graph import KnowledgeGraph
from repetorium.generators import generate
from repetorium.generators.banks import load_bank
from repetorium.yaml_io import safe_load

IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}\Z")


class ContentError(ValueError):
    pass


def text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"{label} must be a nonempty string.")
    return value


def identifier(value, label: str) -> str:
    value = text(value, label)
    if not IDENTIFIER.fullmatch(value):
        raise ContentError(f"{label} must use letters, numbers, dots, underscores or hyphens (max 80).")
    return value


def read_manifest(directory: Path) -> dict:
    try:
        path = directory / "library.yaml"
        personal = path.exists()
        manifest = safe_load(
            (path if personal else directory / "pack.yaml").read_text(encoding="utf-8")
        )
        if (not isinstance(manifest, dict) or type(manifest.get("format")) is not int
                or manifest["format"] != 1):
            raise ContentError("Content manifest must declare format: 1.")
        identifier(manifest.get("id"), "Library ID")
        for key in (("name", "version") if personal else ("name", "version", "license")):
            text(manifest.get(key), f"Library {key}")
        sources = manifest.get("sources", [])
        if not isinstance(sources, list) or any(not isinstance(s, str) or not s.strip() for s in sources):
            raise ContentError("Library sources must be a list of nonempty strings.")
        return manifest
    except (OSError, ValueError, yaml.YAMLError) as error:
        if isinstance(error, ContentError):
            raise
        raise ContentError(f"Invalid library manifest: {error}") from error


def validate_library(directory: Path) -> tuple[dict, KnowledgeGraph]:
    # A reload must validate the current files, not previously cached exercises.
    load_bank.cache_clear()
    load_templates.cache_clear()
    try:
        manifest = read_manifest(directory)
        graph = KnowledgeGraph.load(directory / "graph")
        if not graph.skills:
            raise ContentError("The knowledge library must contain at least one skill.")
        practice_banks = {}
        validated_banks = set()
        invalid_banks = set()
        bank_errors = []
        for skill in graph.skills.values():
            identifier(skill.id, "Skill ID")
            text(skill.title, f"{skill.id} title")
            if skill.guide:
                KnowledgeGraph.validate_guide(skill.id, skill.guide)
            if not isinstance(skill.params, dict) or any(
                key in skill.params for key in ("_content_dir", "_banks")
            ):
                raise ContentError(f"{skill.id}: invalid or reserved params.")
            if not isinstance(skill.xp, int) or isinstance(skill.xp, bool) or skill.xp < 0:
                raise ContentError(f"{skill.id}: reward points must be a nonnegative integer.")
            if skill.generator.startswith("bank_"):
                bank_name = identifier(skill.params.get("bank"), f"{skill.id} bank")
                bank_key = (bank_name, skill.generator)
                if bank_key not in validated_banks:
                    validated_banks.add(bank_key)
                    try:
                        bank = load_bank(bank_name, directory)
                        validate_bank(bank, skill.generator)
                        practice_banks[bank_name] = deepcopy(bank)
                    except (ContentError, OSError, TypeError, KeyError, IndexError,
                            AttributeError, ArithmeticError, yaml.YAMLError) as error:
                        invalid_banks.add(bank_key)
                        bank_errors.append(
                            f"banks/{bank_name}.yaml ({skill.id}, {skill.generator}): {error}"
                        )
                if bank_key in invalid_banks:
                    continue
            for difficulty in (1, 2, 3):
                item = generate(skill.generator, skill.id, 42, difficulty,
                                {**skill.params, "_content_dir": directory})
                text(item.prompt, f"{skill.id} exercise prompt")
                text(item.answer_text(), f"{skill.id} exercise answer")
        if bank_errors:
            details = "\n".join(f"- {error}" for error in bank_errors)
            raise ContentError(f"Invalid practice banks:\n{details}")
        from repetorium.assessments import load_mock_tests

        load_mock_tests(directory, set(graph.skills))
        templates = load_templates(directory / "cases")
        for template in templates.values():
            identifier(template.id, "Case ID")
            case = template.instantiate(42)
            references = [q["skill"] for q in case["questions"]]
            references += [sid for ids in template.raw.get("rubric_skills", {}).values() for sid in ids]
            references += template.raw.get("case_skills", [])
            if any(sid not in graph.skills for sid in references):
                raise ContentError(f"Case {template.id} references unknown skills.")
        graph.practice_banks = practice_banks
        graph.case_templates = deepcopy(templates)
        return manifest, graph
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError,
            NameError, ArithmeticError, SyntaxError, yaml.YAMLError) as error:
        if isinstance(error, ContentError):
            raise
        raise ContentError(f"Invalid knowledge library: {error}") from error
    finally:
        load_bank.cache_clear()
        load_templates.cache_clear()


def validate_bank(bank, generator: str) -> None:
    if not isinstance(bank, dict):
        raise ContentError("Practice bank must be a mapping.")
    entries = bank.get("items" if generator == "bank_classify" else "entries")
    if not isinstance(entries, list) or not entries:
        raise ContentError("Practice bank needs nonempty entries/items.")
    if generator == "bank_classify":
        text(bank.get("prompt"), "Classification prompt")
        categories = bank.get("categories")
        if not isinstance(categories, list) or len(categories) < 2:
            raise ContentError("Classification bank needs at least two categories.")
        for category in categories:
            text(category, "Category")
        if len(set(categories)) != len(categories):
            raise ContentError("Classification categories must be distinct.")
    errors = []
    assigned_difficulties = set()
    has_untagged_entry = False
    for index, entry in enumerate(entries, start=1):
        if isinstance(entry, dict) and "difficulty" in entry:
            difficulty = entry["difficulty"]
            if (not isinstance(difficulty, bool) and isinstance(difficulty, int)
                    and difficulty in (1, 2, 3)):
                assigned_difficulties.add(difficulty)
        else:
            has_untagged_entry = True
        location = f"entry {index}"
        if isinstance(entry, dict) and isinstance(entry.get("prompt"), str):
            location += f" ({entry['prompt'][:80]!r})"
        try:
            _validate_bank_entry(entry, bank, generator)
        except (ContentError, TypeError, KeyError, IndexError, AttributeError) as error:
            errors.append(f"{location}: {error}")

    missing_difficulties = {1, 2, 3} - assigned_difficulties
    if missing_difficulties and not has_untagged_entry:
        labels = {1: "Easy", 2: "Medium", 3: "Hard"}
        missing_labels = ", ".join(labels[level] for level in sorted(missing_difficulties))
        errors.append(
            "Difficulty tags leave no questions for "
            f"{missing_labels}; add tagged questions at those levels or leave an "
            "untagged question as a fallback."
        )
    if errors:
        raise ContentError("Practice bank validation failed:\n" + "\n".join(
            f"- {error}" for error in errors
        ))


def _validate_bank_entry(entry: object, bank: dict, generator: str) -> None:
    if not isinstance(entry, dict):
        raise ContentError("Each practice entry must be a mapping.")
    if "difficulty" in entry and (
        isinstance(entry["difficulty"], bool)
        or not isinstance(entry["difficulty"], int)
        or entry["difficulty"] not in (1, 2, 3)
    ):
        raise ContentError("Practice difficulty must be 1 (easy), 2 (medium), or 3 (hard).")
    if "explain" in entry:
        text(entry["explain"], "Practice explanation")
    else:
        raise ContentError("Every practice question needs an explanation.")
    if "follow_up_prompt" in entry:
        text(entry["follow_up_prompt"], "Practice follow-up prompt")
    if "exhibits" in entry:
        exhibits = entry["exhibits"]
        if not isinstance(exhibits, list):
            raise ContentError("Practice exhibits must be a list of content blocks.")
        for index, exhibit in enumerate(exhibits):
            try:
                validate_content_block(exhibit, f"Practice exhibit {index + 1}")
            except ValueError as error:
                raise ContentError(str(error)) from error
    if generator == "bank_classify":
        text(entry.get("text"), "Classification item")
        if entry.get("category") not in bank["categories"]:
            raise ContentError("Classification item has an unknown category.")
        return
    if generator == "bank_mixed":
        validate_mixed_entry(entry)
        return
    text(entry.get("prompt"), "Practice prompt")
    if generator == "bank_choice":
        if "type" in entry and entry["type"] != "choice":
            raise ContentError(
                f"bank_choice only accepts choice items, not {entry['type']!r}; "
                "use bank_mixed for multiple response types."
            )
        options = entry.get("distractors")
        label, minimum = "Choice distractors", 1
    elif generator == "bank_order":
        if "type" in entry and entry["type"] != "order":
            raise ContentError(
                f"bank_order only accepts order items, not {entry['type']!r}; "
                "use bank_mixed for multiple response types."
            )
        options = entry.get("steps")
        label, minimum = "Ordered steps", 2
    else:
        raise ContentError(f"Unsupported practice-bank generator {generator!r}.")
    _validate_distinct_options(options, label, minimum)
    if generator == "bank_choice" and text(entry.get("correct"), "Correct answer") in options:
        raise ContentError("Correct answer cannot also be a distractor.")


def validate_mixed_entry(entry: dict) -> None:
    prompt = text(entry.get("prompt"), "Practice prompt")
    kind = entry.get("type")
    if kind is None:
        raise ContentError(
            "Missing required 'type'; every bank_mixed entry must declare its response type."
        )
    if kind == "choice":
        _validate_distinct_options(entry.get("distractors"), "Choice distractors", 1)
        if text(entry.get("correct"), "Correct answer") in entry["distractors"]:
            raise ContentError("Correct answer cannot also be a distractor.")
    elif kind == "numeric":
        _validate_finite_number(entry.get("answer"), "Numeric answer")
        for key in ("unit",):
            if key in entry and not isinstance(entry[key], str):
                raise ContentError(f"{key} must be a string.")
        for key in ("tolerance", "abs_tolerance"):
            if key in entry:
                _validate_finite_number(entry[key], key)
                if entry[key] < 0:
                    raise ContentError(f"{key} cannot be negative.")
    elif kind == "multi_select":
        correct = entry.get("correct")
        if not isinstance(correct, list) or not correct:
            raise ContentError("Multi-select questions need at least one correct option.")
        for option in correct:
            text(option, "Correct option")
        distractors = entry.get("distractors")
        _validate_distinct_options(distractors, "Multi-select distractors", 1)
        all_options = [*correct, *distractors]
        if len(set(all_options)) != len(all_options):
            raise ContentError("Multi-select options must be distinct.")
    elif kind == "matching":
        pairs = entry.get("pairs")
        if not isinstance(pairs, list) or len(pairs) < 2:
            raise ContentError("Matching questions need at least two pairs.")
        left, right = [], []
        for pair in pairs:
            if not isinstance(pair, dict):
                raise ContentError("Each matching pair must be a mapping.")
            left.append(text(pair.get("left"), "Matching prompt"))
            right.append(text(pair.get("right"), "Matching answer"))
        if len(set(left)) != len(left) or len(set(right)) != len(right):
            raise ContentError("Matching prompts and answers must each be distinct.")
    elif kind == "true_false":
        if type(entry.get("answer")) is not bool:
            raise ContentError("True/false answers must be booleans.")
    elif kind == "order":
        _validate_distinct_options(entry.get("steps"), "Ordered steps", 2)
    else:
        raise ContentError(
            f"{prompt}: unsupported mixed-bank question type {kind!r}; "
            "use a documented type such as choice, numeric, order, matching, multi_select, "
            "or true_false."
        )


def _validate_distinct_options(options: object, label: str, minimum: int) -> None:
    if not isinstance(options, list) or len(options) < minimum:
        raise ContentError(f"{label} need at least {minimum} distinct options.")
    for option in options:
        text(option, label)
    if len(set(options)) != len(options):
        raise ContentError(f"{label} must be distinct.")


def _validate_finite_number(value: object, label: str) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or isinstance(value, float) and not isfinite(value)):
        raise ContentError(f"{label} must be a finite number.")
