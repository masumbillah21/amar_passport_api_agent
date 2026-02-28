# Bangladesh Passport Virtual Consular Officer

Docker-first FastAPI + Streamlit app for Bangladesh e-passport readiness analysis.

The app accepts a natural-language applicant scenario, parses the details, lets the user review the extracted values, and then generates a passport readiness report in English and Bangla.

## What It Includes

- FastAPI backend
- Streamlit frontend
- CrewAI orchestration
- deterministic local fallback rules
- Docker Compose setup

## Project Structure

```text
.
├── .env-example
├── apps
│   ├── api.py
│   └── streamlit_app.py
├── passport_advisor
│   ├── agents.py
│   ├── data.py
│   ├── models.py
│   ├── report.py
│   ├── scenario_parser.py
│   └── service.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── project_requiremnts.txt
```

## Quick Start

### 1. Create `.env`

Copy the template:

```bash
cp .env-example .env
```

Then set one provider key in `.env`, for example:

```dotenv
GROQ_API_KEY=your_key_here
```

### 2. Build and Run

```bash
docker compose up --build
```

### 3. Open the App

- Frontend: `http://localhost:8501`
- API: `http://localhost:8000`

## Environment

Docker Compose loads API runtime settings from `.env`.

Supported provider variables:

- `SHOW_AGENT_THINKING`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL_NAME`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

Provider priority:

1. Groq
2. OpenAI
3. Anthropic
4. Gemini

Default Groq model:

- `groq/llama-3.3-70b-versatile`

Frontend trace toggle:

- `SHOW_AGENT_THINKING=true`
  - set to `false` to hide `Agent Thinking` in the UI

## How It Works

1. User enters a natural-language scenario.
2. The parser creates a draft applicant profile.
3. The UI shows a review form so unclear fields can be corrected.
4. The backend generates the final report.
5. CrewAI is attempted first.
6. If CrewAI cannot complete, the local rule engine finishes the request.

CrewAI falls back only when:

- `crewai` is unavailable
- no supported LLM credential is configured
- CrewAI raises an execution error

## Agent Trace

When CrewAI starts successfully, verbose output is visible in:

- API logs:
  - `docker compose logs -f api`
- frontend:
  - `Agent Thinking`

If no trace appears, the request was completed by fallback logic only.

## API Endpoints

- `GET /health`
- `POST /passport/parse`
- `POST /passport/report`
- `POST /passport/text`

### Parse Example

```bash
curl -X POST http://localhost:8000/passport/parse \
  -H "Content-Type: application/json" \
  -d '{"scenario":"I am a 24-year-old private sector employee. I need a 64-page passport urgently because I have a business trip in two weeks. I have an NID and I live in Dhaka."}'
```

## Notes

- `.env` is ignored by git
- `.env-example` is the committed template
- CrewAI telemetry is disabled by default to avoid signal-handler warnings in the API container
