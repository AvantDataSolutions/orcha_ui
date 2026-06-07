from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import empty_state, filter_chip, legend_chip, section_card
from orcha_ui.components.layout import app_shell
from orcha_ui.state import LineageState


def _link_row(row: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            legend_chip(row["task_label"], row["color"]),
            rx.text(row["source_label"], color="#0f172a", weight="medium"),
            rx.text("→", color="#64748b"),
            rx.text(row["target_label"], color="#0f172a", weight="medium"),
            spacing="3",
            wrap="wrap",
            width="100%",
            align="center",
        ),
        border="1px solid rgba(148, 163, 184, 0.18)",
        border_radius="18px",
        background_color="rgba(255,255,255,0.9)",
        padding="0.9rem 1rem",
        width="100%",
    )


def lineage_page() -> rx.Component:
    content = rx.vstack(
        section_card(
            rx.hstack(
                rx.button("Select All", on_click=LineageState.select_all, color_scheme="cyan"),
                rx.button("Clear", on_click=LineageState.clear_all, variant="soft", color_scheme="gray"),
                spacing="3",
            ),
            rx.flex(
                rx.foreach(
                    LineageState.task_filters,
                    lambda item: filter_chip(item["label"], item["active"], LineageState.toggle_task(item["value"])),
                ),
                wrap="wrap",
                gap="0.65rem",
                width="100%",
            ),
            title="Task Filter",
            subtitle="Filter the lineage map to the tasks you want to compare.",
        ),
        section_card(
            rx.flex(
                rx.foreach(LineageState.legend, lambda item: legend_chip(item["label"], item["color"])),
                wrap="wrap",
                gap="0.75rem",
                width="100%",
            ),
            title="Legend",
            subtitle="Each task path is colour-coded consistently across the lineage diagram.",
        ),
        section_card(
            rx.cond(
                LineageState.link_rows,
                rx.box(
                    rx.vstack(
                        rx.foreach(LineageState.link_rows, _link_row),
                        spacing="3",
                        width="100%",
                        align_items="stretch",
                    ),
                    max_height="44rem",
                    overflow="auto",
                    width="100%",
                ),
                empty_state("No Lineage Links", "No successful-run lineage edges are available for the selected task set."),
            ),
            title="Lineage Paths",
            subtitle="Shared sources and sinks are merged while task-specific intermediate modules remain distinct.",
        ),
        spacing="5",
        width="100%",
        align_items="stretch",
    )
    return app_shell(
        active_route="/lineage",
        page_title="Lineage",
        page_description="Visualise task dependencies, shared sources, and downstream sinks across successful runs.",
        content=content,
    )


__all__ = ["lineage_page"]