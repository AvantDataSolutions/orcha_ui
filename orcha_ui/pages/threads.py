from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import empty_state, metric, section_card, tone_badge
from orcha_ui.components.layout import app_shell
from orcha_ui.state import ThreadsState


def _summary_card() -> rx.Component:
    return section_card(
        rx.box(
            metric("Instances", ThreadsState.instance_count, "slate"),
            metric("Threads", ThreadsState.total_threads, "slate"),
            metric("Unhealthy", ThreadsState.unhealthy_threads, ThreadsState.health_tone),
            metric("Last Refreshed", ThreadsState.last_refreshed, "slate"),
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(8.5rem, 1fr))",
            gap="0.65rem",
            width="100%",
        ),
        title="Thread Health",
        subtitle="Supervised background threads across all orcha processes.",
    )


def _thread_row(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(row["name"], font_family="'IBM Plex Mono', monospace", size="1")),
        rx.table.cell(tone_badge(row["group"], "slate")),
        rx.table.cell(tone_badge(row["state"], row["state_tone"])),
        rx.table.cell(rx.text(row["last_heartbeat"], size="1")),
        rx.table.cell(rx.text(row["last_tick"], size="1")),
        rx.table.cell(rx.text(row["interval"], size="1")),
        rx.table.cell(tone_badge(row["restart_count"], rx.cond(row["restart_count"] > 0, "amber", "slate"))),
        rx.table.cell(tone_badge(row["error_count"], rx.cond(row["error_count"] > 0, "amber", "slate"))),
        rx.table.cell(rx.text(row["last_error"], size="1", color="#b91c1c", white_space="pre-wrap")),
    )


def _instance_group(instance: dict) -> rx.Component:
    return section_card(
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Thread"),
                        rx.table.column_header_cell("Group"),
                        rx.table.column_header_cell("State"),
                        rx.table.column_header_cell("Heartbeat"),
                        rx.table.column_header_cell("Last Tick"),
                        rx.table.column_header_cell("Interval"),
                        rx.table.column_header_cell("Restarts"),
                        rx.table.column_header_cell("Errors"),
                        rx.table.column_header_cell("Last Error"),
                    )
                ),
                rx.table.body(rx.foreach(instance["threads"], _thread_row)),
                variant="surface",
                size="1",
                width="100%",
            ),
            width="100%",
            overflow_x="auto",
        ),
        title=instance["instance_id"],
        subtitle=rx.cond(
            instance["online"],
            f"Updated {instance['updated']} · {instance['total']} threads",
            f"Last seen {instance['updated']} · process may be down",
        ),
        actions=tone_badge(instance["status_label"], instance["status_tone"]),
    )


def threads_page() -> rx.Component:
    content = rx.vstack(
        _summary_card(),
        rx.cond(
            ThreadsState.has_instances,
            rx.vstack(
                rx.foreach(ThreadsState.instances, _instance_group),
                spacing="3",
                width="100%",
                align_items="stretch",
            ),
            empty_state(
                "No Thread Health Reported",
                "No supervised threads have reported in yet. The scheduler and "
                "task runner publish health once they start.",
            ),
        ),
        spacing="3",
        width="100%",
        align_items="stretch",
    )
    actions = rx.button(
        "Refresh", on_click=ThreadsState.refresh, variant="soft", color_scheme="gray", size="2"
    )
    return app_shell(
        active_route="/threads",
        page_title="Threads",
        page_description="Lifecycle and health of supervised background threads.",
        content=content,
        actions=actions,
    )


__all__ = ["threads_page"]
