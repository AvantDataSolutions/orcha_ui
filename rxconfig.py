import os

import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


frontend_port = _int_env("REFLEX_FRONTEND_PORT", 3000)
backend_port = _int_env("REFLEX_BACKEND_PORT", 8000)
frontend_host = os.getenv("REFLEX_DEPLOY_URL") or f"http://localhost:{frontend_port}"
api_url = os.getenv("API_URL") or os.getenv("REFLEX_API_URL") or f"http://localhost:{backend_port}"


config = rx.Config(
    app_name="orcha_ui",
    app_module_import="orcha_ui.app",
    frontend_port=frontend_port,
    backend_port=backend_port,
    api_url=api_url,
    deploy_url=frontend_host,
    backend_host="0.0.0.0",
    telemetry_enabled=False,
    show_built_with_reflex=False,
    react_strict_mode=False,
    vite_allowed_hosts=True,
    disable_plugins=[SitemapPlugin],
)