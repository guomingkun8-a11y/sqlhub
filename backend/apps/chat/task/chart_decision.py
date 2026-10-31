"""Validate model-selected charts against the executed query result."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

CHART_TYPES = {"bar", "column", "line", "pie"}


def _number(value: Any) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def decide_chart(
    chart: dict[str, Any] | str | None,
    result: dict[str, Any],
    desired_display: str = "auto",
    requested_type: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Return a renderable chart and an optional reason code for table fallback.

    ``result`` is the executed query's ``fields``, ``fields_info`` and ``data``.
    Reason codes are internal; callers translate them before showing users.
    """
    if isinstance(chart, str):
        try:
            chart = json.loads(chart)
        except json.JSONDecodeError:
            chart = None
    fields = result.get("fields") or []
    fields = list(dict.fromkeys(field for field in fields if isinstance(field, str)))
    title = chart.get("title") if isinstance(chart, dict) else None
    title = title if isinstance(title, str) else ""
    table = {
        "type": "table",
        "title": title,
        "columns": [{"name": field, "value": field} for field in fields],
    }
    if desired_display == "table":
        return table, None
    if (
        not isinstance(chart, dict)
        or not isinstance(chart.get("type"), str)
        or chart["type"] not in CHART_TYPES | {"table"}
    ):
        return table, "invalid_chart"
    if chart["type"] == "table":
        return table, "chart_unavailable" if desired_display == "chart" else None
    if requested_type and (
        not isinstance(requested_type, str) or requested_type not in CHART_TYPES
    ):
        return table, "invalid_chart"

    rows = result.get("data") or []
    if not isinstance(rows, list) or not rows:
        return table, "empty_result"
    if not fields:
        return table, "invalid_chart_field"

    # Match a model's lower-cased alias only when it identifies one real field.
    names: dict[str, str | None] = {}
    for field in fields:
        key = field.casefold()
        names[key] = field if key not in names else None

    def axis_field(item: Any) -> dict[str, str] | None:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            return None
        field = names.get(item["value"].casefold())
        if field is None:
            return None
        name = item.get("name")
        return {
            "name": name if isinstance(name, str) and name else field,
            "value": field,
        }

    axis = chart.get("axis")
    if not isinstance(axis, dict):
        return table, "invalid_chart_axis"
    y_raw = axis.get("y")
    y_items = y_raw if isinstance(y_raw, list) else [y_raw]
    if not y_items or any(axis_field(raw) is None for raw in y_items):
        return table, "invalid_chart_field"
    y = [axis_field(raw) for raw in y_items]
    metrics = [item["value"] for item in y if item is not None]
    if len(set(metrics)) != len(metrics):
        return table, "invalid_chart_axis"

    info = result.get("fields_info") or []
    numeric_fields = {
        item["name"].casefold()
        for item in info
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item.get("is_numeric") is True
    }
    metric_numbers: dict[str, list[Decimal]] = {}
    for metric in metrics:
        values = [row.get(metric) for row in rows if isinstance(row, dict)]
        present = [value for value in values if value is not None and value != ""]
        numbers = [_number(value) for value in present]
        if not numbers or any(number is None for number in numbers):
            return table, "missing_numeric_metric"
        if metric.casefold() not in numeric_fields and any(
            isinstance(value, str) for value in present
        ):
            return table, "missing_numeric_metric"
        metric_numbers[metric] = [number for number in numbers if number is not None]

    x = axis_field(axis["x"]) if axis.get("x") is not None else None
    series = axis_field(axis["series"]) if axis.get("series") is not None else None
    if (axis.get("x") is not None and x is None) or (
        axis.get("series") is not None and series is None
    ):
        return table, "invalid_chart_field"

    chart_type = requested_type or chart["type"]
    if chart_type == "pie":
        if series is None and chart["type"] != "pie":
            series = x
        if series is None or series["value"] in metrics or len(metrics) != 1:
            return table, "missing_dimension"
        if requested_type == "pie" and x and x["value"] != series["value"]:
            return table, "invalid_chart_axis"
        if not any(
            isinstance(row, dict) and row.get(series["value"]) is not None
            for row in rows
        ):
            return table, "missing_dimension"
        if any(value < 0 for value in metric_numbers[metrics[0]]):
            return table, "pie_requires_nonnegative"
        if sum(metric_numbers[metrics[0]]) == 0:
            return table, "pie_requires_positive_total"
        return {
            "type": "pie",
            "title": title,
            "axis": {"y": y[0], "series": series},
        }, None

    if x is None and chart["type"] == "pie":
        x, series = series, None
    if x is None or x["value"] in metrics:
        return table, "missing_dimension"
    if not any(
        isinstance(row, dict) and row.get(x["value"]) is not None for row in rows
    ):
        return table, "missing_dimension"
    if series and (series["value"] in metrics or len(metrics) != 1):
        return table, "invalid_chart_axis"

    chart_axis: dict[str, Any] = {"x": x, "y": y}
    if series:
        chart_axis["series"] = series
    if len(metrics) > 1:
        quota = axis.get("multi-quota")
        quota_values = quota.get("value") if isinstance(quota, dict) else None
        if (
            not isinstance(quota_values, list)
            or not all(isinstance(value, str) for value in quota_values)
            or set(quota_values) != set(metrics)
        ):
            return table, "invalid_chart_axis"
        quota_name = quota.get("name")
        chart_axis["multi-quota"] = {
            "name": quota_name if isinstance(quota_name, str) else "",
            "value": metrics,
        }
    return {"type": chart_type, "title": title, "axis": chart_axis}, None
