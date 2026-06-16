"""Thin Reflex wrapper around the React Flow (@xyflow/react) diagramming library.

React Flow renders an interactive node-and-edge canvas (pan / zoom / drag) which
is exactly the "line-and-box" lineage layout we want. Node positions are computed
server-side in ``queries.build_lineage_flow`` so the visual arrangement (entities
pinned left, sources next, transforms in the middle, sinks on the right) is fully
controlled from Python; React Flow is only responsible for drawing and interaction.
"""
from __future__ import annotations

import reflex as rx


class ReactFlowLib(rx.Component):
    """Base for every component exported by @xyflow/react."""

    library = "@xyflow/react@12.8.6"


class ReactFlow(ReactFlowLib):
    tag = "ReactFlow"

    nodes: rx.Var[list[dict]]
    edges: rx.Var[list[dict]]

    fit_view: rx.Var[bool]
    nodes_draggable: rx.Var[bool]
    nodes_connectable: rx.Var[bool]
    elements_selectable: rx.Var[bool]
    pan_on_drag: rx.Var[bool]
    zoom_on_scroll: rx.Var[bool]
    min_zoom: rx.Var[float]
    max_zoom: rx.Var[float]
    pro_options: rx.Var[dict]
    default_edge_options: rx.Var[dict]

    # Clicking empty canvas fires with the click event only (no node payload).
    on_pane_click: rx.EventHandler[lambda e: []]


class Background(ReactFlowLib):
    tag = "Background"

    color: rx.Var[str]
    gap: rx.Var[int]
    size: rx.Var[int]
    variant: rx.Var[str]


class Controls(ReactFlowLib):
    tag = "Controls"

    show_interactive: rx.Var[bool]


class MiniMap(ReactFlowLib):
    tag = "MiniMap"

    pannable: rx.Var[bool]
    zoomable: rx.Var[bool]


react_flow = ReactFlow.create
background = Background.create
controls = Controls.create
mini_map = MiniMap.create


__all__ = ["react_flow", "background", "controls", "mini_map"]
