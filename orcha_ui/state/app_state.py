from __future__ import annotations

from datetime import datetime as dt, timedelta as td
from typing import Any

import reflex as rx

from orcha_ui.services import queries
from orcha_ui.services.formatting import to_datetime_local
from orcha_ui.services.types import (
    KvEntry,
    KvEntryResult,
    KvListingResult,
    LabelValueItem,
    LineageLegendItem,
    LineageLinkRow,
    LineageQueryResult,
    LineageTaskFilter,
    LogEntry,
    LogsQueryResult,
    OverviewQueryResult,
    RunDetailPayload,
    RunDetailQueryResult,
    RunSliceData,
    SchedulerSummary,
    TaskDetailPayload,
    TaskDetailQueryResult,
    ToggleFilter,
    WorkspaceGroup,
)


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


def _build_picker(
    options: list[LabelValueItem],
    selected_value: str | None,
) -> tuple[list[str], dict[str, str], dict[str, str], str]:
    items: list[str] = []
    lookup: dict[str, str] = {}
    reverse_lookup: dict[str, str] = {}
    selected_label = ""
    selected_text = str(selected_value or "")
    for option in options:
        label = option["label"]
        value = option["value"]
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

    def _apply_payload(self, payload: OverviewQueryResult) -> None:
        self.last_refreshed = payload["last_refreshed"]
        self.display_start_label = payload["display_start_label"]
        self.display_end_label = payload["display_end_label"]
        self.scheduler = payload["scheduler"]
        self.workspace_groups = payload["workspace_groups"]
        self.selected_tags = payload["selected_tags"]
        self.selected_workspaces = payload["selected_workspaces"]
        self.hours_text = str(payload["hours"])
        self.end_time_text = payload["end_time_text"]
        selected_tag_set = set(self.selected_tags)
        self.tag_filters = [
            {"label": tag, "active": tag in selected_tag_set}
            for tag in payload["available_tags"]
        ]
        selected_workspace_set = set(self.selected_workspaces)
        self.workspace_filters = [
            {"label": workspace, "active": workspace in selected_workspace_set}
            for workspace in payload["available_workspaces"]
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

    def _apply_payload(self, payload: TaskDetailQueryResult) -> None:
        items, lookup, _reverse, selected_label = _build_picker(
            payload["task_options"],  # type: ignore[arg-type]
            payload["selected_task_id"],
        )
        self.task_picker_items = items
        self.task_picker_lookup = lookup
        self.selected_task_label = selected_label
        self.exists = payload["exists"]
        self.task = payload["task"] or _empty_task_detail_payload()
        if self.exists:
            schedule_options = self.task["schedule_options"]
            schedule_items, schedule_lookup, _schedule_reverse, selected_schedule_label = _build_picker(
                schedule_options,  # type: ignore[arg-type]
                self.task["default_schedule_value"],
            )
            self.schedule_picker_items = schedule_items
            self.schedule_picker_lookup = schedule_lookup
            self.selected_schedule_label = selected_schedule_label
            self.schedule_config_lookup = {
                option["label"]: option["config_text"]
                for option in schedule_options
            }
            self.manual_config_text = self.schedule_config_lookup.get(
                self.selected_schedule_label,
                self.task["manual_config_text"],
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
        self.status_message = "Ready."
        self.status_tone = "blue"
        self._load_task(_route_param(self, "task_id"))

    @rx.event
    def select_task_label(self, label: str) -> None:
        task_id = self.task_picker_lookup.get(label, "")
        self.selected_task_label = label
        self.status_message = "Ready."
        self.status_tone = "blue"
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
        task_id = str(self.task["task_id"])
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
        task_id = str(self.task["task_id"])
        self.show_cancel_modal = False
        self.status_message = queries.cancel_unstarted_runs(task_id)
        self.status_tone = "green"
        self._load_task(task_id)

    @rx.event
    def create_manual_run(self) -> None:
        task_id = str(self.task["task_id"])
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
    def confirm_delete_task(self) -> None:
        task_id = str(self.task["task_id"])
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

    def _apply_payload(self, payload: RunDetailQueryResult) -> None:
        task_items, task_lookup, _task_reverse, selected_task_label = _build_picker(
            payload["task_options"],  # type: ignore[arg-type]
            payload["selected_task_id"],
        )
        run_items, run_lookup, _run_reverse, selected_run_label = _build_picker(
            payload["run_options"],  # type: ignore[arg-type]
            payload["selected_run_id"],
        )
        self.task_picker_items = task_items
        self.task_picker_lookup = task_lookup
        self.selected_task_label = selected_task_label
        self.run_picker_items = run_items
        self.run_picker_lookup = run_lookup
        self.selected_run_label = selected_run_label
        self.exists = payload["exists"]
        self.run = payload["run"] or _empty_run_detail_payload()
        self.show_full_output = False

    def _load_run(self, run_id: str | None) -> None:
        self._apply_payload(queries.get_run_detail_payload(run_id))

    @rx.event
    def load_from_route(self) -> None:
        self.status_message = "Ready."
        self.status_tone = "blue"
        self._load_run(_route_param(self, "run_id"))

    @rx.event
    def select_task_label(self, label: str) -> None:
        task_id = self.task_picker_lookup.get(label, "")
        self.selected_task_label = label
        self.status_message = "Ready."
        self.status_tone = "blue"
        run_options = queries.list_run_options(task_id)
        if not run_options:
            self.run_picker_items = []
            self.run_picker_lookup = {}
            self.selected_run_label = ""
            self.exists = False
            self.run = _empty_run_detail_payload()
            return rx.redirect("/run_details")
        next_run_id = run_options[0]["value"]
        self._load_run(next_run_id)
        return rx.redirect(f"/run_details/{next_run_id}")

    @rx.event
    def select_run_label(self, label: str) -> None:
        run_id = self.run_picker_lookup.get(label, "")
        self.selected_run_label = label
        self.status_message = "Ready."
        self.status_tone = "blue"
        if run_id:
            self._load_run(run_id)
            return rx.redirect(f"/run_details/{run_id}")
        return rx.redirect("/run_details")

    @rx.event
    def refresh(self) -> None:
        run_id = str(self.run["run_id"])
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
        run_id = str(self.run["run_id"])
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

    def _apply_payload(self, payload: LogsQueryResult) -> None:
        self.start_time_text = payload["start_time_text"]
        self.end_time_text = payload["end_time_text"]
        self.limit_text = str(payload["limit"])
        self.selected_sources = payload["selected_sources"]
        selected_set = set(self.selected_sources)
        self.source_filters = [
            {"label": source, "active": source in selected_set}
            for source in payload["all_sources"]
        ]
        self.entries = payload["entries"]
        self.last_refreshed = payload["last_refreshed"]
        self.refresh_disabled = payload["refresh_disabled"]

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

    def _apply_listing(self, payload: KvListingResult) -> None:
        self.entries = payload["entries"]
        self.key_items = [option["value"] for option in payload["key_options"]]
        self.status_message = payload["status_message"]
        self.status_tone = payload["status_tone"]
        if self.selected_key and self.selected_key not in self.key_items:
            self.selected_key = ""

    def _apply_entry_result(self, result: KvEntryResult) -> None:
        self.status_message = result["status_message"]
        self.status_tone = result["status_tone"]
        if "metadata" in result:
            self.metadata = result["metadata"]  # type: ignore[assignment]
        if "value_text" in result:
            self.value_text = str(result["value_text"])
        if "value_mode" in result:
            self.value_mode = str(result["value_mode"])
        if "expiry_minutes" in result:
            expiry = result["expiry_minutes"]
            self.expiry_minutes_text = "" if expiry in (None, "") else str(expiry)

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
        self._apply_entry_result(result)

    @rx.event
    def save_entry(self) -> None:
        result = queries.save_kv_entry(
            key=self.key_input,
            value_text=self.value_text,
            value_mode=self.value_mode,
            expiry_minutes=self.expiry_minutes_text,
            encryption_key=self.encryption_key,
        )
        self._apply_entry_result(result)
        self.load()

    @rx.event
    def delete_entry(self) -> None:
        result = queries.delete_kv_entry(self.key_input)
        self._apply_entry_result(result)
        if result["ok"]:
            self.value_text = ""
        self.load()


class LineageState(rx.State):
    task_filters: list[LineageTaskFilter] = []
    selected_task_ids: list[str] = []
    legend: list[LineageLegendItem] = []
    link_rows: list[LineageLinkRow] = []
    flow_nodes: list[dict] = []
    flow_edges: list[dict] = []
    base_flow_nodes: list[dict] = []
    base_flow_edges: list[dict] = []
    focused_task: str = ""
    pinned_task: str = ""

    @rx.var
    def has_flow(self) -> bool:
        return len(self.flow_nodes) > 0

    def _restyle(self) -> None:
        self.flow_nodes, self.flow_edges = queries.apply_lineage_focus(
            self.base_flow_nodes, self.base_flow_edges, self.focused_task
        )

    def _apply_payload(self, payload: LineageQueryResult) -> None:
        selected_ids = payload["selected_task_ids"]
        self.selected_task_ids = selected_ids
        selected_set = set(selected_ids)
        self.task_filters = [
            {
                "label": option["label"],
                "value": option["value"],
                "active": option["value"] in selected_set,
            }
            for option in payload["task_options"]
        ]
        self.legend = payload["legend"]
        self.link_rows = payload["link_rows"]
        self.base_flow_nodes = payload["flow_nodes"]
        self.base_flow_edges = payload["flow_edges"]
        # Drop any focus/pin that no longer maps to a visible task, then restyle.
        available = {item["task_id"] for item in self.legend}
        if self.pinned_task not in available:
            self.pinned_task = ""
        if self.focused_task not in available:
            self.focused_task = ""
        self._restyle()

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
        self.selected_task_ids = [item["value"] for item in self.task_filters]
        self._load_payload()

    @rx.event
    def clear_all(self) -> None:
        self.selected_task_ids = []
        self._load_payload()

    @rx.event
    def hover_task(self, task_id: str) -> None:
        # Hover only previews a highlight; a pinned task keeps precedence.
        if self.pinned_task:
            return
        if self.focused_task != task_id:
            self.focused_task = task_id
            self._restyle()

    @rx.event
    def unhover_task(self) -> None:
        if self.pinned_task:
            return
        if self.focused_task:
            self.focused_task = ""
            self._restyle()

    @rx.event
    def toggle_pin_task(self, task_id: str) -> None:
        # Click to lock a task's highlight on; click again (or the focused node)
        # to release it.
        if self.pinned_task == task_id:
            self.pinned_task = ""
            self.focused_task = ""
        else:
            self.pinned_task = task_id
            self.focused_task = task_id
        self._restyle()

    @rx.event
    def clear_focus(self) -> None:
        self.pinned_task = ""
        self.focused_task = ""
        self._restyle()


__all__ = [
    "KvdbState",
    "LineageState",
    "LogsState",
    "OverviewState",
    "RunDetailState",
    "TaskDetailState",
]
