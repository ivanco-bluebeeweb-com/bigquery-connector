"""Panel UI -- connections list/connect form + datasets / tables /
jobs & queries / scheduled queries in the left sidebar and main center
panel.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as Databricks
Connector's / Snowflake Connector's panels.py).

Form container is stretched full-width (align="stretch") and every field
carries its own visible label via the _field() wrapper below plus a
contextually specific placeholder. No setup instructions are duplicated
here that already exist in "App settings" (panels_settings.py).
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
from handlers_connection import _load_connections


def _field(label: str, node: ui.UINode) -> ui.UINode:
    return ui.Stack(direction="v", gap=1, align="stretch", children=[
        ui.Text(label, variant="caption"),
        node,
    ])


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", full_width=True,
        on_click=ui.Call("__panel__bigquery_settings"),
    )


def _connect_form() -> ui.UINode:
    return ui.Stack(direction="v", gap=1, align="stretch", children=[
        ui.Empty(
            message="Connect your Google Cloud project to manage BigQuery datasets, tables, queries, and scheduled jobs. Get a Service Account JSON key from IAM & Admin > Service Accounts > Keys > Add Key > JSON.",
            icon="database",
        ),
        ui.Form(
            action="connect_bigquery", submit_label="Подключить",
            children=[
              ui.Stack(direction="v", gap=3, align="stretch", children=[
                _field("Service Account JSON", ui.Password(
                    param_name="service_account_json",
                    placeholder="Вставьте содержимое JSON-файла целиком",
                )),
                _field("Имя подключения (опционально)", ui.Input(
                    param_name="label",
                    placeholder="Мой GCP-проект",
                )),
              ]),
            ],
        ),
    ])


@ext.panel("bigquery_sidebar", slot="left")
async def bigquery_sidebar(ctx) -> ui.UINode:
    connections = await _load_connections(ctx)
    if not connections:
        return ui.Stack(direction="v", gap=3, align="stretch", children=[
            _connect_form(),
        ])
    label = connections[0].get("label") or connections[0].get("project_id", "")
    nav = [
        ("Datasets", "bigquery_datasets"),
        ("Tables", "bigquery_tables"),
        ("Jobs & Queries", "bigquery_jobs"),
        ("Scheduled Queries", "bigquery_scheduled"),
    ]
    return ui.Stack(direction="v", gap=1, align="start", children=[
        ui.Text(label, variant="body"),
        ui.Divider(),
        *[ui.ListItem(id=target, title=lbl, on_click=ui.Call(f"__panel__{target}")) for lbl, target in nav],
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("bigquery_datasets", slot="center", center_overlay=True)
async def bigquery_datasets_panel(ctx) -> ui.UINode:
    connections = await _load_connections(ctx)
    if not connections:
        return ui.Empty(message="Connect a Google Cloud project first.", icon="database")
    from handlers_datasets import list_datasets
    from schemas import ListDatasetsParams
    result = await list_datasets(ctx, ListDatasetsParams(connection_id=""))
    items = result.data.items if result.ok and result.data else []
    if not items:
        return ui.Empty(message="No datasets found in this project.", icon="database")
    return ui.DataTable(
        columns=[
            {"key": "dataset_id", "label": "Dataset"},
            {"key": "location", "label": "Location"},
            {"key": "default_table_expiration_ms", "label": "Default TTL (ms)"},
        ],
        rows=[i.model_dump() for i in items],
    )


@ext.panel("bigquery_tables", slot="center", center_overlay=True)
async def bigquery_tables_panel(ctx) -> ui.UINode:
    connections = await _load_connections(ctx)
    if not connections:
        return ui.Empty(message="Connect a Google Cloud project first.", icon="database")
    from handlers_datasets import list_datasets, list_tables
    from schemas import ListDatasetsParams, ListTablesParams
    ds_result = await list_datasets(ctx, ListDatasetsParams(connection_id=""))
    datasets = ds_result.data.items if ds_result.ok and ds_result.data else []
    if not datasets:
        return ui.Empty(message="No datasets found in this project.", icon="database")
    all_rows = []
    for d in datasets:
        t_result = await list_tables(ctx, ListTablesParams(connection_id="", dataset_id=d.dataset_id))
        t_items = t_result.data.items if t_result.ok and t_result.data else []
        for t in t_items:
            row = t.model_dump()
            row["dataset_id"] = d.dataset_id
            all_rows.append(row)
    if not all_rows:
        return ui.Empty(message="No tables found in any dataset.", icon="database")
    return ui.DataTable(
        columns=[
            {"key": "dataset_id", "label": "Dataset"},
            {"key": "table_id", "label": "Table"},
            {"key": "table_type", "label": "Type"},
            {"key": "num_rows", "label": "Rows"},
            {"key": "num_bytes", "label": "Bytes"},
            {"key": "time_partitioning", "label": "Partitioned"},
        ],
        rows=all_rows,
    )


@ext.panel("bigquery_jobs", slot="center", center_overlay=True)
async def bigquery_jobs_panel(ctx) -> ui.UINode:
    connections = await _load_connections(ctx)
    if not connections:
        return ui.Empty(message="Connect a Google Cloud project first.", icon="database")
    from handlers_jobs import list_jobs
    from schemas import ListJobsParams
    result = await list_jobs(ctx, ListJobsParams(connection_id="", max_results=50))
    items = result.data.items if result.ok and result.data else []
    table = ui.Empty(message="No recent jobs.", icon="activity") if not items else ui.DataTable(
        columns=[
            {"key": "job_id", "label": "Job"},
            {"key": "state", "label": "State"},
            {"key": "query", "label": "Query"},
            {"key": "total_bytes_processed", "label": "Bytes processed"},
        ],
        rows=[i.model_dump() for i in items],
    )
    return ui.Stack(direction="v", gap=2, align="stretch", children=[
        ui.Form(
            action="execute_sql", submit_label="Выполнить запрос",
            children=[
              ui.Stack(direction="v", gap=3, align="stretch", children=[
                _field("SQL-запрос", ui.Input(
                    param_name="sql",
                    placeholder="SELECT * FROM `project.dataset.table` LIMIT 100",
                )),
              ]),
            ],
        ),
        ui.Divider(),
        table,
    ])


@ext.panel("bigquery_scheduled", slot="center", center_overlay=True)
async def bigquery_scheduled_panel(ctx) -> ui.UINode:
    connections = await _load_connections(ctx)
    if not connections:
        return ui.Empty(message="Connect a Google Cloud project first.", icon="database")
    from handlers_scheduled import list_scheduled_queries
    from schemas import ListScheduledQueriesParams
    result = await list_scheduled_queries(ctx, ListScheduledQueriesParams(connection_id="", location="us"))
    items = result.data.items if result.ok and result.data else []
    if not items:
        return ui.Empty(message="No scheduled queries configured.", icon="clock")
    return ui.DataTable(
        columns=[
            {"key": "display_name", "label": "Name"},
            {"key": "schedule", "label": "Schedule"},
            {"key": "state", "label": "State"},
            {"key": "query", "label": "Query"},
        ],
        rows=[i.model_dump() for i in items],
    )
