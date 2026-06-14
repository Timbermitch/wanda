"""
log_setup.py — shared logging configuration for Wanda.

Replaces ad-hoc ``print()`` calls used for diagnostics so verbosity can be
switched without editing code. Set ``WANDA_LOG_LEVEL`` (e.g. DEBUG, INFO,
WARNING) to control how much Wanda narrates. Logs go to stderr so they never
mix with the report Wanda writes to stdout.
"""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def get_logger(name: str = "wanda") -> logging.Logger:
    """Return a configured logger. Idempotent — safe to call from any module."""
    global _CONFIGURED
    if not _CONFIGURED:
        level_name = os.getenv("WANDA_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))
        root = logging.getLogger("wanda")
        root.setLevel(level)
        root.addHandler(handler)
        root.propagate = False
        _CONFIGURED = True
    return logging.getLogger(name if name.startswith("wanda") else f"wanda.{name}")
