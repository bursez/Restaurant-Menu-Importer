# Restaurant Menu Importer

Dockerized web application foundation for extracting structured JSON from restaurant menu content. Milestone 5 supports pasted text, `.txt` / `.md` uploads, and public URL imports for HTML menu pages. URL imports validate outbound targets for SSRF safety, fetch pages with redirect/timeout/size limits, extract readable HTML menu text, record likely PDF menu links for later processing, persist normalized source text in PostgreSQL, and show import history plus detail shells in the React UI.

PDF extraction, Gemini integration, JSON editing/export, and the evaluation dashboard are planned for later milestones in [docs/implementation-plan.md](docs/implementation-plan.md).

## Stack

- Backend: Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy async, Alembic
- Frontend: Node 22, React, TypeScript, Vite, Vitest, React Testing Library
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

The frontend uses the Vite `/api` proxy when running in Compose.

## Import APIs

- `POST /api/imports/text`: create an import from pasted menu text.
- `POST /api/imports/file`: create an import from a UTF-8 `.txt` or `.md` upload.
- `POST /api/imports/url`: create an import from a public HTTP/HTTPS HTML menu page.
- `GET /api/imports`: list recent imports.
- `GET /api/imports/{id}`: inspect status, source metadata, and event history.

Imports are persisted with `pending` status because Gemini extraction is introduced in a later milestone.

URL imports reject localhost, private/internal network targets, link-local addresses, metadata IPs, unsupported schemes, and credentialed URLs. The fetcher follows a small number of validated redirects, enforces timeouts and response size limits, and stores cleaned HTML text as the import source. Likely PDF menu links discovered inside HTML pages are recorded in import event metadata, but direct PDF extraction starts in the PDF/OCR milestone.

## Local Backend

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
python -m pytest
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
npm run test
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
- Milestone 3 work lives on `feature/03-schema-validation`.
- Milestone 4 work lives on `feature/04-text-file-imports`.
- Milestone 5 work lives on `feature/05-url-html-extraction`.

## Milestone 5 Scope

Included:

- Pasted text import endpoint
- `.txt` and `.md` upload endpoint
- URL import endpoint for public HTML menu pages
- URL validation with SSRF protections for private/internal targets
- HTTP fetching with redirect, timeout, size, and content-type handling
- HTML text extraction using readability and BeautifulSoup
- PDF menu-link discovery recorded in import events
- Text normalization for line endings, spacing, bullet characters, blank lines, and extracted HTML text
- Source metadata persistence for pasted text labels, file names, and URL final destinations
- React import tabs for URL, pasted text, and file uploads
- Import history and detail shell with AI extraction placeholder state
- Backend API/security tests and frontend component tests

Not included yet:

- Gemini API integration
- PDF extraction or OCR fallback
- JSON editing/export or evaluation workflows
