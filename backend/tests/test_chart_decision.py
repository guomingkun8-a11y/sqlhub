from apps.chat.task.chart_decision import decide_chart

RESULT = {
    "fields": ["status", "count"],
    "fields_info": [
        {"name": "status", "is_numeric": False},
        {"name": "count", "is_numeric": True},
    ],
    "data": [{"status": "done", "count": 3}, {"status": "open", "count": 2}],
}
BAR = {
    "type": "bar",
    "title": "Tasks by status",
    "axis": {
        "x": {"name": "Status", "value": "status"},
        "y": [{"name": "Count", "value": "count"}],
    },
}


def test_table_request_uses_real_fields_even_when_model_hallucinates_columns():
    chart, reason = decide_chart(
        {"type": "table", "columns": [{"value": "secret"}]}, RESULT, "table"
    )
    assert chart["columns"] == [
        {"name": "status", "value": "status"},
        {"name": "count", "value": "count"},
    ]
    assert reason is None


def test_valid_chart_and_requested_pie():
    chart, reason = decide_chart(BAR, RESULT, "chart")
    assert chart == BAR
    assert reason is None

    pie, reason = decide_chart(BAR, RESULT, "chart", "pie")
    assert pie["type"] == "pie"
    assert pie["axis"]["series"]["value"] == "status"
    assert reason is None


def test_invalid_chart_fields_and_non_numeric_metric_fall_back():
    unknown = {**BAR, "axis": {**BAR["axis"], "x": {"value": "secret"}}}
    chart, reason = decide_chart(unknown, RESULT, "chart")
    assert chart["type"] == "table"
    assert reason == "invalid_chart_field"

    non_numeric = {**BAR, "axis": {**BAR["axis"], "y": {"value": "status"}}}
    chart, reason = decide_chart(non_numeric, RESULT, "chart")
    assert chart["type"] == "table"
    assert reason == "missing_numeric_metric"


def test_pie_rejects_negative_or_empty_results():
    negative = {**RESULT, "data": [{"status": "open", "count": -1}]}
    chart, reason = decide_chart(BAR, negative, "chart", "pie")
    assert chart["type"] == "table"
    assert reason == "pie_requires_nonnegative"

    chart, reason = decide_chart(BAR, {**RESULT, "data": []}, "chart")
    assert chart["type"] == "table"
    assert reason == "empty_result"


def test_unknown_or_missing_chart_falls_back_without_mutating_result():
    for invalid in ({"type": "scatter"}, {"type": []}, "not JSON"):
        chart, reason = decide_chart(invalid, RESULT, "chart")
        assert chart["type"] == "table"
        assert reason == "invalid_chart"
    assert RESULT["fields"] == ["status", "count"]
