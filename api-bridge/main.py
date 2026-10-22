from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
load_dotenv(ROOT / ".env")

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_UPLOAD_ROWS = 100_000

app = FastAPI(title="Data Sentient API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Dataset:
    def __init__(self, name: str, frame: pd.DataFrame, filename: str):
        self.name = name
        self.frame = frame
        self.filename = filename
        self.created_at = datetime.now(timezone.utc)
        self.layer = "RAW"


class QueryRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    table: str | None = None


datasets: dict[str, Dataset] = {}
audit_events: list[dict[str, Any]] = []


def _seed_demo_data() -> None:
    if datasets:
        return
    frame = pd.DataFrame(
        [
            {"order_id": 10401 + index, "region": ["West", "East", "Central", "South"][index % 4],
             "category": ["Technology", "Furniture", "Office Supplies"][index % 3],
             "revenue": round(1240 + (index * 173.45) % 9800, 2),
             "order_date": (datetime(2026, 9, 1) + pd.Timedelta(days=index % 45)).date().isoformat()}
            for index in range(64)
        ]
    )
    datasets["DEMO_ORDERS"] = Dataset("DEMO_ORDERS", frame, "demo_orders.csv")


def _record_event(
    filename: str, table: str, status: str, rows: int, details: str
) -> dict[str, Any]:
    event = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "table": table,
        "status": status,
        "rows": rows,
        "details": details,
    }
    audit_events.insert(0, event)
    del audit_events[200:]
    return event


def _table_name(filename: str) -> str:
    stem = Path(filename).stem
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_").upper()
    if not normalized or not normalized[0].isalpha():
        normalized = f"TABLE_{normalized}"
    return normalized[:100]


def _parse_csv(contents: bytes, filename: str) -> pd.DataFrame:
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400, detail="CSV must use UTF-8 encoding."
        ) from error

    if not text.strip():
        raise HTTPException(status_code=400, detail="The uploaded CSV is empty.")
    try:
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
            frame = pd.read_csv(io.StringIO(text), sep=dialect.delimiter)
        except csv.Error:
            frame = pd.read_csv(io.StringIO(text))
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as error:
        raise HTTPException(
            status_code=400, detail=f"Could not parse CSV: {error}"
        ) from error

    if frame.empty:
        raise HTTPException(status_code=400, detail="The CSV contains no data rows.")
    if len(frame.columns) > 200:
        raise HTTPException(status_code=400, detail="CSV cannot contain more than 200 columns.")
    if len(frame) > MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"CSV cannot contain more than {MAX_UPLOAD_ROWS:,} rows.",
        )
    frame.columns = [str(column).strip() for column in frame.columns]
    if any(not column for column in frame.columns):
        raise HTTPException(status_code=400, detail="Every CSV column needs a name.")
    if frame.columns.duplicated().any():
        raise HTTPException(status_code=400, detail="CSV column names must be unique.")
    return frame


def _backend_storage_enabled() -> bool:
    return os.getenv("DATA_SENTIENT_STORAGE", "local").lower() == "snowflake"


def _ensure_backend_importable() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def _ingest_with_backend(path: str) -> str:
    _ensure_backend_importable()
    from agent_ingest import ingest_csv

    result = ingest_csv(path, use_agent=False)
    if result.startswith("❌"):
        raise RuntimeError(result)
    return result


def _process_with_backend(table: str) -> None:
    _ensure_backend_importable()
    from curated_agent import load_raw_to_curated

    load_raw_to_curated(table, use_agent=False)


def _preview(frame: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    return frame.head(limit).astype(object).where(pd.notna(frame.head(limit)), None).to_dict("records")


def _configured_ai_client() -> tuple[str, Any, str] | None:
    from openai import OpenAI

    provider_setting = os.getenv("AI_PROVIDER", "auto").strip().lower()
    if provider_setting == "auto":
        if os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            return None
    elif provider_setting in {"gemini", "openai"}:
        provider = provider_setting
    else:
        raise ValueError("AI_PROVIDER must be 'auto', 'gemini', or 'openai'.")

    key_name = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    api_key = os.getenv(key_name)
    if not api_key:
        raise ValueError(f"{key_name} must be set when AI_PROVIDER={provider}.")

    if provider == "gemini":
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    else:
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return provider, client, model


def _model_sql(question: str, item: Dataset, client: Any, model: str) -> str:
    schema = [
        {"name": str(column), "type": str(dtype)}
        for column, dtype in item.frame.dtypes.items()
    ]
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Write one read-only SQLite SELECT statement for the user's question. "
                    f"The only available table is {item.name}. Use only its listed columns. "
                    "Return SQL only, with no markdown or explanation."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\nTable: {item.name}\nSchema: {schema}",
            },
        ],
    )
    sql = response.choices[0].message.content
    if not sql:
        raise ValueError("The AI provider returned an empty SQL query.")
    return sql.strip().removeprefix("```sql").removesuffix("```").strip()


def _summarize_query(
    question: str,
    sql: str,
    table: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    client: Any,
    model: str,
) -> str:
    from openai import APIError

    sample_rows = [
        {
            str(column): str(value)[:300] if value is not None else None
            for column, value in row.items()
        }
        for row in rows[:20]
    ]
    context = {
        "question": question,
        "table": table,
        "sql": sql,
        "returned_row_count": len(rows),
        "columns": columns,
        "sample_results": sample_rows,
    }
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize this data query result for a business user in 1-3 "
                        "short sentences. State what the result shows, use only supplied "
                        "facts, and do not infer causation or claim the sample is the full "
                        "result. Do not repeat personal contact details."
                    ),
                },
                {"role": "user", "content": json.dumps(context, default=str)},
            ],
        )
    except APIError as error:
        raise RuntimeError(f"AI summary unavailable: {error}") from error

    summary = response.choices[0].message.content
    if not summary or not summary.strip():
        raise ValueError("The AI provider returned an empty summary.")
    return summary.strip()


def _local_query_summary(
    question: str,
    table: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> str:
    if not rows:
        return f'Your question about {table} returned no matching rows.'
    if len(rows) == 1 and len(columns) == 1:
        value = rows[0].get(columns[0])
        return f"{columns[0].replace('_', ' ').title()}: {value}."
    if len(rows) == 1:
        values = ", ".join(
            f"{column.replace('_', ' ').title()}: {rows[0].get(column)}"
            for column in columns[:4]
        )
        return f"Your question about {table} returned one result: {values}."
    return (
        f'Your question about {table} returned {len(rows)} rows across '
        f'{len(columns)} columns. The results table below shows the matching data.'
    )


def _run_read_only_sql(sql: str, item: Dataset) -> tuple[list[str], list[dict[str, Any]]]:
    statement = sql.strip().rstrip(";").strip()
    if not re.match(r"(?is)^select\b", statement) or ";" in statement:
        raise ValueError("Only a single read-only SELECT query is allowed.")

    connection = sqlite3.connect(":memory:")
    try:
        item.frame.to_sql(item.name, connection, index=False, if_exists="replace")
        allowed_actions = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", -1),
        }
        def authorize(
            action: int,
            table: str | None,
            _column: str | None,
            _database: str | None,
            _trigger: str | None,
        ) -> int:
            if action not in allowed_actions:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and table != item.name:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        cursor = connection.execute(statement)
        columns = [column[0] for column in cursor.description or []]
        rows = [
            dict(zip(columns, row))
            for row in cursor.fetchmany(100)
        ]
        return columns, rows
    finally:
        connection.close()


def _quality(frame: pd.DataFrame) -> dict[str, Any]:
    cells = max(1, frame.shape[0] * frame.shape[1])
    missing = int(frame.isna().sum().sum())
    duplicate_rows = int(frame.duplicated().sum())
    score = round(max(0, 100 - (missing / cells * 70) - (duplicate_rows / max(1, len(frame)) * 30)))
    return {
        "score": score,
        "missing_values": missing,
        "duplicate_rows": duplicate_rows,
        "columns": len(frame.columns),
        "rows": len(frame),
    }


def _ai_file_recommendations(frame: pd.DataFrame) -> tuple[list[str] | None, str | None]:
    try:
        ai_config = _configured_ai_client()
    except ValueError as error:
        return None, str(error)
    if ai_config is None:
        return None, None

    from openai import APIError

    _provider, client, model = ai_config

    summary = {
        "rows": len(frame),
        "columns": [
            {
                "name": str(column),
                "type": str(dtype),
                "missing": int(frame[column].isna().sum()),
            }
            for column, dtype in frame.dtypes.items()
        ],
        "duplicate_rows": int(frame.duplicated().sum()),
    }
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data quality assistant. Give exactly three concise, "
                        "actionable CSV ingestion recommendations based only on the "
                        "provided schema and aggregate statistics. Do not infer row values."
                    ),
                },
                {"role": "user", "content": str(summary)},
            ],
        )
    except APIError as error:
        return None, f"AI analysis was unavailable: {error}"

    content = response.choices[0].message.content
    if not content:
        return None, "AI analysis returned no recommendations."
    recommendations = [
        line.strip().lstrip("-•0123456789. ")
        for line in content.splitlines()
        if line.strip()
    ][:3]
    return recommendations, None


def _dataset_summary(item: Dataset) -> dict[str, Any]:
    return {
        "name": item.name,
        "filename": item.filename,
        "layer": item.layer,
        "rows": len(item.frame),
        "columns": len(item.frame.columns),
        "created_at": item.created_at.isoformat(),
        "quality": _quality(item.frame),
        "schema": [
            {"name": str(column), "type": str(dtype)}
            for column, dtype in item.frame.dtypes.items()
        ],
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "storage": "snowflake" if _backend_storage_enabled() else "local",
    }


@app.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    _seed_demo_data()
    raw = [item for item in datasets.values() if item.layer == "RAW"]
    curated = [item for item in datasets.values() if item.layer == "CURATED"]
    quality_datasets = curated or raw
    rows = sum(len(item.frame) for item in curated or raw)
    today = datetime.now(timezone.utc).date()
    flow = {
        (today - pd.Timedelta(days=offset)).isoformat(): {"day": (today - pd.Timedelta(days=offset)).strftime("%a"), "raw": 0, "curated": 0}
        for offset in range(6, -1, -1)
    }
    for event in audit_events:
        event_day = datetime.fromisoformat(event["timestamp"]).date().isoformat()
        if event_day in flow:
            layer = "curated" if event["table"].startswith("CURATED.") else "raw"
            flow[event_day][layer] += event["rows"]
    return {
        "metrics": {
            "rows_processed": rows,
            "active_pipelines": 3,
            "data_quality": round(
                sum(_quality(item.frame)["score"] for item in quality_datasets)
                / max(1, len(quality_datasets))
            ),
            "success_rate": (
                round(
                    sum(event["status"] == "SUCCESS" for event in audit_events)
                    / len(audit_events)
                    * 100,
                    1,
                )
                if audit_events
                else None
            ),
            "raw_tables": len(raw),
            "curated_tables": len(curated),
        },
        "datasets": [_dataset_summary(item) for item in datasets.values()],
        "activity": audit_events[:6],
        "flow": list(flow.values()),
        "storage": "snowflake" if _backend_storage_enabled() else "local",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/datasets")
async def list_datasets() -> list[dict[str, Any]]:
    _seed_demo_data()
    return [_dataset_summary(item) for item in datasets.values()]


@app.get("/api/audit")
async def audit(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
) -> list[dict[str, Any]]:
    events = audit_events
    if status and status != "All statuses":
        events = [event for event in events if event["status"].lower() == status.lower()]
    if search:
        term = search.casefold()
        events = [
            event
            for event in events
            if term in event["filename"].casefold()
            or term in event["table"].casefold()
            or term in event["details"].casefold()
        ]
    return events[:200]


@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".csv"):
        _record_event(filename or "unknown", "RAW.UNKNOWN", "FAILED", 0, "Only .csv files are supported")
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        _record_event(filename, f"RAW.{_table_name(filename)}", "FAILED", 0, "CSV exceeds 15 MB upload limit")
        raise HTTPException(status_code=413, detail="CSV files must be 15 MB or smaller.")
    table = _table_name(filename)
    try:
        frame = _parse_csv(contents, filename)
    except HTTPException as error:
        _record_event(filename, f"RAW.{table}", "FAILED", 0, str(error.detail))
        raise

    if _backend_storage_enabled():
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary_path = Path(temporary_directory) / filename
                temporary_path.write_bytes(contents)
                await asyncio.to_thread(_ingest_with_backend, str(temporary_path))
        except Exception as error:
            _record_event(filename, f"RAW.{table}", "FAILED", 0, "Snowflake ingestion failed")
            raise HTTPException(status_code=502, detail=f"Snowflake ingestion failed: {error}") from error

    item = Dataset(table, frame, filename)
    datasets[table] = item
    _record_event(filename, f"RAW.{table}", "SUCCESS", len(frame), "CSV analyzed and loaded to RAW")
    ai_recommendations, ai_warning = await asyncio.to_thread(_ai_file_recommendations, frame)
    return {
        "dataset": _dataset_summary(item),
        "analysis": {
            "quality": _quality(frame),
            "preview": _preview(frame),
            "recommendations": ai_recommendations or [
                f"Detected {len(frame):,} rows across {len(frame.columns)} columns.",
                "Review missing values before promoting this dataset to CURATED.",
                "Column names and types are ready for schema normalization.",
            ],
            "mode": "ai" if ai_recommendations else "local",
            "warning": ai_warning,
        },
        "storage": "snowflake" if _backend_storage_enabled() else "local",
    }


@app.post("/api/process/{table}")
async def process(table: str) -> dict[str, Any]:
    _seed_demo_data()
    raw_table = table.upper()
    source = datasets.get(raw_table)
    if not source:
        raise HTTPException(status_code=404, detail=f"RAW table '{raw_table}' was not found.")

    if _backend_storage_enabled():
        try:
            await asyncio.to_thread(_process_with_backend, raw_table)
        except Exception as error:
            _record_event(source.filename, f"CURATED.{raw_table}_CURATED", "FAILED", 0, "CURATED processing failed")
            raise HTTPException(status_code=502, detail=f"CURATED processing failed: {error}") from error

    frame = source.frame.copy()
    frame.columns = [
        re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_]", "_", str(column))).strip("_").upper()
        or f"UNNAMED_{index + 1}"
        for index, column in enumerate(frame.columns)
    ]
    before = len(frame)
    frame = frame.drop_duplicates().reset_index(drop=True)
    curated_table = f"{raw_table}_CURATED"
    curated = Dataset(curated_table, frame, source.filename)
    curated.layer = "CURATED"
    datasets[curated_table] = curated
    quality = _quality(frame)
    _record_event(source.filename, f"CURATED.{curated_table}", "SUCCESS", len(frame), "RAW to CURATED transformation completed")
    return {
        "source_table": raw_table,
        "table": curated_table,
        "rows_processed": before,
        "rows_output": len(frame),
        "duplicates_removed": before - len(frame),
        "quality": quality,
        "schema": _dataset_summary(curated)["schema"],
        "preview": _preview(frame),
        "storage": "snowflake" if _backend_storage_enabled() else "local",
    }


@app.post("/api/query")
async def query(request: QueryRequest) -> dict[str, Any]:
    _seed_demo_data()
    if _backend_storage_enabled():
        _ensure_backend_importable()
        from security_utils import validate_user_input

        try:
            question = validate_user_input(request.question)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    else:
        question = request.question.strip()

    item = datasets.get((request.table or "").upper()) if request.table else None
    if item is None:
        item = next((dataset for dataset in datasets.values() if dataset.layer == "CURATED"), None)
    if item is None:
        item = next(iter(datasets.values()))

    try:
        ai_config = _configured_ai_client()
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    if ai_config:
        provider, client, model = ai_config
        try:
            sql = await asyncio.to_thread(_model_sql, question, item, client, model)
            columns, rows = _run_read_only_sql(sql, item)
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"AI query failed: {error}") from error
        try:
            summary = await asyncio.to_thread(
                _summarize_query,
                question,
                sql,
                item.name,
                columns,
                rows,
                client,
                model,
            )
            summary_mode = "ai"
            summary_note = None
        except (RuntimeError, ValueError) as error:
            summary = _local_query_summary(question, item.name, columns, rows)
            summary_mode = "local"
            summary_note = str(error)
        note = (
            f"AI-generated SQL ({provider}) was executed as a read-only query "
            "against this dataset."
        )
    else:
        frame = item.frame
        question_lower = question.lower()
        if "count" in question_lower or "how many" in question_lower or "number of" in question_lower:
            result_frame = pd.DataFrame([{"ROW_COUNT": len(frame)}])
            sql = f"SELECT COUNT(*) AS ROW_COUNT FROM {item.name}"
        elif "average" in question_lower or "avg" in question_lower:
            numeric = frame.select_dtypes(include="number").columns.tolist()
            if numeric:
                column = numeric[0]
                result_frame = pd.DataFrame([{"COLUMN": column, "AVERAGE": round(float(frame[column].mean()), 2)}])
                sql = f"SELECT AVG({column}) AS AVERAGE FROM {item.name}"
            else:
                result_frame = frame.head(10)
                sql = f"SELECT * FROM {item.name} LIMIT 10"
        else:
            result_frame = frame.head(10)
            sql = f"SELECT * FROM {item.name} LIMIT 10"
        columns = [str(column) for column in result_frame.columns]
        rows = _preview(result_frame, 10)
        summary = _local_query_summary(question, item.name, columns, rows)
        summary_mode = "local"
        summary_note = "AI summary unavailable; showing a summary generated from the returned results."
        note = (
            "Using built-in query templates. Set GEMINI_API_KEY or OPENAI_API_KEY "
            "to enable model-generated SQL."
        )

    return {
        "question": question,
        "sql": sql,
        "table": item.name,
        "row_count": len(rows),
        "columns": columns,
        "rows": rows,
        "summary": summary,
        "summary_mode": summary_mode,
        "summary_note": summary_note,
        "note": note,
    }


@app.on_event("startup")
async def initialize_demo_data() -> None:
    _seed_demo_data()
