from __future__ import annotations

from datetime import datetime as dt, timedelta as td
from typing import Any
import json
import math

import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output

from orcha_ui.credentials import (
    PLOTLY_APP_PATH
)

# Use the log structure defined in orcha.utils.log
from orcha.utils.log import LogManager
from orcha.core import tasks


def can_read():
    return True


dash.register_page(
    __name__,
    name='Lineage',
    path='/lineage',
    image_url=f'{PLOTLY_APP_PATH}assets/page_imgs/lineage.png',
    title='Lineage | Orcha',
    description='Explore data lineage and workflow dependencies within Orcha.',
    can_read_callback=can_read,
    can_edit_callback=lambda: True,
    order=400,
)


def build_lineage_figure(selected_task_ids: set[str] | None = None) -> go.Figure:

    all_tasks = tasks.TaskItem.get_all()

    # filter tasks if selection provided
    if selected_task_ids:
        all_tasks = [t for t in all_tasks if t.task_idk in selected_task_ids]

    latest_runs: dict[str, tasks.RunItem] = {}

    for task in all_tasks:
        latest_run = tasks.RunItem.get_latest(task=task, status='success')
        if latest_run:
            latest_runs[task.task_idk] = latest_run

    fig = go.Figure()
    # Collect run outputs from latest runs and parse JSON (keep task idk for grouping)
    runs_data: list[tuple[str, dict[str, Any]]] = []
    for task_idk, run in latest_runs.items():
        # assume output exists
        output = run.output or {}
        runs_data.append((task_idk, output))

    # Build graph: nodes and edges
    # We'll create module nodes and entity nodes (prefixed for clarity)
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str]] = set()

    # groups_all maps task_idk -> all node keys belonging to that task (used for hover mapping)
    groups_all: dict[str, set[str]] = {}
    # modules_by_task maps task_idk -> module node keys (used for component grouping and boxes)
    modules_by_task: dict[str, set[str]] = {}

    for task_idk, out in runs_data:
        groups_all.setdefault(task_idk, set())
        modules_by_task.setdefault(task_idk, set())
        run_times = out.get("run_times") or out.get("run_times", [])
        if not isinstance(run_times, list):
            continue

        prev_module_idk: str | None = None
        for entry in run_times:
            module_idk = entry.get("module_idk")
            module_type = entry.get("module_type")
            module_entity = entry.get("module_entity")

            if not module_idk:
                continue

            mod_label = f"module:{module_idk}"
            if mod_label not in nodes:
                nodes[mod_label] = {"kind": "module", "label": module_idk, "module_type": (module_type or "").lower()}
            # record membership for this task's group
            groups_all.setdefault(task_idk, set()).add(mod_label)
            modules_by_task[task_idk].add(mod_label)

            # Create entity node if present (duplicate per role so same name can exist on both sides)
            ent_label = None
            if module_entity:
                mtype = (module_type or "").lower()
                if mtype.startswith("source"):
                    ent_label = f"entity_source:{module_entity}"
                elif mtype.startswith("sink"):
                    ent_label = f"entity_sink:{module_entity}"
                else:
                    ent_label = f"entity_other:{module_entity}"

                if ent_label not in nodes:
                    nodes[ent_label] = {"kind": "entity", "label": module_entity, "role": mtype if mtype else "other"}
                # record membership for this task's group
                groups_all.setdefault(task_idk, set()).add(ent_label)

            # Connect previous module -> current module in sequence (workflow ordering)
            if prev_module_idk:
                edges.add((f"module:{prev_module_idk}", mod_label))

            # Connect module <-> entity depending on type
            # For sources, connect entity -> module; for sinks, module -> entity; otherwise module -> entity
            if ent_label:
                if isinstance(module_type, str) and module_type.lower().startswith("source"):
                    edges.add((ent_label, mod_label))
                elif isinstance(module_type, str) and module_type.lower().startswith("sink"):
                    edges.add((mod_label, ent_label))
                else:
                    edges.add((mod_label, ent_label))

            prev_module_idk = module_idk

    # If no nodes collected, return empty placeholder
    if not nodes:
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), plot_bgcolor="white")
        fig.add_annotation(text="No lineage data available", x=0.5, y=0.5, showarrow=False, xref="paper", yref="paper")
        return fig

    # Layout nodes left-to-right in columns:
    # source entities -> sources -> (others/middle) -> sinks -> sink entities
    node_keys = list(nodes.keys())
    pos: dict[str, tuple[float, float]] = {}

    columns = {
        "source_entities": [],
        "sources": [],
        "others": [],
        "sinks": [],
        "sink_entities": [],
    }

    for key, meta in nodes.items():
        if meta.get("kind") == "module":
            mt = (meta.get("module_type") or "").lower()
            if mt.startswith("source"):
                columns["sources"].append(key)
            elif mt.startswith("sink"):
                columns["sinks"].append(key)
            else:
                columns["others"].append(key)
        else:
            # key prefix determines column to allow same entity name to live in both lists
            if key.startswith("entity_source:"):
                columns["source_entities"].append(key)
            elif key.startswith("entity_sink:"):
                columns["sink_entities"].append(key)
            else:
                columns["others"].append(key)

    # Define column order left-to-right. If `others` is empty it will still occupy the middle.
    col_order = ["source_entities", "sources", "others", "sinks", "sink_entities"]
    spacing_x = 3.0
    spacing_y = 1.5

    for ci, col_name in enumerate(col_order):
        items = columns[col_name]
        count = len(items)
        x = ci * spacing_x
        for i, key in enumerate(items):
            # center the column vertically
            y = (i - (count - 1) / 2) * spacing_y if count > 0 else 0
            pos[key] = (x, y)

    # Build reverse mapping node -> tasks so we can show hover info for nodes
    node_to_tasks: dict[str, set[str]] = {k: set() for k in nodes.keys()}
    for task_idk, members in groups_all.items():
        for m in members:
            if m in node_to_tasks:
                node_to_tasks[m].add(task_idk)

    # Build task components based on shared modules (not entities) so that tasks sharing
    # only entities can still be separated vertically
    task_ids = list(modules_by_task.keys())
    parent: dict[str, str] = {t: t for t in task_ids}

    def find(t: str) -> str:
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(task_ids)):
        for j in range(i + 1, len(task_ids)):
            ti, tj = task_ids[i], task_ids[j]
            if modules_by_task.get(ti, set()) & modules_by_task.get(tj, set()):
                union(ti, tj)

    comp_members: dict[str, set[str]] = {}
    for t in task_ids:
        r = find(t)
        comp_members.setdefault(r, set()).add(t)

    # Fixed vertical stacking of non-overlapping components (tasks that do not share modules)
    comp_offsets: dict[str, float] = {r: 0.0 for r in comp_members}
    separation_y = 1.5

    def comp_base_bounds(comp: str) -> tuple[float, float, float, float]:
        xs: list[float] = []
        ys: list[float] = []
        for t in comp_members.get(comp, set()):
            for k in modules_by_task.get(t, set()):
                if k in pos:
                    x, y = pos[k]
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return 0, 0, 0, 0
        return min(xs), max(xs), min(ys), max(ys)

    # order components by their leftmost x to keep layout stable
    ordered_comps = sorted(comp_members.keys(), key=lambda c: comp_base_bounds(c)[0] if comp_base_bounds(c) else 0)
    current_y = 0.0
    for comp in ordered_comps:
        b = comp_base_bounds(comp)
        if not b:
            comp_offsets[comp] = current_y
            continue
        minx, maxx, miny, maxy = b
        comp_offsets[comp] = current_y - miny
        height = maxy - miny
        current_y += height + separation_y

    # adjusted positions using component offsets; nodes take the offset of their first task (all tasks in a component share offset)
    pos_use: dict[str, tuple[float, float]] = {}
    for key, (x, y) in pos.items():
        comp = None
        tasks_for_node = sorted(list(node_to_tasks.get(key, set())))
        for t in tasks_for_node:
            comp = find(t)
            break
        off = comp_offsets.get(comp, 0.0) if comp else 0.0
        pos_use[key] = (x, y + off)

    # Draw edges as lines and annotations (arrows)
    edge_x = []
    edge_y = []

    for src, dst in edges:
        sx, sy = pos_use.get(src, (0, 0))
        dx, dy = pos_use.get(dst, (0, 0))
        # straight line segment
        edge_x += [sx, dx, None]
        edge_y += [sy, dy, None]

    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(width=1, color="#888"),
            hoverinfo="none",
            showlegend=False,
        )
    )

    # Node scatter
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_hovertext = []
    for key in node_keys:
        x, y = pos_use[key]
        node_x.append(x)
        node_y.append(y)
        node_text.append(nodes[key]["label"])
        node_color.append("#1f77b4" if nodes[key]["kind"] == "module" else "#ff7f0e")
        # hover text: show label and list of associated tasks
        tasks_for_node = sorted(node_to_tasks.get(key, []))
        if tasks_for_node:
            node_hovertext.append(f"{nodes[key]['label']}<br>Tasks: {', '.join(tasks_for_node)}")
        else:
            node_hovertext.append(nodes[key]["label"])

    # place labels above nodes for clarity
    node_textposition = ["top center"] * len(node_x)

    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition=node_textposition,
            hovertext=node_hovertext,
            marker=dict(size=28, color=node_color, line=dict(width=1, color="#333")),
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Add arrow annotations for directed edges
    for src, dst in edges:
        sx, sy = pos_use.get(src, (0, 0))
        dx, dy = pos_use.get(dst, (0, 0))
        fig.add_annotation(
            x=dx,
            y=dy,
            ax=sx,
            ay=sy,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            opacity=0.6,
        )

    # Draw grouping bounding boxes for each task (groups may overlap)
    shapes: list[dict] = []
    pad_x = 0.7
    pad_y = 0.6
    # simple palette for boxes (semi-transparent fills)
    palette = [
        "rgba(200,230,255,0.18)",
        "rgba(200,255,200,0.14)",
        "rgba(255,230,200,0.12)",
        "rgba(240,200,255,0.12)",
        "rgba(255,220,220,0.10)",
    ]

    # track placed label positions so we can avoid overlap
    placed_labels: list[tuple[float, float]] = []

    for gi, (task_idk, members) in enumerate(modules_by_task.items()):
        coords = [pos_use[k] for k in members if k in pos_use]
        if not coords:
            continue
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        fill = palette[gi % len(palette)]
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="y",
                x0=minx - pad_x,
                x1=maxx + pad_x,
                y0=miny - pad_y,
                y1=maxy + pad_y,
                line=dict(color=fill.replace("0.", "1.") if "rgba" in fill else "#888", width=1),
                fillcolor=fill,
                layer="below",
            )
        )
        # add a label for the group in the top-left corner of the box
        label_x = minx - pad_x + 0.1
        label_y = maxy + pad_y - 0.15
        # avoid overlaps with previously placed labels by shifting down if necessary
        # thresholds tuned to typical spacing; adjust if labels still overlap
        thresh_x = 1.0
        thresh_y = 0.1
        shift_y = 0.35
        # guard iterations to avoid infinite loops
        for _ in range(50):
            conflict = False
            for lx, ly in placed_labels:
                if abs(label_x - lx) < thresh_x and abs(label_y - ly) < thresh_y:
                    conflict = True
                    break
            if not conflict:
                break
            label_y -= shift_y
        placed_labels.append((label_x, label_y))

        fig.add_annotation(
            x=label_x,
            y=label_y,
            xref="x",
            yref="y",
            text=str(task_idk),
            showarrow=False,
            align="left",
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#666",
            font=dict(size=10),
        )

    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="closest",
        shapes=shapes,
    )

    return fig


def layout(hours: int | None = None, start: str | None = None, end: str | None = None, sources: str | None = None):

    all_tasks = tasks.TaskItem.get_all()
    task_options = [
        {"label": f"{t.name} ({t.task_idk})", "value": t.task_idk}
        for t in all_tasks
    ]
    selected_task_ids = [t.task_idk for t in all_tasks]

    initial_fig = build_lineage_figure(set(selected_task_ids))

    return html.Div(
        className="container-fluid",
        children=[
            html.Div(className='col-12 pb-2', children=[
                html.Label('Task Types', style={'font-weight': 'normal'}),
                dcc.Dropdown(
                    style={'width': '100%'},
                    id='lineage-task-filter',
                    options=task_options,
                    value=selected_task_ids,
                    multi=True,
                    placeholder='Filter tasks',
                ),
            ]),
            dcc.Graph(id="lineage-graph", figure=initial_fig),
        ],
    )


@dash.callback(
    Output("lineage-graph", "figure"),
    Input("lineage-task-filter", "value"),
)
def update_lineage_graph(selected_task_ids):
    selected = set(selected_task_ids) if selected_task_ids else None
    return build_lineage_figure(selected)
