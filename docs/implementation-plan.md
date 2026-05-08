# Restaurant Menu Importer - Implementation Plan

## 1. Product Goal

Build a fully dockerized web application that accepts restaurant menu content from URLs, pasted text, or uploaded `.txt` / `.md` files, extracts structured menu data with the Google Gemini API, validates the result against a canonical schema, stores import history in PostgreSQL, and lets users inspect, correct, export, and evaluate the generated JSON.

The implementation will be delivered through GitHub pull requests. For each milestone, the implementer will branch from `dev`, implement each feature as an individual commit, run the full local and GitHub Actions test suite, open a PR, handle review feedback, merge the PR, and continue from the updated `dev` branch.

## 2. Chosen Stack

### Backend

- Python 3.12
- FastAPI for the HTTP API
- Pydantic v2 for request, response, domain, and Gemini structured-output schemas
- SQLAlchemy 2.x with async sessions
- Alembic for database migrations
- PostgreSQL 16 as the primary database
- `asyncpg` as the PostgreSQL driver
- `httpx` for URL fetching
- BeautifulSoup4, lxml, and readability-lxml for HTML cleanup
- PyMuPDF and pdfplumber for PDF text extraction
- Tesseract OCR, OCRmyPDF, and Pillow for scanned/image-only PDF fallback
- `google-genai` for the Google Gemini API
- pytest, pytest-asyncio, respx, pytest-cov, and hypothesis for testing
- Ruff, mypy, and Bandit for linting, typing, and security checks

### Frontend

- Node 22 LTS
- TypeScript
- React with Vite
- TanStack Query for API state
- React Hook Form and Zod for forms and client validation
- Monaco Editor or CodeMirror for JSON preview/editing
- Vitest and React Testing Library for unit/component tests
- Playwright for end-to-end tests
- ESLint and Prettier for code quality

### Infrastructure

- Docker and Docker Compose for local development
- Development Dockerfiles for backend and frontend
- PostgreSQL service in Compose
- GitHub Actions for CI, Docker image build validation, tests, linting, type checks, migrations, and E2E tests

## 3. Gemini API Decision

Use the Google Gemini API with structured JSON output.

Default model: `gemini-2.5-flash`.

Reasoning:

- It supports structured outputs, which fits the requirement to return valid JSON.
- It has a large context window, useful for long menus and multi-page PDFs.
- It is positioned by Google as a strong price/performance model for high-volume, low-latency processing.
- The backend can define the output schema once with Pydantic and pass the generated JSON Schema to Gemini.

Fallback model option: `gemini-2.5-pro` for difficult extractions, such as very noisy OCR, mixed-language menus, or menus where price/category alignment fails confidence checks.

The application will not rely only on the LLM. It will use deterministic fetch, extraction, cleaning, validation, normalization, and post-processing before and after the Gemini call.

## 4. Reference Menu Input Lessons

The five provided URLs should become regression fixtures and manual evaluation examples:

- Re Sale PDF: text is extractable, but item names, descriptions, and prices are often separated by visual columns. The parser must preserve page order and pass line-position hints where possible.
- Il Covo del Ribelle PDF: long multi-page menu with legends, icons, spicy/vegetarian markers, tasting menus, variants, and repeated footer text. The cleaner must remove repeated legends/footers and preserve category boundaries.
- Linktree-hosted Love Menu PDF: should be treated as a remote PDF behind a non-restaurant CDN URL. The fetcher must inspect content type and not assume restaurant domains.
- Nobu Milan PDF: bilingual Italian/English entries, prices without currency symbols, item descriptions immediately below item names, and roll variants with multiple prices. The schema and prompt must support multilingual names/descriptions and variants.
- Pizzeria Da Michele PDF: available as a PDF URL but text extraction can be empty, so OCR fallback is mandatory.

## 5. Target Architecture

```text
Browser UI
  |
  v
Frontend React App
  |
  v
FastAPI Backend
  |-- Auth-free MVP API routes
  |-- Import orchestration service
  |-- Fetch and document extraction services
  |-- Gemini extraction service
  |-- Validation and normalization service
  |-- Export service
  |
  v
PostgreSQL
  |-- imports
  |-- extracted_menus
  |-- import_events
  |-- evaluation_cases
```

## 6. Core Data Model

### Canonical Output JSON

```json
{
  "restaurant": "Trattoria da Mario",
  "currency": "EUR",
  "language": "it",
  "source": {
    "type": "url",
    "value": "https://example.com/menu.pdf"
  },
  "categories": [
    {
      "name": "Starters",
      "items": [
        {
          "name": "Bruschetta al pomodoro",
          "description": "Toasted bread with fresh tomato and basil",
          "price": 6.5,
          "price_text": "€ 6,50",
          "allergens": ["gluten"],
          "tags": ["vegetarian"],
          "variants": []
        }
      ]
    }
  ]
}
```

### Database Tables

- `imports`: one row per user submission, including input type, source URL/file name, status, error message, model used, timing, and created/updated timestamps.
- `extracted_menus`: canonical JSON output, normalized restaurant name, currency, language, confidence score, and validation status.
- `import_events`: append-only log of fetch, extract, LLM, validation, and export events for debuggability.
- `evaluation_cases`: test/evaluation metadata for real menus, expected fixture path, actual output path, and qualitative scores.

## 7. Processing Pipeline

### URL Input

1. Validate URL scheme and block private/internal network targets to prevent SSRF.
2. Fetch with `httpx` using timeouts, redirects limits, content-size limits, and a restaurant-menu-friendly user agent.
3. Detect content type from headers and file signature.
4. For HTML pages, extract readable text, links to likely menu PDFs, and visible menu sections.
5. For PDF URLs, download and run PDF extraction directly.
6. If HTML contains menu PDF links, process the best candidate PDF and keep the HTML text as supplemental context.
7. Store raw fetch metadata but avoid storing large raw files unless explicitly configured.

### Text/File Input

1. Accept pasted text, `.txt`, or `.md`.
2. Normalize whitespace, Unicode currency symbols, bullet characters, and line endings.
3. Preserve line breaks because menu layout often encodes category and price relationships through line order.

### PDF Extraction

1. Try PyMuPDF text extraction.
2. Try pdfplumber layout-aware extraction when text exists but price alignment looks poor.
3. Detect image-only or low-text PDFs.
4. Run OCR fallback with OCRmyPDF/Tesseract for image-only PDFs.
5. Split extracted content into page-aware chunks with page numbers and line numbers.
6. Remove repeated headers, footers, legal notes, and legends only when they are confidently repeated.

### Gemini Extraction

1. Build a prompt containing the canonical schema rules, locale/price normalization rules, allergen/tag rules, and source text.
2. Request structured JSON using Gemini API `response_mime_type: application/json` and the Pydantic-generated JSON Schema.
3. Use `gemini-2.5-flash` by default.
4. Retry once with a narrower chunking strategy if validation fails.
5. Escalate to `gemini-2.5-pro` only for failed or low-confidence extractions if configured.

### Validation and Cleanup

1. Validate Gemini output with Pydantic.
2. Normalize prices from comma decimals to floats.
3. Preserve original price strings in `price_text` when useful.
4. Use `null` for missing prices.
5. Infer `EUR` when euro symbols or Italian menu context are present.
6. Deduplicate categories and items conservatively.
7. Trim descriptions and remove orphan legal/footer text.
8. Return validation warnings instead of silently hiding suspicious output.

## 8. API Surface

### Import APIs

- `POST /api/imports/text`: create import from pasted text.
- `POST /api/imports/url`: create import from URL.
- `POST /api/imports/file`: create import from `.txt` or `.md` upload.
- `GET /api/imports`: list recent imports.
- `GET /api/imports/{id}`: get import status, warnings, and output summary.
- `GET /api/imports/{id}/json`: download canonical JSON.
- `PATCH /api/imports/{id}/json`: save user-corrected JSON after validation.
- `DELETE /api/imports/{id}`: delete an import and its output.

### Evaluation APIs

- `GET /api/evaluations/cases`: list reference cases.
- `POST /api/evaluations/run`: run extraction against the 5 required cases or the full 10-menu evaluation set.
- `GET /api/evaluations/{id}`: view accuracy notes and validation results.

### Health APIs

- `GET /api/health`: backend liveness.
- `GET /api/health/db`: database readiness.
- `GET /api/health/gemini`: optional Gemini configuration check without consuming meaningful tokens.

## 9. Frontend UX

### Main Screens

- Home/import screen with tabs for URL, pasted text, and file upload.
- Import progress view with pipeline steps: Fetch, Extract Text, AI Extraction, Validate, Complete.
- Results screen with category/item table and JSON editor preview.
- Validation warnings panel for missing prices, unknown currency, duplicate items, or low-confidence extraction.
- Import history screen.
- Evaluation dashboard showing the required 5 menu cases and the full 10-menu qualitative evaluation set.

### UX Requirements

- The UI must make JSON output easy to copy/download.
- The user must be able to edit generated JSON and revalidate it.
- Errors must explain the failing stage instead of showing a generic failure.
- The interface must work on desktop and mobile.

## 10. Security and Reliability

- Block localhost, private IP ranges, link-local addresses, and cloud metadata IPs for URL imports.
- Limit download size and extraction time.
- Strip scripts and unsafe HTML before storing/processing.
- Never expose `GEMINI_API_KEY` to the frontend.
- Use backend-only environment variables for secrets.
- Add rate limiting hooks, even if disabled by default in local development.
- Store import errors with sanitized messages.
- Add structured logging with request IDs.
- Add deterministic validation so malformed LLM output cannot be saved as accepted output.

## 11. CI/CD Strategy

GitHub Actions will run on every PR into `dev`:

- Backend lint: Ruff
- Backend format check: Ruff format
- Backend type check: mypy
- Backend tests: pytest with coverage
- Backend security scan: Bandit
- Frontend lint: ESLint
- Frontend format check: Prettier
- Frontend unit tests: Vitest
- Frontend validation: TypeScript check and Vite build
- Docker build: backend and frontend images
- Compose smoke test: API, frontend, and PostgreSQL boot successfully
- Alembic migration check
- Playwright E2E smoke tests

The workflow must support required checks before merging. The implementer will monitor GitHub Actions after each PR is opened, fix failing checks with additional commits, and merge once the PR is green and approved/mergeable.

## 12. Branching and PR Workflow

For every milestone:

1. Start from the latest `dev` branch.
2. Create a branch named `feature/<milestone-number>-<short-name>`.
3. Implement each feature in that milestone as a separate commit.
4. Run local tests and Docker smoke checks.
5. Push the branch to GitHub.
6. Open a PR targeting `dev`.
7. Wait for GitHub Actions.
8. Fix failures with additional focused commits.
9. Update PR description with implementation notes and test results.
10. Merge the PR after checks pass.
11. Pull/update `dev` before starting the next milestone.

The implementer will handle branch creation, commits, pushes, PR creation, review-feedback fixes, GitHub Actions monitoring, and merges because GitHub access is available.

## 13. Milestones

Each milestone is scoped so it can be implemented as one PR.

### PR 1 - Repository Bootstrap and Docker Foundation

Branch: `feature/01-bootstrap-docker`

Goal: create the application skeleton, Docker environment, and baseline developer workflow.

Features and commits:

- Commit 1: Add monorepo structure with `backend/`, `frontend/`, `docs/`, `tests/`, and `.github/`.
- Commit 2: Add backend FastAPI skeleton with health endpoint and settings management.
- Commit 3: Add frontend Vite React TypeScript skeleton.
- Commit 4: Add PostgreSQL Docker Compose service and environment examples.
- Commit 5: Add backend and frontend development Dockerfiles.
- Commit 6: Add README quickstart with Docker Compose instructions.

Acceptance criteria:

- `docker compose up` starts frontend, backend, and PostgreSQL.
- `GET /api/health` returns healthy.
- Frontend loads and can call backend health.
- No Gemini functionality is required yet.

GitHub Actions required:

- Backend smoke tests pass.
- Frontend build passes.
- Docker images build successfully.

### PR 2 - Database, Migrations, and Import Persistence

Branch: `feature/02-import-persistence`

Goal: persist imports, extracted output, and event logs.

Features and commits:

- Commit 1: Add SQLAlchemy async database setup.
- Commit 2: Add Alembic migrations for `imports`, `extracted_menus`, and `import_events`.
- Commit 3: Add repository/service layer for creating and updating imports.
- Commit 4: Add API endpoints for listing and retrieving imports.
- Commit 5: Add backend integration tests using a test PostgreSQL database.

Acceptance criteria:

- Imports can be created with pending/running/succeeded/failed statuses.
- Import events are recorded for lifecycle steps.
- Migrations run cleanly from an empty database.

GitHub Actions required:

- PostgreSQL service is available during backend tests.
- Alembic upgrade check passes.

### PR 3 - Canonical Schema and Validation Layer

Branch: `feature/03-schema-validation`

Goal: define the menu schema and deterministic validation/normalization behavior.

Features and commits:

- Commit 1: Add Pydantic models for menu output, categories, items, variants, source metadata, and validation warnings.
- Commit 2: Add JSON Schema generation for Gemini structured output.
- Commit 3: Add price normalization for `€ 6,50`, `6.50`, `€ 7/hg`, multi-price variants, and missing prices.
- Commit 4: Add category/item deduplication and whitespace cleanup.
- Commit 5: Add schema unit tests covering Italian and English examples.

Acceptance criteria:

- Invalid generated JSON is rejected with useful validation errors.
- Missing prices are represented as `null`.
- Euro values with comma decimals normalize correctly.
- Original price text can be preserved when needed.

GitHub Actions required:

- Unit tests pass with coverage for normalization edge cases.
- mypy and Ruff pass.

### PR 4 - Text and File Import MVP

Branch: `feature/04-text-file-imports`

Goal: support pasted text and `.txt` / `.md` files end to end without Gemini yet.

Features and commits:

- Commit 1: Add `POST /api/imports/text` endpoint.
- Commit 2: Add `POST /api/imports/file` endpoint for `.txt` and `.md` uploads.
- Commit 3: Add text normalization and source metadata storage.
- Commit 4: Add frontend form tabs for pasted text and file upload.
- Commit 5: Add frontend import history and import detail shell.
- Commit 6: Add API and component tests.

Acceptance criteria:

- Users can submit pasted text.
- Users can upload `.txt` and `.md` files.
- Imports are persisted and visible in history.
- The app shows an informative placeholder before AI extraction exists.

GitHub Actions required:

- Backend API tests pass.
- Frontend component tests pass.
- Docker Compose smoke test passes.

### PR 5 - URL Fetching and HTML Menu Extraction

Branch: `feature/05-url-html-extraction`

Goal: safely fetch URLs and extract usable text from HTML pages.

Features and commits:

- Commit 1: Add URL validation with SSRF protections.
- Commit 2: Add HTTP fetch service with redirects, timeout, size, and content-type handling.
- Commit 3: Add HTML text extraction using readability and BeautifulSoup.
- Commit 4: Add menu-link discovery for PDF links inside HTML pages.
- Commit 5: Add `POST /api/imports/url` endpoint.
- Commit 6: Add frontend URL import flow.
- Commit 7: Add mocked URL fetch tests and security tests.

Acceptance criteria:

- Public HTTP/HTTPS menu pages can be fetched.
- Private/internal URLs are rejected.
- HTML is cleaned into readable text.
- Likely menu PDF links are detected and recorded for later PDF processing.

GitHub Actions required:

- URL security tests pass.
- No live network dependency in CI tests.

### PR 6 - PDF Extraction and OCR Fallback

Branch: `feature/06-pdf-ocr-extraction`

Goal: support PDF menu URLs and robust text extraction, including scanned/image-only PDFs.

Features and commits:

- Commit 1: Add PDF content detection and download handling.
- Commit 2: Add PyMuPDF text extraction with page-aware output.
- Commit 3: Add pdfplumber layout-aware fallback for column-heavy PDFs.
- Commit 4: Add OCR fallback with Tesseract/OCRmyPDF for empty-text PDFs.
- Commit 5: Add repeated header/footer/legend cleanup heuristics.
- Commit 6: Add fixtures for the 5 provided menu URLs using stored sample text/OCR outputs.
- Commit 7: Add tests for text-layer PDFs, column PDFs, bilingual PDFs, and OCR-required PDFs.

Acceptance criteria:

- PDF URLs are accepted by the URL import endpoint.
- Text-layer PDFs produce page-aware text.
- Empty-text PDFs trigger OCR fallback.
- The 5 provided reference menus are represented as regression fixtures.

GitHub Actions required:

- PDF extraction tests pass in Docker.
- OCR dependencies are available in the backend container.
- CI does not depend on downloading the live PDFs on every run; live refresh can be a manual workflow.

### PR 7 - Gemini Extraction Service

Branch: `feature/07-gemini-extraction`

Goal: connect extracted text to Gemini and produce validated canonical JSON.

Features and commits:

- Commit 1: Add Gemini client configuration and secure environment variable handling.
- Commit 2: Add prompt builder for restaurant menu extraction.
- Commit 3: Add structured-output call using the Pydantic JSON Schema.
- Commit 4: Add retry strategy for invalid or low-confidence output.
- Commit 5: Add fake Gemini adapter for deterministic CI tests.
- Commit 6: Wire text/file/url imports through extraction, validation, and persistence.
- Commit 7: Add backend tests for successful extraction, Gemini failures, validation failures, and retry behavior.

Acceptance criteria:

- Submitting text, file, or URL can produce canonical JSON.
- Gemini API key is never required for standard CI tests.
- Invalid Gemini responses fail safely and store useful import errors.
- The model name used is stored with each import.

GitHub Actions required:

- Fake-Gemini integration tests pass.
- No secret is required for PR CI.
- Optional manual workflow supports live Gemini smoke testing when `GEMINI_API_KEY` is configured.

### PR 8 - Results UI, JSON Editor, and Export

Branch: `feature/08-results-export-ui`

Goal: make extracted data usable from the web UI.

Features and commits:

- Commit 1: Add results table grouped by category.
- Commit 2: Add JSON preview/editor with syntax highlighting.
- Commit 3: Add client-side JSON validation with Zod matching the backend schema.
- Commit 4: Add save-corrected-JSON endpoint integration.
- Commit 5: Add download/copy JSON actions.
- Commit 6: Add validation warnings panel.
- Commit 7: Add frontend tests for result rendering and edited JSON save flow.

Acceptance criteria:

- Users can view extracted categories and dishes.
- Users can inspect and edit raw JSON.
- Edited JSON is validated before saving.
- Users can download the final JSON.

GitHub Actions required:

- Frontend unit/component tests pass.
- Backend patch/download endpoint tests pass.

### PR 9 - Evaluation Dataset and Accuracy Dashboard

Branch: `feature/09-evaluation-dashboard`

Goal: satisfy the required 5 real-menu tests and 10-menu qualitative accuracy evaluation.

Features and commits:

- Commit 1: Add evaluation case model/table and seed data for the 5 provided menus.
- Commit 2: Add 5 additional public restaurant menu cases for the 10-menu qualitative set.
- Commit 3: Add expected JSON fixtures for required cases.
- Commit 4: Add evaluation runner that compares validity, category coverage, item count, price coverage, and language handling.
- Commit 5: Add qualitative scoring fields and notes.
- Commit 6: Add frontend evaluation dashboard.
- Commit 7: Add README section with accuracy methodology and known limitations.

Acceptance criteria:

- The project includes at least 5 real menu test cases from the provided references.
- The project documents qualitative accuracy over 10 menus.
- Evaluation outputs identify where extraction is strong or weak.
- The dashboard can run/display evaluation results locally.

GitHub Actions required:

- Fixture-based evaluation tests pass.
- Live evaluation remains manual or scheduled, not required for every PR.

### PR 10 - End-to-End Tests and GitHub Workflow Hardening

Branch: `feature/10-e2e-ci-hardening`

Goal: make the PR workflow reliable for local development and review.

Features and commits:

- Commit 1: Add Playwright E2E tests for text import, URL import with mocked server, JSON editing, and export.
- Commit 2: Add Docker Compose CI smoke test.
- Commit 3: Add GitHub Actions matrix or split jobs for backend, frontend, Docker, and E2E.
- Commit 4: Add coverage reporting and minimum thresholds.
- Commit 5: Add PR template with test checklist.
- Commit 6: Add Dependabot or Renovate configuration.

Acceptance criteria:

- A fresh PR runs all important checks automatically.
- E2E tests exercise the happy path and important failure paths.
- Docker images build on CI.
- PR descriptions consistently report test evidence.

GitHub Actions required:

- All required checks are green before merge.

### PR 11 - Documentation and Local Handoff

Branch: `feature/11-docs-handoff`

Goal: prepare the app for reliable local handoff.

Features and commits:

- Commit 1: Add environment variable documentation and secret handling guidance.
- Commit 2: Add local setup and troubleshooting notes.
- Commit 3: Add structured logging and request IDs.
- Commit 4: Add basic rate-limiting middleware configuration.
- Commit 5: Add database backup/restore notes for the local development environment.
- Commit 6: Add final README architecture, API, and troubleshooting sections.
- Commit 7: Add final manual QA checklist.

Acceptance criteria:

- New developers can run the app from the README.
- Required secrets are clear.
- Logs and errors are useful enough to debug failed imports.

GitHub Actions required:

- Full CI remains green.

## 14. Testing Strategy

### Backend Tests

- Unit tests for validators, normalizers, prompt builder, URL guard, and parsers.
- Integration tests for API endpoints and PostgreSQL persistence.
- Contract tests for canonical JSON schema stability.
- Mocked Gemini tests using deterministic fake responses.
- PDF fixture tests for text extraction and OCR fallback.

### Frontend Tests

- Component tests for forms, history, result tables, warning panels, and JSON editor.
- API mocking tests for success/failure states.
- Accessibility checks for forms and result views.

### E2E Tests

- Paste text and receive JSON.
- Import mocked URL and receive JSON.
- Upload `.txt` or `.md` and receive JSON.
- Edit JSON and save corrected result.
- Download JSON.
- Display validation failure gracefully.

### Manual / Live Tests

- Run live extraction against the 5 provided menu URLs.
- Run live extraction against the 10-menu qualitative evaluation set.
- Verify OCR behavior on Pizzeria Da Michele or another image-only PDF.
- Verify Gemini fallback only runs when configured.

## 15. Definition of Done

The application is complete when:

- It accepts URL, free text, `.txt`, and `.md` inputs.
- It can process HTML menus and PDF menus.
- It has OCR fallback for image-only PDFs.
- It uses Google Gemini API structured output.
- It returns valid canonical JSON for every successful import.
- It handles Italian and English menus.
- It represents missing prices as `null`.
- It includes at least 5 real menu test cases.
- It includes qualitative evaluation over 10 menus.
- It has a minimal but usable web UI.
- It is fully dockerized.
- It uses PostgreSQL.
- It has documented setup, AI choice, and execution instructions.
- GitHub Actions pass on the completed `dev` branch.

## 16. Risks and Mitigations

- Risk: PDF layout extraction misaligns item names and prices.
  Mitigation: use page-aware extraction, pdfplumber layout mode, line-position hints, and fixture tests based on column-heavy menus.

- Risk: OCR is slow or flaky in CI.
  Mitigation: keep OCR tests small, use fixture PDFs, and separate live-heavy evaluation into a manual workflow.

- Risk: Gemini returns schema-valid but semantically wrong data.
  Mitigation: add deterministic post-validation, confidence warnings, evaluation metrics, and user correction UI.

- Risk: URL import creates SSRF/security exposure.
  Mitigation: strict URL validation, DNS/IP checks, private range blocking, redirects validation, timeouts, and size limits.

- Risk: API keys leak to the frontend.
  Mitigation: Gemini calls happen only in the backend; frontend never receives secrets.

- Risk: live menu URLs change or disappear.
  Mitigation: store stable fixtures for CI and keep live URL refresh as a manual workflow.

## 17. Initial GitHub Setup Notes

Before PR 1 starts, the repository should have a `dev` branch. If the current local folder is not yet a Git repository, initialize or clone the GitHub repository first, add `docs/brief.md` and this implementation plan, create `dev`, and push it. From that point onward, every implementation milestone follows the branch-per-PR workflow above.

## 18. References Used for Planning

- Project brief: `docs/brief.md`
- Gemini structured output documentation: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini model documentation: https://ai.google.dev/gemini-api/docs/models
- Re Sale menu PDF: https://www.resaleristorante.com/source/menu-resale-completo.pdf
- Il Covo del Ribelle menu PDF: https://ilcovodelribelle.com/wp-content/uploads/2023/12/MENU-COVO.pdf
- Love Menu PDF: https://ugc.production.linktr.ee/c203a2fe-ff6a-44b7-8250-95384d8e145d_LoveMenuA4--1-.pdf
- Nobu Milan menu PDF: https://noburestaurants.com/assets/Menus/Milan/ddd1a111f3/Nobu-Milan-Dinner-Menu.pdf
- Pizzeria Da Michele menu PDF: https://www.pizzeriadamichele.it/wp-content/uploads/2024/11/Menu-2024DaMichele-asporto.pdf
