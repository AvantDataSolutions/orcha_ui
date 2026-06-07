from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import empty_state, filter_chip, metric, section_card, tone_badge
from orcha_ui.components.layout import app_shell
from orcha_ui.state import LogsState


def _control(label: str, component: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
        component,
        spacing="2",
        align_items="start",
        min_width="12rem",
    )


def _log_entry(entry: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(entry["created"], size="2", color="#64748b"),
                rx.spacer(),
                tone_badge(entry["source"], "slate"),
                tone_badge(entry["category"], "blue"),
                tone_badge(entry["actor"], "purple"),
                width="100%",
                align="center",
            ),
            rx.text(entry["text"], color="#0f172a", size="3"),
            rx.box(
                rx.text(entry["json"], margin="0", white_space="pre-wrap", font_family="'IBM Plex Mono', monospace", font_size="0.78rem"),
                border_radius="16px",
                background_color="#f8fafc",
                border="1px solid rgba(148, 163, 184, 0.18)",
                padding="0.85rem",
                width="100%",
                overflow_x="auto",
            ),
            spacing="3",
            align_items="stretch",
            width="100%",
        ),
        width="100%",
        padding="1rem",
        border_radius="20px",
        border="1px solid rgba(148, 163, 184, 0.18)",
        background_color="rgba(255,255,255,0.9)",
    )


def logs_page() -> rx.Component:
    content = rx.vstack(
        section_card(
            rx.flex(
                _control(
                    "Start",
                    rx.input(
                        value=LogsState.start_time_text,
                        on_change=LogsState.set_start_time_text,
                        type="datetime-local",
                        width="100%",
                    ),
                ),
                _control(
                    "End",
                    rx.input(
                        value=LogsState.end_time_text,
                        on_change=LogsState.set_end_time_text,
                        type="datetime-local",
                        width="100%",
                    ),
                ),
                _control(
                    "Limit",
                    rx.input(
                        value=LogsState.limit_text,
                        on_change=LogsState.set_limit_text,
                        type="number",
                        width="8rem",
                    ),
                ),
                _control(
                    "Actions",
                    rx.hstack(
                        rx.button("Now", on_click=LogsState.set_now, color_scheme="cyan"),
                        rx.button("Refresh", on_click=LogsState.refresh, variant="soft", color_scheme="gray"),
                        spacing="3",
                    ),
                ),
                wrap="wrap",
                gap="1rem",
                width="100%",
            ),
            rx.flex(
                metric("Last Refreshed", LogsState.last_refreshed, "slate"),
                metric("Refresh Mode", rx.cond(LogsState.refresh_disabled, "Static End Time", "Live Window"), rx.cond(LogsState.refresh_disabled, "amber", "green")),
                wrap="wrap",
                gap="1rem",
                width="100%",
            ),
            rx.vstack(
                rx.text("Sources", size="2", color="#64748b", text_transform="uppercase", letter_spacing="0.06em"),
                rx.flex(
                    rx.foreach(
                        LogsState.source_filters,
                        lambda item: filter_chip(item["label"], item["active"], LogsState.toggle_source(item["label"])),
                    ),
                    wrap="wrap",
                    gap="0.65rem",
                    width="100%",
                ),
                spacing="2",
                align_items="stretch",
                width="100%",
            ),
            title="Log Filters",
            subtitle="Filter the operational log stream by time window, source, and record count.",
        ),
        rx.cond(
            LogsState.has_entries,
            section_card(
                rx.box(
                    rx.vstack(
                        rx.foreach(LogsState.entries, _log_entry),
                        spacing="3",
                        width="100%",
                        align_items="stretch",
                    ),
                    max_height="42rem",
                    overflow="auto",
                    width="100%",
                ),
                title="Entries",
                subtitle="Recent log records matching the current filters.",
            ),
            empty_state("No Logs Found", "No log records matched the selected time range and source filters."),
        ),
        spacing="5",
        width="100%",
        align_items="stretch",
    )
    return app_shell(
        active_route="/logs",
        page_title="Logs",
        page_description="Operational log explorer with source filtering and explicit time-window control.",
        content=content,
    )


__all__ = ["logs_page"]