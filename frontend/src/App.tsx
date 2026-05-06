import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { z } from "zod";
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
  extracted_menu: ExtractedMenu | null;
};

type ImportDetail = ImportSummary & {
  events: ImportEvent[];
};

type ValidationWarning = {
  code: string;
  message: string;
  path: string | null;
  context: Record<string, unknown>;
};

type MenuVariant = {
  name: string;
  price: number | null;
  price_text: string | null;
};

type MenuItem = {
  name: string;
  description: string | null;
  price: number | null;
  price_text: string | null;
  allergens: string[];
  tags: string[];
  variants: MenuVariant[];
};

type MenuCategory = {
  name: string;
  items: MenuItem[];
};

type CanonicalMenu = {
  restaurant: string;
  currency: string | null;
  language: string | null;
  source: {
    type: ImportInputType;
    value: string;
  };
  categories: MenuCategory[];
  confidence_score: number | null;
  validation_warnings: ValidationWarning[];
};

type ExtractedMenu = {
  id: string;
  restaurant_name: string | null;
  currency: string | null;
  language: string | null;
  confidence_score: string | number | null;
  validation_status: string;
  canonical_json: CanonicalMenu;
  created_at: string;
  updated_at: string;
};

const warningSchema = z.object({
  code: z.enum([
    "missing_price",
    "unknown_currency",
    "duplicate_category",
    "duplicate_item",
    "low_confidence",
    "normalized_price",
  ]),
  message: z.string().min(1),
  path: z.string().nullable().optional(),
  context: z.record(z.string(), z.unknown()).default({}),
});

const variantSchema = z.object({
  name: z.string().min(1),
  price: z.number().nonnegative().nullable().optional(),
  price_text: z.string().nullable().optional(),
});

const itemSchema = z.object({
  name: z.string().min(1),
  description: z.string().nullable().optional(),
  price: z.number().nonnegative().nullable().optional(),
  price_text: z.string().nullable().optional(),
  allergens: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  variants: z.array(variantSchema).default([]),
});

const canonicalMenuSchema = z.object({
  restaurant: z.string().min(1),
  currency: z.string().length(3).nullable().optional(),
  language: z.string().min(2).max(16).nullable().optional(),
  source: z.object({
    type: z.enum(["text", "file", "url"]),
    value: z.string().min(1),
  }),
  categories: z.array(
    z.object({
      name: z.string().min(1),
      items: z.array(itemSchema).default([]),
    }),
  ),
  confidence_score: z.number().min(0).max(1).nullable().optional(),
  validation_warnings: z.array(warningSchema).default([]),
});

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

function formatPrice(item: Pick<MenuItem | MenuVariant, "price" | "price_text">) {
  if (item.price_text) {
    return item.price_text;
  }
  return typeof item.price === "number" ? item.price.toFixed(2) : "Missing";
}

function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function validationMessage(error: z.ZodError) {
  return error.issues.map((issue) => `${issue.path.join(".") || "menu"}: ${issue.message}`).join("\n");
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
  const [jsonDraft, setJsonDraft] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [jsonNotice, setJsonNotice] = useState<string | null>(null);
  const [isSavingJson, setIsSavingJson] = useState(false);
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

  useEffect(() => {
    setJsonDraft(selectedImport?.extracted_menu ? prettyJson(selectedImport.extracted_menu.canonical_json) : "");
    setJsonError(null);
  }, [selectedImport]);

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

  function parseAndValidateDraft() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonDraft);
    } catch (err) {
      throw new Error(err instanceof SyntaxError ? err.message : "JSON could not be parsed");
    }

    const result = canonicalMenuSchema.safeParse(parsed);
    if (!result.success) {
      throw new Error(validationMessage(result.error));
    }
    return result.data;
  }

  async function saveJsonDraft() {
    setJsonError(null);
    setJsonNotice(null);
    if (!selectedImport) {
      return;
    }

    let canonicalJson: z.infer<typeof canonicalMenuSchema>;
    try {
      canonicalJson = parseAndValidateDraft();
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "JSON is not valid");
      return;
    }

    setIsSavingJson(true);
    try {
      const response = await fetch(`${apiBaseUrl}/imports/${selectedImport.id}/json`, {
        body: JSON.stringify({ canonical_json: canonicalJson }),
        headers: { "Content-Type": "application/json" },
        method: "PATCH",
      });
      if (!response.ok) {
        throw new Error(await parseApiError(response));
      }
      const updatedImport = (await response.json()) as ImportDetail;
      setSelectedImport(updatedImport);
      setJsonNotice("JSON saved");
      await loadImports();
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "Could not save JSON");
    } finally {
      setIsSavingJson(false);
    }
  }

  async function copyJsonDraft() {
    setJsonError(null);
    setJsonNotice(null);
    try {
      parseAndValidateDraft();
      await navigator.clipboard.writeText(jsonDraft);
      setJsonNotice("JSON copied");
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "Could not copy JSON");
    }
  }

  async function downloadJson() {
    setJsonError(null);
    setJsonNotice(null);
    if (!selectedImport) {
      return;
    }
    try {
      const response = await fetch(`${apiBaseUrl}/imports/${selectedImport.id}/json`);
      if (!response.ok) {
        throw new Error(await parseApiError(response));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `menu-${selectedImport.id}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setJsonNotice("JSON download started");
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "Could not download JSON");
    }
  }

  const canSubmit =
    mode === "text" ? text.trim().length > 0 : mode === "file" ? file !== null : url.trim().length > 0;

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <p className="eyebrow">Milestone 8</p>
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

            {selectedImport.extracted_menu ? (
              <div className="results-workspace">
                <section className="result-table" aria-labelledby="results-title">
                  <div className="subsection-heading">
                    <div>
                      <h3 id="results-title">{selectedImport.extracted_menu.canonical_json.restaurant}</h3>
                      <p>
                        {selectedImport.extracted_menu.currency || "Unknown currency"} ·{" "}
                        {selectedImport.extracted_menu.language || "Unknown language"}
                      </p>
                    </div>
                    <span>{selectedImport.extracted_menu.canonical_json.categories.length} categories</span>
                  </div>

                  {selectedImport.extracted_menu.canonical_json.categories.map((category) => (
                    <article className="category-table" key={category.name}>
                      <h4>{category.name}</h4>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th scope="col">Dish</th>
                              <th scope="col">Description</th>
                              <th scope="col">Price</th>
                              <th scope="col">Tags</th>
                            </tr>
                          </thead>
                          <tbody>
                            {category.items.map((item) => (
                              <tr key={`${category.name}-${item.name}-${item.price_text ?? item.price ?? "no-price"}`}>
                                <td>
                                  <strong>{item.name}</strong>
                                  {item.variants.length > 0 ? (
                                    <ul>
                                      {item.variants.map((variant) => (
                                        <li key={`${item.name}-${variant.name}`}>
                                          {variant.name}: {formatPrice(variant)}
                                        </li>
                                      ))}
                                    </ul>
                                  ) : null}
                                </td>
                                <td>{item.description || "No description"}</td>
                                <td>{formatPrice(item)}</td>
                                <td>{[...item.tags, ...item.allergens].join(", ") || "None"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </article>
                  ))}
                </section>

                <section className="json-editor" aria-labelledby="json-title">
                  <div className="subsection-heading">
                    <div>
                      <h3 id="json-title">Canonical JSON</h3>
                      <p>Validated against the menu schema before saving.</p>
                    </div>
                    <div className="action-row">
                      <button className="secondary-button" type="button" onClick={copyJsonDraft}>
                        Copy
                      </button>
                      <button className="secondary-button" type="button" onClick={downloadJson}>
                        Download
                      </button>
                      <button type="button" onClick={saveJsonDraft} disabled={isSavingJson}>
                        {isSavingJson ? "Saving" : "Save JSON"}
                      </button>
                    </div>
                  </div>
                  <textarea
                    aria-label="Canonical JSON editor"
                    className="json-textarea"
                    onChange={(event) => setJsonDraft(event.target.value)}
                    spellCheck={false}
                    value={jsonDraft}
                  />
                  {jsonError ? <pre className="json-error">{jsonError}</pre> : null}
                  {jsonNotice ? <p className="json-notice">{jsonNotice}</p> : null}
                </section>

                <section className="warnings-panel" aria-labelledby="warnings-title">
                  <h3 id="warnings-title">Validation warnings</h3>
                  {selectedImport.extracted_menu.canonical_json.validation_warnings.length === 0 ? (
                    <p className="empty-state">No warnings for this extraction.</p>
                  ) : (
                    selectedImport.extracted_menu.canonical_json.validation_warnings.map((warning) => (
                      <article key={`${warning.code}-${warning.path ?? warning.message}`}>
                        <strong>{warning.code.replace(/_/g, " ")}</strong>
                        <p>{warning.message}</p>
                        {warning.path ? <small>{warning.path}</small> : null}
                      </article>
                    ))
                  )}
                </section>
              </div>
            ) : (
              <div className="placeholder-panel">
                <h3>No extracted JSON yet</h3>
                <p>Completed imports will show structured results, editable JSON, and export actions here.</p>
              </div>
            )}

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
