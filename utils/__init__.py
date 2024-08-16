from __future__ import annotations

from datetime import datetime as dt

def format_dt(time: dt | None) -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S') if time else 'N/A'