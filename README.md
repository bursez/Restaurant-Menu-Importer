# Restaurant Menu Importer

Dockerized web application foundation for extracting structured JSON from restaurant menu content. Milestone 11 supports pasted text, `.txt` / `.md` uploads, public HTML menu page imports, direct PDF menu URL imports, Gemini structured extraction, editable/exportable canonical JSON, fixture-backed evaluation, security/reliability controls, and required CI/CD checks for pull requests into `dev`.

## Stack

- Backend: Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy async, Alembic, PyMuPDF, pdfplumber, OCRmyPDF/Tesseract
- Frontend: Node 22, React, TypeScript, Vite, Vitest, React Testing Library
- Infrastructure: Docker Compose, PostgreSQL 16
- CI: GitHub Actions quality gates, tests, Docker builds, Compose smoke checks, migrations, and Playwright E2E smoke tests

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
- `POST /api/imports/url`: create an import from a public HTTP/HTTPS HTML menu page or direct PDF menu URL.
- `GET /api/imports`: list recent imports.
- `GET /api/imports/{id}`: inspect status, source metadata, and event history.
- `GET /api/imports/{id}/json`: download the validated canonical JSON.
- `PATCH /api/imports/{id}/json`: save user-corrected canonical JSON after backend validation.
- `GET /api/evaluations/cases`: list the seeded evaluation dataset.
- `POST /api/evaluations/run`: run deterministic fixture evaluation for `required` or `full`.
- `GET /api/evaluations/{id}`: retrieve a stored evaluation run.

Imports are persisted, processed through Gemini extraction, validated against the canonical menu schema, and stored with `succeeded` or `failed` status. Failed Gemini calls or invalid structured output are stored on the import as useful errors.

The frontend renders completed imports as category-grouped dish tables with prices, descriptions, tags, allergens, variants, validation warnings, and an editable canonical JSON view. Edited JSON is checked in the browser with a Zod schema that mirrors the backend Pydantic schema, then saved through the backend for final validation and persistence.

URL imports reject localhost, private/internal network targets, link-local addresses, metadata IPs, unsupported schemes, and credentialed URLs. The fetcher follows a small number of validated redirects, enforces timeouts and response size limits, and stores cleaned HTML or PDF text as the import source. Likely PDF menu links discovered inside HTML pages are recorded in import event metadata.

Every backend request receives an `X-Request-ID` response header. Incoming valid request IDs are preserved; otherwise the API generates one and includes it in structured JSON logs with method, path, status, duration, and client host. Import errors stored in the database and returned for URL-import failures are sanitized to avoid leaking local paths, URL credentials, tokens, or API keys.

Rate limiting hooks are wired into the backend and disabled by default for local development. Enable them with:

```sh
APP_RATE_LIMIT_ENABLED=true
APP_RATE_LIMIT_REQUESTS=120
APP_RATE_LIMIT_WINDOW_SECONDS=60
```

URL content extraction is also bounded independently of fetch and Gemini request timeouts:

```sh
APP_URL_EXTRACTION_TIMEOUT_SECONDS=30
```

Gemini credentials are backend-only settings. Use `APP_GEMINI_API_KEY` on the backend service or local backend process; do not expose it through `VITE_` frontend environment variables.

PDF URL imports are detected from `Content-Type: application/pdf` or the PDF file signature. Text-layer PDFs are extracted with PyMuPDF into `[Page N]` sections. Sparse or layout-sensitive text can fall back to pdfplumber, and empty-text PDFs use OCRmyPDF/Tesseract OCR. Repeated headers, footers, legends, and legal/allergen lines are removed when they repeat across pages.

The backend container and CI install OCR system packages. For local backend development outside Docker, install `ocrmypdf` and `tesseract` on your system if you want to exercise scanned PDF fallback locally.

## Evaluation Dashboard

Milestone 9 adds a local evaluation dataset and dashboard. The required cases are the five reference menus from the implementation plan:

- Re Sale
- Il Covo del Ribelle
- Love Menu
- Nobu Milan
- Pizzeria Da Michele

The full qualitative set adds five public restaurant menus: Osteria Francescana, Dishoom Covent Garden, Eleven Madison Park, Gramercy Tavern, and St. John. Required cases include expected JSON fixtures under `backend/app/evaluation_fixtures/expected/`; all ten cases include deterministic actual-output fixtures under `backend/app/evaluation_fixtures/actual/`.

The evaluation runner compares fixture output on:

- Schema validity against the canonical menu model.
- Category coverage against expected fixtures where available.
- Item-count alignment against expected fixtures where available.
- Price coverage across extracted items and variants.
- Language handling against expected fixtures where available.
- Qualitative score, strengths, weaknesses, and notes for human review.

Live extraction is intentionally not part of normal PR CI. The dashboard and tests use stable fixtures so local and CI runs stay deterministic; manual live evaluation can refresh fixture quality when menu pages or PDFs change.

## Gemini Extraction

Set these environment variables to use live Gemini extraction:

```sh
APP_GEMINI_API_KEY=your-gemini-api-key
APP_GEMINI_MODEL=gemini-2.5-flash
APP_GEMINI_USE_FAKE=false
APP_GEMINI_MAX_RETRIES=2
APP_GEMINI_MIN_CONFIDENCE=0.55
```

`APP_GEMINI_API_KEY` is read as a secret setting and is not required for normal CI. Tests use the deterministic fake Gemini adapter, and the optional `Gemini smoke` workflow can run a live extraction when the repository has a `GEMINI_API_KEY` secret configured.

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

Backend CI runs these local-equivalent checks:

```sh
cd backend
ruff check .
ruff format --check .
mypy app tests
bandit -c pyproject.toml -r app
pytest --cov=app --cov-report=term-missing
alembic upgrade head
alembic check
```

## Local Frontend

```sh
cd frontend
npm install
npm run dev
npm run test
npm run lint
npm run format:check
npm run build
```

For local frontend development outside Docker, either run the backend locally on port `8000` and set:

```sh
VITE_API_BASE_URL=http://localhost:8000/api
```

or keep using the Docker Compose setup.

Frontend CI also runs a Playwright smoke test against the Compose stack:

```sh
cd frontend
npx playwright install chromium
npm run e2e
```

## CI/CD

GitHub Actions runs on every pull request into `dev` and on pushes to `dev`. The required workflow covers:

- Backend linting with Ruff and Ruff format checks.
- Backend typing with mypy.
- Backend tests with pytest coverage.
- Backend security scanning with Bandit.
- Alembic upgrade and migration drift checks.
- Frontend linting with ESLint and formatting with Prettier.
- Frontend unit tests with Vitest.
- TypeScript validation and Vite production build.
- Backend and frontend Docker image builds.
- Docker Compose smoke boot for PostgreSQL, API, and frontend.
- Playwright E2E smoke coverage against the running Compose stack.

## Git Workflow Notes

This repository follows the milestone workflow described in section 17 of the implementation plan:

- `dev` contains the initial project planning docs.
- Milestone 1 work lives on `feature/01-bootstrap-docker`.
- Milestone 2 work lives on `feature/02-import-persistence`.
- Milestone 3 work lives on `feature/03-schema-validation`.
- Milestone 4 work lives on `feature/04-text-file-imports`.
- Milestone 5 work lives on `feature/05-url-html-extraction`.
- Milestone 6 work lives on `feature/06-pdf-ocr-extraction`.
- Milestone 7 work lives on `feature/07-gemini-extraction`.
- Milestone 8 work lives on `feature/08-results-export-ui`.
- Milestone 9 work lives on `feature/09-evaluation-dashboard`.
- Milestone 10 is merged into `dev`.
- Milestone 11 is merged into `dev`.

## Milestone 11 Scope

Included:

- Pasted text import endpoint
- `.txt` and `.md` upload endpoint
- URL import endpoint for public HTML menu pages
- Direct PDF URL imports
- URL validation with SSRF protections for private/internal targets
- HTTP fetching with redirect, timeout, size, and content-type handling
- HTML text extraction using readability and BeautifulSoup
- PDF menu-link discovery recorded in import events for HTML pages
- PDF content detection from headers and file signatures
- Page-aware PyMuPDF text extraction
- pdfplumber layout-aware fallback for sparse or layout-sensitive PDFs
- OCRmyPDF/Tesseract fallback for empty-text PDFs
- Gemini client configuration with secure API key handling
- Prompt builder for restaurant menu extraction
- Structured-output Gemini request using the canonical Pydantic JSON Schema
- Retry handling for invalid or low-confidence model output
- Deterministic fake Gemini adapter for CI
- Text, file, and URL imports wired through extraction, validation, and persistence
- Stored model name and import errors for extraction outcomes
- Repeated PDF header, footer, legend, and legal/allergen line cleanup
- Stored reference text fixtures for Re Sale, Il Covo del Ribelle, Love Menu, Nobu Milan, and Pizzeria Da Michele
- Text normalization for line endings, spacing, bullet characters, blank lines, and extracted HTML text
- Source metadata persistence for pasted text labels, file names, and URL final destinations
- React import tabs for URL, pasted text, and file uploads
- Import history and detail shell with AI extraction placeholder state
- Backend API/security/PDF extraction tests and frontend component tests
- Backend Gemini extraction success, failure, validation, and retry tests
- Optional manual live Gemini smoke workflow
- Results table grouped by extracted category
- Editable canonical JSON view
- Client-side canonical menu validation with Zod
- Backend JSON download endpoint
- Backend corrected JSON save endpoint
- Copy and download JSON actions
- Validation warnings panel
- Frontend tests for result rendering and edited JSON save flow
- Backend tests for patch and download JSON endpoints
- Evaluation case database model and Alembic migration
- Seed data for the 5 required reference menus
- Five additional public restaurant menu cases for the 10-menu qualitative set
- Expected JSON fixtures for required cases
- Deterministic actual-output fixtures for all 10 cases
- Evaluation runner for validity, category coverage, item counts, price coverage, language handling, and qualitative notes
- Evaluation APIs for listing cases, running evaluations, and retrieving stored runs
- React evaluation dashboard with dataset and accuracy result tables
- Backend fixture-based evaluation tests
- Frontend dashboard test coverage
- README accuracy methodology and known limitations
- Request ID middleware and structured JSON request logging
- Optional in-memory rate limiting hooks, disabled by default
- URL extraction timeout around HTML/PDF processing
- Required GitHub Actions checks for backend lint, format, types, tests with coverage, security scanning, migration validation, frontend lint, format, unit tests, TypeScript validation, Vite build, Docker image builds, Compose smoke, and Playwright E2E smoke
- Local backend quality tool configuration for Ruff, mypy, Bandit, and pytest coverage
- Local frontend quality tool configuration for ESLint, Prettier, and Playwright
- Sanitized stored import errors for extraction failures
- Sanitized URL-import error responses
- Backend-only Gemini secret configuration in Compose and docs
- Deterministic validation that rejects empty item output and malformed category/item structures
- Backend tests for request IDs, rate limiting hooks, sanitized errors, and stricter validation

Not included yet:

- Playwright end-to-end tests
- GitHub Actions hardening beyond the existing checks
- Live evaluation as a required CI job
