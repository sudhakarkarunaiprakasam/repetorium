from io import StringIO

import pytest
import yaml

from repetorium.yaml_io import safe_dump, safe_load


def test_safe_load_matches_pyyaml_safe_loader_for_text_and_streams():
    source = "created: 2026-01-02\nitems: [first, second]\n"
    expected = yaml.safe_load(source)

    assert safe_load(source) == expected
    assert safe_load(StringIO(source)) == expected


def test_safe_load_rejects_python_object_constructors():
    with pytest.raises(yaml.YAMLError):
        safe_load("!!python/object/new:complex ['1']")


def test_safe_dump_round_trips_safe_values():
    value = {"name": "CFA — Level I", "skills": ["quant", "ethics"]}

    assert yaml.safe_load(safe_dump(value, sort_keys=False, allow_unicode=True)) == value
