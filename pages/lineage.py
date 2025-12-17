from __future__ import annotations

import colorsys
from typing import Any

import dash
from dash import Input, Output, dcc, html

from orcha.core import tasks
from orcha_ui.credentials import PLOTLY_APP_PATH


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


def _is_source(module_type: str | None) -> bool:
    return isinstance(module_type, str) and module_type.lower().startswith("source")


def _is_sink(module_type: str | None) -> bool:
    return isinstance(module_type, str) and module_type.lower().startswith("sink")


def build_lineage_d3_model(selected_task_ids: set[str] | None = None) -> dict[str, Any]:
    all_tasks = tasks.TaskItem.get_all()
    if selected_task_ids:
        all_tasks = [t for t in all_tasks if t.task_idk in selected_task_ids]

    # Collect latest successful run output per task
    runs_data: list[tuple[tasks.TaskItem, dict[str, Any]]] = []
    for task in all_tasks:
        latest_run = tasks.RunItem.get_latest(task=task, status="success")
        if not latest_run:
            continue
        out = latest_run.output or {}
        if isinstance(out, dict):
            runs_data.append((task, out))

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str]] = []
    next_id = 1

    def ensure_node(
        key: str,
        *,
        label: str,
        kind: str,
        subtype: str | None = None,
        group: str | None = None,
    ) -> int:
        nonlocal next_id
        if key in nodes:
            if group:
                nodes[key].setdefault("groups", set()).add(group)
            return nodes[key]["id"]
        node_id = next_id
        next_id += 1
        nodes[key] = {
            "id": node_id,
            "key": key,
            "label": label,
            "kind": kind,
            "subtype": subtype,
            "groups": set([group]) if group else set(),
        }
        return node_id

    def add_edge(parent_key: str, child_key: str) -> None:
        edges.append((parent_key, child_key))

    for task, out in runs_data:
        task_group = str(task.task_idk)
        run_times = out.get("run_times") or []
        if not isinstance(run_times, list) or not run_times:
            continue

        prev_key: str | None = None
        last_source_key: str | None = None
        task_inserted = False

        for step_index, entry in enumerate(run_times):
            if not isinstance(entry, dict):
                continue

            module_idk = entry.get("module_idk")
            module_type = entry.get("module_type")
            module_entity = entry.get("module_entity")
            if not module_idk:
                continue

            if _is_source(module_type):
                # shared source module + shared source entity
                if module_entity:
                    ent_key = f"entity:source:{module_entity}"
                    ensure_node(ent_key, label=str(module_entity), kind="entity", subtype="source", group=task_group)
                module_key = f"module:source:{module_idk}"
                ensure_node(module_key, label=str(module_idk), kind="module", subtype="source", group=task_group)
                if module_entity:
                    add_edge(ent_key, module_key)

                # If there are multiple sources in a run, chain them in-order.
                if last_source_key is not None:
                    add_edge(last_source_key, module_key)
                last_source_key = module_key
                continue

            if not task_inserted:
                if last_source_key is not None:
                    prev_key = last_source_key
                else:
                    prev_key = None
                task_inserted = True

            if _is_sink(module_type):
                # shared sink module across all tasks
                module_key = f"module:sink:{module_idk}"
                ensure_node(module_key, label=str(module_idk), kind="module", subtype="sink", group=task_group)
                if prev_key is not None:
                    add_edge(prev_key, module_key)
                prev_key = module_key

                if module_entity:
                    # shared sink entity across all sinks
                    ent_key = f"entity:sink:{module_entity}"
                    ensure_node(ent_key, label=str(module_entity), kind="entity", subtype="sink", group=task_group)
                    add_edge(module_key, ent_key)
                continue

            # intermediate: never shared across tasks
            module_key = f"module:mid:{task.task_idk}:{module_idk}:{step_index}"
            ensure_node(
                module_key,
                label=str(module_idk),
                kind="module",
                subtype="mid",
                group=task_group,
            )
            if prev_key is not None:
                add_edge(prev_key, module_key)
            prev_key = module_key

    node_list = sorted((v for v in nodes.values()), key=lambda n: n["id"])
    edge_list = [
        (nodes[p]["id"], nodes[c]["id"], p, c)
        for p, c in edges if p in nodes and c in nodes
    ]

    # Tree parent mapping: choose the first inbound edge as the parent.
    parent_by_id: dict[int, int] = {}
    for from_id, to_id, _pkey, _ckey in edge_list:
        if to_id not in parent_by_id:
            parent_by_id[to_id] = from_id

    # Root node
    d3_nodes: list[dict[str, Any]] = [
        {
            "id": 0,
            "parentId": None,
            "label": "root",
            "kind": "root",
            "subtype": "",
            "groups": []
        }
    ]

    for n in node_list:
        node_id = int(n["id"])
        kind = str(n.get("kind") or "module")
        subtype = str(n.get("subtype") or "")
        label = str(n.get("label") or n.get("key") or node_id)
        groups = sorted(str(g) for g in (n.get("groups") or set()) if g)
        d3_nodes.append(
            {
                "id": node_id,
                "parentId": int(parent_by_id.get(node_id, 0)),
                "label": label,
                "kind": kind,
                "subtype": subtype,
                "groups": groups,
            }
        )

    id_to_groups: dict[int, set[str]] = {
        int(n["id"]): set(n.get("groups") or set()) for n in node_list
    }
    task_links: list[dict[str, Any]] = []
    for from_id, to_id, pkey, ckey in edge_list:
        # Determine task ownership for this edge.
        candidate_groups: set[str] = set()
        if isinstance(pkey, str) and pkey.startswith("task:"):
            candidate_groups.add(pkey.split(":", 1)[1])
        elif isinstance(pkey, str) and pkey.startswith("module:mid:"):
            # module:mid:<task_idk>:...
            parts = pkey.split(":")
            if len(parts) >= 3:
                candidate_groups.add(parts[2])
        else:
            candidate_groups = id_to_groups.get(int(from_id), set()) & id_to_groups.get(int(to_id), set())

        task_id = sorted(candidate_groups)[0] if candidate_groups else None
        if task_id:
            task_links.append({"source": int(from_id), "target": int(to_id), "task": str(task_id)})

    task_order = sorted({str(t.task_idk) for t, _out in runs_data})

    # Generate a palette sized to the number of tasks. Use HSL spacing for
    # visually distinct colours and return hex strings.
    def _generate_palette(n: int) -> list[str]:
        if n <= 0:
            return []
        cols: list[str] = []
        for i in range(n):
            h = (i * 360.0 / n) % 360.0
            r, g, b = colorsys.hls_to_rgb(h / 360.0, 0.55, 0.65)
            cols.append('#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255)))
        return cols

    palette = _generate_palette(len(task_order))

    return {
        "nodes": d3_nodes,
        "task_links": task_links,
        "task_order": task_order,
        "palette": palette
    }


def layout(hours: int | None = None, start: str | None = None, end: str | None = None, sources: str | None = None):

    all_tasks = tasks.TaskItem.get_all()
    task_options = [
        {"label": f"{t.name} ({t.task_idk})", "value": t.task_idk}
        for t in all_tasks
    ]
    selected_task_ids = [t.task_idk for t in all_tasks]

    initial_model = build_lineage_d3_model(set(selected_task_ids))
    task_order = initial_model.get('task_order') or []
    palette = initial_model.get('palette')
    task_name_map = {str(t.task_idk): (t.name if getattr(t, 'name', None) else str(t.task_idk)) for t in all_tasks}
    legend_children = []
    for idx, tid in enumerate(task_order):
        if palette and idx < len(palette):
            color = palette[idx]
        else:
            n = max(len(task_order), 1)
            h = (idx * 360.0 / n) % 360.0
            r, g, b = colorsys.hls_to_rgb(h / 360.0, 0.55, 0.65)
            color = '#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255))
        label = task_name_map.get(str(tid), str(tid))
        legend_children.append(html.Div([
            html.Span(style={
                'display': 'inline-block', 'width': '14px', 'height': '14px',
                'backgroundColor': color, 'marginRight': '6px',
                'verticalAlign': 'middle', 'borderRadius': '3px',
                'border': '1px solid #ccc'
            }),
            html.Span(label, style={'verticalAlign': 'middle', 'fontSize': '0.9em'})
            ], style={
                'display': 'inline-flex', 'alignItems': 'center',
                'marginRight': '12px', 'marginBottom': '6px'
            }
        ))

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
            html.Div(className='col-12 pb-1', children=[
                html.Label('Legend', style={'font-weight': 'normal', 'marginRight': '8px'}),
                html.Div(id='lineage-legend', children=legend_children, style={'display': 'flex', 'flexWrap': 'wrap', 'alignItems': 'center'})
            ]),
            dcc.Store(id="lineage-flow-model", data=initial_model),
            dcc.Store(id="lineage-d3-rendered", data=None),
            html.Div(
                id="lineage-d3-canvas",
                style={
                    "position": "relative",
                    "height": "78vh",
                    "minHeight": "520px",
                    "overflow": "auto",
                },
            ),
            html.Div(id="lineage-d3-dummy", style={"display": "none"}),
        ],
    )


@dash.callback(
    Output("lineage-flow-model", "data"),
    Input("lineage-task-filter", "value"),
)
def update_lineage_graph(selected_task_ids):
    selected = set(selected_task_ids) if selected_task_ids else None
    model = build_lineage_d3_model(selected)
    return model

dash.clientside_callback(
    r"""
async function(model) {
    console.log('Rendering lineage D3', model);
    if(!model || !Array.isArray(model.nodes)) {
        return dash_clientside.no_update;
    }

    // Assumes D3 is already injected into the Dash environment.
    const d3ref = (typeof d3 !== 'undefined') ? d3 : null;
    if(!d3ref) {
        console.error('D3 library not found');
        return dash_clientside.no_update;
    }

    const canvas = document.getElementById('lineage-d3-canvas');
    if(!canvas) {
        return dash_clientside.no_update;
    }

    // Clear existing content.
    canvas.innerHTML = '';

    const nodes = model.nodes.slice();
    const byId = new Map(nodes.map((n) => [Number(n.id), n]));

    // Ensure we have a single root for layout only.
    if(!byId.has(0)) {
        nodes.unshift({id: 0, parentId: null, label: 'root', kind: 'root', subtype: '', groups: []});
    }

    let root;
    try {
        root = d3ref.stratify()
            .id((d) => String(d.id))
            .parentId((d) => (d.parentId == null ? null : String(d.parentId)))(nodes);
    } catch(e) {
        console.error('Failed to stratify lineage nodes', e);
        return dash_clientside.no_update;
    }

    const margin = {top: 24, right: 24, bottom: 24, left: 24};
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(600, Math.floor(rect.width || 800));

    // Layout: vertical tree.
    const dx = 86;
    const dy = 220;
    const treeLayout = d3ref.tree().nodeSize([dx, dy]);
    treeLayout(root);

    let x0 = Infinity, x1 = -Infinity;
    root.each((d) => {
        if(d.x < x0) x0 = d.x;
        if(d.x > x1) x1 = d.x;
    });
    const height = Math.max(520, Math.floor((x1 - x0) + margin.top + margin.bottom + 40));

    const svg = d3ref.select(canvas)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height]);

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top - x0})`);

    const linkGen = d3ref.linkHorizontal()
        .x((d) => d.y)
        .y((d) => d.x);

    // Nodes (hide the layout root node)
    const node = g.append('g')
        .selectAll('g')
        .data(root.descendants().filter((d) => {
            if(!d || !d.data) return false;
            // Exclude the layout root and any 'task' nodes (tasks are not
            // represented as visible nodes anymore).
            const k = String(d.data.kind || '');
            return k !== 'root' && k !== 'task';
        }))
        .join('g')
        .attr('transform', (d) => `translate(${d.y},${d.x})`);

    const kindClass = (d) => {
        const k = (d && d.data && d.data.kind) ? String(d.data.kind) : 'module';
        const s = (d && d.data && d.data.subtype) ? String(d.data.subtype) : '';
        return `lineage-node lineage-kind-${k} lineage-subtype-${s}`;
    };

    const fillFor = (d) => {
        const k = (d && d.data && d.data.kind) ? String(d.data.kind) : 'module';
        if(k === 'task') return '#ffffff';
        if(k === 'entity') return '#ffffff';
        if(k === 'root') return 'transparent';
        return '#ffffff';
    };

    // Draw a star for task nodes, circles for others.
    // Use a square symbol for task nodes (smaller size) instead of a star.
    const squareSymbol = d3ref.symbol().type(d3ref.symbolSquare).size(280);
    node.each(function(d) {
        try {
            const k = (d && d.data && d.data.kind) ? String(d.data.kind) : 'module';
            if(k === 'task') {
                d3ref.select(this)
                    .append('path')
                    .attr('d', squareSymbol)
                    .attr('fill', fillFor(d))
                    .attr('stroke', '#666')
                    .attr('stroke-width', 1.5)
                    .attr('class', kindClass(d));
            } else {
                d3ref.select(this)
                    .append('circle')
                    .attr('r', (d.data && d.data.kind === 'root') ? 0 : 10)
                    .attr('fill', fillFor(d))
                    .attr('stroke', '#666')
                    .attr('stroke-width', 1.5)
                    .attr('class', kindClass(d));
            }
        } catch(e) {
            // Fallback to circle if symbol generation fails.
            d3ref.select(this)
                .append('circle')
                .attr('r', 10)
                .attr('fill', fillFor(d))
                .attr('stroke', '#666')
                .attr('stroke-width', 1.5)
                .attr('class', kindClass(d));
        }
    });

    // Place labels below each node and center them. Increase `dy` for extra padding.
    node.append('text')
        .attr('dy', '2em')
        .attr('x', 0)
        .attr('text-anchor', 'middle')
        .attr('class', 'small')
        .text((d) => (d.data && d.data.label) ? String(d.data.label) : String(d.id));

    // Task group bounding boxes removed — bounding boxes disabled.
    // The previous rendering logic was intentionally removed to simplify
    // the lineage visualization and avoid overlapping boxes.

    // Per-task colored links.
    try {
        const palette = model.palette;
        const taskOrder = model.task_order;
        const colorFor = (task) => {
            const t = String(task);
            const idx = taskOrder.indexOf(t);
            if(idx < 0) return '#000000';
            if(Array.isArray(palette) && idx < palette.length) return palette[idx];

            const n = taskOrder.length || 1;
            const h = (idx * 360.0 / n) % 360.0;
            const s = 0.65;
            const l = 0.55;
            // HSL -> RGB conversion
            const hslToHex = (hh, ss, ll) => {
                const a = ss * Math.min(ll, 1 - ll);
                const f = (n) => {
                    const k = (n + hh / 30) % 12;
                    const color = ll - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
                    return Math.round(255 * color).toString(16).padStart(2, '0');
                };
                return `#${f(0)}${f(8)}${f(4)}`;
            };
            return hslToHex(h, s, l);
        };

        const pos = new Map();
        root.each((d) => {
            if(d && d.data && d.data.kind !== 'root') {
                pos.set(Number(d.data.id), {x: d.x, y: d.y});
            }
        });

        const links = Array.isArray(model.task_links) ? model.task_links : [];
        const linkData = links
            .map((e) => ({
                task: e.task,
                source: pos.get(Number(e.source)),
                target: pos.get(Number(e.target))
            }))
            .filter((e) => e.task && e.source && e.target);

        g.append('g')
            .attr('fill', 'none')
            .attr('stroke-width', 2)
            .attr('stroke-opacity', 0.85)
            .selectAll('path')
            .data(linkData)
            .join('path')
            .attr('stroke', (d) => colorFor(d.task))
            .attr('d', (d) => linkGen({source: d.source, target: d.target}));
    } catch(e) {
        console.warn('Per-task link render failed', e);
    }

    return Date.now();
}
""",
    Output("lineage-d3-rendered", "data"),
    Input("lineage-flow-model", "data"),
    prevent_initial_call=False,
)
