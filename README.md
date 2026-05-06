# Restaurant Menu Importer

Dockerized web application foundation for extracting structured JSON from restaurant menu content. Milestone 7 supports pasted text, `.txt` / `.md` uploads, public HTML menu page imports, and direct PDF menu URL imports. URL imports validate outbound targets for SSRF safety, fetch pages or PDFs with redirect/timeout/size limits, extract readable HTML or page-aware PDF text, fall back through layout-aware PDF extraction and OCR for empty text layers, persist normalized source text in PostgreSQL, send extracted text through Gemini structured output, validate canonical JSON, and show import history plus detail shells in the React UI.

JSON editing/export and the evaluation dashboard are planned for later milestones in [docs/implementation-plan.md](docs/implementation-plan.md).

## Stack

- Backend: Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy async, Alembic, PyMuPDF, pdfplumber, OCRmyPDF/Tesseract
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
- `POST /api/imports/url`: create an import from a public HTTP/HTTPS HTML menu page or direct PDF menu URL.
- `GET /api/imports`: list recent imports.
- `GET /api/imports/{id}`: inspect status, source metadata, and event history.

Imports are persisted, processed through Gemini extraction, validated against the canonical menu schema, and stored with `succeeded` or `failed` status. Failed Gemini calls or invalid structured output are stored on the import as useful errors.

URL imports reject localhost, private/internal network targets, link-local addresses, metadata IPs, unsupported schemes, and credentialed URLs. The fetcher follows a small number of validated redirects, enforces timeouts and response size limits, and stores cleaned HTML or PDF text as the import source. Likely PDF menu links discovered inside HTML pages are recorded in import event metadata.

PDF URL imports are detected from `Content-Type: application/pdf` or the PDF file signature. Text-layer PDFs are extracted with PyMuPDF into `[Page N]` sections. Sparse or layout-sensitive text can fall back to pdfplumber, and empty-text PDFs use OCRmyPDF/Tesseract OCR. Repeated headers, footers, legends, and legal/allergen lines are removed when they repeat across pages.

The backend container and CI install OCR system packages. For local backend development outside Docker, install `ocrmypdf` and `tesseract` on your system if you want to exercise scanned PDF fallback locally.

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
- Milestone 6 work lives on `feature/06-pdf-ocr-extraction`.
- Milestone 7 work lives on `feature/07-gemini-extraction`.

## Milestone 7 Scope

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

Not included yet:

- JSON editing/export or evaluation workflows
