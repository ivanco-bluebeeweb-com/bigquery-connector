"""Project audit -- aggregated health report. Same shape as Databricks
Connector's handlers_analytics.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import bigquery_client as bqc
from app import ext, chat
from handlers_connection import _resolve_connection
from schemas import AuditProjectParams, AuditReport, AuditFinding


@chat.function(
    "audit_project",
    "Build one aggregated health report across the connected BigQuery project: datasets with no default table expiration, non-partitioned large tables, and recent failed jobs.",
    action_type="read",
    chain_callable=True,
    data_model=AuditReport,
    event="bigquery-connector.audit_project",
)
async def audit_project(ctx, params: AuditProjectParams) -> ActionResult:
    """Audit the connected project."""
    conn = await _resolve_connection(ctx, params.connection_id)
    if isinstance(conn, ActionResult):
        return conn
    findings: list[AuditFinding] = []

    try:
        datasets = await bqc.list_datasets(ctx, conn)
    except bqc.ClientFail as exc:
        return ActionResult.error(str(exc))
    for d in datasets:
        ref = d.get("datasetReference", {}) or {}
        dataset_id = ref.get("datasetId", "")
        if not d.get("defaultTableExpirationMs"):
            findings.append(AuditFinding(
                kind="dataset_no_default_expiration",
                detail=f"Dataset '{dataset_id}' has no default table expiration -- tables accumulate indefinitely, growing storage costs.",
                severity="medium",
            ))
        try:
            tables = await bqc.list_tables(ctx, conn, dataset_id)
        except bqc.ClientFail:
            tables = []
        for t in tables:
            tref = t.get("tableReference", {}) or {}
            num_bytes = int(t.get("numBytes", 0) or 0)
            if num_bytes > 10 * 1024**3 and not t.get("timePartitioning"):
                findings.append(AuditFinding(
                    kind="large_table_not_partitioned",
                    detail=f"Table '{dataset_id}.{tref.get('tableId', '')}' is over 10GB and not time-partitioned -- queries against it likely scan more bytes (and cost more) than necessary.",
                    severity="high",
                ))

    try:
        jobs = await bqc.list_jobs(ctx, conn, 25)
    except bqc.ClientFail:
        jobs = []
    failed = [j for j in jobs if (j.get("status", {}) or {}).get("errorResult")]
    for j in failed[:5]:
        ref = j.get("jobReference", {}) or {}
        err = (j.get("status", {}) or {}).get("errorResult", {}) or {}
        findings.append(AuditFinding(
            kind="failed_job",
            detail=f"Job '{ref.get('jobId', '')}' failed: {err.get('message', 'unknown error')}",
            severity="low",
        ))

    summary = f"{len(datasets)} dataset(s) checked, {len(findings)} finding(s)."
    return ActionResult.success(data=AuditReport(findings=findings, summary=summary))
