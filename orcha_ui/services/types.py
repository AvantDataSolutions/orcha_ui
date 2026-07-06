"""
Shared TypedDicts for the orcha_ui service/state layer.

Keeping types here breaks the potential circular import between
queries.py (which builds these structures) and app_state.py (which
consumes them as Reflex state vars).
"""
from __future__ import annotations

from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# Primitive / shared building blocks
# ---------------------------------------------------------------------------

class LabelValueItem(TypedDict):
    label: str
    value: str


class ToggleFilter(TypedDict):
    label: str
    active: bool


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


# ---------------------------------------------------------------------------
# Domain objects stored as Reflex state vars
# ---------------------------------------------------------------------------

class SchedulerSummary(TypedDict):
    started: str
    started_tone: str
    last_active: str
    last_active_tone: str


class OverviewSummary(TypedDict):
    """Health counts across the current lookback window (Overview header)."""
    failed: int
    warn: int
    running: int
    success: int


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
    highlight_error: bool
    highlight_disabled: bool
    failure_count: int
    running_count: int
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


class ThreadRow(TypedDict):
    name: str
    group: str
    state: str
    state_tone: str
    last_heartbeat: str
    last_tick: str
    interval: str
    restart_count: int
    error_count: int
    consecutive_errors: int
    last_error: str
    last_error_at: str


class ThreadInstanceGroup(TypedDict):
    instance_id: str
    online: bool
    status_label: str
    status_tone: str
    updated: str
    total: int
    unhealthy: int
    threads: list[ThreadRow]


class ThreadsQueryResult(TypedDict):
    instances: list[ThreadInstanceGroup]
    total_threads: int
    unhealthy_threads: int
    instance_count: int
    last_refreshed: str
    has_data: bool


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


# ---------------------------------------------------------------------------
# Query result envelopes  (what queries.py returns, what _apply_payload takes)
# ---------------------------------------------------------------------------

class OverviewQueryResult(TypedDict):
    hours: int
    end_time_text: str
    last_refreshed: str
    scheduler: SchedulerSummary
    overview_summary: OverviewSummary
    workspace_groups: list[WorkspaceGroup]
    available_tags: list[str]
    available_workspaces: list[str]
    selected_tags: list[str]
    selected_workspaces: list[str]
    show_disabled: bool
    display_start_label: str
    display_end_label: str


class TaskDetailQueryResult(TypedDict):
    exists: bool
    task_options: list[LabelValueItem]
    selected_task_id: str
    task: TaskDetailPayload | None


class RunDetailQueryResult(TypedDict):
    exists: bool
    task_options: list[LabelValueItem]
    selected_task_id: str
    run_options: list[LabelValueItem]
    selected_run_id: str
    run: RunDetailPayload | None


class LogsQueryResult(TypedDict):
    entries: list[LogEntry]
    all_sources: list[str]
    selected_sources: list[str]
    start_time_text: str
    end_time_text: str
    limit: int
    last_refreshed: str
    refresh_disabled: bool


class KvListingResult(TypedDict):
    entries: list[KvEntry]
    key_options: list[LabelValueItem]
    status_message: str
    status_tone: str


class _KvEntryResultBase(TypedDict):
    ok: bool
    status_message: str
    status_tone: str


class KvEntryResult(_KvEntryResultBase, total=False):
    """Fields always present via _KvEntryResultBase; optional fields below."""
    metadata: list[LabelValueItem]
    value_text: str
    value_mode: str
    expiry_minutes: float | None


class LineageQueryResult(TypedDict):
    selected_task_ids: list[str]
    task_options: list[LabelValueItem]
    task_workspaces: dict[str, str]
    available_workspaces: list[str]
    legend: list[LineageLegendItem]
    link_rows: list[LineageLinkRow]
    flow_nodes: list[dict[str, Any]]
    flow_edges: list[dict[str, Any]]
