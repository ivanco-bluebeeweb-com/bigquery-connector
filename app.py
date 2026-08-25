"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK, SAME REASONING AS GCP CONNECTOR / SNOWFLAKE CONNECTOR.

BigQuery is the user's OWN GCP project -- Imperal cannot and should not
broker access to someone else's data warehouse centrally. The user
provides their own Service Account JSON key, Vault-encrypted via
`ctx.secrets`, and every call runs against their own GCP project.

WHY A SINGLE service_account_json FIELD, NOT SEPARATE FIELDS.

The Service Account JSON key downloaded from IAM & Admin already contains
project_id, client_email, and private_key together -- same precedent as
GCP Connector's own `connect_gcp`. Asking the user to split it into
separate fields invites copy-paste errors (e.g. missing newlines in the
private key), so the whole JSON blob is pasted once and parsed server-side.

CONNECTIONS ARE STORED AS ONE JSON ARRAY, SAME AS DATABRICKS/SNOWFLAKE.

`bigquery_connections` holds a JSON array of
`{id, label, project_id, client_email, private_key}` objects, and every
tool's `connection_id` parameter addresses one entry -- see
handlers_connection.py's `_load_connections`/`_save_connections`.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "bigquery-connector",
    version="0.1.0",
    display_name="Google BigQuery",
    description=(
        "Connect your own Google BigQuery project to manage datasets, tables, "
        "queries/jobs, and scheduled queries, and audit warehouse cost and "
        "health -- from Imperal. Uses your own GCP Service Account -- nothing "
        "is hosted or proxied by Imperal beyond the request itself."
    ),
    icon="icon.svg",
    capabilities=[
        "bigquery:read",
        "bigquery:write",
    ],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="bigquery",
    description=(
        "Google BigQuery Connector -- connect your own GCP project via "
        "Service Account, then manage datasets/tables/queries/jobs/"
        "scheduled queries, and audit project health and cost."
    ),
)

ext.secret(
    "bigquery_connections",
    (
        "Your connected Google Cloud projects -- stored as a JSON array, "
        "one entry per project, each with its own Service Account "
        "credentials (project_id, client_email, private_key). Managed "
        "through connect_bigquery / disconnect_bigquery -- you should not "
        "need to edit this directly."
    ),
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=180,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call -- just confirms at
    least one project connection is stored, same shape as Databricks
    Connector's health_check."""
    import json as _json
    raw = await ctx.secrets.get("bigquery_connections")
    try:
        count = len(_json.loads(raw)) if raw else 0
    except Exception:
        count = 0
    return {
        "healthy": True,
        "detail": (
            f"{count} Google Cloud project(s) connected." if count
            else "Not connected yet -- run connect_bigquery."
        ),
    }
