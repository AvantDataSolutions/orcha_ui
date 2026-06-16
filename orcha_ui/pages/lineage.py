from __future__ import annotations

import reflex as rx

from orcha_ui.components.common import empty_state, filter_chip, legend_chip, section_card
from orcha_ui.components.layout import app_shell
from orcha_ui.components.react_flow import background, controls, mini_map, react_flow
from orcha_ui.services.queries import LINEAGE_NODE_LEGEND
from orcha_ui.state import LineageState


def _node_kind_legend() -> rx.Component:
    return rx.flex(
        *[
            rx.hstack(
                legend_chip(item["label"], item["color"]),
                rx.text(item["hint"], color="#94a3b8", size="1"),
                spacing="2",
                align="center",
            )
            for item in LINEAGE_NODE_LEGEND
        ],
        wrap="wrap",
        gap="0.75rem",
        width="100%",
    )


def _task_legend_chip(item: dict) -> rx.Component:
    """A task-colour swatch that highlights its task path on hover and pins on click."""
    pinned = LineageState.pinned_task == item["task_id"]
    return rx.hstack(
        rx.box(
            width="14px",
            height="14px",
            background_color=item["color"],
            border_radius="4px",
            border="1px solid rgba(15,23,42,0.15)",
        ),
        rx.text(item["label"], size="2"),
        rx.cond(pinned, rx.icon("pin", size=12, color="#475569"), rx.fragment()),
        spacing="2",
        align="center",
        padding="0.2rem 0.55rem",
        border_radius="999px",
        cursor="pointer",
        border=rx.cond(pinned, f"1.5px solid {item['color']}", "1.5px solid transparent"),
        background_color=rx.cond(pinned, "rgba(255,255,255,0.95)", "rgba(255,255,255,0.55)"),
        box_shadow=rx.cond(pinned, "0 1px 6px rgba(15,23,42,0.12)", "none"),
        on_mouse_enter=LineageState.hover_task(item["task_id"]),
        on_mouse_leave=LineageState.unhover_task,
        on_click=LineageState.toggle_pin_task(item["task_id"]),
    )


def _diagram() -> rx.Component:
    return rx.box(
        react_flow(
            background(color="#e2e8f0", gap=18),
            controls(show_interactive=False),
            mini_map(pannable=True, zoomable=True),
            nodes=LineageState.flow_nodes,
            edges=LineageState.flow_edges,
            fit_view=True,
            nodes_draggable=True,
            nodes_connectable=False,
            elements_selectable=True,
            min_zoom=0.1,
            max_zoom=2.0,
            pro_options={"hideAttribution": True},
            on_pane_click=LineageState.clear_focus,
            width="100%",
            height="100%",
        ),
        width="100%",
        height="46rem",
        border="1px solid rgba(148, 163, 184, 0.25)",
        border_radius="18px",
        overflow="hidden",
        background_color="rgba(248, 250, 252, 0.6)",
    )


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
                rx.button("Select None", on_click=LineageState.clear_all, variant="soft", color_scheme="gray"),
                spacing="3",
            ),
            rx.cond(
                LineageState.available_workspaces,
                rx.hstack(
                    rx.text("Workspace:", color="#64748b", size="2", flex_shrink="0"),
                    rx.flex(
                        rx.foreach(
                            LineageState.available_workspaces,
                            lambda workspace: rx.button(
                                workspace,
                                on_click=LineageState.select_workspace(workspace),
                                size="1",
                                variant="soft",
                                color_scheme="cyan",
                            ),
                        ),
                        wrap="wrap",
                        gap="0.5rem",
                        width="100%",
                    ),
                    align="center",
                    spacing="3",
                    width="100%",
                ),
                rx.fragment(),
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
            subtitle="Filter the lineage map to the tasks you want to compare. Use Workspace to jump to one group of tasks.",
        ),
        section_card(
            _node_kind_legend(),
            rx.box(height="1px", background_color="rgba(148,163,184,0.18)", width="100%"),
            rx.hstack(
                rx.text("Highlight a task:", color="#64748b", size="2"),
                rx.spacer(),
                rx.cond(
                    LineageState.pinned_task != "",
                    rx.button(
                        "Clear highlight",
                        on_click=LineageState.clear_focus,
                        size="1",
                        variant="soft",
                        color_scheme="gray",
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align="center",
            ),
            rx.flex(
                rx.foreach(LineageState.legend, _task_legend_chip),
                wrap="wrap",
                gap="0.6rem",
                width="100%",
            ),
            rx.text(
                "Hover a task to spotlight its path; click to pin it. Click empty canvas to release.",
                color="#94a3b8",
                size="1",
            ),
            rx.cond(
                LineageState.has_flow,
                _diagram(),
                empty_state(
                    "No Lineage Diagram",
                    "No successful-run lineage edges are available for the selected task set.",
                ),
            ),
            title="Lineage Diagram",
            subtitle="Drag nodes, scroll to zoom, and pan to explore.",
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
                    max_height="28rem",
                    overflow="auto",
                    width="100%",
                ),
                empty_state("No Lineage Links", "No successful-run lineage edges are available for the selected task set."),
            ),
            title="Lineage Paths",
            subtitle="The same connections as a readable list. Shared sources and sinks are merged while task-specific intermediate modules remain distinct.",
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
