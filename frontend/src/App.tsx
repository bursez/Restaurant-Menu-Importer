import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import "./App.css";

type ImportStatus = "pending" | "running" | "succeeded" | "failed";
type ImportInputType = "text" | "file" | "url";
type ImportMode = "text" | "file" | "url";

type ImportEvent = {
  id: string;
  stage: string;
  message: string;
  event_metadata: Record<string, unknown>;
  created_at: string;
};

type ImportSummary = {
  id: string;
  input_type: ImportInputType;
  source_value: string | null;
  source_filename: string | null;
  status: ImportStatus;
  error_message: string | null;
  model_used: string | null;
  duration_ms: number | null;
  created_at: string;
  updated_at: string;
};

type ImportDetail = ImportSummary & {
  events: ImportEvent[];
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function parseApiError(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : `Request failed with ${response.status}`;
  } catch {
    return `Request failed with ${response.status}`;
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function App() {
  const [mode, setMode] = useState<ImportMode>("text");
  const [text, setText] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [imports, setImports] = useState<ImportSummary[]>([]);
  const [selectedImport, setSelectedImport] = useState<ImportDetail | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSourcePreview = useMemo(() => {
    if (!selectedImport?.source_value) {
      return "";
    }
    return selectedImport.source_value.length > 1400
      ? `${selectedImport.source_value.slice(0, 1400)}...`
      : selectedImport.source_value;
  }, [selectedImport]);

  async function loadImports() {
    setIsLoadingHistory(true);
    setError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/imports`);
      if (!response.ok) {
        throw new Error(await parseApiError(response));
      }

      setImports((await response.json()) as ImportSummary[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load import history");
    } finally {
      setIsLoadingHistory(false);
    }
  }

  async function loadImportDetail(importId: string) {
    setError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/imports/${importId}`);
      if (!response.ok) {
        throw new Error(await parseApiError(response));
      }

      setSelectedImport((await response.json()) as ImportDetail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load import details");
    }
  }

  useEffect(() => {
    void loadImports();
  }, []);

  async function submitTextImport() {
    const response = await fetch(`${apiBaseUrl}/imports/text`, {
      body: JSON.stringify({
        text,
        source_name: sourceName.trim() || null,
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(await parseApiError(response));
    }

    setText("");
    setSourceName("");
    return (await response.json()) as ImportDetail;
  }

  async function submitFileImport() {
    if (!file) {
      throw new Error("Choose a .txt or .md file");
    }

    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${apiBaseUrl}/imports/file`, {
      body: formData,
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(await parseApiError(response));
    }

    setFile(null);
    return (await response.json()) as ImportDetail;
  }

  async function submitUrlImport() {
    const response = await fetch(`${apiBaseUrl}/imports/url`, {
      body: JSON.stringify({ url }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(await parseApiError(response));
    }

    setUrl("");
    return (await response.json()) as ImportDetail;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const createdImport =
        mode === "text"
          ? await submitTextImport()
          : mode === "file"
            ? await submitFileImport()
            : await submitUrlImport();
      setSelectedImport(createdImport);
      await loadImports();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  const canSubmit =
    mode === "text" ? text.trim().length > 0 : mode === "file" ? file !== null : url.trim().length > 0;

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <p className="eyebrow">Milestone 5</p>
          <h1>Restaurant Menu Importer</h1>
        </div>
        <button className="secondary-button" type="button" onClick={loadImports} disabled={isLoadingHistory}>
          Refresh
        </button>
      </header>

      {error ? <p className="alert">{error}</p> : null}

      <section className="workspace" aria-label="Import workspace">
        <form className="import-panel" onSubmit={handleSubmit}>
          <div className="tab-list" role="tablist" aria-label="Import source">
            <button
              aria-selected={mode === "url"}
              className="tab-button"
              onClick={() => setMode("url")}
              role="tab"
              type="button"
            >
              URL
            </button>
            <button
              aria-selected={mode === "text"}
              className="tab-button"
              onClick={() => setMode("text")}
              role="tab"
              type="button"
            >
              Pasted text
            </button>
            <button
              aria-selected={mode === "file"}
              className="tab-button"
              onClick={() => setMode("file")}
              role="tab"
              type="button"
            >
              File
            </button>
          </div>

          {mode === "url" ? (
            <div className="field-stack">
              <label htmlFor="menu-url">Menu page URL</label>
              <input
                id="menu-url"
                inputMode="url"
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com/menu"
                required
                type="url"
                value={url}
              />
            </div>
          ) : mode === "text" ? (
            <div className="field-stack">
              <label htmlFor="source-name">Source name</label>
              <input
                id="source-name"
                maxLength={255}
                onChange={(event) => setSourceName(event.target.value)}
                placeholder="Dinner menu"
                type="text"
                value={sourceName}
              />
              <label htmlFor="menu-text">Menu text</label>
              <textarea
                id="menu-text"
                onChange={(event) => setText(event.target.value)}
                required
                rows={14}
                value={text}
              />
            </div>
          ) : (
            <div className="field-stack">
              <label htmlFor="menu-file">Menu file</label>
              <input id="menu-file" accept=".txt,.md,text/plain,text/markdown" onChange={handleFileChange} type="file" />
              {file ? <p className="file-name">{file.name}</p> : null}
            </div>
          )}

          <button type="submit" disabled={isSubmitting || !canSubmit}>
            {isSubmitting ? "Importing" : "Create import"}
          </button>
        </form>

        <aside className="history-panel" aria-labelledby="history-title">
          <div className="panel-heading">
            <h2 id="history-title">History</h2>
            <span>{imports.length}</span>
          </div>
          <div className="history-list">
            {imports.length === 0 ? <p className="empty-state">No imports yet.</p> : null}
            {imports.map((importRecord) => (
              <button
                className="history-item"
                key={importRecord.id}
                onClick={() => loadImportDetail(importRecord.id)}
                type="button"
              >
                <span>
                  {importRecord.source_filename || importRecord.input_type}
                  <small>{formatDate(importRecord.created_at)}</small>
                </span>
                <strong data-status={importRecord.status}>{importRecord.status}</strong>
              </button>
            ))}
          </div>
        </aside>
      </section>

      <section className="detail-panel" aria-labelledby="detail-title">
        <div className="panel-heading">
          <h2 id="detail-title">Import detail</h2>
          {selectedImport ? <strong data-status={selectedImport.status}>{selectedImport.status}</strong> : null}
        </div>

        {selectedImport ? (
          <div className="detail-grid">
            <dl>
              <div>
                <dt>Type</dt>
                <dd>{selectedImport.input_type}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>
                  {selectedImport.source_filename ||
                    (selectedImport.input_type === "text" ? "Pasted text" : "Uploaded file")}
                </dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatDate(selectedImport.created_at)}</dd>
              </div>
            </dl>

            <div className="placeholder-panel">
              <h3>AI extraction pending</h3>
              <p>Stored source text is ready for the Gemini extraction milestone.</p>
            </div>

            <div className="source-preview">
              <h3>Source text</h3>
              <pre>{selectedSourcePreview}</pre>
            </div>

            <div className="event-list">
              <h3>Events</h3>
              {selectedImport.events.map((event) => (
                <article key={event.id}>
                  <strong>{event.stage}</strong>
                  <p>{event.message}</p>
                </article>
              ))}
            </div>
          </div>
        ) : (
          <p className="empty-state">Select or create an import.</p>
        )}
      </section>
    </main>
  );
}
