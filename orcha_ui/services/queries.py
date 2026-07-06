from __future__ import annotations

import colorsys
import json
from collections import defaultdict
from datetime import datetime as dt
from datetime import timedelta as td
from typing import Any

from orcha.core import scheduler, tasks, thread_monitor
from orcha.utils import kvdb
from orcha.utils.log import LogManager
from orcha_ui.constants import NODE_KIND_COLORS
from orcha_ui.services.formatting import (
    format_dt,
    parse_local_dt,
    run_duration,
    run_start_time,
    run_status_color,
    safe_json,
    seconds_only,
    summarise_run_output,
    trim_text,
)
from orcha_ui.services.types import (
    DetailField,
    KvEntry,
    KvEntryResult,
    KvListingResult,
    LabelValueItem,
    LineageLegendItem,
    LineageLinkRow,
    LineageQueryResult,
    LogEntry,
    LogsQueryResult,
    OverviewQueryResult,
    OverviewTaskCard,
    RunDetailQueryResult,
    RunHistoryRow,
    RunSliceData,
    RunSliceSegment,
    ScheduleCard,
    ScheduleOption,
    SchedulerSummary,
    TaskDetailQueryResult,
    ThreadInstanceGroup,
    ThreadRow,
    ThreadsQueryResult,
    WorkspaceGroup,
)

# An instance whose health snapshot hasn't been updated within this window is
# treated as offline (the supervisor persists every ~10s by default).
_THREAD_INSTANCE_ONLINE_WINDOW = td(seconds=60)

# State -> badge tone for the threads page.
_THREAD_STATE_TONES = {
    "running": "green",
    "idle": "slate",
    "starting": "blue",
    "errored": "amber",
    "stalled": "amber",
    "crashed": "red",
    "stopped": "slate",
}

_THREAD_UNHEALTHY_STATES = {"errored", "stalled", "crashed"}


def list_task_options() -> list[LabelValueItem]:
    all_tasks = tasks.TaskItem.get_all()
    all_tasks.sort(key=lambda task: (_task_workspace(task), task.name, str(task.task_idk)))
    return [
        {
            "label": f"{task.name} ({_task_workspace(task)} | {task.task_idk})",
            "value": str(task.task_idk),
        }
        for task in all_tasks
    ]


def list_run_options(task_id: str | None) -> list[LabelValueItem]:
    if not task_id:
        return []
    task = tasks.TaskItem.get(task_id)
    if task is None:
        return []
    runs = tasks.RunItem.get_all(
        task=task,
        since=dt.now() - td(days=30),
        max_count=100,
        schedule=None,
    )
    runs.sort(key=lambda run: run.scheduled_time, reverse=True)
    return [
        {
            "label": f"{format_dt(run.scheduled_time)} - {run.status} ({run.run_idk})",
            "value": str(run.run_idk),
        }
        for run in runs
    ]


def list_task_tags() -> list[str]:
    tags = {"all"}
    for task in tasks.TaskItem.get_all():
        tags.update(task.task_tags)
    return sorted(tags)


def list_workspaces() -> list[str]:
    workspaces = {"All Workspaces"}
    for task in tasks.TaskItem.get_all():
        workspaces.add(_task_workspace(task))
    return sorted(workspaces, key=lambda value: (value != "All Workspaces", value.lower()))


def get_overview_payload(
    *,
    hours: int = 6,
    end_time_text: str | None = None,
    selected_tags: list[str] | None = None,
    selected_workspaces: list[str] | None = None,
    show_disabled: bool = False,
    failures_only: bool = False,
) -> OverviewQueryResult:
    display_end_time = parse_local_dt(end_time_text, dt.now())
    display_start_time = display_end_time - td(hours=max(hours, 1))

    all_tasks = tasks.TaskItem.get_all()
    all_tags = list_task_tags()
    all_workspaces = list_workspaces()

    selected_tags = selected_tags or ["all"]
    selected_workspaces = selected_workspaces or ["All Workspaces"]

    filtered_tasks: list[tasks.TaskItem]
    if selected_tags and "all" not in selected_tags:
        filtered_tasks = [
            task
            for task in all_tasks
            if any(tag in selected_tags for tag in task.task_tags)
        ]
    else:
        filtered_tasks = list(all_tasks)

    effective_workspaces = list(selected_workspaces)
    if "All Workspaces" in effective_workspaces and len(effective_workspaces) > 1:
        effective_workspaces = [workspace for workspace in effective_workspaces if workspace != "All Workspaces"]
    if "All Workspaces" not in effective_workspaces:
        filtered_tasks = [
            task
            for task in filtered_tasks
            if _task_workspace(task) in effective_workspaces
        ]

    if not show_disabled:
        filtered_tasks = [
            task
            for task in filtered_tasks
            if task.status not in {"disabled", "deleted"}
        ]

    task_runs: dict[str, list[tasks.RunItem]] = {}
    overview_summary = {"failed": 0, "warn": 0, "running": 0, "success": 0}
    for task in filtered_tasks:
        runs = tasks.RunItem.get_all(
            task=task,
            schedule=None,
            since=dt.now() - td(days=10),
        )
        task_runs[str(task.task_idk)] = runs
        # Health counts across the lookback window, aggregated over all visible tasks.
        for run in runs:
            marker = run.start_time or run.scheduled_time
            if marker is None or not (display_start_time <= marker <= display_end_time):
                continue
            if run.status in overview_summary:
                overview_summary[run.status] += 1

    scheduler_summary = _build_scheduler_summary()
    workspace_groups: list[WorkspaceGroup] = []
    grouped_tasks: dict[str, list[tasks.TaskItem]] = {}
    for task in filtered_tasks:
        grouped_tasks.setdefault(_task_workspace(task), []).append(task)

    for workspace in sorted(grouped_tasks):
        workspace_tasks = grouped_tasks[workspace]
        workspace_tasks.sort(key=lambda task: task.name.lower())
        task_cards = [
            _build_overview_task_card(
                task=task,
                all_runs=task_runs.get(str(task.task_idk), []),
                display_start_time=display_start_time,
                display_end_time=display_end_time,
            )
            for task in workspace_tasks
        ]
        overview_summary["running"] += sum(card["running_count"] for card in task_cards)
        if failures_only:
            task_cards = [card for card in task_cards if card["highlight_error"]]
        if not task_cards:
            continue
        workspace_groups.append(
            {
                "workspace": workspace,
                "task_cards": task_cards,
            }
        )

    return {
        "hours": max(hours, 1),
        "end_time_text": display_end_time.strftime("%Y-%m-%dT%H:%M"),
        "last_refreshed": seconds_only(dt.now()),
        "scheduler": scheduler_summary,
        "overview_summary": {
            "failed": overview_summary["failed"],
            "warn": overview_summary["warn"],
            "running": overview_summary["running"],
            "success": overview_summary["success"],
        },
        "workspace_groups": workspace_groups,
        "available_tags": all_tags,
        "available_workspaces": all_workspaces,
        "selected_tags": selected_tags,
        "selected_workspaces": effective_workspaces or ["All Workspaces"],
        "show_disabled": show_disabled,
        "display_start_label": format_dt(display_start_time),
        "display_end_label": format_dt(display_end_time),
    }


def get_task_detail_payload(task_id: str | None) -> TaskDetailQueryResult:
    options = list_task_options()
    if not task_id:
        return {
            "exists": False,
            "task_options": options,
            "selected_task_id": "",
            "task": None,
        }

    task = tasks.TaskItem.get(task_id)
    if task is None:
        return {
            "exists": False,
            "task_options": options,
            "selected_task_id": str(task_id),
            "task": None,
        }

    all_runs = tasks.RunItem.get_all(
        task=task,
        since=dt.now() - td(days=2),
        schedule=None,
    )
    all_runs.sort(key=lambda run: run.scheduled_time)
    all_runs = all_runs[-200:]

    schedule_options: list[ScheduleOption] = []
    schedule_cards: list[ScheduleCard] = []
    default_manual_config = safe_json({"notes": "manually created run"})
    for schedule in task.schedule_sets:
        config_with_defaults = dict(task.task_config)
        config_with_defaults.update(schedule.config)
        config_with_defaults["notes"] = "manually created run"
        schedule_options.append(
            {
                "label": schedule.cron_schedule,
                "value": str(schedule.set_idk),
                "config_text": safe_json(config_with_defaults, indent=4),
            }
        )
        trigger_runs: list[str] = []
        if schedule.trigger_config:
            trigger_runs.append(str(schedule.trigger_config.task.task_idk))
        else:
            trigger_runs.append("No trigger runs")
        schedule_cards.append(
            {
                "frequency": schedule.cron_schedule,
                "config_text": safe_json(schedule.config, indent=4),
                "trigger_runs": trigger_runs,
            }
        )

    if not schedule_options:
        schedule_options = [{"label": "No schedules", "value": "", "config_text": default_manual_config}]

    fields: list[DetailField] = [
        {"label": "Task ID", "value": str(task.task_idk), "tone": "slate", "code": False},
        {"label": "Name", "value": task.name, "tone": "slate", "code": False},
        {"label": "Description", "value": task.description or "N/A", "tone": "slate", "code": False},
        {"label": "Thread Group", "value": str(task.thread_group), "tone": "slate", "code": False},
        {"label": "Tags", "value": ", ".join(task.task_tags) if task.task_tags else "None", "tone": "slate", "code": False},
        {"label": "Status", "value": task.status, "tone": _tone_for_task_status(task.status), "code": False},
        {"label": "Last Active", "value": f"{format_dt(task.last_active)} ({seconds_only(dt.now() - task.last_active)})", "tone": "slate", "code": False},
        {"label": "Metadata", "value": safe_json(task.task_metadata, indent=4), "tone": "slate", "code": True},
    ]

    run_history_rows: list[RunHistoryRow] = [
        {
            "run_id": str(run.run_idk),
            "schedule": _run_schedule_text(task, run),
            "status": run.status,
            "status_tone": _tone_for_run_status(run.status),
            "scheduled_time": format_dt(run.scheduled_time),
            "start_time": format_dt(run.start_time),
            "end_time": format_dt(run.end_time),
            "href": f"/run_details/{run.run_idk}",
        }
        for run in sorted(all_runs, key=lambda run: run.scheduled_time, reverse=True)
    ]

    return {
        "exists": True,
        "task_options": options,
        "selected_task_id": str(task.task_idk),
        "task": {
            "task_id": str(task.task_idk),
            "task_href": f"/task_details/{task.task_idk}",
            "name": task.name,
            "description": task.description or "N/A",
            "status": task.status,
            "status_tone": _tone_for_task_status(task.status),
            "toggle_label": "Disable Task" if task.status == "enabled" else "Enable Task",
            "toggle_tone": "red" if task.status == "enabled" else "blue",
            "fields": fields,
            "schedule_cards": schedule_cards,
            "schedule_options": schedule_options,
            "default_schedule_value": str(schedule_options[0]["value"]),
            "manual_config_text": schedule_options[0]["config_text"],
            "recent_runs_timeline": build_run_timeline_data(
                all_runs=all_runs,
                display_start_time=dt.now() - td(days=2),
                display_end_time=dt.now(),
                display_count=200,
            ),
            "run_history_rows": run_history_rows,
        },
    }


def get_task_schedule_config(task_id: str | None, schedule_id: str | None) -> str:
    task = tasks.TaskItem.get(task_id) if task_id else None
    if task is None:
        return "No task found"
    if not schedule_id:
        return safe_json({"notes": "manually created run"}, indent=4)
    for schedule in task.schedule_sets:
        if str(schedule.set_idk) == str(schedule_id):
            config_with_defaults = dict(task.task_config)
            config_with_defaults.update(schedule.config)
            config_with_defaults["notes"] = "manually created run"
            return safe_json(config_with_defaults, indent=4)
    return "No schedule found"


def toggle_task_status(task_id: str | None) -> str:
    task = tasks.TaskItem.get(task_id) if task_id else None
    if task is None:
        return "Task not found"
    if task.status == "enabled":
        task.set_status("disabled", "Manually disabled")
        return "Task disabled"
    task.set_status("enabled", "Manually enabled")
    return "Task enabled"


def cancel_unstarted_runs(task_id: str | None) -> str:
    task = tasks.TaskItem.get(task_id) if task_id else None
    if task is None:
        return "No task selected"
    unstarted_runs = task.get_queued_runs()
    for run in unstarted_runs:
        run.set_status("cancelled", output={"message": "Unstarted runs manually cancelled"})
        run.set_progress(progress="complete", zero_duration=True)
    return f"Cancelled {len(unstarted_runs)} unstarted runs"


def create_manual_run(task_id: str | None, schedule_id: str | None, config_text: str | None) -> tuple[str, str | None]:
    task = tasks.TaskItem.get(task_id) if task_id else None
    if task is None:
        return "Create failed", None
    try:
        new_config = json.loads(config_text or "{}")
    except json.JSONDecodeError:
        return "Config is not valid JSON", None

    selected_schedule = None
    config_override = new_config
    original_schedule_config: dict[str, Any] | None = None
    if task.schedule_sets:
        for schedule in task.schedule_sets:
            if str(schedule.set_idk) == str(schedule_id):
                selected_schedule = schedule
                original_schedule_config = dict(schedule.config)
                schedule.config = new_config
                config_override = {}
                break
        if selected_schedule is None:
            return "Create failed", None

    try:
        run = tasks.RunItem.create(
            task=task,
            run_type="manual",
            schedule=selected_schedule,
            scheduled_time=dt.now(),
            created_by="orcha_ui",
            config_override=config_override,
        )
    finally:
        if selected_schedule is not None and original_schedule_config is not None:
            selected_schedule.config = original_schedule_config

    if run is None:
        return "Create failed", None
    return "Manual run created", str(run.run_idk)


def delete_task(task_id: str | None) -> tuple[bool, str]:
    task = tasks.TaskItem.get(task_id) if task_id else None
    if task is None:
        return False, "Task not found"
    try:
        task.delete_from_db()
    except Exception as exc:
        return False, f"Delete failed: {exc}"
    return True, "Task deleted"


def get_run_detail_payload(run_id: str | None) -> RunDetailQueryResult:
    task_options = list_task_options()
    if not run_id:
        return {
            "exists": False,
            "task_options": task_options,
            "selected_task_id": "",
            "run_options": [],
            "selected_run_id": "",
            "run": None,
        }

    run = tasks.RunItem.get(run_id)
    if run is None:
        return {
            "exists": False,
            "task_options": task_options,
            "selected_task_id": "",
            "run_options": [],
            "selected_run_id": str(run_id),
            "run": None,
        }

    duration = "Not Started"
    if run.start_time:
        if run.end_time:
            duration = str(td(seconds=(run.end_time - run.start_time).total_seconds()))
        else:
            duration = f"In Progress ({str(dt.now() - run.start_time)[:-7]})"

    schedule_text = "N/A"
    if run.run_type == "scheduled" and run.set_idf is not None:
        schedule = run._task.get_schedule_set(run.set_idf)
        if schedule is not None:
            schedule_text = schedule.cron_schedule

    full_output = safe_json(run.output, indent=4, default="No output") if run.output else "No output"
    summarised = summarise_run_output(run.output) if run.output else {}
    summarised_output = safe_json(summarised, indent=4, default="No output") if summarised else "No output"

    fields: list[DetailField] = [
        {"label": "Run ID", "value": str(run.run_idk), "tone": "slate", "code": False},
        {"label": "Scheduled Time", "value": format_dt(run.scheduled_time), "tone": "slate", "code": False},
        {"label": "Created By", "value": f"{run.created_by} ({format_dt(run.created_time)})", "tone": "slate", "code": False},
        {"label": "Start Time", "value": format_dt(run.start_time), "tone": "slate", "code": False},
        {"label": "End Time", "value": format_dt(run.end_time), "tone": "slate", "code": False},
        {"label": "Duration", "value": duration, "tone": "slate", "code": False},
        {"label": "Last Active", "value": f"{format_dt(run.last_active)} ({seconds_only(dt.now() - run.last_active)})" if run.last_active else "N/A", "tone": "slate", "code": False},
        {"label": "Progress", "value": run.progress, "tone": _tone_for_progress(run.progress), "code": False},
        {"label": "Status", "value": run.status, "tone": _tone_for_run_status(run.status), "code": False},
        {"label": "Type", "value": run.run_type, "tone": "slate", "code": False},
        {"label": "Schedule", "value": schedule_text, "tone": "slate", "code": False},
    ]

    return {
        "exists": True,
        "task_options": task_options,
        "selected_task_id": str(run.task_idf),
        "run_options": list_run_options(str(run.task_idf)),
        "selected_run_id": str(run.run_idk),
        "run": {
            "run_id": str(run.run_idk),
            "task_id": str(run.task_idf),
            "task_href": f"/task_details/{run.task_idf}",
            "task_name": run._task.name,
            "task_description": run._task.description or "N/A",
            "task_status": run._task.status,
            "task_status_tone": _tone_for_task_status(run._task.status),
            "fields": fields,
            "config_text": safe_json(run.config, indent=4),
            "full_output": full_output,
            "summarised_output": summarised_output,
            "triggered_run_id": str(run.output.get("triggered_run_id")) if run.output and run.output.get("triggered_run_id") else "",
            "triggered_run_href": f"/run_details/{run.output.get('triggered_run_id')}" if run.output and run.output.get("triggered_run_id") else "",
            "can_cancel": run.progress != "complete",
        },
    }


def cancel_run(run_id: str | None) -> str:
    run = tasks.RunItem.get(run_id) if run_id else None
    if run is None:
        return "Run not found"
    run.set_status(
        status="cancelled",
        output={"message": "Run was cancelled by user."},
    )
    run.set_progress("complete", zero_duration=True)
    return "Run cancelled"


def get_logs_payload(
    *,
    start_time_text: str | None,
    end_time_text: str | None,
    selected_sources: list[str] | None,
    limit: int,
) -> LogsQueryResult:
    end_dt = parse_local_dt(end_time_text, dt.now())
    start_dt = parse_local_dt(start_time_text, end_dt - td(hours=6))
    if end_dt < start_dt:
        start_dt = end_dt - td(hours=1)

    selected_sources = selected_sources or ["All Sources"]
    if len(selected_sources) > 1 and "All Sources" in selected_sources:
        selected_sources = [source for source in selected_sources if source != "All Sources"]

    limit_value = max(1, min(int(limit or 100), 5000))
    all_sources = ["All Sources", *_get_distinct_sources()]
    entries = _query_logs(start_dt=start_dt, end_dt=end_dt, sources=selected_sources, limit=limit_value)

    return {
        "entries": entries,
        "all_sources": all_sources,
        "selected_sources": selected_sources,
        "start_time_text": start_dt.strftime("%Y-%m-%dT%H:%M"),
        "end_time_text": end_dt.strftime("%Y-%m-%dT%H:%M"),
        "limit": limit_value,
        "last_refreshed": seconds_only(dt.now()),
        "refresh_disabled": end_dt < (dt.now() - td(minutes=1)),
    }


def get_kv_listing_payload(*, search_text: str | None, limit: int, include_expired: bool) -> KvListingResult:
    try:
        entries = kvdb.list_items(
            storage_type="postgres",
            limit=max(1, int(limit or 100)),
            search=(search_text or "").strip() or None,
            include_expired=include_expired,
        )
    except Exception as exc:
        return {
            "entries": [],
            "key_options": [],
            "status_message": f"Unable to query kvdb entries: {exc}",
            "status_tone": "red",
        }

    serialised_entries = [_serialise_kv_entry(entry) for entry in entries]
    return {
        "entries": serialised_entries,
        "key_options": [{"label": entry["key"], "value": entry["key"]} for entry in serialised_entries],
        "status_message": "Ready.",
        "status_tone": "blue",
    }


def load_kv_entry(key: str | None, encryption_key: str | None) -> KvEntryResult:
    key_value = (key or "").strip()
    if not key_value:
        return {
            "ok": False,
            "status_message": "Provide a key before loading.",
            "status_tone": "amber",
        }

    meta = _find_entry_metadata(key_value)
    encryption_key_clean = (encryption_key or "").strip() or None
    if meta and meta.get("is_encrypted") and not encryption_key_clean:
        return {
            "ok": False,
            "status_message": "Entry is encrypted. Provide an encryption key to load it.",
            "status_tone": "amber",
            "metadata": _build_kv_metadata(meta),
        }

    try:
        raw_value = kvdb.get(
            key=key_value,
            as_type=object,
            storage_type="postgres",
            no_key_return="exception",
            encryption_key=encryption_key_clean,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status_message": f"Error loading key: {exc}",
            "status_tone": "red",
            "metadata": _build_kv_metadata(meta),
            "value_text": "",
        }

    value_text, value_mode = _stringify_value(raw_value)
    expiry_minutes = None
    if meta and meta.get("ttl_seconds") is not None and meta["ttl_seconds"] > 0:
        expiry_minutes = round(meta["ttl_seconds"] / 60, 2)

    return {
        "ok": True,
        "status_message": "Entry loaded.",
        "status_tone": "green",
        "metadata": _build_kv_metadata(meta),
        "value_text": value_text,
        "value_mode": value_mode,
        "expiry_minutes": expiry_minutes,
    }


def save_kv_entry(
    *,
    key: str | None,
    value_text: str | None,
    value_mode: str | None,
    expiry_minutes: str | float | int | None,
    encryption_key: str | None,
) -> KvEntryResult:
    key_value = (key or "").strip()
    if not key_value:
        return {"ok": False, "status_message": "A key is required for this action.", "status_tone": "amber"}

    try:
        parsed_value = _parse_value(value_text or "", value_mode or "json")
    except ValueError as exc:
        return {"ok": False, "status_message": f"Unable to parse value: {exc}", "status_tone": "red"}

    expiry = None
    if expiry_minutes not in (None, ""):
        try:
            minutes_float = float(expiry_minutes)
        except ValueError:
            return {"ok": False, "status_message": "Expiry minutes must be numeric.", "status_tone": "red"}
        if minutes_float > 0:
            expiry = td(minutes=minutes_float)

    encryption_key_clean = (encryption_key or "").strip() or None
    kvdb.store(
        storage_type="postgres",
        key=key_value,
        value=parsed_value,
        expiry=expiry,
        encryption_key=encryption_key_clean,
    )

    metadata = _build_kv_metadata(_find_entry_metadata(key_value))
    suffix = " (encrypted)" if encryption_key_clean else ""
    return {
        "ok": True,
        "status_message": f"Entry \"{key_value}\" saved{suffix}.",
        "status_tone": "green",
        "metadata": metadata,
    }


def delete_kv_entry(key: str | None) -> KvEntryResult:
    key_value = (key or "").strip()
    if not key_value:
        return {"ok": False, "status_message": "A key is required for this action.", "status_tone": "amber"}
    deleted = kvdb.delete(storage_type="postgres", key=key_value)
    if deleted:
        return {
            "ok": True,
            "status_message": f"Entry \"{key_value}\" deleted.",
            "status_tone": "green",
            "metadata": _build_kv_metadata(None),
        }
    return {
        "ok": False,
        "status_message": f"Entry \"{key_value}\" was not found.",
        "status_tone": "amber",
    }


def get_lineage_payload(selected_task_ids: list[str] | None = None) -> LineageQueryResult:
    all_tasks = tasks.TaskItem.get_all()
    all_tasks.sort(key=lambda task: (_task_workspace(task), task.name, str(task.task_idk)))
    task_options: list[LabelValueItem] = [
        {
            "label": f"{task.name} ({task.task_idk})",
            "value": str(task.task_idk),
        }
        for task in all_tasks
    ]
    # Workspace metadata powers the "select by workspace" shortcuts on the page.
    task_workspaces = {str(task.task_idk): _task_workspace(task) for task in all_tasks}
    available_workspaces = sorted(set(task_workspaces.values()), key=lambda value: value.lower())
    selected_values = [str(task.task_idk) for task in all_tasks] if selected_task_ids is None else list(selected_task_ids)
    selected_set = set(selected_values) if selected_task_ids is not None else None
    model = build_lineage_model(selected_set)
    legend: list[LineageLegendItem] = [
        {
            "task_id": task_id,
            "label": model.get("task_labels", {}).get(task_id, task_id),
            "color": model.get("palette", [])[index] if index < len(model.get("palette", [])) else "#64748b",
        }
        for index, task_id in enumerate(model.get("task_order", []))
    ]
    node_lookup = {
        int(node.get("id", 0)): str(node.get("label", ""))
        for node in model.get("nodes", [])
    }
    color_lookup = {item["task_id"]: item["color"] for item in legend}
    task_label_lookup = {item["task_id"]: item["label"] for item in legend}
    link_rows: list[LineageLinkRow] = sorted(
        [
            {
                "task_id": str(link["task"]),
                "task_label": task_label_lookup.get(str(link["task"]), str(link["task"])),
                "color": color_lookup.get(str(link["task"]), "#64748b"),
                "source_label": node_lookup.get(int(link["source"]), str(link["source"])),
                "target_label": node_lookup.get(int(link["target"]), str(link["target"])),
            }
            for link in model.get("task_links", [])
        ],
        key=lambda row: (row["task_label"], row["source_label"], row["target_label"]),
    )
    flow_nodes, flow_edges = build_lineage_flow(model)
    return {
        "task_options": task_options,
        "selected_task_ids": selected_values,
        "task_workspaces": task_workspaces,
        "available_workspaces": available_workspaces,
        "legend": legend,
        "link_rows": link_rows,
        "flow_nodes": flow_nodes,
        "flow_edges": flow_edges,
    }


def build_lineage_model(selected_task_ids: set[str] | None = None) -> dict[str, Any]:
    all_tasks = tasks.TaskItem.get_all()
    if selected_task_ids is not None:
        all_tasks = [task for task in all_tasks if str(task.task_idk) in selected_task_ids]

    runs_data: list[tuple[tasks.TaskItem, dict[str, Any]]] = []
    for task in all_tasks:
        latest_run = tasks.RunItem.get_latest(task=task, status="success")
        if not latest_run:
            continue
        output = summarise_run_output(latest_run.output or {})
        if isinstance(output, dict):
            runs_data.append((task, output))

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str]] = []
    # Real set of tasks that traverse each (parent, child) edge. A shared edge
    # (e.g. a shared entity -> a shared source) genuinely belongs to several
    # tasks, so we record every one rather than collapsing to a single label.
    edge_tasks: dict[tuple[str, str], set[str]] = defaultdict(set)
    next_id = 1

    def ensure_node(
        key: str,
        *,
        label: str,
        kind: str,
        subtype: str | None = None,
        group: str | None = None,
    ) -> int:
        nonlocal next_id
        if key in nodes:
            if group:
                nodes[key].setdefault("groups", set()).add(group)
            return int(nodes[key]["id"])
        node_id = next_id
        next_id += 1
        nodes[key] = {
            "id": node_id,
            "key": key,
            "label": label,
            "kind": kind,
            "subtype": subtype,
            "groups": {group} if group else set(),
        }
        return node_id

    def add_edge(parent_key: str, child_key: str, task_group: str) -> None:
        edges.append((parent_key, child_key))
        edge_tasks[(parent_key, child_key)].add(task_group)

    for task, output in runs_data:
        task_group = str(task.task_idk)
        run_times = output.get("run_times_summary") or []
        if not isinstance(run_times, list) or not run_times:
            continue

        # Collect each stage independently so a task with multiple sources (or
        # multiple sinks) renders them as parallel siblings in a single column
        # rather than chaining them end to end across several columns. Only the
        # transforms keep their run order, forming the chain between the two ends.
        source_keys: list[str] = []
        transform_keys: list[str] = []
        sink_keys: list[str] = []

        for index, entry in enumerate(run_times):
            if not isinstance(entry, dict):
                continue
            module_idk = entry.get("module_idk")
            module_type = entry.get("module_type")
            module_entity = entry.get("module_entity")
            if not module_idk:
                continue

            if _is_source(module_type):
                module_key = f"module:source:{module_idk}"
                ensure_node(module_key, label=str(module_idk), kind="module", subtype="source", group=task_group)
                if module_entity:
                    # Source-side copy of the entity, pinned to the far left.
                    entity_key = f"entity:source:{module_entity}"
                    ensure_node(entity_key, label=str(module_entity), kind="entity", subtype="entity", group=task_group)
                    add_edge(entity_key, module_key, task_group)
                source_keys.append(module_key)
                continue

            if _is_sink(module_type):
                module_key = f"module:sink:{module_idk}"
                ensure_node(module_key, label=str(module_idk), kind="module", subtype="sink", group=task_group)
                if module_entity:
                    # Sink-side copy of the entity, pinned to the far right. An
                    # entity used by both a source and a sink is deliberately drawn
                    # twice (entity:source:* on the left, entity:sink:* on the
                    # right) so edges never have to wrap back across the diagram.
                    entity_key = f"entity:sink:{module_entity}"
                    ensure_node(entity_key, label=str(module_entity), kind="entity", subtype="entity", group=task_group)
                    add_edge(module_key, entity_key, task_group)
                sink_keys.append(module_key)
                continue

            module_key = f"module:mid:{task.task_idk}:{module_idk}:{index}"
            ensure_node(module_key, label=str(module_idk), kind="module", subtype="mid", group=task_group)
            transform_keys.append(module_key)

        # Wire the stages together: every source feeds the first transform, the
        # transforms chain in run order, and the last transform feeds every sink.
        # With no transforms, sources fan directly into the sinks.
        for parent_key, child_key in zip(transform_keys, transform_keys[1:]):
            add_edge(parent_key, child_key, task_group)
        downstream_head = transform_keys[0] if transform_keys else None
        upstream_tail = transform_keys[-1] if transform_keys else None
        for source_key in source_keys:
            if downstream_head is not None:
                add_edge(source_key, downstream_head, task_group)
            else:
                for sink_key in sink_keys:
                    add_edge(source_key, sink_key, task_group)
        if upstream_tail is not None:
            for sink_key in sink_keys:
                add_edge(upstream_tail, sink_key, task_group)

    node_list = sorted((value for value in nodes.values()), key=lambda item: int(item["id"]))
    edge_list = [
        (nodes[parent]["id"], nodes[child]["id"], parent, child)
        for parent, child in edges
        if parent in nodes and child in nodes
    ]

    parent_by_id: dict[int, int] = {}
    for from_id, to_id, _parent_key, _child_key in edge_list:
        if int(to_id) not in parent_by_id:
            parent_by_id[int(to_id)] = int(from_id)

    tree_nodes: list[dict[str, Any]] = [
        {
            "id": 0,
            "parentId": None,
            "label": "root",
            "kind": "root",
            "subtype": "",
            "groups": [],
        }
    ]
    for node in node_list:
        node_id = int(node["id"])
        tree_nodes.append(
            {
                "id": node_id,
                "parentId": int(parent_by_id.get(node_id, 0)),
                "label": str(node.get("label") or node.get("key") or node_id),
                "kind": str(node.get("kind") or "module"),
                "subtype": str(node.get("subtype") or ""),
                "groups": sorted(str(group) for group in (node.get("groups") or set()) if group),
            }
        )

    # Each edge carries the full set of tasks that traverse it (``tasks``) plus a
    # stable representative (``task``) used for colour/label. Highlighting matches
    # on the set, so an edge shared by several tasks lights up for each of them.
    task_links: list[dict[str, Any]] = []
    for (parent_key, child_key), task_set in edge_tasks.items():
        if parent_key not in nodes or child_key not in nodes:
            continue
        tasks_sorted = sorted(str(task) for task in task_set if task)
        if not tasks_sorted:
            continue
        task_links.append(
            {
                "source": int(nodes[parent_key]["id"]),
                "target": int(nodes[child_key]["id"]),
                "task": tasks_sorted[0],
                "tasks": tasks_sorted,
            }
        )

    task_order = sorted({str(task.task_idk) for task, _output in runs_data})
    palette = _generate_palette(len(task_order))
    task_labels = {
        str(task.task_idk): (task.name if getattr(task, "name", None) else str(task.task_idk))
        for task, _output in runs_data
    }
    return {
        "nodes": tree_nodes,
        "task_links": task_links,
        "task_order": task_order,
        "palette": palette,
        "task_labels": task_labels,
    }


# Horizontal gap between layers (columns) and vertical gap between sibling
# nodes, in React Flow canvas units. Tuned so 180px-wide boxes never overlap.
_FLOW_COL_GAP = 300
_FLOW_ROW_GAP = 100
_FLOW_NODE_WIDTH = 180

# Box colours keyed by node subtype (falling back to kind). Nodes are coloured
# by *what they are* (entity / source / transform / sink); edges are coloured by
# *which task* they belong to, so the two encodings never collide.
_FLOW_NODE_STYLES: dict[str, dict[str, str]] = {
    "entity": {"bg": "#e0f2fe", "border": "#0ea5e9", "fg": "#0c4a6e"},
    "source": {"bg": "#cffafe", "border": "#06b6d4", "fg": "#155e75"},
    "mid": {"bg": "#f1f5f9", "border": "#64748b", "fg": "#1e293b"},
    "sink": {"bg": "#ccfbf1", "border": "#14b8a6", "fg": "#115e51"},
}

# Human-readable layer captions for the diagram, in left-to-right order. Used by
# the page to render the static node-kind legend that explains box colours.
LINEAGE_NODE_LEGEND: list[dict[str, str]] = [
    {"label": "Entity", "color": "#0ea5e9", "hint": "Data store (source end, left / sink end, right)"},
    {"label": "Source", "color": "#06b6d4", "hint": "Task ingestion step"},
    {"label": "Transform", "color": "#64748b", "hint": "Intermediate module"},
    {"label": "Sink", "color": "#14b8a6", "hint": "Final output (right)"},
]


def _node_style(style: dict[str, str], state: str) -> dict[str, Any]:
    """Box CSS for a node given a focus state: 'normal', 'match', or 'dim'."""
    box: dict[str, Any] = {
        "background": style["bg"],
        "color": style["fg"],
        "border": f"1.5px solid {style['border']}",
        "borderRadius": "12px",
        "padding": "8px 14px",
        "fontSize": "12px",
        "fontWeight": 600,
        "width": _FLOW_NODE_WIDTH,
        "textAlign": "center",
        "transition": "box-shadow 120ms ease, opacity 120ms ease",
    }
    if state == "match":
        box["opacity"] = 1
        box["boxShadow"] = f"0 0 0 3px {style['border']}, 0 8px 22px rgba(15, 23, 42, 0.20)"
    elif state == "dim":
        box["opacity"] = 0.28
        box["boxShadow"] = "none"
    else:
        box["opacity"] = 1
        box["boxShadow"] = "0 1px 2px rgba(15, 23, 42, 0.08)"
    return box


def _edge_style(color: str, state: str) -> dict[str, Any]:
    """Stroke CSS for an edge given a focus state: 'normal', 'match', or 'dim'.

    Every edge carries a faint white casing (drop-shadow) so that where two
    differently-coloured lines cross or run alongside each other they stay
    visually separable even before anything is highlighted.
    """
    if state == "match":
        return {
            "stroke": color,
            "strokeWidth": 4,
            "opacity": 1,
            "filter": f"drop-shadow(0 0 2px {color})",
        }
    if state == "dim":
        return {"stroke": color, "strokeWidth": 1.5, "opacity": 0.1}
    return {
        "stroke": color,
        "strokeWidth": 2.5,
        "opacity": 1,
        "filter": "drop-shadow(0 0 1.2px rgba(255, 255, 255, 0.95))",
    }


def _flow_node(node: dict[str, Any], *, x: float, y: float) -> dict[str, Any]:
    subtype = str(node.get("subtype") or "")
    kind = str(node.get("kind") or "module")
    style_key = subtype if subtype in _FLOW_NODE_STYLES else kind
    style = _FLOW_NODE_STYLES.get(style_key, _FLOW_NODE_STYLES["mid"])
    tasks_for_node = sorted(str(group) for group in (node.get("groups") or []) if group)
    return {
        "id": str(node["id"]),
        "type": "default",
        "position": {"x": float(x), "y": float(y)},
        # data carries everything apply_lineage_focus needs to recompute styling
        # without re-querying: the style key and the tasks this node belongs to.
        "data": {
            "label": str(node.get("label") or node.get("id")),
            "styleKey": style_key if style_key in _FLOW_NODE_STYLES else "mid",
            "tasks": tasks_for_node,
        },
        "sourcePosition": "right",
        "targetPosition": "left",
        "draggable": True,
        "zIndex": 1,
        "style": _node_style(style, "normal"),
    }


def _flow_edge(
    source: int,
    target: int,
    color: str,
    tasks: list[str],
    task_colors: dict[str, str],
    offset: int,
) -> dict[str, Any]:
    return {
        "id": f"e{source}-{target}",
        "source": str(source),
        "target": str(target),
        "type": "smoothstep",
        # Per-task lateral offset spreads otherwise-overlapping parallel risers
        # so distinct tasks heading to the same node don't perfectly coincide.
        "pathOptions": {"offset": offset, "borderRadius": 14},
        # ``tasks`` is every task that traverses this edge; ``color`` is the cached
        # base (representative) colour and ``taskColors`` maps each task to its own
        # colour so a highlighted shared edge recolours to the *focused* task.
        "data": {"tasks": tasks, "color": color, "taskColors": task_colors},
        "zIndex": 1,
        "style": _edge_style(color, "normal"),
        "markerEnd": {"type": "arrowclosed", "color": color, "width": 16, "height": 16},
    }


def apply_lineage_focus(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    focused_task: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return restyled copies of nodes/edges emphasising one task.

    Pure function of the elements' ``data`` payloads, so it is idempotent and can
    be re-applied on every hover/click without touching the database. With no
    focus everything renders normally; with a focus the matching task's nodes and
    edges are outlined and raised above (higher z-index) everything else, which is
    dimmed — directly disambiguating overlapping lines.
    """
    styled_nodes: list[dict[str, Any]] = []
    for node in nodes:
        data = node.get("data", {})
        if not focused_task:
            state = "normal"
        elif focused_task in (data.get("tasks") or []):
            state = "match"
        else:
            state = "dim"
        style = _FLOW_NODE_STYLES.get(str(data.get("styleKey") or "mid"), _FLOW_NODE_STYLES["mid"])
        updated = dict(node)
        updated["style"] = _node_style(style, state)
        updated["zIndex"] = 20 if state == "match" else (0 if state == "dim" else 1)
        styled_nodes.append(updated)

    styled_edges: list[dict[str, Any]] = []
    for edge in edges:
        data = edge.get("data", {})
        color = str(data.get("color") or "#94a3b8")
        if not focused_task:
            state = "normal"
        elif focused_task in (data.get("tasks") or []):
            state = "match"
            # A shared edge recolours to the focused task so the highlighted path
            # is a single consistent colour end to end.
            color = str((data.get("taskColors") or {}).get(focused_task, color))
        else:
            state = "dim"
        updated = dict(edge)
        updated["style"] = _edge_style(color, state)
        updated["animated"] = state == "match"
        updated["zIndex"] = 20 if state == "match" else (0 if state == "dim" else 1)
        marker_color = color if state != "dim" else "#e2e8f0"
        updated["markerEnd"] = {"type": "arrowclosed", "color": marker_color, "width": 16, "height": 16}
        styled_edges.append(updated)

    return styled_nodes, styled_edges


def build_lineage_flow(model: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn the lineage model into positioned React Flow nodes and edges.

    The layout is a left-to-right layered (Sugiyama-style) DAG:

    * ``layer`` (x column) is the longest path from a root, so entities — which
      never have an incoming edge — always land in the leftmost column, sources
      sit just to their right, transforms chain across the middle, and sinks fall
      out at the far right.
    * Within a layer, nodes are ordered by the barycentre of their already-placed
      parents to keep connections roughly horizontal and reduce edge crossings.
    """
    raw_nodes = [node for node in model.get("nodes", []) if int(node.get("id", 0)) != 0]
    if not raw_nodes:
        return [], []

    node_by_id = {int(node["id"]): node for node in raw_nodes}
    valid_ids = set(node_by_id)

    task_order = model.get("task_order", [])
    palette = model.get("palette", [])
    task_color = {
        task_id: (palette[index] if index < len(palette) else "#94a3b8")
        for index, task_id in enumerate(task_order)
    }

    children: dict[int, list[int]] = defaultdict(list)
    parents: dict[int, list[int]] = defaultdict(list)
    edge_pairs: list[tuple[int, int, list[str]]] = []
    seen_edges: set[tuple[int, int]] = set()
    for link in model.get("task_links", []):
        source = int(link["source"])
        target = int(link["target"])
        if source not in valid_ids or target not in valid_ids:
            continue
        children[source].append(target)
        parents[target].append(source)
        key = (source, target)
        if key not in seen_edges:
            seen_edges.add(key)
            edge_tasks_list = [str(t) for t in (link.get("tasks") or [link.get("task", "")]) if t]
            edge_pairs.append((source, target, edge_tasks_list))

    # Longest-path layering with a cycle guard (lineage graphs are DAGs, but a bad
    # run could in theory produce a loop — never recurse into the active stack).
    layer: dict[int, int] = {}

    def compute_layer(node_id: int, stack: frozenset[int]) -> int:
        if node_id in layer:
            return layer[node_id]
        depth = 0
        for parent in parents.get(node_id, []):
            if parent in stack:
                continue
            depth = max(depth, compute_layer(parent, stack | {node_id}) + 1)
        layer[node_id] = depth
        return depth

    for node_id in valid_ids:
        compute_layer(node_id, frozenset())

    by_layer: dict[int, list[int]] = defaultdict(list)
    for node_id in valid_ids:
        by_layer[layer[node_id]].append(node_id)

    # ``task_rank`` is the average position (in task_order) of every task a node
    # belongs to. Ordering each column by it first keeps a task's nodes in a
    # stable horizontal band across the whole diagram, so a single task's path
    # runs roughly straight instead of zig-zagging — which is what dominates the
    # visible line length. Nodes shared by several tasks settle between their
    # bands. Barycentre of already-placed parents then breaks ties to reduce
    # crossings within a band.
    task_pos = {task_id: index for index, task_id in enumerate(task_order)}

    def task_rank(nid: int) -> float:
        groups = node_by_id[nid].get("groups") or []
        ranks = [task_pos[group] for group in groups if group in task_pos]
        return sum(ranks) / len(ranks) if ranks else float(len(task_pos))

    order_index: dict[int, int] = {}
    for current_layer in sorted(by_layer):
        layer_nodes = by_layer[current_layer]

        def barycentre(nid: int) -> float:
            placed = [order_index[p] for p in parents.get(nid, []) if p in order_index]
            return sum(placed) / len(placed) if placed else task_rank(nid)

        layer_nodes.sort(
            key=lambda nid: (task_rank(nid), barycentre(nid), str(node_by_id[nid].get("label", "")))
        )
        for index, node_id in enumerate(layer_nodes):
            order_index[node_id] = index

    max_count = max((len(nodes) for nodes in by_layer.values()), default=1)
    flow_nodes: list[dict[str, Any]] = []
    for current_layer in sorted(by_layer):
        layer_nodes = sorted(by_layer[current_layer], key=lambda nid: order_index[nid])
        # Vertically centre shorter columns so the diagram stays balanced.
        offset = (max_count - len(layer_nodes)) / 2.0
        for index, node_id in enumerate(layer_nodes):
            flow_nodes.append(
                _flow_node(
                    node_by_id[node_id],
                    x=current_layer * _FLOW_COL_GAP,
                    y=(index + offset) * _FLOW_ROW_GAP,
                )
            )

    flow_edges = []
    for source, target, edge_task_list in edge_pairs:
        # Representative task drives colour + lateral offset; the full list drives
        # highlight matching.
        representative = edge_task_list[0] if edge_task_list else ""
        flow_edges.append(
            _flow_edge(
                source,
                target,
                task_color.get(representative, "#94a3b8"),
                edge_task_list,
                {task_id: task_color.get(task_id, "#94a3b8") for task_id in edge_task_list},
                offset=20 + 12 * task_pos.get(representative, 0),
            )
        )
    return flow_nodes, flow_edges


def build_compact_run_slices(task_runs: list[tasks.RunItem]) -> RunSliceData:
    # Equal-width chips that fill the whole strip, so a short run of runs reads as a
    # full status bar rather than a few chips stranded in an empty track.
    count = len(task_runs)
    width = f"{100 / count:.4f}%" if count else "0%"
    segments: list[RunSliceSegment] = [
        {
            "kind": "run",
            "href": f"/run_details/{run.run_idk}",
            "width": width,
            "min_width": "6px",
            "height": "18px",
            "color": run_status_color(run.status, run.progress),
            "tooltip": _run_tooltip(run),
        }
        for run in task_runs
    ]
    # Compact strips don't render start/end labels, but RunSliceData carries them so
    # every slice payload has a uniform shape for the Reflex state var.
    return {
        "has_segments": bool(segments),
        "segments": segments,
        "empty_text": "No recent runs to display",
        "start_label": "",
        "end_label": "",
    }


def build_run_timeline_data(
    *,
    all_runs: list[tasks.RunItem],
    display_start_time: dt,
    display_end_time: dt,
    display_count: int | None = None,
) -> RunSliceData:
    display_hours = max((display_end_time - display_start_time).total_seconds() / 3600, 1 / 60)
    filtered_runs = sorted(all_runs, key=lambda run: run.scheduled_time)
    filtered_runs = [
        run
        for run in filtered_runs
        if display_start_time <= run.scheduled_time <= display_end_time
    ]
    if display_count:
        filtered_runs = filtered_runs[-display_count:]

    segments: list[RunSliceSegment] = []
    previous_end = display_start_time

    for run in filtered_runs:
        start_time, end_time = _run_bounds(run)
        # Idle gap before the run so it lands at its real position on the window;
        # the run's own width is its duration.
        if start_time > previous_end:
            segments.append(_blank_segment(previous_end, start_time, display_hours))
        segments.append(_run_segment(run, display_hours))
        previous_end = max(previous_end, end_time)

    # Trailing idle fills to the end of the window; a run that finished ~now therefore
    # sits at the right edge instead of being stretched across the remaining space.
    if previous_end < display_end_time:
        segments.append(_blank_segment(previous_end, display_end_time, display_hours))

    return {
        "has_segments": bool(filtered_runs),
        "segments": segments,
        "empty_text": "No recent runs to display",
        "start_label": format_dt(display_start_time),
        "end_label": format_dt(display_end_time),
    }


def get_threads_payload() -> ThreadsQueryResult:
    """
    Build the payload for the Threads page: the live health of every supervised
    background thread (scheduler loops, task runner handlers, the supervisor
    itself), grouped by the process instance reporting them.
    """
    now = dt.now()
    snapshot = thread_monitor.get_health_snapshot()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot:
        grouped[str(row.get("instance_id") or "unknown")].append(row)

    instances: list[ThreadInstanceGroup] = []
    total_threads = 0
    unhealthy_threads = 0
    for instance_id in sorted(grouped):
        rows = grouped[instance_id]
        updated_at = max(
            (value for row in rows if (value := row.get("updated_at"))),
            default=None,
        )
        online = updated_at is not None and updated_at > (now - _THREAD_INSTANCE_ONLINE_WINDOW)

        thread_rows = [_build_thread_row(row, online=online) for row in rows]
        thread_rows.sort(key=lambda item: (item["group"], item["name"]))
        instance_unhealthy = sum(
            1 for row in rows if str(row.get("state")) in _THREAD_UNHEALTHY_STATES
        )
        total_threads += len(rows)
        unhealthy_threads += instance_unhealthy

        if not online:
            status_label, status_tone = "Offline", "red"
        elif instance_unhealthy:
            status_label, status_tone = f"{instance_unhealthy} unhealthy", "amber"
        else:
            status_label, status_tone = "Healthy", "green"

        instances.append(
            {
                "instance_id": instance_id,
                "online": online,
                "status_label": status_label,
                "status_tone": status_tone,
                "updated": f"{seconds_only(now - updated_at)} ago" if updated_at else "N/A",
                "total": len(rows),
                "unhealthy": instance_unhealthy,
                "threads": thread_rows,
            }
        )

    # Show offline instances last so live processes are at the top.
    instances.sort(key=lambda item: (not item["online"], item["instance_id"]))

    return {
        "instances": instances,
        "total_threads": total_threads,
        "unhealthy_threads": unhealthy_threads,
        "instance_count": len(instances),
        "last_refreshed": seconds_only(now),
        "has_data": bool(snapshot),
    }


def _build_thread_row(row: dict[str, Any], *, online: bool) -> ThreadRow:
    state = str(row.get("state") or "unknown")
    # A thread on an offline instance is only as trustworthy as its last report,
    # so visually de-emphasise its (now stale) state.
    state_tone = "slate" if not online else _THREAD_STATE_TONES.get(state, "slate")
    interval = row.get("interval_s")
    return {
        "name": str(row.get("thread_name") or ""),
        "group": str(row.get("thread_group") or ""),
        "state": state,
        "state_tone": state_tone,
        "last_heartbeat": _ago(row.get("last_heartbeat")),
        "last_tick": _ago(row.get("last_tick_at")),
        "interval": f"{interval:g}s" if isinstance(interval, (int, float)) else "N/A",
        "restart_count": int(row.get("restart_count") or 0),
        "error_count": int(row.get("error_count") or 0),
        "consecutive_errors": int(row.get("consecutive_errors") or 0),
        "last_error": str(row.get("last_error") or "None"),
        "last_error_at": format_dt(row.get("last_error_at")),
    }


def _ago(value: dt | None) -> str:
    if value is None:
        return "N/A"
    return f"{seconds_only(dt.now() - value)} ago"


def _build_scheduler_summary() -> SchedulerSummary:
    scheduler_last_active = scheduler.Scheduler.get_last_active()
    scheduler_loaded_at = scheduler.Scheduler.get_loaded_at()
    if scheduler_last_active is None:
        return {
            "started": "Not Active",
            "started_tone": "red",
            "last_active": "Not Active",
            "last_active_tone": "red",
        }

    uptime = seconds_only(dt.now() - scheduler_loaded_at) if scheduler_loaded_at else "Not Active"
    uptime_tone = "red" if scheduler_loaded_at is None else "green"
    last_active = seconds_only(dt.now() - scheduler_last_active)
    last_active_tone = "green" if scheduler_last_active > (dt.now() - td(minutes=2)) else "red"
    return {
        "started": uptime,
        "started_tone": uptime_tone,
        "last_active": last_active,
        "last_active_tone": last_active_tone,
    }


def _build_overview_task_card(
    *,
    task: tasks.TaskItem,
    all_runs: list[tasks.RunItem],
    display_start_time: dt,
    display_end_time: dt,
) -> OverviewTaskCard:
    all_runs = sorted(all_runs, key=lambda run: run.scheduled_time)
    recent_runs = all_runs[-10:]
    active_runs = task.get_running_runs()

    # Card highlight rules:
    #   red   -> task is in "error" status OR the most recent run failed
    #   grey  -> task is disabled (dimmed at 75% opacity)
    #   none  -> everything else
    # (Timeouts surface as `failed`; `warn` is a softer degraded state.)
    failure_count = sum(1 for run in recent_runs if run.status == tasks.RunStatusEnum.failed.value)
    last_run_failed = bool(recent_runs) and recent_runs[-1].status == tasks.RunStatusEnum.failed.value
    highlight_error = last_run_failed or task.status == "error"
    highlight_disabled = task.status == "disabled" and not highlight_error

    next_scheduled = task.get_next_scheduled_time()
    next_scheduled_text = seconds_only(next_scheduled)
    if task.status == "disabled":
        next_scheduled_text = "Disabled"
    elif task.status == "inactive":
        next_scheduled_text = "Inactive"
    elif task.status == "error":
        next_scheduled_text = "Error"

    last_active_delta = seconds_only(dt.now() - task.last_active)
    last_active_tone = "green" if task.last_active > (dt.now() - td(minutes=2)) else "red"

    workspace_text = "" if _task_workspace(task) == "No Workspace" else f" ({_task_workspace(task)})"
    return {
        "task_id": str(task.task_idk),
        "task_href": f"/task_details/{task.task_idk}",
        "name": f"{task.name}{workspace_text}",
        "description": task.description or "No description provided.",
        "status": task.status,
        "status_tone": _tone_for_task_status(task.status),
        "highlight_error": highlight_error,
        "highlight_disabled": highlight_disabled,
        "failure_count": failure_count,
        "running_count": len(active_runs),
        "last_active": last_active_delta,
        "last_active_tone": last_active_tone,
        "last_run": format_dt(recent_runs[-1].scheduled_time) if recent_runs else "N/A",
        "next_scheduled": next_scheduled_text,
        "active_runs": build_compact_run_slices(active_runs),
        "recent_runs": build_compact_run_slices(recent_runs),
        "timeline": build_run_timeline_data(
            all_runs=all_runs,
            display_start_time=display_start_time,
            display_end_time=display_end_time,
            display_count=100,
        ),
    }


def _blank_segment(start_time: dt, end_time: dt, display_hours: float) -> RunSliceSegment:
    duration_hours = max((end_time - start_time).total_seconds() / 3600, 0)
    width = max((duration_hours / display_hours) * 100, 0.5)
    return {
        "kind": "gap",
        "href": "",
        "width": f"{width:.3f}%",
        "min_width": "4px",
        "height": "18px",
        "color": "rgba(148, 163, 184, 0.18)",
        "tooltip": "",
    }


def _run_bounds(run: tasks.RunItem) -> tuple[dt, dt]:
    """Effective [start, end] used to both size and position a run on the timeline."""
    start_time = run.start_time if run.start_time is not None else run.scheduled_time
    if run.end_time is not None:
        end_time = run.end_time
    elif run.status in {
        tasks.RunStatusEnum.warn.value,
        tasks.RunStatusEnum.failed.value,
        tasks.RunStatusEnum.success.value,
    }:
        end_time = run.last_active or start_time
    else:
        end_time = start_time
    return start_time, end_time


def _run_segment(run: tasks.RunItem, display_hours: float) -> RunSliceSegment:
    start_time, end_time = _run_bounds(run)
    duration_hours = max((end_time - start_time).total_seconds() / 3600, 0)
    width = max((duration_hours / display_hours) * 100, 0.5)
    return {
        "kind": "run",
        "href": f"/run_details/{run.run_idk}",
        "width": f"{width:.3f}%",
        "min_width": "6px",
        "height": "18px",
        "color": run_status_color(run.status, run.progress),
        "tooltip": _run_tooltip(run),
    }


def _run_tooltip(run: tasks.RunItem) -> str:
    return "\n".join(
        [
            f"Scheduled: {format_dt(run.scheduled_time)}",
            f"Start: {run_start_time(run)}",
            f"Duration: {run_duration(run)}",
            f"Status: {run.status}",
            f"Config: {safe_json(run.config, indent=2)}",
        ]
    )


def _run_schedule_text(task: tasks.TaskItem, run: tasks.RunItem) -> str:
    if run.run_type == "manual":
        return "Manual"
    if run.set_idf is None:
        return "No Schedules"
    schedule = task.get_schedule_set(run.set_idf)
    if schedule is None:
        return "Unknown"
    return schedule.cron_schedule


def _task_workspace(task: tasks.TaskItem) -> str:
    return str(task.task_metadata.get("workspace", "No Workspace"))


def _tone_for_task_status(status: str | None) -> str:
    value = (status or "").lower()
    if value == "enabled":
        return "green"
    if value == "error":
        return "alert"  # emphasized (solid) red so a broken task stands out
    if value in {"inactive", "disabled", "deleted"}:
        return "slate"
    return "blue"


def _tone_for_run_status(status: str | None) -> str:
    value = (status or "").lower()
    if value == "success":
        return "green"
    if value == "failed":
        return "alert"  # emphasized (solid) red — the signal operators hunt for
    if value in {"warn", "warning"}:
        return "amber"
    if value == "cancelled":
        return "slate"  # neutral, not a failure — keep it quiet
    return "blue"


def _tone_for_progress(progress: str | None) -> str:
    value = (progress or "").lower()
    if value == "running":
        return "purple"
    if value == "queued":
        return "blue"
    if value == "complete":
        return "green"
    return "slate"


def _get_distinct_sources() -> list[str]:
    return LogManager.get_distinct_sources()


def _query_logs(start_dt: dt, end_dt: dt, sources: list[str] | None, limit: int) -> list[LogEntry]:
    filtered_sources = None if not sources or "All Sources" in sources else sources
    rows = LogManager.get_entries(
        limit=limit,
        sources=filtered_sources,
        start=start_dt,
        end=end_dt,
    )
    result: list[LogEntry] = []
    for row in rows:
        text = getattr(row, "text", "") or ""
        json_value = getattr(row, "json", {}) or {}
        json_text = trim_text(str(json_value), 200)
        result.append(
            {
                "created": format_dt(getattr(row, "created", None)),
                "source": _to_title_case(getattr(row, "source", "") or ""),
                "category": _to_title_case(getattr(row, "category", "") or ""),
                "actor": _to_title_case(getattr(row, "actor", "") or ""),
                "text": trim_text(text, 200),
                "json": json_text,
            }
        )
    return result


def _to_title_case(text: str) -> str:
    return text.replace("_", " ").title()


def _format_expiry(expiry: dt | None) -> str:
    if expiry is None:
        return "No expiry"
    return expiry.strftime("%Y-%m-%d %H:%M:%S")


def _format_ttl(ttl_seconds: int | None) -> str:
    if ttl_seconds is None:
        return "No expiry"
    delta = td(seconds=abs(ttl_seconds))
    delta_text = seconds_only(delta)
    if ttl_seconds >= 0:
        return f"in {delta_text}"
    return f"{delta_text} ago"


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _serialise_kv_entry(entry: dict[str, Any]) -> KvEntry:
    preview = entry.get("value_preview") or ""
    if entry.get("load_error"):
        preview = f"Error: {entry['load_error']}"
    return {
        "key": str(entry["key"]),
        "type": str(entry.get("type", "unknown")),
        "encrypted": "Yes" if entry.get("is_encrypted") else "No",
        "size": _format_bytes(int(entry.get("size_bytes", 0))),
        "expiry": _format_expiry(entry.get("expiry")),
        "ttl": _format_ttl(entry.get("ttl_seconds")),
        "preview": trim_text(str(preview), 160),
        "row_tone": "amber" if entry.get("is_expired") else ("red" if entry.get("load_error") else "slate"),
    }


def _stringify_value(value: Any) -> tuple[str, str]:
    if isinstance(value, (dict, list)):
        return safe_json(value, indent=2), "json"
    if isinstance(value, bool):
        return ("true" if value else "false"), "bool"
    if isinstance(value, int):
        return str(value), "int"
    if isinstance(value, float):
        return str(value), "float"
    if isinstance(value, str):
        return value, "string"
    return repr(value), "python"


def _parse_value(raw_value: str, mode: str) -> Any:
    if mode == "json":
        return json.loads(raw_value)
    if mode == "string":
        return raw_value
    if mode == "int":
        return int(raw_value)
    if mode == "float":
        return float(raw_value)
    if mode == "bool":
        lowered = raw_value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
        raise ValueError("Boolean value must be true/false, 1/0, yes/no, y/n, or on/off")
    raise ValueError(f"Unsupported value mode: {mode}")


def _find_entry_metadata(key: str) -> dict[str, Any] | None:
    search_key = key.strip()
    if not search_key:
        return None
    try:
        rows = kvdb.list_items(storage_type="postgres", search=search_key, limit=5, include_expired=True)
    except Exception:
        return None
    for row in rows:
        if row["key"] == search_key:
            return row
    return None


def _build_kv_metadata(entry: dict[str, Any] | None) -> list[LabelValueItem]:
    if entry is None:
        return [{"label": "Status", "value": "No entry selected."}]
    status = "Expired" if entry.get("is_expired") else "Active"
    return [
        {"label": "Status", "value": status},
        {"label": "Type", "value": str(entry.get("type", "unknown"))},
        {"label": "Encrypted", "value": "Yes" if entry.get("is_encrypted") else "No"},
        {"label": "Size", "value": _format_bytes(int(entry.get("size_bytes", 0)))},
        {"label": "Expiry", "value": _format_expiry(entry.get("expiry"))},
        {"label": "TTL", "value": _format_ttl(entry.get("ttl_seconds"))},
    ]


def _is_source(module_type: str | None) -> bool:
    return isinstance(module_type, str) and module_type.lower().startswith("source")


def _is_sink(module_type: str | None) -> bool:
    return isinstance(module_type, str) and module_type.lower().startswith("sink")


def _generate_palette(count: int) -> list[str]:
    if count <= 0:
        return []
    colors = []
    for index in range(count):
        hue = (index * 360.0 / count) % 360.0
        red, green, blue = colorsys.hls_to_rgb(hue / 360.0, 0.55, 0.65)
        colors.append(f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}")
    return colors


def _node_color(node: dict[str, Any]) -> str:
    kind = str(node.get("kind") or "module")
    subtype = str(node.get("subtype") or "")
    if subtype in NODE_KIND_COLORS:
        return NODE_KIND_COLORS[subtype]
    return NODE_KIND_COLORS.get(kind, NODE_KIND_COLORS["module"])