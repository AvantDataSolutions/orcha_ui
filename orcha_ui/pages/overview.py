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
    summary = OverviewState.overview_summary
    return section_card(
        rx.box(
            metric("Failed", summary["failed"], rx.cond(summary["failed"] > 0, "alert", "slate")),
            metric("Warn", summary["warn"], rx.cond(summary["warn"] > 0, "amber", "slate")),
            metric("Running", summary["running"], rx.cond(summary["running"] > 0, "purple", "slate")),
            metric("Succeeded", summary["success"], rx.cond(summary["success"] > 0, "green", "slate")),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(6.5rem, 1fr))",
            gap="0.65rem",
            width="100%",
        ),
        rx.box(
            metric("Started", OverviewState.scheduler["started"], OverviewState.scheduler["started_tone"]),
            metric("Last Active", OverviewState.scheduler["last_active"], OverviewState.scheduler["last_active_tone"]),
            metric("Last Refreshed", OverviewState.last_refreshed, "slate"),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(8.5rem, 1fr))",
            gap="0.65rem",
            width="100%",
        ),
        title="Scheduler & Health",
        subtitle="Run outcomes in window · scheduler heartbeat.",
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
                rx.vstack(
                    rx.checkbox(
                        "Failures only",
                        checked=OverviewState.failures_only,
                        on_change=OverviewState.toggle_failures_only,
                    ),
                    rx.checkbox(
                        "Show disabled tasks",
                        checked=OverviewState.show_disabled,
                        on_change=OverviewState.toggle_show_disabled,
                    ),
                    spacing="1",
                    align_items="start",
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


def _status_badge(card: dict) -> rx.Component:
    # "enabled" is the normal state and shouldn't compete for attention — render it
    # as quiet muted text so only abnormal statuses (error/disabled/inactive) pop.
    return rx.cond(
        card["status"] == "enabled",
        rx.text("enabled", size="1", color="#94a3b8"),
        tone_badge(card["status"], card["status_tone"]),
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
                _status_badge(card),
                width="100%",
                align="center",
                spacing="2",
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
        border_radius="14px",
        border=rx.cond(
            card["highlight_error"],
            "1px solid rgba(220, 38, 38, 0.55)",
            rx.cond(card["highlight_disabled"], "1px solid rgba(100, 116, 139, 0.55)", "1px solid rgba(148, 163, 184, 0.28)"),
        ),
        border_left=rx.cond(
            card["highlight_error"],
            "4px solid #dc2626",
            rx.cond(card["highlight_disabled"], "4px solid #475569", "4px solid transparent"),
        ),
        background_color=rx.cond(
            card["highlight_error"],
            "rgba(254, 226, 226, 0.85)",
            rx.cond(card["highlight_disabled"], "rgba(241, 245, 249, 0.9)", "#ffffff"),
        ),
        box_shadow="0 2px 8px rgba(15, 23, 42, 0.08)",
        opacity=rx.cond(card["highlight_disabled"], "0.75", "1"),
    )


def _workspace_group(group: dict) -> rx.Component:
    # No white panel wrapper here — task cards are white and sit directly on the
    # blue page background so each card reads as a distinct, elevated card.
    return rx.vstack(
        rx.heading(group["workspace"], size="4", color="#0f172a"),
        rx.box(
            rx.foreach(group["task_cards"], _task_card),
            display="grid",
            grid_template_columns="repeat(auto-fill, minmax(21.5rem, 1fr))",
            gap="0.9rem",
            width="100%",
        ),
        spacing="2",
        width="100%",
        align_items="stretch",
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
            OverviewState.is_loading,
            rx.center(
                rx.spinner(size="3"),
                width="100%",
                min_height="8rem",
                padding="2rem",
            ),
            rx.cond(
                OverviewState.has_workspace_groups,
                rx.vstack(
                    rx.foreach(OverviewState.workspace_groups, _workspace_group),
                    spacing="3",
                    width="100%",
                    align_items="stretch",
                ),
                empty_state("No Tasks Found", "No tasks matched the current overview filters."),
            ),
        ),
        spacing="3",
        width="100%",
        align_items="stretch",
    )
    actions = rx.hstack(
        rx.button("Now", on_click=OverviewState.set_now, color_scheme="cyan", size="2"),
        rx.button("Refresh", on_click=OverviewState.refresh, variant="soft", color_scheme="gray", size="2"),
        spacing="2",
    )
    return app_shell(
        active_route="/overview",
        page_title="Overview",
        page_description="Operational snapshot of scheduler health, task activity, and recent run timelines.",
        content=content,
        actions=actions,
    )


__all__ = ["overview_page"]