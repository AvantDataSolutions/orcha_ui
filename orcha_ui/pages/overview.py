import reflex as rx

from orcha_ui.components.common import empty_state, filter_chip, metric, section_card, tone_badge
from orcha_ui.components.layout import app_shell
from orcha_ui.components.run_slices import compact_run_strip
from orcha_ui.state import OverviewState


def _control(label: str, component: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
        component,
        spacing="1",
        align_items="start",
        min_width="8.75rem",
    )


def _scheduler_card() -> rx.Component:
    return section_card(
        rx.box(
            metric("Started", OverviewState.scheduler["started"], OverviewState.scheduler["started_tone"]),
            metric("Last Active", OverviewState.scheduler["last_active"], OverviewState.scheduler["last_active_tone"]),
            metric("Last Refreshed", OverviewState.last_refreshed, "slate"),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(8.5rem, 1fr))",
            gap="0.65rem",
            width="100%",
        ),
        title="Scheduler",
        subtitle="Heartbeat and freshness.",
    )


def _filters_card() -> rx.Component:
    return section_card(
        rx.box(
            _control(
                "End Time",
                rx.input(
                    value=OverviewState.end_time_text,
                    on_change=OverviewState.set_end_time_text,
                    type="datetime-local",
                    width="100%",
                ),
            ),
            _control(
                "View Hours",
                rx.input(
                    value=OverviewState.hours_text,
                    on_change=OverviewState.set_hours_text,
                    type="number",
                    width="6.5rem",
                ),
            ),
            _control(
                "Flags",
                rx.checkbox(
                    "Show disabled tasks",
                    checked=OverviewState.show_disabled,
                    on_change=OverviewState.toggle_show_disabled,
                ),
            ),
            _control(
                "Actions",
                rx.hstack(
                    rx.button("Now", on_click=OverviewState.set_now, color_scheme="cyan", size="2"),
                    rx.button("Refresh", on_click=OverviewState.refresh, variant="soft", color_scheme="gray", size="2"),
                    spacing="1",
                ),
            ),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(9.5rem, 1fr))",
            gap="0.75rem",
            width="100%",
        ),
        rx.box(
            rx.vstack(
                rx.text("Task Types", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.flex(
                    rx.foreach(
                        OverviewState.tag_filters,
                        lambda item: filter_chip(item["label"], item["active"], OverviewState.toggle_tag(item["label"])),
                    ),
                    wrap="wrap",
                    gap="0.45rem",
                    width="100%",
                ),
                spacing="1",
                width="100%",
                align_items="stretch",
            ),
            rx.vstack(
                rx.text("Workspaces", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.flex(
                    rx.foreach(
                        OverviewState.workspace_filters,
                        lambda item: filter_chip(item["label"], item["active"], OverviewState.toggle_workspace(item["label"])),
                    ),
                    wrap="wrap",
                    gap="0.45rem",
                    width="100%",
                ),
                spacing="1",
                width="100%",
                align_items="stretch",
            ),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(16rem, 1fr))",
            gap="0.75rem",
            width="100%",
        ),
        title="Filters",
        subtitle="Lookback window and active slices.",
    )


def _task_strip(label: str, content: rx.Component) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(label, size="2", color="#64748b", margin="0", line_height="1.1"),
            rx.box(content, width="100%"),
            spacing="0",
            width="100%",
            align_items="stretch",
        ),
        width="100%",
    )


def _task_card(card: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.link(
                    rx.heading(card["name"], size="4", color="#0f172a"),
                    href=card["task_href"],
                    text_decoration="none",
                ),
                rx.spacer(),
                tone_badge(card["status"], card["status_tone"]),
                width="100%",
                align="center",
            ),
            rx.text(card["description"], color="#475569", size="2"),
            rx.box(
                metric("Last Active", card["last_active"], card["last_active_tone"]),
                metric("Last Run", card["last_run"], "slate"),
                metric("Next Scheduled", card["next_scheduled"], "blue"),
                display="grid",
                grid_template_columns="repeat(auto-fit, minmax(9.5rem, 1fr))",
                gap="0.75rem",
                width="100%",
            ),
            rx.box(
                _task_strip("Active Runs", compact_run_strip(card["active_runs"])),
                _task_strip("Recent Runs", compact_run_strip(card["recent_runs"])),
                display="grid",
                grid_template_columns="repeat(auto-fit, minmax(13rem, 1fr))",
                gap="0.75rem",
                width="100%",
            ),
            spacing="1",
            align_items="stretch",
            width="100%",
        ),
        width="100%",
        padding="0.75rem 0.85rem",
        border_radius="18px",
        border=rx.cond(card["highlight_error"], "1px solid rgba(220, 38, 38, 0.22)", "1px solid rgba(148, 163, 184, 0.18)"),
        background_color=rx.cond(card["highlight_error"], "rgba(254, 242, 242, 0.7)", "rgba(255, 255, 255, 0.92)"),
        opacity=rx.cond(card["dimmed"], "0.68", "1"),
    )


def _workspace_group(group: dict) -> rx.Component:
    return section_card(
        rx.box(
            rx.foreach(group["task_cards"], _task_card),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(21.5rem, 1fr))",
            gap="0.9rem",
            width="100%",
        ),
        title=group["workspace"],
        subtitle="Tasks grouped by workspace.",
    )


def overview_page() -> rx.Component:
    content = rx.vstack(
        rx.flex(
            rx.box(_filters_card(), flex="2 1 38rem", min_width="20rem", width="100%"),
            rx.box(_scheduler_card(), flex="1 1 20rem", min_width="18rem", width="100%"),
            wrap="wrap",
            gap="0.9rem",
            width="100%",
            align="stretch",
        ),
        rx.cond(
            OverviewState.has_workspace_groups,
            rx.vstack(
                rx.foreach(OverviewState.workspace_groups, _workspace_group),
                spacing="4",
                width="100%",
                align_items="stretch",
            ),
            empty_state("No Tasks Found", "No tasks matched the current overview filters."),
        ),
        spacing="4",
        width="100%",
        align_items="stretch",
    )
    return app_shell(
        active_route="/overview",
        page_title="Overview",
        page_description="Operational snapshot of scheduler health, task activity, and recent run timelines.",
        content=content,
    )


__all__ = ["overview_page"]