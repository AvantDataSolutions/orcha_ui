from __future__ import annotations

from datetime import datetime as dt, timedelta as td
from typing import Any, TypedDict

import plotly.graph_objects as go
import reflex as rx

from orcha_ui.services import queries
from orcha_ui.services.formatting import to_datetime_local


class ToggleFilter(TypedDict):
    label: str
    active: bool


class SchedulerSummary(TypedDict):
    started: str
    started_tone: str
    last_active: str
    last_active_tone: str


class DetailField(TypedDict):
    label: str
    value: str
    tone: str
    code: bool


class RunSliceSegment(TypedDict):
    kind: str
    href: str
    width: str
    min_width: str
    height: str
    color: str
    tooltip: str


class RunSliceData(TypedDict):
    has_segments: bool
    segments: list[RunSliceSegment]
    empty_text: str
    start_label: str
    end_label: str


class ScheduleOption(TypedDict):
    label: str
    value: str
    config_text: str


class ScheduleCard(TypedDict):
    frequency: str
    config_text: str
    trigger_runs: list[str]


class RunHistoryRow(TypedDict):
    run_id: str
    schedule: str
    status: str
    status_tone: str
    scheduled_time: str
    start_time: str
    end_time: str
    href: str


class OverviewTaskCard(TypedDict):
    task_id: str
    task_href: str
    name: str
    description: str
    status: str
    status_tone: str
    dimmed: bool
    highlight_error: bool
    last_active: str
    last_active_tone: str
    last_run: str
    next_scheduled: str
    active_runs: RunSliceData
    recent_runs: RunSliceData
    timeline: RunSliceData


class WorkspaceGroup(TypedDict):
    workspace: str
    task_cards: list[OverviewTaskCard]


class TaskDetailPayload(TypedDict):
    task_id: str
    task_href: str
    name: str
    description: str
    status: str
    status_tone: str
    toggle_label: str
    toggle_tone: str
    fields: list[DetailField]
    schedule_cards: list[ScheduleCard]
    schedule_options: list[ScheduleOption]
    default_schedule_value: str
    manual_config_text: str
    recent_runs_timeline: RunSliceData
    run_history_rows: list[RunHistoryRow]


class RunDetailPayload(TypedDict):
    run_id: str
    task_id: str
    task_href: str
    task_name: str
    task_description: str
    task_status: str
    task_status_tone: str
    fields: list[DetailField]
    config_text: str
    full_output: str
    summarised_output: str
    triggered_run_id: str
    triggered_run_href: str
    can_cancel: bool


class LogEntry(TypedDict):
    created: str
    source: str
    category: str
    actor: str
    text: str
    json: str


class KvEntry(TypedDict):
    key: str
    type: str
    encrypted: str
    size: str
    expiry: str
    ttl: str
    preview: str
    row_tone: str


class LabelValueItem(TypedDict):
    label: str
    value: str


class LineageTaskFilter(TypedDict):
    label: str
    value: str
    active: bool


class LineageLegendItem(TypedDict):
    task_id: str
    label: str
    color: str


class LineageLinkRow(TypedDict):
    task_id: str
    task_label: str
    color: str
    source_label: str
    target_label: str


def _empty_task_detail_payload() -> TaskDetailPayload:
    return {
        "task_id": "",
        "task_href": "",
        "name": "",
        "description": "",
        "status": "",
        "status_tone": "slate",
        "toggle_label": "Enable Task",
        "toggle_tone": "blue",
        "fields": [],
        "schedule_cards": [],
        "schedule_options": [],
        "default_schedule_value": "",
        "manual_config_text": "{}",
        "recent_runs_timeline": {
            "has_segments": False,
            "segments": [],
            "empty_text": "No recent runs to display",
            "start_label": "",
            "end_label": "",
        },
        "run_history_rows": [],
    }


def _empty_run_detail_payload() -> RunDetailPayload:
    return {
        "run_id": "",
        "task_id": "",
        "task_href": "",
        "task_name": "",
        "task_description": "",
        "task_status": "",
        "task_status_tone": "slate",
        "fields": [],
        "config_text": "{}",
        "full_output": "No output",
        "summarised_output": "No output",
        "triggered_run_id": "",
        "triggered_run_href": "",
        "can_cancel": False,
    }


def _parse_int(value: str | int | None, default: int) -> int:
    try:
        parsed = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
    return parsed


def _build_picker(options: list[dict[str, Any]], selected_value: str | None) -> tuple[list[str], dict[str, str], dict[str, str], str]:
    items: list[str] = []
    lookup: dict[str, str] = {}
    reverse_lookup: dict[str, str] = {}
    selected_label = ""
    selected_text = str(selected_value or "")
    for option in options:
        label = str(option.get("label", ""))
        value = str(option.get("value", ""))
        items.append(label)
        lookup[label] = value
        reverse_lookup[value] = label
        if value == selected_text:
            selected_label = label
    if not selected_label and items:
        selected_label = items[0]
    return items, lookup, reverse_lookup, selected_label


def _route_param(state: rx.State, name: str) -> str:
    try:
        params = getattr(getattr(state.router, "page", None), "params", {}) or {}
    except Exception:
        return ""
    value = params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


class OverviewState(rx.State):
    hours_text: str = "6"
    end_time_text: str = to_datetime_local(dt.now())
    show_disabled: bool = False
    last_refreshed: str = ""
    display_start_label: str = ""
    display_end_label: str = ""
    scheduler: SchedulerSummary = {
        "started": "Not Active",
        "started_tone": "red",
        "last_active": "Not Active",
        "last_active_tone": "red",
    }
    workspace_groups: list[WorkspaceGroup] = []
    tag_filters: list[ToggleFilter] = [{"label": "all", "active": True}]
    workspace_filters: list[ToggleFilter] = [{"label": "All Workspaces", "active": True}]
    selected_tags: list[str] = ["all"]
    selected_workspaces: list[str] = ["All Workspaces"]

    @rx.var
    def has_workspace_groups(self) -> bool:
        return len(self.workspace_groups) > 0

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        self.last_refreshed = str(payload.get("last_refreshed", ""))
        self.display_start_label = str(payload.get("display_start_label", ""))
        self.display_end_label = str(payload.get("display_end_label", ""))
        self.scheduler = dict(payload.get("scheduler", self.scheduler))
        self.workspace_groups = list(payload.get("workspace_groups", []))
        self.selected_tags = list(payload.get("selected_tags", ["all"]))
        self.selected_workspaces = list(payload.get("selected_workspaces", ["All Workspaces"]))
        self.hours_text = str(payload.get("hours", self.hours_text))
        self.end_time_text = str(payload.get("end_time_text", self.end_time_text))
        self.tag_filters = [
            {"label": str(tag), "active": str(tag) in set(self.selected_tags)}
            for tag in payload.get("available_tags", ["all"])
        ]
        self.workspace_filters = [
            {"label": str(workspace), "active": str(workspace) in set(self.selected_workspaces)}
            for workspace in payload.get("available_workspaces", ["All Workspaces"])
        ]

    def _load_payload(self) -> None:
        payload = queries.get_overview_payload(
            hours=max(_parse_int(self.hours_text, 6), 1),
            end_time_text=self.end_time_text,
            selected_tags=self.selected_tags,
            selected_workspaces=self.selected_workspaces,
            show_disabled=self.show_disabled,
        )
        self._apply_payload(payload)

    @rx.event
    def load(self) -> None:
        self._load_payload()

    @rx.event
    def set_hours_text(self, value: str) -> None:
        self.hours_text = value

    @rx.event
    def set_end_time_text(self, value: str) -> None:
        self.end_time_text = value

    @rx.event
    def toggle_show_disabled(self, checked: bool) -> None:
        self.show_disabled = bool(checked)
        self._load_payload()

    @rx.event
    def toggle_tag(self, tag: str) -> None:
        if tag == "all":
            self.selected_tags = ["all"]
        else:
            current = {value for value in self.selected_tags if value != "all"}
            if tag in current:
                current.remove(tag)
            else:
                current.add(tag)
            self.selected_tags = sorted(current) if current else ["all"]
        self._load_payload()

    @rx.event
    def toggle_workspace(self, workspace: str) -> None:
        if workspace == "All Workspaces":
            self.selected_workspaces = ["All Workspaces"]
        else:
            current = {value for value in self.selected_workspaces if value != "All Workspaces"}
            if workspace in current:
                current.remove(workspace)
            else:
                current.add(workspace)
            self.selected_workspaces = sorted(current) if current else ["All Workspaces"]
        self._load_payload()

    @rx.event
    def refresh(self) -> None:
        self._load_payload()

    @rx.event
    def set_now(self) -> None:
        self.end_time_text = to_datetime_local(dt.now())
        self._load_payload()


class TaskDetailState(rx.State):
    task_picker_items: list[str] = []
    task_picker_lookup: dict[str, str] = {}
    selected_task_label: str = ""
    exists: bool = False
    task: TaskDetailPayload = _empty_task_detail_payload()
    schedule_picker_items: list[str] = []
    schedule_picker_lookup: dict[str, str] = {}
    schedule_config_lookup: dict[str, str] = {}
    selected_schedule_label: str = ""
    manual_config_text: str = "{}"
    status_message: str = "Ready."
    status_tone: str = "blue"
    show_delete_modal: bool = False
    show_cancel_modal: bool = False

    @rx.var
    def has_task(self) -> bool:
        return self.exists

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        items, lookup, _reverse, selected_label = _build_picker(payload.get("task_options", []), payload.get("selected_task_id", ""))
        self.task_picker_items = items
        self.task_picker_lookup = lookup
        self.selected_task_label = selected_label
        self.exists = bool(payload.get("exists", False))
        self.task = payload.get("task") or _empty_task_detail_payload()
        if self.exists:
            schedule_options = list(self.task.get("schedule_options", []))
            schedule_items, schedule_lookup, _schedule_reverse, selected_schedule_label = _build_picker(
                schedule_options,
                self.task.get("default_schedule_value", ""),
            )
            self.schedule_picker_items = schedule_items
            self.schedule_picker_lookup = schedule_lookup
            self.selected_schedule_label = selected_schedule_label
            self.schedule_config_lookup = {
                str(option.get("label", "")): str(option.get("config_text", "{}"))
                for option in schedule_options
            }
            self.manual_config_text = self.schedule_config_lookup.get(
                self.selected_schedule_label,
                str(self.task.get("manual_config_text", "{}")),
            )
        else:
            self.schedule_picker_items = []
            self.schedule_picker_lookup = {}
            self.schedule_config_lookup = {}
            self.selected_schedule_label = ""
            self.manual_config_text = "{}"

    def _load_task(self, task_id: str | None) -> None:
        payload = queries.get_task_detail_payload(task_id)
        self._apply_payload(payload)

    @rx.event
    def load_from_route(self) -> None:
        self._load_task(_route_param(self, "task_id"))

    @rx.event
    def select_task_label(self, label: str):
        task_id = self.task_picker_lookup.get(label, "")
        self.selected_task_label = label
        self._load_task(task_id)
        if task_id:
            return rx.redirect(f"/task_details/{task_id}")
        return rx.redirect("/task_details")

    @rx.event
    def select_schedule_label(self, label: str) -> None:
        self.selected_schedule_label = label
        self.manual_config_text = self.schedule_config_lookup.get(label, self.manual_config_text)

    @rx.event
    def set_manual_config_text(self, value: str) -> None:
        self.manual_config_text = value

    @rx.event
    def toggle_task(self) -> None:
        task_id = str(self.task.get("task_id", ""))
        if not task_id:
            self.status_message = "Task not found"
            self.status_tone = "red"
            return
        self.status_message = queries.toggle_task_status(task_id)
        self.status_tone = "green"
        self._load_task(task_id)

    @rx.event
    def ask_cancel_unstarted(self) -> None:
        self.show_cancel_modal = True

    @rx.event
    def close_cancel_unstarted(self) -> None:
        self.show_cancel_modal = False

    @rx.event
    def confirm_cancel_unstarted(self) -> None:
        task_id = str(self.task.get("task_id", ""))
        self.show_cancel_modal = False
        self.status_message = queries.cancel_unstarted_runs(task_id)
        self.status_tone = "green"
        self._load_task(task_id)

    @rx.event
    def create_manual_run(self) -> None:
        task_id = str(self.task.get("task_id", ""))
        schedule_id = self.schedule_picker_lookup.get(self.selected_schedule_label, "")
        message, _run_id = queries.create_manual_run(task_id, schedule_id, self.manual_config_text)
        self.status_message = message
        self.status_tone = "green" if "created" in message.lower() else "red"
        self._load_task(task_id)

    @rx.event
    def ask_delete_task(self) -> None:
        self.show_delete_modal = True

    @rx.event
    def close_delete_task(self) -> None:
        self.show_delete_modal = False

    @rx.event
    def confirm_delete_task(self):
        task_id = str(self.task.get("task_id", ""))
        self.show_delete_modal = False
        deleted, message = queries.delete_task(task_id)
        self.status_message = message
        self.status_tone = "green" if deleted else "red"
        if deleted:
            self._apply_payload(queries.get_task_detail_payload(None))
            return rx.redirect("/overview")
        self._load_task(task_id)


class RunDetailState(rx.State):
    task_picker_items: list[str] = []
    task_picker_lookup: dict[str, str] = {}
    selected_task_label: str = ""
    run_picker_items: list[str] = []
    run_picker_lookup: dict[str, str] = {}
    selected_run_label: str = ""
    exists: bool = False
    run: RunDetailPayload = _empty_run_detail_payload()
    show_full_output: bool = False
    show_cancel_modal: bool = False
    status_message: str = "Ready."
    status_tone: str = "blue"

    @rx.var
    def has_run(self) -> bool:
        return self.exists

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        task_items, task_lookup, _task_reverse, selected_task_label = _build_picker(
            payload.get("task_options", []),
            payload.get("selected_task_id", ""),
        )
        run_items, run_lookup, _run_reverse, selected_run_label = _build_picker(
            payload.get("run_options", []),
            payload.get("selected_run_id", ""),
        )
        self.task_picker_items = task_items
        self.task_picker_lookup = task_lookup
        self.selected_task_label = selected_task_label
        self.run_picker_items = run_items
        self.run_picker_lookup = run_lookup
        self.selected_run_label = selected_run_label
        self.exists = bool(payload.get("exists", False))
        self.run = payload.get("run") or _empty_run_detail_payload()
        self.show_full_output = False

    def _load_run(self, run_id: str | None) -> None:
        self._apply_payload(queries.get_run_detail_payload(run_id))

    @rx.event
    def load_from_route(self) -> None:
        self._load_run(_route_param(self, "run_id"))

    @rx.event
    def select_task_label(self, label: str):
        task_id = self.task_picker_lookup.get(label, "")
        self.selected_task_label = label
        run_options = queries.list_run_options(task_id)
        if not run_options:
            self.run_picker_items = []
            self.run_picker_lookup = {}
            self.selected_run_label = ""
            self.exists = False
            self.run = _empty_run_detail_payload()
            return rx.redirect("/run_details")
        next_run_id = str(run_options[0].get("value", ""))
        self._load_run(next_run_id)
        return rx.redirect(f"/run_details/{next_run_id}")

    @rx.event
    def select_run_label(self, label: str):
        run_id = self.run_picker_lookup.get(label, "")
        self.selected_run_label = label
        if run_id:
            self._load_run(run_id)
            return rx.redirect(f"/run_details/{run_id}")
        return rx.redirect("/run_details")

    @rx.event
    def refresh(self) -> None:
        run_id = str(self.run.get("run_id", ""))
        self._load_run(run_id)

    @rx.event
    def toggle_output_mode(self) -> None:
        self.show_full_output = not self.show_full_output

    @rx.event
    def ask_cancel_run(self) -> None:
        self.show_cancel_modal = True

    @rx.event
    def close_cancel_run(self) -> None:
        self.show_cancel_modal = False

    @rx.event
    def confirm_cancel_run(self) -> None:
        run_id = str(self.run.get("run_id", ""))
        self.show_cancel_modal = False
        self.status_message = queries.cancel_run(run_id)
        self.status_tone = "green"
        self._load_run(run_id)


class LogsState(rx.State):
    start_time_text: str = to_datetime_local(dt.now() - td(hours=6))
    end_time_text: str = to_datetime_local(dt.now())
    limit_text: str = "100"
    selected_sources: list[str] = ["All Sources"]
    source_filters: list[ToggleFilter] = [{"label": "All Sources", "active": True}]
    entries: list[LogEntry] = []
    last_refreshed: str = ""
    refresh_disabled: bool = False

    @rx.var
    def has_entries(self) -> bool:
        return len(self.entries) > 0

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        self.start_time_text = str(payload.get("start_time_text", self.start_time_text))
        self.end_time_text = str(payload.get("end_time_text", self.end_time_text))
        self.limit_text = str(payload.get("limit", self.limit_text))
        self.selected_sources = list(payload.get("selected_sources", ["All Sources"]))
        self.source_filters = [
            {"label": str(source), "active": str(source) in set(self.selected_sources)}
            for source in payload.get("all_sources", ["All Sources"])
        ]
        self.entries = list(payload.get("entries", []))
        self.last_refreshed = str(payload.get("last_refreshed", ""))
        self.refresh_disabled = bool(payload.get("refresh_disabled", False))

    def _load_payload(self) -> None:
        payload = queries.get_logs_payload(
            start_time_text=self.start_time_text,
            end_time_text=self.end_time_text,
            selected_sources=self.selected_sources,
            limit=max(_parse_int(self.limit_text, 100), 1),
        )
        self._apply_payload(payload)

    @rx.event
    def load(self) -> None:
        now_text = to_datetime_local(dt.now())
        if not self.end_time_text:
            self.end_time_text = now_text
        if not self.start_time_text:
            self.start_time_text = now_text
        self._load_payload()

    @rx.event
    def set_start_time_text(self, value: str) -> None:
        self.start_time_text = value

    @rx.event
    def set_end_time_text(self, value: str) -> None:
        self.end_time_text = value

    @rx.event
    def set_limit_text(self, value: str) -> None:
        self.limit_text = value

    @rx.event
    def toggle_source(self, source: str) -> None:
        if source == "All Sources":
            self.selected_sources = ["All Sources"]
        else:
            current = {value for value in self.selected_sources if value != "All Sources"}
            if source in current:
                current.remove(source)
            else:
                current.add(source)
            self.selected_sources = sorted(current) if current else ["All Sources"]
        self._load_payload()

    @rx.event
    def refresh(self) -> None:
        self._load_payload()

    @rx.event
    def set_now(self) -> None:
        self.end_time_text = to_datetime_local(dt.now())
        self._load_payload()


class KvdbState(rx.State):
    search_text: str = ""
    limit_text: str = "100"
    include_expired: bool = False
    entries: list[KvEntry] = []
    key_items: list[str] = []
    selected_key: str = ""
    key_input: str = ""
    value_text: str = ""
    value_mode: str = "json"
    expiry_minutes_text: str = "5"
    encryption_key: str = ""
    metadata: list[LabelValueItem] = [{"label": "Status", "value": "No entry selected."}]
    status_message: str = "Ready."
    status_tone: str = "blue"

    @rx.var
    def has_entries(self) -> bool:
        return len(self.entries) > 0

    def _apply_listing(self, payload: dict[str, Any]) -> None:
        self.entries = list(payload.get("entries", []))
        self.key_items = [str(option.get("value", "")) for option in payload.get("key_options", [])]
        self.status_message = str(payload.get("status_message", self.status_message))
        self.status_tone = str(payload.get("status_tone", self.status_tone))
        if self.selected_key and self.selected_key not in self.key_items:
            self.selected_key = ""

    @rx.event
    def load(self) -> None:
        payload = queries.get_kv_listing_payload(
            search_text=self.search_text,
            limit=max(_parse_int(self.limit_text, 100), 1),
            include_expired=self.include_expired,
        )
        self._apply_listing(payload)

    @rx.event
    def set_search_text(self, value: str) -> None:
        self.search_text = value

    @rx.event
    def set_limit_text(self, value: str) -> None:
        self.limit_text = value

    @rx.event
    def toggle_include_expired(self, checked: bool) -> None:
        self.include_expired = bool(checked)
        self.load()

    @rx.event
    def select_key(self, value: str) -> None:
        self.selected_key = value
        self.key_input = value

    @rx.event
    def set_key_input(self, value: str) -> None:
        self.key_input = value

    @rx.event
    def set_value_text(self, value: str) -> None:
        self.value_text = value

    @rx.event
    def set_value_mode(self, value: str) -> None:
        self.value_mode = value

    @rx.event
    def set_expiry_minutes_text(self, value: str) -> None:
        self.expiry_minutes_text = value

    @rx.event
    def set_encryption_key(self, value: str) -> None:
        self.encryption_key = value

    @rx.event
    def load_entry(self) -> None:
        result = queries.load_kv_entry(self.key_input, self.encryption_key)
        self.status_message = str(result.get("status_message", self.status_message))
        self.status_tone = str(result.get("status_tone", self.status_tone))
        self.metadata = list(result.get("metadata", self.metadata))
        if "value_text" in result:
            self.value_text = str(result.get("value_text", ""))
        if "value_mode" in result:
            self.value_mode = str(result.get("value_mode", self.value_mode))
        if "expiry_minutes" in result:
            expiry_minutes = result.get("expiry_minutes")
            self.expiry_minutes_text = "" if expiry_minutes in (None, "") else str(expiry_minutes)

    @rx.event
    def save_entry(self) -> None:
        result = queries.save_kv_entry(
            key=self.key_input,
            value_text=self.value_text,
            value_mode=self.value_mode,
            expiry_minutes=self.expiry_minutes_text,
            encryption_key=self.encryption_key,
        )
        self.status_message = str(result.get("status_message", self.status_message))
        self.status_tone = str(result.get("status_tone", self.status_tone))
        self.metadata = list(result.get("metadata", self.metadata))
        self.load()

    @rx.event
    def delete_entry(self) -> None:
        result = queries.delete_kv_entry(self.key_input)
        self.status_message = str(result.get("status_message", self.status_message))
        self.status_tone = str(result.get("status_tone", self.status_tone))
        self.metadata = list(result.get("metadata", self.metadata))
        if bool(result.get("ok", False)):
            self.value_text = ""
        self.load()


class LineageState(rx.State):
    task_filters: list[LineageTaskFilter] = []
    selected_task_ids: list[str] = []
    legend: list[LineageLegendItem] = []
    link_rows: list[LineageLinkRow] = []
    figure: go.Figure = go.Figure()

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        selected_ids = list(payload.get("selected_task_ids", []))
        self.selected_task_ids = selected_ids
        self.task_filters = [
            {
                "label": str(option.get("label", "")),
                "value": str(option.get("value", "")),
                "active": str(option.get("value", "")) in set(selected_ids),
            }
            for option in payload.get("task_options", [])
        ]
        self.legend = list(payload.get("legend", []))
        self.link_rows = list(payload.get("link_rows", []))
        self.figure = payload.get("figure", go.Figure())

    def _load_payload(self) -> None:
        self._apply_payload(queries.get_lineage_payload(self.selected_task_ids))

    @rx.event
    def load(self) -> None:
        if not self.selected_task_ids:
            self._apply_payload(queries.get_lineage_payload(None))
            return
        self._load_payload()

    @rx.event
    def toggle_task(self, task_id: str) -> None:
        current = list(self.selected_task_ids)
        if task_id in current:
            current = [value for value in current if value != task_id]
        else:
            current.append(task_id)
        self.selected_task_ids = current
        self._load_payload()

    @rx.event
    def select_all(self) -> None:
        self.selected_task_ids = [str(item.get("value", "")) for item in self.task_filters]
        self._load_payload()

    @rx.event
    def clear_all(self) -> None:
        self.selected_task_ids = []
        self._load_payload()


__all__ = [
    "KvdbState",
    "LineageState",
    "LogsState",
    "OverviewState",
    "RunDetailState",
    "TaskDetailState",
]