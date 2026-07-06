from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import detail_field, empty_state, overlay_panel, pre_block, section_card, tone_badge
from orcha_ui.components.layout import app_shell
from orcha_ui.state import RunDetailState


def _run_field(field: dict) -> rx.Component:
    return rx.box(
        detail_field(field["label"], field["value"], field["tone"], field["code"]),
        flex="1",
        min_width="15rem",
    )


def run_details_page() -> rx.Component:
    picker = section_card(
        rx.flex(
            rx.box(
                rx.text("Task", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.select(
                    RunDetailState.task_picker_items,
                    value=RunDetailState.selected_task_label,
                    on_change=RunDetailState.select_task_label,
                    placeholder="Select a task",
                    width="100%",
                ),
                flex="1",
                min_width="20rem",
            ),
            rx.box(
                rx.text("Run", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.select(
                    RunDetailState.run_picker_items,
                    value=RunDetailState.selected_run_label,
                    on_change=RunDetailState.select_run_label,
                    placeholder="Select a run",
                    width="100%",
                ),
                flex="1",
                min_width="24rem",
            ),
            wrap="wrap",
            gap="1rem",
            width="100%",
        ),
        title="Run Picker",
        subtitle="Navigate between tasks and runs without leaving the detail context.",
    )

    details = rx.cond(
        RunDetailState.has_run,
        rx.vstack(
            rx.box(
                rx.box(
                    section_card(
                        rx.flex(
                            rx.foreach(RunDetailState.run["fields"], _run_field),
                            wrap="wrap",
                            gap="1rem",
                            width="100%",
                        ),
                        title=RunDetailState.run["task_name"],
                        actions=rx.hstack(
                            tone_badge(RunDetailState.run["task_status"], RunDetailState.run["task_status_tone"]),
                            rx.link(
                                rx.button("Open Task", color_scheme="cyan", size="2"),
                                href=RunDetailState.run["task_href"],
                                text_decoration="none",
                            ),
                            rx.cond(
                                RunDetailState.run["triggered_run_href"] != "",
                                rx.link(
                                    rx.button("Open Triggered Run", variant="soft", color_scheme="gray", size="2"),
                                    href=RunDetailState.run["triggered_run_href"],
                                    text_decoration="none",
                                ),
                                rx.fragment(),
                            ),
                            spacing="2",
                            align="center",
                        ),
                    ),
                    min_width="0",
                    width="100%",
                ),
                rx.box(
                    section_card(
                        pre_block(RunDetailState.run["config_text"], min_height="12rem"),
                        title="Config",
                        subtitle="Resolved config captured on the run record.",
                    ),
                    min_width="0",
                    width="100%",
                ),
                display="grid",
                grid_template_columns=rx.breakpoints(initial="minmax(0, 1fr)", xl="minmax(0, 2fr) minmax(0, 1fr)"),
                gap="1rem",
                width="100%",
                align_items="start",
            ),
            section_card(
                rx.hstack(
                    rx.button(
                        rx.cond(RunDetailState.show_full_output, "View Summarised", "View Full Output"),
                        on_click=RunDetailState.toggle_output_mode,
                        color_scheme="cyan",
                        variant="soft",
                    ),
                    spacing="3",
                ),
                rx.cond(
                    RunDetailState.show_full_output,
                    pre_block(RunDetailState.run["full_output"], min_height="18rem"),
                    pre_block(RunDetailState.run["summarised_output"], min_height="18rem"),
                ),
                title="Output",
                subtitle="Switch between the summarised output and the full run payload.",
            ),
            spacing="3",
            width="100%",
            align_items="stretch",
        ),
        empty_state("No Run Selected", "Choose a task and run to inspect the execution details and output."),
    )

    content = rx.vstack(
        overlay_panel(
            is_open=RunDetailState.show_cancel_modal,
            title="Cancel Run",
            body=rx.text("Cancel the currently selected run and mark it complete?", color="#475569"),
            confirm_label="Cancel Run",
            confirm_color="amber",
            on_confirm=RunDetailState.confirm_cancel_run,
            on_cancel=RunDetailState.close_cancel_run,
        ),
        picker,
        details,
        spacing="3",
        width="100%",
        align_items="stretch",
    )
    actions = rx.hstack(
        rx.button("Refresh", on_click=RunDetailState.refresh, color_scheme="cyan", size="2"),
        rx.cond(
            RunDetailState.run["can_cancel"],
            rx.button(
                "Cancel Run",
                on_click=RunDetailState.ask_cancel_run,
                color_scheme="amber",
                variant="soft",
                size="2",
            ),
            rx.fragment(),
        ),
        spacing="2",
    )
    return app_shell(
        active_route="/run_details",
        page_title="Run Details",
        page_description="Inspect a single run, jump to its task, and review the resolved output payload.",
        content=content,
        actions=actions,
    )


__all__ = ["run_details_page"]