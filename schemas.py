"""Pydantic params models + SDL entity contracts for Google BigQuery
Connector. Module-scope (V17 federal invariant). Organized by domain:
connection, datasets, tables, jobs/queries, scheduled queries, audit.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ── Connection ──────────────────────────────────────────────────────────

class ConnectBigQueryParams(BaseModel):
    service_account_json: str = Field(
        "", description="Paste the full contents of your GCP Service Account JSON key file.",
    )
    label: str = Field("", description="Optional friendly name for this connection.")


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""
    project_id: str = ""


class ProviderConnectionList(sdl.Entity):
    items: list[ProviderConnection] = []


class DisconnectBigQueryParams(BaseModel):
    connection_id: str = Field(..., description="Connection id from list_connections.")


class DeleteResult(sdl.Entity):
    ok: bool = True
    detail: str = ""


# ── Datasets ────────────────────────────────────────────────────────────

class ListDatasetsParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")


class BigQueryDataset(sdl.Entity):
    dataset_id: str = ""
    location: str = ""
    default_table_expiration_ms: int = 0
    description: str = ""


class DatasetList(sdl.Entity):
    items: list[BigQueryDataset] = []


class GetDatasetParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    dataset_id: str = Field(..., description="Dataset id, e.g. 'sales_data'.")


class CreateDatasetParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    dataset_id: str = Field(..., description="New dataset id, e.g. 'sales_data'.")
    location: str = Field("US", description="Dataset location, e.g. 'US', 'EU', 'us-central1'.")
    description: str = Field("", description="Optional dataset description.")
    default_table_expiration_days: int = Field(
        0, description="Optional default table expiration in days (0 = never expire).",
    )


class DeleteDatasetParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    dataset_id: str = Field(..., description="Dataset id to delete.")
    delete_contents: bool = Field(
        False, description="If true, deletes all tables inside the dataset too. Cannot be undone.",
    )


# ── Tables ──────────────────────────────────────────────────────────────

class ListTablesParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    dataset_id: str = Field(..., description="Dataset id to list tables from.")


class BigQueryTable(sdl.Entity):
    table_id: str = ""
    dataset_id: str = ""
    num_rows: int = 0
    num_bytes: int = 0
    table_type: str = ""
    time_partitioning: str = ""


class TableList(sdl.Entity):
    items: list[BigQueryTable] = []


class GetTableParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    dataset_id: str = Field(..., description="Dataset id.")
    table_id: str = Field(..., description="Table id.")


class DeleteTableParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    dataset_id: str = Field(..., description="Dataset id.")
    table_id: str = Field(..., description="Table id to delete. Cannot be undone.")


# ── Jobs / Queries ────────────────────────────────────────────────────

class ExecuteQueryParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    query: str = Field(..., description="Standard SQL query to run, e.g. 'SELECT * FROM `project.dataset.table` LIMIT 100'.")
    dry_run: bool = Field(
        False, description="If true, only estimates bytes that would be processed/billed without running the query.",
    )
    max_results: int = Field(100, description="Maximum rows to return.")


class QueryResult(sdl.Entity):
    job_id: str = ""
    state: str = ""
    total_bytes_processed: int = 0
    total_rows: int = 0
    rows: list[dict] = []
    schema_fields: list[str] = []
    cache_hit: bool = False


class GetJobParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    job_id: str = Field(..., description="Job id from execute_query or list_jobs.")


class BigQueryJob(sdl.Entity):
    job_id: str = ""
    state: str = ""
    query_preview: str = ""
    total_bytes_processed: int = 0
    created: str = ""
    user_email: str = ""
    error: str = ""


class JobList(sdl.Entity):
    items: list[BigQueryJob] = []


class ListJobsParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    max_results: int = Field(25, description="Maximum jobs to return.")


class CancelJobParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    job_id: str = Field(..., description="Job id to cancel.")


# ── Scheduled queries (Data Transfer Service) ────────────────────────

class ListScheduledQueriesParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    location: str = Field("us", description="Region the scheduled queries live in, e.g. 'us', 'eu'.")


class ScheduledQuery(sdl.Entity):
    name: str = ""
    display_name: str = ""
    schedule: str = ""
    next_run_time: str = ""
    state: str = ""


class ScheduledQueryList(sdl.Entity):
    items: list[ScheduledQuery] = []


class CreateScheduledQueryParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    location: str = Field("us", description="Region to create the scheduled query in, e.g. 'us', 'eu'.")
    display_name: str = Field(..., description="Name shown for this scheduled query.")
    query: str = Field(..., description="SQL query to run on schedule.")
    schedule: str = Field(
        "every 24 hours", description="Schedule in BigQuery Data Transfer syntax, e.g. 'every 24 hours', 'every mon 09:00'.",
    )
    destination_dataset_id: str = Field(
        "", description="Optional dataset id to write results into as a new table.",
    )


class DeleteScheduledQueryParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    transfer_config_name: str = Field(..., description="Full transfer config resource name from list_scheduled_queries.")


class RunScheduledQueryParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")
    transfer_config_name: str = Field(..., description="Full transfer config resource name from list_scheduled_queries.")


# ── Audit ────────────────────────────────────────────────────────────

class AuditProjectParams(BaseModel):
    connection_id: str = Field("", description="Connection id; omit to use the only connected project.")


class AuditFinding(sdl.Entity):
    kind: str = ""
    detail: str = ""
    severity: str = "medium"


class AuditReport(sdl.Entity):
    findings: list[AuditFinding] = []
    summary: str = ""
