from __future__ import annotations

import colorsys
import json
from datetime import datetime as dt
from datetime import timedelta as td
from typing import Any

import plotly.graph_objects as go

from orcha.core import scheduler, tasks
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


def list_task_options() -> list[dict[str, str]]:
    all_tasks = tasks.TaskItem.get_all()
    all_tasks.sort(key=lambda task: (_task_workspace(task), task.name, str(task.task_idk)))
    return [
        {
            "label": f"{task.name} ({_task_workspace(task)} | {task.task_idk})",
            "value": str(task.task_idk),
        }
        for task in all_tasks
    ]


def list_run_options(task_id: str | None) -> list[dict[str, str]]:
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
) -> dict[str, Any]:
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
    for task in filtered_tasks:
        task_runs[str(task.task_idk)] = tasks.RunItem.get_all(
            task=task,
            schedule=None,
            since=dt.now() - td(days=10),
        )

    scheduler_summary = _build_scheduler_summary()
    workspace_groups: list[dict[str, Any]] = []
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
        "workspace_groups": workspace_groups,
        "available_tags": all_tags,
        "available_workspaces": all_workspaces,
        "selected_tags": selected_tags,
        "selected_workspaces": effective_workspaces or ["All Workspaces"],
        "show_disabled": show_disabled,
        "display_start_label": format_dt(display_start_time),
        "display_end_label": format_dt(display_end_time),
    }


def get_task_detail_payload(task_id: str | None) -> dict[str, Any]:
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

    schedule_options = []
    schedule_cards = []
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
        trigger_runs = []
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

    fields = [
        {"label": "Task ID", "value": str(task.task_idk), "tone": "slate", "code": False},
        {"label": "Name", "value": task.name, "tone": "slate", "code": False},
        {"label": "Description", "value": task.description or "N/A", "tone": "slate", "code": False},
        {"label": "Thread Group", "value": str(task.thread_group), "tone": "slate", "code": False},
        {"label": "Tags", "value": ", ".join(task.task_tags) if task.task_tags else "None", "tone": "slate", "code": False},
        {"label": "Status", "value": task.status, "tone": _tone_for_task_status(task.status), "code": False},
        {"label": "Last Active", "value": f"{format_dt(task.last_active)} ({seconds_only(dt.now() - task.last_active)})", "tone": "slate", "code": False},
        {"label": "Metadata", "value": safe_json(task.task_metadata, indent=4), "tone": "slate", "code": True},
    ]

    run_history_rows = [
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


def get_run_detail_payload(run_id: str | None) -> dict[str, Any]:
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

    fields = [
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
) -> dict[str, Any]:
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


def get_kv_listing_payload(*, search_text: str | None, limit: int, include_expired: bool) -> dict[str, Any]:
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


def load_kv_entry(key: str | None, encryption_key: str | None) -> dict[str, Any]:
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
) -> dict[str, Any]:
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


def delete_kv_entry(key: str | None) -> dict[str, Any]:
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


def get_lineage_payload(selected_task_ids: list[str] | None = None) -> dict[str, Any]:
    all_tasks = tasks.TaskItem.get_all()
    task_options = [
        {
            "label": f"{task.name} ({task.task_idk})",
            "value": str(task.task_idk),
        }
        for task in all_tasks
    ]
    selected_values = [str(task.task_idk) for task in all_tasks] if selected_task_ids is None else list(selected_task_ids)
    selected_set = set(selected_values) if selected_task_ids is not None else None
    model = build_lineage_model(selected_set)
    legend = [
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
    link_rows = sorted(
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
    return {
        "task_options": task_options,
        "selected_task_ids": selected_values,
        "legend": legend,
        "link_rows": link_rows,
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

    def add_edge(parent_key: str, child_key: str) -> None:
        edges.append((parent_key, child_key))

    for task, output in runs_data:
        task_group = str(task.task_idk)
        run_times = output.get("run_times_summary") or []
        if not isinstance(run_times, list) or not run_times:
            continue

        prev_key: str | None = None
        last_source_key: str | None = None
        task_inserted = False

        for index, entry in enumerate(run_times):
            if not isinstance(entry, dict):
                continue
            module_idk = entry.get("module_idk")
            module_type = entry.get("module_type")
            module_entity = entry.get("module_entity")
            if not module_idk:
                continue

            if _is_source(module_type):
                if module_entity:
                    entity_key = f"entity:source:{module_entity}"
                    ensure_node(entity_key, label=str(module_entity), kind="entity", subtype="source", group=task_group)
                module_key = f"module:source:{module_idk}"
                ensure_node(module_key, label=str(module_idk), kind="module", subtype="source", group=task_group)
                if module_entity:
                    add_edge(entity_key, module_key)
                if last_source_key is not None:
                    add_edge(last_source_key, module_key)
                last_source_key = module_key
                continue

            if not task_inserted:
                prev_key = last_source_key if last_source_key is not None else None
                task_inserted = True

            if _is_sink(module_type):
                module_key = f"module:sink:{module_idk}"
                ensure_node(module_key, label=str(module_idk), kind="module", subtype="sink", group=task_group)
                if prev_key is not None:
                    add_edge(prev_key, module_key)
                prev_key = module_key
                if module_entity:
                    entity_key = f"entity:sink:{module_entity}"
                    ensure_node(entity_key, label=str(module_entity), kind="entity", subtype="sink", group=task_group)
                    add_edge(module_key, entity_key)
                continue

            module_key = f"module:mid:{task.task_idk}:{module_idk}:{index}"
            ensure_node(module_key, label=str(module_idk), kind="module", subtype="mid", group=task_group)
            if prev_key is not None:
                add_edge(prev_key, module_key)
            prev_key = module_key

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

    id_to_groups: dict[int, set[str]] = {int(node["id"]): set(node.get("groups") or set()) for node in node_list}
    task_links: list[dict[str, Any]] = []
    for from_id, to_id, parent_key, child_key in edge_list:
        candidate_groups: set[str] = set()
        if isinstance(parent_key, str) and parent_key.startswith("task:"):
            candidate_groups.add(parent_key.split(":", 1)[1])
        elif isinstance(parent_key, str) and parent_key.startswith("module:mid:"):
            parts = parent_key.split(":")
            if len(parts) >= 3:
                candidate_groups.add(parts[2])
        else:
            candidate_groups = id_to_groups.get(int(from_id), set()) & id_to_groups.get(int(to_id), set())
        task_id = sorted(candidate_groups)[0] if candidate_groups else None
        if task_id:
            task_links.append({"source": int(from_id), "target": int(to_id), "task": str(task_id)})

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


def build_lineage_figure(model: dict[str, Any]) -> go.Figure:
    nodes = [node for node in model.get("nodes", []) if int(node.get("id", 0)) != 0]
    links = model.get("task_links", [])
    figure = go.Figure()
    if not nodes:
        figure.add_annotation(
            text="No lineage data available for the current task selection.",
            showarrow=False,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            font={"size": 16, "color": "#475569"},
        )
        figure.update_layout(margin={"l": 20, "r": 20, "t": 40, "b": 20}, paper_bgcolor="rgba(0,0,0,0)")
        return figure

    node_ids = [int(node["id"]) for node in nodes]
    id_to_index = {node_id: index for index, node_id in enumerate(node_ids)}
    task_palette = {task_id: model.get("palette", [])[index] for index, task_id in enumerate(model.get("task_order", []))}

    figure.add_trace(
        go.Sankey(
            arrangement="snap",
            node={
                "pad": 18,
                "thickness": 18,
                "label": [str(node["label"]) for node in nodes],
                "color": [_node_color(node) for node in nodes],
                "line": {"color": "#cbd5e1", "width": 1},
                "hovertemplate": "%{label}<extra></extra>",
            },
            link={
                "source": [id_to_index[link["source"]] for link in links if link["source"] in id_to_index and link["target"] in id_to_index],
                "target": [id_to_index[link["target"]] for link in links if link["source"] in id_to_index and link["target"] in id_to_index],
                "value": [1 for link in links if link["source"] in id_to_index and link["target"] in id_to_index],
                "color": [task_palette.get(link["task"], "rgba(100,116,139,0.55)") for link in links if link["source"] in id_to_index and link["target"] in id_to_index],
                "customdata": [model.get("task_labels", {}).get(link["task"], link["task"]) for link in links if link["source"] in id_to_index and link["target"] in id_to_index],
                "hovertemplate": "%{source.label} → %{target.label}<br>Task: %{customdata}<extra></extra>",
            },
        )
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Work Sans, sans-serif", "size": 12, "color": "#0f172a"},
        margin={"l": 24, "r": 24, "t": 20, "b": 12},
        height=760,
    )
    return figure


def build_compact_run_slices(task_runs: list[tasks.RunItem]) -> dict[str, Any]:
    segments = [
        {
            "kind": "run",
            "href": f"/run_details/{run.run_idk}",
            "width": "14px",
            "min_width": "14px",
            "height": "18px",
            "color": run_status_color(run.status, run.progress),
            "tooltip": _run_tooltip(run),
        }
        for run in task_runs
    ]
    return {
        "has_segments": bool(segments),
        "segments": segments,
        "empty_text": "No recent runs to display",
    }


def build_run_timeline_data(
    *,
    all_runs: list[tasks.RunItem],
    display_start_time: dt,
    display_end_time: dt,
    display_count: int | None = None,
) -> dict[str, Any]:
    display_hours = max((display_end_time - display_start_time).total_seconds() / 3600, 1 / 60)
    filtered_runs = sorted(all_runs, key=lambda run: run.scheduled_time)
    filtered_runs = [
        run
        for run in filtered_runs
        if display_start_time <= run.scheduled_time <= display_end_time
    ]
    if display_count:
        filtered_runs = filtered_runs[-display_count:]

    segments: list[dict[str, Any]] = []
    previous_end = display_start_time

    for index, run in enumerate(filtered_runs):
        if run.scheduled_time > previous_end:
            segments.append(_blank_segment(previous_end, run.scheduled_time, display_hours))

        segments.append(_run_segment(run, display_hours))

        next_run = filtered_runs[index + 1] if index < len(filtered_runs) - 1 else None
        previous_end = next_run.scheduled_time if next_run is not None else display_end_time
        if next_run is None and run.scheduled_time < display_end_time:
            segments.append(_blank_segment(run.scheduled_time, display_end_time, display_hours))

    return {
        "has_segments": bool(filtered_runs),
        "segments": segments,
        "empty_text": "No recent runs to display",
        "start_label": format_dt(display_start_time),
        "end_label": format_dt(display_end_time),
    }


def _build_scheduler_summary() -> dict[str, Any]:
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
) -> dict[str, Any]:
    all_runs = sorted(all_runs, key=lambda run: run.scheduled_time)
    recent_runs = all_runs[-5:]
    active_runs = task.get_running_runs()

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
        "dimmed": task.status not in {"enabled", "error"},
        "highlight_error": task.status == "error",
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


def _blank_segment(start_time: dt, end_time: dt, display_hours: float) -> dict[str, Any]:
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


def _run_segment(run: tasks.RunItem, display_hours: float) -> dict[str, Any]:
    if run.start_time is not None:
        start_time = run.start_time
    else:
        start_time = run.scheduled_time

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
        return "red"
    if value in {"inactive", "disabled", "deleted"}:
        return "slate"
    return "blue"


def _tone_for_run_status(status: str | None) -> str:
    value = (status or "").lower()
    if value == "success":
        return "green"
    if value in {"failed", "cancelled"}:
        return "red"
    if value in {"warn", "warning"}:
        return "amber"
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


def _query_logs(start_dt: dt, end_dt: dt, sources: list[str] | None, limit: int) -> list[dict[str, Any]]:
    filtered_sources = None if not sources or "All Sources" in sources else sources
    rows = LogManager.get_entries(
        limit=limit,
        sources=filtered_sources,
        start=start_dt,
        end=end_dt,
    )
    result = []
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


def _serialise_kv_entry(entry: dict[str, Any]) -> dict[str, Any]:
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


def _build_kv_metadata(entry: dict[str, Any] | None) -> list[dict[str, str]]:
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