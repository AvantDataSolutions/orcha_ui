from __future__ import annotations

NAV_ITEMS = [
    {
        "name": "Overview",
        "route": "/overview",
        "image": "/page_imgs/home.svg",
        "title": "Overview | Orcha",
        "description": "Overview of current Orcha tasks and runs.",
    },
    {
        "name": "Run Details",
        "route": "/run_details",
        "image": "/page_imgs/bullseye.svg",
        "title": "Run Details | Orcha",
        "description": "View the details of a specific run.",
    },
    {
        "name": "Task Details",
        "route": "/task_details",
        "image": "/page_imgs/list-task.svg",
        "title": "Task Details | Orcha",
        "description": "View the details of a specific task.",
    },
    {
        "name": "Logs",
        "route": "/logs",
        "image": "/page_imgs/log.png",
        "title": "Logs | Orcha",
        "description": "Explore application logs with date range and source filters.",
    },
    {
        "name": "Threads",
        "route": "/threads",
        "image": "/page_imgs/activity.svg",
        "title": "Threads | Orcha",
        "description": "Health and lifecycle of supervised background threads.",
    },
    {
        "name": "Lineage",
        "route": "/lineage",
        "image": "/page_imgs/lineage.png",
        "title": "Lineage | Orcha",
        "description": "Explore data lineage and workflow dependencies within Orcha.",
    },
    {
        "name": "KVDB Explorer",
        "route": "/kvdb",
        "image": "/page_imgs/database.svg",
        "title": "KVDB Explorer | Orcha",
        "description": "Inspect and edit KVDB entries.",
    },
]

USER_LABEL = "User: user@orcha"

APP_VERSION = "v2"
APP_VERSION_TONE = "beta"  # shown next to APP_VERSION; set to "" to hide the tag

RUN_STATUS_COLORS = {
    "success": "#16a34a",
    "failed": "#dc2626",
    "warn": "#f59e0b",
    "warning": "#f59e0b",
    "queued": "#2563eb",
    "running": "#7c3aed",
    "cancelled": "#64748b",
    "unstarted": "#2563eb",
    "unknown": "#94a3b8",
}

NODE_KIND_COLORS = {
    "root": "#e2e8f0",
    "module": "#0f172a",
    "entity": "#0ea5e9",
    "source": "#06b6d4",
    "sink": "#14b8a6",
    "mid": "#334155",
}