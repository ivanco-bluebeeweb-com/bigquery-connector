"""Jobs/queries handlers -- execute (with dry-run cost preview), get/list/
cancel jobs. Same shape as Databricks Connector's handlers_jobs.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import bigquery_client as bqc
from app import ext, chat
from handlers_connection import _resolve_connection
from schemas import (
    ExecuteQueryParams, QueryResult, GetJobParams, BigQueryJob,
    ListJobsParams, JobList, CancelJobParams, DeleteResult,
)


def _to_job(j: dict) -> BigQueryJob:
    ref = j.get("jobReference", {}) or {}
    status = j.get("status", {}) or {}
    stats = j.get("statistics", {}) or {}
    q = stats.get("query", {}) or {}
    cfg = j.get("configuration", {}).get("query", {}) if j.get("configuration") else {}
    err = status.get("errorResult", {}) or {}
    return BigQueryJob(
        job_id=ref.get("jobId", ""),
        state=status.get("state", ""),
        query=(cfg.get("query", "") or "")[:500],
        total_bytes_processed=int(q.get("totalBytesProcessed", 0) or 0),
        error_message=err.get("message", "") if err else "",
    )


@chat.function(
    "execute_sql",
    "Run a SQL query against BigQuery. Always dry-runs first to estimate bytes billed, then executes and returns result rows.",
    action_type="write",
    chain_callable=True,
    data_model=QueryResult,
    effects=["create:resource"],
    event="bigquery-connector.execute_sql",
)
async def execute_sql(ctx, params: ExecuteQueryParams) -> ActionResult:
    """Execute a SQL query, with a dry-run cost estimate first."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        estimate = await bqc.dry_run_query(ctx, conn, params.sql)
    except bqc.ClientFail as exc:
        return ActionResult.error(f"Query validation failed: {exc}")
    try:
        result = await bqc.execute_query(ctx, conn, params.sql, params.max_results or 100)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))

    rows = result.get("rows", []) or []
    schema = (result.get("schema", {}) or {}).get("fields", []) or []
    col_names = [f.get("name", "") for f in schema]
    parsed_rows = []
    for r in rows:
        values = [c.get("v", "") for c in r.get("f", [])]
        parsed_rows.append(dict(zip(col_names, values)))

    return ActionResult.success(data=QueryResult(
        job_id=(result.get("jobReference", {}) or {}).get("jobId", ""),
        estimated_bytes_processed=int(
            (estimate.get("statistics", {}) or {}).get("query", {}).get("totalBytesProcessed", 0) or 0
        ),
        total_rows=int(result.get("totalRows", 0) or 0),
        columns=col_names,
        rows=parsed_rows,
    ), summary="Execute sql done.")


@chat.function(
    "get_job",
    "Read one BigQuery job in full by its id -- status, timing, and any error info.",
    action_type="read",
    chain_callable=True,
    data_model=BigQueryJob,
    event="bigquery-connector.get_job",
)
async def get_job(ctx, params: GetJobParams) -> ActionResult:
    """Read one job."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        row = await bqc.get_job(ctx, conn, params.job_id)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_to_job(row), summary="Job retrieved.")


@chat.function(
    "list_jobs",
    "List recent BigQuery jobs (query runs) in the connected project, most recent first.",
    action_type="read",
    chain_callable=True,
    data_model=JobList,
    event="bigquery-connector.list_jobs",
)
async def list_jobs(ctx, params: ListJobsParams) -> ActionResult:
    """List jobs."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        rows = await bqc.list_jobs(ctx, conn, params.max_results or 50)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=JobList(items=[_to_job(j) for j in rows]), summary="Jobs listed.")


@chat.function(
    "cancel_job",
    "Cancel a running BigQuery job.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    effects=["update:resource"],
    event="bigquery-connector.cancel_job",
)
async def cancel_job(ctx, params: CancelJobParams) -> ActionResult:
    """Cancel a job."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    try:
        await bqc.cancel_job(ctx, conn, params.job_id)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail=f"Job '{params.job_id}' cancel requested."), summary="Cancel job done.")
