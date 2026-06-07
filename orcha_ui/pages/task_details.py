from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import banner, detail_field, empty_state, overlay_panel, pre_block, section_card, tone_badge
from orcha_ui.components.layout import app_shell
from orcha_ui.components.run_slices import timeline_strip
from orcha_ui.state import TaskDetailState


def _task_field(field: dict) -> rx.Component:
    return rx.box(
        detail_field(field["label"], field["value"], field["tone"], field["code"]),
        flex="1",
        min_width="15rem",
    )


def _schedule_card(card: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text("Frequency", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.spacer(),
                tone_badge(card["frequency"], "blue"),
                width="100%",
            ),
            rx.text("Config", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
            pre_block(card["config_text"], min_height="8rem"),
            rx.text("Trigger Runs", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
            rx.flex(
                rx.foreach(card["trigger_runs"], lambda item: tone_badge(item, "slate")),
                wrap="wrap",
                gap="0.5rem",
                width="100%",
            ),
            spacing="3",
            align_items="stretch",
            width="100%",
        ),
        padding="1rem",
        border_radius="20px",
        border="1px solid rgba(148, 163, 184, 0.18)",
        background_color="rgba(255,255,255,0.92)",
        width="100%",
    )


def _history_row(row: dict) -> rx.Component:
    return rx.link(
        rx.box(
            rx.flex(
                rx.box(
                    rx.text(row["run_id"], weight="medium", color="#0f172a"),
                    rx.text(row["schedule"], size="2", color="#64748b"),
                    min_width="12rem",
                ),
                tone_badge(row["status"], row["status_tone"]),
                rx.box(rx.text(row["scheduled_time"], size="2", color="#475569"), min_width="12rem"),
                rx.box(rx.text(row["start_time"], size="2", color="#475569"), min_width="12rem"),
                rx.box(rx.text(row["end_time"], size="2", color="#475569"), min_width="12rem"),
                wrap="wrap",
                gap="1rem",
                width="100%",
                align="center",
            ),
            border="1px solid rgba(148, 163, 184, 0.18)",
            border_radius="18px",
            padding="0.9rem 1rem",
            background_color="rgba(255,255,255,0.85)",
            width="100%",
        ),
        href=row["href"],
        text_decoration="none",
        width="100%",
    )


def task_details_page() -> rx.Component:
    picker = section_card(
        rx.flex(
            rx.box(
                rx.text("Task", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.select(
                    TaskDetailState.task_picker_items,
                    value=TaskDetailState.selected_task_label,
                    on_change=TaskDetailState.select_task_label,
                    placeholder="Select a task",
                    width="100%",
                ),
                flex="1",
                min_width="22rem",
            ),
            wrap="wrap",
            gap="1rem",
            width="100%",
        ),
        title="Task Picker",
        subtitle="Choose the task to inspect and manage.",
    )

    details = rx.cond(
        TaskDetailState.has_task,
        rx.vstack(
            section_card(
                rx.flex(
                    rx.foreach(TaskDetailState.task["fields"], _task_field),
                    wrap="wrap",
                    gap="1rem",
                    width="100%",
                ),
                title=TaskDetailState.task["name"],
                subtitle=TaskDetailState.task["description"],
                actions=rx.hstack(
                    rx.button(TaskDetailState.task["toggle_label"], on_click=TaskDetailState.toggle_task, color_scheme="cyan"),
                    rx.button("Cancel Unstarted", on_click=TaskDetailState.ask_cancel_unstarted, variant="soft", color_scheme="amber"),
                    rx.button("Delete Task", on_click=TaskDetailState.ask_delete_task, color_scheme="red"),
                    spacing="3",
                ),
            ),
            section_card(
                rx.cond(
                    TaskDetailState.task["schedule_cards"],
                    rx.flex(
                        rx.foreach(TaskDetailState.task["schedule_cards"], _schedule_card),
                        wrap="wrap",
                        gap="1rem",
                        width="100%",
                    ),
                    empty_state("No Schedules", "This task only supports manual or trigger-based runs."),
                ),
                title="Schedules",
                subtitle="Configured schedules and trigger dependencies for the selected task.",
            ),
            section_card(
                rx.flex(
                    rx.box(
                        rx.text("Schedule", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                        rx.select(
                            TaskDetailState.schedule_picker_items,
                            value=TaskDetailState.selected_schedule_label,
                            on_change=TaskDetailState.select_schedule_label,
                            placeholder="Select a schedule",
                            width="100%",
                        ),
                        flex="1",
                        min_width="20rem",
                    ),
                    rx.box(
                        rx.text("Actions", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                        rx.hstack(
                            rx.button("Create Manual Run", on_click=TaskDetailState.create_manual_run, color_scheme="cyan"),
                            rx.link(
                                rx.button("Open Current Task", variant="soft", color_scheme="gray"),
                                href=TaskDetailState.task["task_href"],
                                text_decoration="none",
                            ),
                            spacing="3",
                        ),
                    ),
                    wrap="wrap",
                    gap="1rem",
                    width="100%",
                ),
                rx.text_area(
                    value=TaskDetailState.manual_config_text,
                    on_change=TaskDetailState.set_manual_config_text,
                    min_height="18rem",
                    resize="vertical",
                    width="100%",
                ),
                title="Manual Run",
                subtitle="Review or override the schedule config before creating a manual run.",
            ),
            section_card(
                timeline_strip(TaskDetailState.task["recent_runs_timeline"]),
                title="Recent Runs",
                subtitle="Run activity across the last two days for the selected task.",
            ),
            section_card(
                rx.box(
                    rx.vstack(
                        rx.foreach(TaskDetailState.task["run_history_rows"], _history_row),
                        spacing="3",
                        width="100%",
                        align_items="stretch",
                    ),
                    max_height="34rem",
                    overflow="auto",
                    width="100%",
                ),
                title="Run History",
                subtitle="Recent run records with direct navigation into run details.",
            ),
            spacing="5",
            width="100%",
            align_items="stretch",
        ),
        empty_state("No Task Selected", "Choose a task from the picker to inspect its configuration and run history."),
    )

    content = rx.vstack(
        overlay_panel(
            is_open=TaskDetailState.show_cancel_modal,
            title="Cancel Unstarted Runs",
            body=rx.text("Cancel every queued run for the currently selected task?", color="#475569"),
            confirm_label="Cancel Runs",
            confirm_color="amber",
            on_confirm=TaskDetailState.confirm_cancel_unstarted,
            on_cancel=TaskDetailState.close_cancel_unstarted,
        ),
        overlay_panel(
            is_open=TaskDetailState.show_delete_modal,
            title="Delete Task",
            body=rx.vstack(
                rx.text("This permanently deletes the selected task and its run data.", color="#475569"),
                rx.text("Log records remain intact.", color="#64748b", size="2"),
                spacing="2",
                align_items="start",
            ),
            confirm_label="Delete Task",
            confirm_color="red",
            on_confirm=TaskDetailState.confirm_delete_task,
            on_cancel=TaskDetailState.close_delete_task,
        ),
        picker,
        banner(TaskDetailState.status_message, TaskDetailState.status_tone),
        details,
        spacing="5",
        width="100%",
        align_items="stretch",
    )
    return app_shell(
        active_route="/task_details",
        page_title="Task Details",
        page_description="Inspect task configuration, schedules, run history, and task-level operational actions.",
        content=content,
    )


__all__ = ["task_details_page"]