from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    is_dev: bool
    server_root_url: str
    orcha_core_user: str
    orcha_core_password: str
    orcha_core_server: str
    orcha_core_db: str


def _required_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


settings = Settings(
    is_dev=os.getenv("IS_DEV", "False") == "True",
    server_root_url=os.getenv("SERVER_ROOT_URL", "/"),
    orcha_core_user=_required_env("ORCHA_CORE_USER", "postgres"),
    orcha_core_password=_required_env("ORCHA_CORE_PASSWORD", "postgres"),
    orcha_core_server=_required_env("ORCHA_CORE_SERVER", "localhost:5432"),
    orcha_core_db=_required_env("ORCHA_CORE_DB", "postgres"),
)