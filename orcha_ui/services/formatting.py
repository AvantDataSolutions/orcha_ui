from __future__ import annotations

import json
from datetime import datetime as dt
from datetime import timedelta as td
from typing import Any

from orcha_ui.constants import RUN_STATUS_COLORS


def format_dt(value: dt | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else "N/A"


def parse_local_dt(value: str | None, fallback: dt | None = None) -> dt:
    if not value:
        return fallback or dt.now()
    try:
        return dt.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return fallback or dt.now()


def to_datetime_local(value: dt | None) -> str:
    if value is None:
        value = dt.now()
    return value.strftime("%Y-%m-%dT%H:%M")


def seconds_only(value: dt | td | None) -> str:
    if value is None:
        return ""
    return str(value).split(".")[0]


def safe_json(value: Any, *, indent: int = 2, default: str = "{}") -> str:
    if value in (None, ""):
        return default
    try:
        return json.dumps(value, indent=indent, default=str)
    except TypeError:
        return default


def trim_text(value: str | None, max_length: int = 200) -> str:
    if not value:
        return ""
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def run_status_color(status: str | None, progress: str | None = None) -> str:
    if progress == "queued":
        return RUN_STATUS_COLORS["queued"]
    if progress == "running":
        return RUN_STATUS_COLORS["running"]
    key = (status or "unknown").lower()
    return RUN_STATUS_COLORS.get(key, RUN_STATUS_COLORS["unknown"])


def run_start_time(run: Any) -> str:
    if getattr(run, "start_time", None) is not None:
        return seconds_only(run.start_time)
    return ""


def run_duration(run: Any) -> str:
    if getattr(run, "end_time", None) is not None and getattr(run, "start_time", None) is not None:
        return seconds_only(run.end_time - run.start_time)
    if getattr(run, "start_time", None) is not None:
        return seconds_only(dt.now() - run.start_time)
    return "Not started"


def summarise_run_times(run_times: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not run_times:
        return []

    grouped: dict[str, dict[str, Any]] = {}
    for run_time in run_times:
        module_idk = run_time.get("module_idk", "unknown")
        if module_idk not in grouped:
            grouped[module_idk] = {
                "module_idk": module_idk,
                "module_type": run_time.get("module_type", "N/A"),
                "module_entity": run_time.get("module_entity", "N/A"),
                "start_times": [],
                "end_times": [],
                "durations": [],
                "retry_count": 0,
                "retry_exceptions": [],
                "count": 0,
            }
        grouped[module_idk]["start_times"].append(run_time.get("start_time_posix", 0))
        grouped[module_idk]["end_times"].append(run_time.get("end_time_posix", 0))
        grouped[module_idk]["durations"].append(run_time.get("duration_seconds", 0))
        grouped[module_idk]["count"] += 1
        grouped[module_idk]["retry_count"] += run_time.get("retry_count", 0)
        grouped[module_idk]["retry_exceptions"].extend(run_time.get("retry_exceptions", []))

    summary: list[dict[str, Any]] = []
    for module_idk, data in grouped.items():
        min_start = min(data["start_times"])
        max_end = max(data["end_times"])
        total_duration = sum(data["durations"])
        min_duration = min(data["durations"])
        avg_duration = total_duration / data["count"] if data["count"] > 0 else 0
        max_duration = max(data["durations"])
        item = {
            "module_idk": module_idk,
            "module_type": data["module_type"],
            "module_entity": data["module_entity"],
            "min_start_time": dt.fromtimestamp(min_start).strftime("%Y-%m-%d %H:%M:%S"),
            "max_end_time": dt.fromtimestamp(max_end).strftime("%Y-%m-%d %H:%M:%S"),
            "total_duration_seconds": round(total_duration, 3),
            "min_duration_seconds": round(min_duration, 3),
            "avg_duration_seconds": round(avg_duration, 3),
            "max_duration_seconds": round(max_duration, 3),
            "run_count": data["count"],
            "min_start_posix": min_start,
        }
        if data["retry_count"] > 0:
            item["retry_count"] = data["retry_count"]
            item["retry_exceptions"] = data["retry_exceptions"]
        summary.append(item)

    summary.sort(key=lambda item: item["min_start_posix"])
    return summary


def summarise_run_output(run_output: dict[str, Any] | None) -> dict[str, Any]:
    if not run_output:
        return {}
    if "run_times" not in run_output:
        return run_output

    output_copy = run_output.copy()
    output_copy["run_times_summary"] = summarise_run_times(run_output["run_times"])
    output_copy.pop("run_times", None)
    return output_copy