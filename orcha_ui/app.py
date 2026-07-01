from __future__ import annotations

import reflex as rx

from orcha_ui.pages import kvdb_page, lineage_page, logs_page, overview_page, run_details_page, task_details_page, threads_page
from orcha_ui.services.bootstrap import initialise_orcha
from orcha_ui.state import KvdbState, LineageState, LogsState, OverviewState, RunDetailState, TaskDetailState, ThreadsState


initialise_orcha()


app = rx.App(
    stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
        "https://cdn.jsdelivr.net/npm/@xyflow/react@12.8.6/dist/style.css",
        "/custom.css",
        "/dash_loading.css",
    ],
    style={
        "font_family": "'Work Sans', 'Segoe UI', sans-serif",
        "background": "linear-gradient(180deg, #eff6ff 0%, #f8fafc 35%, #ffffff 100%)",
        "color": "#10223a",
    },
)

app.add_page(task_details_page, route="/task_details/[task_id]", title="Task Details | Orcha", on_load=TaskDetailState.load_from_route)
app.add_page(task_details_page, route="/task_details", title="Task Details | Orcha", on_load=TaskDetailState.load_from_route)
app.add_page(run_details_page, route="/run_details/[run_id]", title="Run Details | Orcha", on_load=RunDetailState.load_from_route)
app.add_page(run_details_page, route="/run_details", title="Run Details | Orcha", on_load=RunDetailState.load_from_route)
app.add_page(overview_page, route="/", title="Orcha", on_load=OverviewState.load)
app.add_page(overview_page, route="/overview", title="Overview | Orcha", on_load=OverviewState.load)
app.add_page(logs_page, route="/logs", title="Logs | Orcha", on_load=LogsState.load)
app.add_page(threads_page, route="/threads", title="Threads | Orcha", on_load=ThreadsState.load)
app.add_page(lineage_page, route="/lineage", title="Lineage | Orcha", on_load=LineageState.load)
app.add_page(kvdb_page, route="/kvdb", title="KVDB Explorer | Orcha", on_load=KvdbState.load)