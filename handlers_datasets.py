"""Dataset + table handlers -- list/get/create/delete datasets, list/get/
delete tables. Same shape as Databricks Connector's handlers_catalog.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import bigquery_client as bqc
from app import ext, chat
from handlers_connection import _resolve_connection
from schemas import (
    ListDatasetsParams, DatasetList, BigQueryDataset,
    GetDatasetParams, CreateDatasetParams, DeleteDatasetParams, DeleteResult,
    ListTablesParams, TableList, BigQueryTable,
    GetTableParams, DeleteTableParams,
)


def _to_dataset(d: dict) -> BigQueryDataset:
    ref = d.get("datasetReference", {}) or {}
    return BigQueryDataset(
        dataset_id=ref.get("datasetId", d.get("id", "")),
        location=d.get("location", ""),
        default_table_expiration_ms=int(d.get("defaultTableExpirationMs", 0) or 0),
        description=d.get("description", "") or "",
    )


def _to_table(t: dict) -> BigQueryTable:
    ref = t.get("tableReference", {}) or {}
    return BigQueryTable(
        table_id=ref.get("tableId", t.get("id", "")),
        table_type=t.get("type", ""),
        num_rows=int(t.get("numRows", 0) or 0),
        num_bytes=int(t.get("numBytes", 0) or 0),
        time_partitioning=bool(t.get("timePartitioning")),
    )


@chat.function(
    "list_datasets",
    "List BigQuery datasets in the connected project, with location and default table expiration.",
    action_type="read",
    chain_callable=True,
    data_model=DatasetList,
    event="bigquery-connector.list_datasets",
)
async def list_datasets(ctx, params: ListDatasetsParams) -> ActionResult:
    """List datasets."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        rows = await bqc.list_datasets(ctx, conn)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DatasetList(items=[_to_dataset(d) for d in rows]), summary="Datasets listed.")


@chat.function(
    "get_dataset",
    "Read one BigQuery dataset in full by its id.",
    action_type="read",
    chain_callable=True,
    data_model=BigQueryDataset,
    event="bigquery-connector.get_dataset",
)
async def get_dataset(ctx, params: GetDatasetParams) -> ActionResult:
    """Read one dataset."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        row = await bqc.get_dataset(ctx, conn, params.dataset_id)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_to_dataset(row), summary="Dataset retrieved.")


@chat.function(
    "create_dataset",
    "Create a new BigQuery dataset in the connected project.",
    action_type="write",
    chain_callable=True,
    data_model=BigQueryDataset,
    effects=["create:resource"],
    event="bigquery-connector.create_dataset",
)
async def create_dataset(ctx, params: CreateDatasetParams) -> ActionResult:
    """Create a dataset."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        row = await bqc.create_dataset(
            ctx, conn, params.dataset_id, params.location or "US",
            params.description, params.default_table_expiration_ms,
        )
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_to_dataset(row), summary="Dataset created.")


@chat.function(
    "delete_dataset",
    "Permanently delete a BigQuery dataset. Cannot be undone.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    effects=["delete:resource"],
    event="bigquery-connector.delete_dataset",
)
async def delete_dataset(ctx, params: DeleteDatasetParams) -> ActionResult:
    """Delete a dataset."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        await bqc.delete_dataset(ctx, conn, params.dataset_id, params.delete_contents)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail=f"Dataset '{params.dataset_id}' deleted."), summary="Dataset deleted.")


@chat.function(
    "list_tables",
    "List tables inside one BigQuery dataset.",
    action_type="read",
    chain_callable=True,
    data_model=TableList,
    event="bigquery-connector.list_tables",
)
async def list_tables(ctx, params: ListTablesParams) -> ActionResult:
    """List tables."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        rows = await bqc.list_tables(ctx, conn, params.dataset_id)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=TableList(items=[_to_table(t) for t in rows]), summary="Tables listed.")


@chat.function(
    "get_table",
    "Read one BigQuery table in full -- schema, row count, size, and partitioning.",
    action_type="read",
    chain_callable=True,
    data_model=BigQueryTable,
    event="bigquery-connector.get_table",
)
async def get_table(ctx, params: GetTableParams) -> ActionResult:
    """Read one table."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        row = await bqc.get_table(ctx, conn, params.dataset_id, params.table_id)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_to_table(row), summary="Table retrieved.")


@chat.function(
    "delete_table",
    "Permanently delete a BigQuery table. Cannot be undone.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    effects=["delete:resource"],
    event="bigquery-connector.delete_table",
)
async def delete_table(ctx, params: DeleteTableParams) -> ActionResult:
    """Delete a table."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        await bqc.delete_table(ctx, conn, params.dataset_id, params.table_id)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail=f"Table '{params.table_id}' deleted."), summary="Table deleted.")
