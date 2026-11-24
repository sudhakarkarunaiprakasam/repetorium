"""Validation for display-only lesson and question content blocks."""

from math import isfinite


def validate_content_block(block: object, label: str) -> None:
    if not isinstance(block, dict):
        raise ValueError(f"{label} must be a typed content block.")
    kind = block.get("type")
    if kind == "text":
        _required_text(block.get("text"), f"{label} text")
    elif kind == "math":
        _required_text(block.get("content"), f"{label} math content")
    elif kind == "code":
        _required_text(block.get("language"), f"{label} code language")
        _required_text(block.get("code"), f"{label} code")
    elif kind == "table":
        _validate_table(block, label)
    elif kind == "chart":
        _validate_chart(block.get("chart"), label)
    else:
        raise ValueError(f"{label} type must be text, math, code, table, or chart.")


def _required_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")


def _validate_table(table: dict, label: str) -> None:
    headers, rows = table.get("headers"), table.get("rows")
    if (not isinstance(headers, list) or not headers
            or any(not isinstance(value, str) or not value.strip() for value in headers)):
        raise ValueError(f"{label} table needs nonempty string headers.")
    if (not isinstance(rows, list) or not rows
            or any(not isinstance(row, list) or len(row) != len(headers) for row in rows)):
        raise ValueError(f"{label} table rows must match the header count.")
    for row in rows:
        for value in row:
            if (isinstance(value, bool) or not isinstance(value, (str, int, float))
                    or (isinstance(value, float) and not isfinite(value))):
                raise ValueError(f"{label} table cells must be text or finite numbers.")
    if "caption" in table:
        _required_text(table["caption"], f"{label} table caption")


def _validate_chart(chart: object, label: str) -> None:
    if not isinstance(chart, dict) or chart.get("type") not in ("bar", "line", "scatter"):
        raise ValueError(f"{label} chart type must be bar, line, or scatter.")
    _required_text(chart.get("title"), f"{label} chart title")
    labels, series = chart.get("labels"), chart.get("series")
    if (not isinstance(labels, list) or not labels
            or any(not isinstance(value, str) or not value.strip() for value in labels)):
        raise ValueError(f"{label} chart needs nonempty string labels.")
    if chart["type"] == "scatter":
        try:
            if any(not isfinite(float(value)) for value in labels):
                raise ValueError
        except ValueError as error:
            raise ValueError(f"{label} scatter chart labels must be numeric.") from error
    if not isinstance(series, list) or not series:
        raise ValueError(f"{label} chart needs at least one series.")
    for entry in series:
        if not isinstance(entry, dict):
            raise ValueError(f"{label} chart series must be mappings.")
        _required_text(entry.get("name"), f"{label} chart series name")
        values = entry.get("values")
        if (not isinstance(values, list) or len(values) != len(labels)
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not isfinite(value) for value in values)):
            raise ValueError(f"{label} chart values must be finite numbers matching its labels.")
