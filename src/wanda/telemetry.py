"""
Opt-in, anonymous usage telemetry — OFF by default.

Wanda sends NOTHING unless a tester explicitly opts in (WANDA_TELEMETRY=on) AND a
collection endpoint is configured. Even then it sends only *operational* metrics —
mode, duration, counts, outcome — and an anonymous install id. It never sends
pipeline / table / column names, workspace ids, query text, report content, or
secrets. Telemetry is fire-and-forget and can never delay or break a run.

    Enable:    set WANDA_TELEMETRY=on
    Endpoint:  set WANDA_TELEMETRY_URL=https://...   (or DEFAULT_TELEMETRY_URL below)
    Disable:   unset WANDA_TELEMETRY   (the default state)
"""
from __future__ import annotations

import atexit
import os
import platform
import threading
import uuid
from pathlib import Path

from .log_setup import get_logger

logger = get_logger("telemetry")

# CM Labs fills this with the beta collection endpoint (a Form / function URL).
# Empty means telemetry is a no-op even if a tester opts in.
DEFAULT_TELEMETRY_URL = ""

_TRUTHY = {"1", "true", "on", "yes"}
_threads: list[threading.Thread] = []
_atexit_registered = False


def _endpoint() -> str:
    return (os.environ.get("WANDA_TELEMETRY_URL") or DEFAULT_TELEMETRY_URL).strip()


def is_enabled() -> bool:
    """True only if the tester opted in AND a collection endpoint exists."""
    opted_in = os.environ.get("WANDA_TELEMETRY", "").strip().lower() in _TRUTHY
    return opted_in and bool(_endpoint())


def _install_id() -> str:
    """A stable anonymous id so distinct testers can be counted (never identified).
    Stored at ~/.wanda/install_id; falls back to a per-process id if unwritable."""
    try:
        path = Path.home() / ".wanda" / "install_id"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        new_id = uuid.uuid4().hex
        path.write_text(new_id, encoding="utf-8")
        return new_id
    except Exception:
        return "ephemeral-" + uuid.uuid4().hex


def emit(event: str, **fields) -> None:
    """Fire-and-forget an anonymous event. Never raises; never blocks the run.

    Pass only non-sensitive operational fields (status, mode, durations, counts).
    Callers must not pass pipeline names, query text, error messages, or secrets.
    """
    if not is_enabled():
        return
    try:
        from . import __version__ as wanda_version
    except Exception:
        wanda_version = "unknown"

    payload = {
        "event": event,
        "install_id": _install_id(),
        "wanda_version": wanda_version,
        "python": platform.python_version(),
        "os": platform.system(),
        **fields,
    }

    _threads[:] = [t for t in _threads if t.is_alive()]  # prune finished
    t = threading.Thread(target=_post, args=(_endpoint(), payload), daemon=True)
    t.start()
    _threads.append(t)

    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_flush)
        _atexit_registered = True


def _post(url: str, payload: dict) -> None:
    """POST one event, swallowing every error — telemetry must never affect a run."""
    try:
        import requests
        requests.post(url, json=payload, timeout=3)
    except Exception as exc:
        logger.debug("telemetry skipped: %s", exc)


def _flush() -> None:
    """At process exit, give in-flight events a brief moment to send (for the CLI,
    which exits quickly). Notebooks stay alive, so their events flush naturally."""
    for t in _threads:
        if t.is_alive():
            t.join(timeout=1.5)
