# Data Sentient

Data Sentient is a data pipeline workspace with a Next.js frontend and a FastAPI bridge. It supports CSV inspection, RAW-to-CURATED processing, natural-language analytics, dashboard monitoring, and audit export.

## Run locally

### API bridge

From the project root, install the Python dependencies and start the API:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r api-bridge/requirements.txt
uvicorn main:app --reload --app-dir api-bridge --port 8000
```

The bridge starts in local mode and includes a small demo dataset. CSV uploads, processing results, and audit events are held in API process memory.

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Use Node.js 20.9 or newer. Open [http://localhost:3000](http://localhost:3000). The frontend connects to `http://localhost:8000` by default. Set `NEXT_PUBLIC_API_URL` at build time to use a different API origin.

## Optional integrations

- Set `OPENAI_API_KEY` in the API environment to enable model-generated SQL and schema-only upload recommendations. Questions and schema/aggregate metadata are sent to the configured provider; uploaded row values are not included. Generated statements are constrained to one read-only `SELECT` against the selected in-memory dataset.
- Set `DATA_SENTIENT_STORAGE=snowflake` and the required Snowflake connection variables to send ingested data and curated processing through the existing modules in `backend/`. Snowflake mode requires the additional dependencies listed in `api-bridge/requirement.txt`.
- Set `FRONTEND_ORIGINS` to a comma-separated list of allowed frontend origins when deploying across origins.

The local API does not require Snowflake credentials or an AI provider. Local datasets and audit events reset when the API process restarts.
