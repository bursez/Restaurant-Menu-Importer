# Restaurant Menu Importer

Dockerized web application foundation for extracting structured JSON from restaurant menu content. Milestone 2 adds backend import persistence with PostgreSQL, SQLAlchemy async sessions, Alembic migrations, import event logs, and read APIs for import history.

The AI extraction, import persistence, schema validation, URL/PDF processing, Gemini integration, and evaluation dashboard are planned for later milestones in [docs/implementation-plan.md](docs/implementation-plan.md).

## Stack

- Backend: Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy async, Alembic
- Frontend: Node 22, React, TypeScript, Vite
- Infrastructure: Docker Compose, PostgreSQL 16
- CI: GitHub Actions smoke/build checks

## Quickstart

Copy the example environment file if you want to customize local settings:

```sh
cp .env.example .env
```

Start the full local stack:

```sh
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health
- PostgreSQL: `localhost:5432`

The frontend checks `/api/health` through the Vite proxy when running in Compose.

## Local Backend

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
pytest
uvicorn app.main:app --reload
```

Run migrations against your configured database before using persistence APIs:

```sh
cd backend
alembic upgrade head
```

## Local Frontend

```sh
cd frontend
npm install
npm run dev
npm run build
```

For local frontend development outside Docker, either run the backend locally on port `8000` and set:

```sh
VITE_API_BASE_URL=http://localhost:8000/api
```

or keep using the Docker Compose setup.

## Git Workflow Notes

This repository was initialized according to section 17 of the implementation plan:

- `dev` contains the initial project planning docs.
- Milestone 1 work lives on `feature/01-bootstrap-docker`.
- Milestone 2 work lives on `feature/02-import-persistence`.
- A Git remote is not configured in this local workspace yet, so pushing the branch and opening the PR still requires adding the GitHub remote.

## Milestone 2 Scope

Included:

- Async SQLAlchemy database setup
- Alembic migration for `imports`, `extracted_menus`, and `import_events`
- Import service/repository methods for creation, status updates, output persistence, and event logging
- `GET /api/imports` and `GET /api/imports/{id}`
- PostgreSQL-backed backend tests and migration check in CI

Not included yet:

- Gemini API integration
- Menu schema validation
- Text/file/url submission endpoints
- URL, PDF, OCR, frontend history UI, or evaluation workflows
