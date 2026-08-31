"""Connection management: connect/disconnect BigQuery projects. Same shape
as Databricks Connector's / Snowflake Connector's handlers_connection.py --
async, one secret holding a JSON array, ActionResult.success()/.error().
"""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import bigquery_client as bqc
from app import ext, chat
from schemas import (
    NoParams,
    ConnectBigQueryParams, ProviderConnection, ProviderConnectionList,
    DisconnectBigQueryParams, DeleteResult,
)

_CONN_SECRET = "bigquery_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_CONN_SECRET)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, items: list[dict]) -> None:
    await ctx.secrets.set(_CONN_SECRET, json.dumps(items))


async def _resolve_connection(ctx, connection_id: str):
    conns = await _load_connections(ctx)
    if not conns:
        return ActionResult.error("No Google Cloud project connected yet.")
    if connection_id:
        for c in conns:
            if c.get("id") == connection_id:
                return c
        return ActionResult.error(f"No BigQuery connection with id '{connection_id}'.")
    if len(conns) == 1:
        return conns[0]
    return ActionResult.error(
        "Multiple projects are connected -- pass connection_id to pick one."
    )


def _to_entity(c: dict) -> ProviderConnection:
    return ProviderConnection(
        id=c.get("id", ""),
        title=c.get("label") or c.get("project_id", ""),
        connected=True,
        detail=c.get("client_email", ""),
        project_id=c.get("project_id", ""),
    )


@chat.function(
    "connect_bigquery",
    "Connect your own Google Cloud project by pasting a Service Account JSON key, after checking it actually works against BigQuery.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    effects=["create:resource"],
    event="bigquery-connector.connect_bigquery",
)
async def connect_bigquery(ctx, params: ConnectBigQueryParams) -> ActionResult:
    """Connect a BigQuery project."""
    try:
        creds = bqc.parse_service_account_json(params.service_account_json)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))

    conn = {
        "id": str(uuid.uuid4()),
        "label": params.label,
        "project_id": creds["project_id"],
        "client_email": creds["client_email"],
        "private_key": creds["private_key"],
    }
    try:
        await bqc.list_datasets(ctx, conn)
    except bqc.ClientFail as exc:
        return ActionResult.error(f"Could not connect to BigQuery: {exc}")

    conns = await _load_connections(ctx)
    conns.append(conn)
    await _save_connections(ctx, conns)
    return ActionResult.success(data=_to_entity(conn), summary="Bigquery connected.")


@chat.function(
    "list_connections",
    "List the connected Google Cloud projects (BigQuery).",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnectionList,
    event="bigquery-connector.list_connections",
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List connections."""
    conns = await _load_connections(ctx)
    return ActionResult.success(data=ProviderConnectionList(items=[_to_entity(c) for c in conns]), summary="Connections listed.")


@chat.function(
    "disconnect_bigquery",
    "Disconnect a Google Cloud project: deletes the saved Service Account key. Nothing in BigQuery itself is changed.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    effects=["delete:resource"],
    event="bigquery-connector.disconnect_bigquery",
)
async def disconnect_bigquery(ctx, params: DisconnectBigQueryParams) -> ActionResult:
    """Disconnect a project."""
    conns = await _load_connections(ctx)
    remaining = [c for c in conns if c.get("id") != params.connection_id]
    if len(remaining) == len(conns):
        return ActionResult.error(f"No BigQuery connection with id '{params.connection_id}'.")
    await _save_connections(ctx, remaining)
    return ActionResult.success(data=DeleteResult(ok=True, detail="Disconnected."), summary="Bigquery disconnected.")
