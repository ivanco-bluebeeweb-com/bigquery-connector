"""App settings panel -- connection management (disconnect rows) plus the
one-time onboarding instructions. Nothing here duplicates the sidebar.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
from handlers_connection import _load_connections


@ext.panel("bigquery_settings", slot="center", center_overlay=True)
async def bigquery_settings(ctx) -> ui.UINode:
    connections = await _load_connections(ctx)
    rows = []
    for c in connections:
        rows.append(ui.Stack(direction="h", gap=2, align="center", children=[
            ui.Text(c.get("label") or c.get("project_id", ""), variant="body"),
            ui.Text(c.get("client_email", ""), variant="caption"),
            ui.Button(
                "Отключить", variant="destructive",
                on_click=ui.Call("disconnect_bigquery", params={"connection_id": c.get("id", "")}),
            ),
        ]))
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Text("Как получить Service Account JSON", variant="subtitle"),
        ui.Text(
            "В Google Cloud Console откройте IAM & Admin > Service Accounts, "
            "выберите (или создайте) сервисный аккаунт с ролями BigQuery Data "
            "Viewer + BigQuery Job User (или выше), затем Keys > Add Key > "
            "JSON -- скачается файл ключа. Вставьте его содержимое целиком в "
            "форму подключения.",
            variant="body",
        ),
        ui.Divider(),
        ui.Text("Подключённые проекты", variant="subtitle"),
        *(rows if rows else [ui.Empty(message="Нет подключённых проектов.", icon="database")]),
    ])
