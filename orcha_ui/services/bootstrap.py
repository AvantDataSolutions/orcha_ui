from __future__ import annotations

from threading import Lock

from orcha.core import initialise

from orcha_ui.services.config import settings

_init_lock = Lock()
_is_initialised = False


def initialise_orcha() -> None:
    global _is_initialised
    if _is_initialised:
        return
    with _init_lock:
        if _is_initialised:
            return
        initialise(
            orcha_user=settings.orcha_core_user,
            orcha_pass=settings.orcha_core_password,
            orcha_server=settings.orcha_core_server,
            orcha_db=settings.orcha_core_db,
            application_name="orcha_ui",
        )
        _is_initialised = True