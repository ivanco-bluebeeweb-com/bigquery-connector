"""Entry point -- imports every module so its @chat.function/@ext.panel
decorators register, then exposes `ext` for the Imperal runtime. Purges
stale sys.modules cache first (same defensive pattern as Databricks
Connector's main.py) so a hot-reload never serves stale bytecode.
"""
from __future__ import annotations

import sys

_MODULES = [
    "app", "schemas", "bigquery_client",
    "handlers_connection", "handlers_datasets", "handlers_jobs",
    "handlers_scheduled", "handlers_analytics",
    "panels", "panels_settings",
]
for _m in _MODULES:
    sys.modules.pop(_m, None)

from app import ext  # noqa: E402
import handlers_connection  # noqa: E402,F401
import handlers_datasets  # noqa: E402,F401
import handlers_jobs  # noqa: E402,F401
import handlers_scheduled  # noqa: E402,F401
import handlers_analytics  # noqa: E402,F401
import panels  # noqa: E402,F401
import panels_settings  # noqa: E402,F401

__all__ = ["ext"]
