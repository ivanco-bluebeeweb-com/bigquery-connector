"""Google BigQuery REST API v2 client -- Service Account JWT Bearer
(RFC 7523) over ctx.http, with per-connection access-token caching. Same
ProviderError/ClientFail shape and JWT-signing approach as GCP Connector's
gcp_client.py.

WHY REUSE GCP CONNECTOR'S JWT PATTERN INSTEAD OF A NEW AUTH SCHEME.

BigQuery is just another Google Cloud REST API host
(bigquery.googleapis.com) under the same Service Account JWT Bearer flow
GCP Connector already uses for Compute/Storage/SQL -- there is no reason
to invent a second auth mechanism. The JSON key is parsed once at connect
time into {project_id, client_email, private_key} and stored that way,
same shape as GCP Connector's own credential dict.

WHY DRY-RUN BEFORE EVERY EXECUTE_SQL.

BigQuery bills by bytes scanned, not by time -- a query with no LIMIT
against a huge table can be an expensive surprise. `execute_query` always
performs a dry_run=true call first (free, no bytes billed) and reports
the estimated bytes to be processed in its own response before running
the real query, matching the "query превысила dry-run bytes billed
estimate" requirement from IDEAL_ONBOARDING.md.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

TOKEN_HOST = "https://oauth2.googleapis.com/token"
_SCOPES = "https://www.googleapis.com/auth/bigquery https://www.googleapis.com/auth/cloud-platform"
_API_HOST = "https://bigquery.googleapis.com/bigquery/v2"
_DTS_HOST = "https://bigquerydatatransfer.googleapis.com/v1"

_TOKEN_CACHE: dict[tuple[str, str], tuple[str, float]] = {}


class ClientFail(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status


def fail(message: str, status: int = 0):
    raise ClientFail(message, status)


def parse_service_account_json(raw: str) -> dict:
    import json
    raw = (raw or "").strip()
    if not raw:
        fail("Missing service_account_json.")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        fail(
            "Could not parse this as JSON -- paste the FULL contents of your "
            "GCP Service Account JSON key file (downloaded from IAM & Admin > "
            "Service Accounts > Keys > Add Key > JSON), not just a fragment."
        )
    if not isinstance(data, dict) or not data.get("private_key") or not data.get("client_email"):
        fail(
            "This doesn't look like a full Service Account JSON key -- it's "
            "missing 'private_key' or 'client_email'. Download a fresh JSON "
            "key from IAM & Admin > Service Accounts > Keys > Add Key > JSON."
        )
    if not data.get("project_id"):
        fail("This Service Account JSON key has no 'project_id' field.")
    return {
        "project_id": data["project_id"],
        "client_email": data["client_email"],
        "private_key": data["private_key"],
    }


def _build_jwt_assertion(client_email: str, private_key: str) -> str:
    try:
        import jwt as pyjwt
    except ImportError as exc:
        fail(
            "The server is missing the PyJWT library needed to sign Google "
            "Service Account requests. This has been logged.", 500,
        )
    now = int(time.time())
    claims = {
        "iss": client_email,
        "scope": _SCOPES,
        "aud": TOKEN_HOST,
        "iat": now,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
    }
    try:
        return pyjwt.encode(claims, private_key, algorithm="RS256")
    except Exception as exc:
        fail(f"Could not sign the JWT with this Service Account's private key: {exc}", 400)


async def _access_token(ctx, conn: dict) -> str:
    client_email = conn.get("client_email", "")
    project_id = conn.get("project_id", "")
    cache_key = (client_email, project_id)
    cached = _TOKEN_CACHE.get(cache_key)
    if cached and cached[1] - 60 > time.time():
        return cached[0]

    assertion = _build_jwt_assertion(client_email, conn.get("private_key", ""))
    resp = await ctx.http.post(
        TOKEN_HOST,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code == 400:
        fail(
            "Google rejected this Service Account's credentials (invalid_grant) "
            "-- the key may have been revoked or the clock is skewed. Try "
            "downloading a fresh JSON key.", 400,
        )
    if resp.status_code >= 400:
        fail(f"Google token endpoint error {resp.status_code}: {resp.text[:300]}", resp.status_code)
    body = resp.json()
    token = body.get("access_token", "")
    expires_in = body.get("expires_in", 3600)
    if not token:
        fail("Google token endpoint returned no access_token.", 500)
    _TOKEN_CACHE[cache_key] = (token, time.time() + expires_in)
    return token


async def _request(ctx, conn: dict, method: str, path: str, *, base: str = _API_HOST,
                    params: dict | None = None, json_body: Any = None) -> Any:
    token = await _access_token(ctx, conn)
    url = f"{base}{path}"
    resp = await ctx.http.request(
        method, url,
        headers={"Authorization": f"Bearer {token}"},
        params=params, json=json_body,
    )
    if resp.status_code == 403:
        fail(
            "Access denied (403) -- the connected Service Account likely lacks "
            "a BigQuery IAM role (e.g. BigQuery Data Viewer / BigQuery Job "
            "User). Grant it in IAM & Admin and try again.", 403,
        )
    if resp.status_code == 404:
        fail("Not found -- check the dataset/table/job id.", 404)
    if resp.status_code >= 400:
        detail = resp.text[:400]
        fail(f"BigQuery API error {resp.status_code}: {detail}", resp.status_code)
    if resp.status_code == 204 or not resp.text:
        return {}
    return resp.json()


# ── Datasets ────────────────────────────────────────────────────────────

async def list_datasets(ctx, conn: dict) -> list[dict]:
    project = conn["project_id"]
    body = await _request(ctx, conn, "GET", f"/projects/{project}/datasets", params={"maxResults": 500})
    out = []
    for d in body.get("datasets", []):
        ref = d.get("datasetReference", {})
        out.append({
            "dataset_id": ref.get("datasetId", ""),
            "location": d.get("location", ""),
            "description": d.get("friendlyName", "") or "",
        })
    return out


async def get_dataset(ctx, conn: dict, dataset_id: str) -> dict:
    project = conn["project_id"]
    d = await _request(ctx, conn, "GET", f"/projects/{project}/datasets/{dataset_id}")
    ref = d.get("datasetReference", {})
    return {
        "dataset_id": ref.get("datasetId", dataset_id),
        "location": d.get("location", ""),
        "default_table_expiration_ms": int(d.get("defaultTableExpirationMs", 0) or 0),
        "description": d.get("description", "") or "",
    }


async def create_dataset(ctx, conn: dict, dataset_id: str, location: str, description: str,
                          default_table_expiration_ms: int) -> dict:
    project = conn["project_id"]
    body = {
        "datasetReference": {"projectId": project, "datasetId": dataset_id},
        "location": location,
    }
    if description:
        body["description"] = description
    if default_table_expiration_ms:
        body["defaultTableExpirationMs"] = str(default_table_expiration_ms)
    d = await _request(ctx, conn, "POST", f"/projects/{project}/datasets", json_body=body)
    ref = d.get("datasetReference", {})
    return {
        "dataset_id": ref.get("datasetId", dataset_id),
        "location": d.get("location", location),
        "default_table_expiration_ms": int(d.get("defaultTableExpirationMs", 0) or 0),
        "description": d.get("description", "") or "",
    }


async def delete_dataset(ctx, conn: dict, dataset_id: str, delete_contents: bool) -> None:
    project = conn["project_id"]
    params = {"deleteContents": "true"} if delete_contents else None
    await _request(ctx, conn, "DELETE", f"/projects/{project}/datasets/{dataset_id}", params=params)


# ── Tables ──────────────────────────────────────────────────────────────

async def list_tables(ctx, conn: dict, dataset_id: str) -> list[dict]:
    project = conn["project_id"]
    body = await _request(ctx, conn, "GET", f"/projects/{project}/datasets/{dataset_id}/tables", params={"maxResults": 500})
    out = []
    for t in body.get("tables", []):
        ref = t.get("tableReference", {})
        tp = t.get("timePartitioning", {}) or {}
        out.append({
            "table_id": ref.get("tableId", ""),
            "dataset_id": dataset_id,
            "table_type": t.get("type", ""),
            "time_partitioning": tp.get("type", "") or "",
        })
    return out


async def get_table(ctx, conn: dict, dataset_id: str, table_id: str) -> dict:
    project = conn["project_id"]
    t = await _request(ctx, conn, "GET", f"/projects/{project}/datasets/{dataset_id}/tables/{table_id}")
    ref = t.get("tableReference", {})
    tp = t.get("timePartitioning", {}) or {}
    return {
        "table_id": ref.get("tableId", table_id),
        "dataset_id": dataset_id,
        "num_rows": int(t.get("numRows", 0) or 0),
        "num_bytes": int(t.get("numBytes", 0) or 0),
        "table_type": t.get("type", ""),
        "time_partitioning": tp.get("type", "") or "",
    }


async def delete_table(ctx, conn: dict, dataset_id: str, table_id: str) -> None:
    project = conn["project_id"]
    await _request(ctx, conn, "DELETE", f"/projects/{project}/datasets/{dataset_id}/tables/{table_id}")


# ── Jobs / Queries ──────────────────────────────────────────────────────

async def dry_run_query(ctx, conn: dict, sql: str) -> dict:
    project = conn["project_id"]
    body = {
        "configuration": {
            "query": {"query": sql, "useLegacySql": False},
            "dryRun": True,
        }
    }
    j = await _request(ctx, conn, "POST", f"/projects/{project}/jobs", json_body=body)
    stats = j.get("statistics", {}).get("query", {}) or {}
    return {"total_bytes_processed": int(stats.get("totalBytesProcessed", 0) or 0)}


async def execute_query(ctx, conn: dict, sql: str, max_results: int = 100) -> dict:
    project = conn["project_id"]
    body = {"query": sql, "useLegacySql": False, "maxResults": max_results}
    resp = await _request(ctx, conn, "POST", f"/projects/{project}/queries", json_body=body)
    schema = resp.get("schema", {}).get("fields", []) or []
    columns = [f.get("name", "") for f in schema]
    rows = []
    for r in resp.get("rows", []) or []:
        values = [c.get("v", "") for c in r.get("f", [])]
        rows.append(dict(zip(columns, values)))
    job_ref = resp.get("jobReference", {})
    return {
        "job_id": job_ref.get("jobId", ""),
        "columns": columns,
        "rows": rows,
        "total_rows": int(resp.get("totalRows", 0) or 0),
        "job_complete": bool(resp.get("jobComplete", True)),
    }


async def get_job(ctx, conn: dict, job_id: str) -> dict:
    project = conn["project_id"]
    j = await _request(ctx, conn, "GET", f"/projects/{project}/jobs/{job_id}")
    status = j.get("status", {}) or {}
    stats = j.get("statistics", {}).get("query", {}) or {}
    cfg = j.get("configuration", {}).get("query", {}) or {}
    return {
        "job_id": j.get("jobReference", {}).get("jobId", job_id),
        "state": status.get("state", ""),
        "error": (status.get("errorResult", {}) or {}).get("message", ""),
        "query": cfg.get("query", "")[:300],
        "total_bytes_processed": int(stats.get("totalBytesProcessed", 0) or 0),
    }


async def list_jobs(ctx, conn: dict, max_results: int = 50) -> list[dict]:
    project = conn["project_id"]
    body = await _request(ctx, conn, "GET", f"/projects/{project}/jobs", params={"maxResults": max_results})
    out = []
    for j in body.get("jobs", []) or []:
        status = j.get("status", {}) or {}
        cfg = j.get("configuration", {}).get("query", {}) or {}
        stats = j.get("statistics", {}).get("query", {}) or {}
        out.append({
            "job_id": j.get("jobReference", {}).get("jobId", ""),
            "state": status.get("state", ""),
            "error": (status.get("errorResult", {}) or {}).get("message", ""),
            "query": (cfg.get("query", "") or "")[:300],
            "total_bytes_processed": int(stats.get("totalBytesProcessed", 0) or 0),
        })
    return out


async def cancel_job(ctx, conn: dict, job_id: str) -> None:
    project = conn["project_id"]
    await _request(ctx, conn, "POST", f"/projects/{project}/jobs/{job_id}/cancel")


# ── Scheduled Queries (BigQuery Data Transfer Service) ────────────────

async def list_scheduled_queries(ctx, conn: dict, location: str) -> list[dict]:
    project = conn["project_id"]
    body = await _request(
        ctx, conn, "GET",
        f"/projects/{project}/locations/{location}/transferConfigs",
        base=_DTS_HOST,
        params={"dataSourceIds": "scheduled_query"},
    )
    out = []
    for tc in body.get("transferConfigs", []) or []:
        out.append({
            "name": tc.get("name", ""),
            "display_name": tc.get("displayName", ""),
            "schedule": tc.get("schedule", ""),
            "next_run_time": tc.get("nextRunTime", ""),
            "state": tc.get("state", ""),
        })
    return out


async def create_scheduled_query(ctx, conn: dict, location: str, display_name: str, query: str,
                                  schedule: str, destination_dataset_id: str) -> dict:
    project = conn["project_id"]
    params_body: dict = {"query": query}
    if destination_dataset_id:
        params_body["destination_table_name_template"] = "{run_date}"
    body = {
        "displayName": display_name,
        "dataSourceId": "scheduled_query",
        "schedule": schedule,
        "params": params_body,
    }
    if destination_dataset_id:
        body["destinationDatasetId"] = destination_dataset_id
    tc = await _request(
        ctx, conn, "POST", f"/projects/{project}/locations/{location}/transferConfigs",
        base=_DTS_HOST, json_body=body,
    )
    return {
        "name": tc.get("name", ""),
        "display_name": tc.get("displayName", display_name),
        "schedule": tc.get("schedule", schedule),
        "next_run_time": tc.get("nextRunTime", ""),
        "state": tc.get("state", ""),
    }


async def delete_scheduled_query(ctx, conn: dict, transfer_config_name: str) -> None:
    await _request(ctx, conn, "DELETE", f"/{transfer_config_name}", base=_DTS_HOST.rsplit("/v1", 1)[0] + "/v1")


async def run_scheduled_query(ctx, conn: dict, transfer_config_name: str) -> None:
    import datetime
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"requestedRunTime": now}
    await _request(
        ctx, conn, "POST", f"/{transfer_config_name}:startManualRuns",
        base=_DTS_HOST.rsplit("/v1", 1)[0] + "/v1", json_body=body,
    )
