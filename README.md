# Data Sentient

Data Sentient is a data pipeline workspace with a Next.js frontend and a FastAPI bridge. It supports CSV inspection, RAW-to-CURATED processing, natural-language analytics, dashboard monitoring, and audit export.

<img width="800"  alt="Screenshot 2026-10-22 at 1 57 52 PM" src="https://github.com/user-attachments/assets/400b33ce-d411-4c98-9ed2-556aafca3136" />
<img width="800" alt="Screenshot 2026-10-22 at 1 57 44 PM" src="https://github.com/user-attachments/assets/48b700b7-3d12-4e16-8d72-4285e8e386b9" />
<img width="800" alt="Screenshot 2026-10-22 at 1 56 10 PM" src="https://github.com/user-attachments/assets/4ee0a350-0b26-4e31-858e-75fc6aa17c14" />
<img width="800" alt="Screenshot 2026-10-22 at 1 56 08 PM" src="https://github.com/user-attachments/assets/29de1b34-f027-479c-9fb6-405ecead9853" />
<img width="800" alt="Screenshot 2026-10-22 at 1 55 59 PM" src="https://github.com/user-attachments/assets/99d61162-7955-4151-b750-b16de07bc44a" />


## Run locally

### API bridge

From the project root, install the Python dependencies and start the API:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r api-bridge/requirements.txt
uvicorn main:app --reload --app-dir api-bridge --port 8000
```

The API bridge reads the project-root `.env` automatically. Set `DATA_SENTIENT_STORAGE=snowflake` there to use the configured Snowflake account; otherwise it starts in local mode with a small demo dataset. In local mode, CSV uploads, processing results, and audit events are held in API process memory.

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Use Node.js 20.9 or newer. Open [http://localhost:3000](http://localhost:3000). The frontend connects to `http://localhost:8000` by default. Set `NEXT_PUBLIC_API_URL` at build time to use a different API origin.

## Optional integrations

- Set `GEMINI_API_KEY` in the project-root `.env` to use Gemini for model-generated SQL and schema-only upload recommendations. The default is `gemini-3.5-flash-lite`; override it with `GEMINI_MODEL` if needed. Gemini returned a 404 for `gemini-2.5-flash-lite` with this API key and recommended the currently available 3.5 Flash Lite model.
- OpenAI is also supported by setting `AI_PROVIDER=openai` and `OPENAI_API_KEY`. With `AI_PROVIDER=auto` (the default), the bridge chooses Gemini when `GEMINI_API_KEY` is set, otherwise OpenAI when `OPENAI_API_KEY` is set. Set `AI_PROVIDER=gemini` to require Gemini explicitly.
- Questions and schema/aggregate metadata are sent to the selected AI provider; uploaded row values are not included in prompts. Generated statements are constrained to one read-only `SELECT` against the selected in-memory dataset.
- Set `DATA_SENTIENT_STORAGE=snowflake` and the required Snowflake connection variables to send ingested data and curated processing through the existing modules in `backend/`. Snowflake mode requires the additional dependencies listed in `api-bridge/requirement.txt`.
- Set `FRONTEND_ORIGINS` to a comma-separated list of allowed frontend origins when deploying across origins.

The local API does not require Snowflake credentials or an AI provider. Local datasets and audit events reset when the API process restarts.
