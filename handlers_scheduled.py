"""Scheduled queries (Data Transfer Service) handlers -- list/create/
delete/run. Same shape as Databricks Connector's handlers_repos_secrets.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import bigquery_client as bqc
from app import ext, chat
from handlers_connection import _resolve_connection
from schemas import (
    ListScheduledQueriesParams, ScheduledQueryList, ScheduledQuery,
    CreateScheduledQueryParams, DeleteScheduledQueryParams, DeleteResult,
    RunScheduledQueryParams,
)


def _to_sq(t: dict) -> ScheduledQuery:
    params = t.get("params", {}) or {}
    return ScheduledQuery(
        name=t.get("name", ""),
        display_name=t.get("displayName", ""),
        query=(params.get("query", "") or "")[:500],
        schedule=t.get("schedule", ""),
        state=t.get("state", ""),
    )


@chat.function(
    "list_scheduled_queries",
    "List scheduled queries (recurring BigQuery jobs via Data Transfer Service) configured for a location in the connected project.",
    action_type="read",
    chain_callable=True,
    data_model=ScheduledQueryList,
    event="bigquery-connector.list_scheduled_queries",
)
async def list_scheduled_queries(ctx, params: ListScheduledQueriesParams) -> ActionResult:
    """List scheduled queries."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        rows = await bqc.list_scheduled_queries(ctx, conn, params.location or "us")
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=ScheduledQueryList(items=[_to_sq(t) for t in rows]), summary="Scheduled queries listed.")


@chat.function(
    "create_scheduled_query",
    "Create a new scheduled query (recurring BigQuery job) via Data Transfer Service.",
    action_type="write",
    chain_callable=True,
    data_model=ScheduledQuery,
    effects=["create:resource"],
    event="bigquery-connector.create_scheduled_query",
)
async def create_scheduled_query(ctx, params: CreateScheduledQueryParams) -> ActionResult:
    """Create a scheduled query."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        row = await bqc.create_scheduled_query(
            ctx, conn, params.location or "us", params.display_name,
            params.query, params.schedule or "every 24 hours",
        )
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_to_sq(row), summary="Scheduled query created.")


@chat.function(
    "delete_scheduled_query",
    "Permanently delete a scheduled query. Cannot be undone.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    effects=["delete:resource"],
    event="bigquery-connector.delete_scheduled_query",
)
async def delete_scheduled_query(ctx, params: DeleteScheduledQueryParams) -> ActionResult:
    """Delete a scheduled query."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        await bqc.delete_scheduled_query(ctx, conn, params.transfer_config_name)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Scheduled query deleted."), summary="Scheduled query deleted.")


@chat.function(
    "run_scheduled_query",
    "Manually trigger a scheduled query to run right now, regardless of its schedule.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    effects=["update:resource"],
    event="bigquery-connector.run_scheduled_query",
)
async def run_scheduled_query(ctx, params: RunScheduledQueryParams) -> ActionResult:
    """Run a scheduled query now."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        await bqc.run_scheduled_query(ctx, conn, params.transfer_config_name)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Scheduled query run triggered."), summary="Scheduled query run requested.")
