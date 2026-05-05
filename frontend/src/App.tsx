import { useEffect, useState } from "react";
import "./App.css";

type HealthState = "checking" | "healthy" | "error";

type HealthResponse = {
  status: string;
  service: string;
  environment: string;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

export function App() {
  const [health, setHealth] = useState<HealthState>("checking");
  const [service, setService] = useState("Backend");

  async function checkHealth() {
    setHealth("checking");

    try {
      const response = await fetch(`${apiBaseUrl}/health`);
      if (!response.ok) {
        throw new Error(`Health check failed with ${response.status}`);
      }

      const data = (await response.json()) as HealthResponse;
      setService(data.service);
      setHealth(data.status === "healthy" ? "healthy" : "error");
    } catch {
      setHealth("error");
    }
  }

  useEffect(() => {
    void checkHealth();
  }, []);

  return (
    <main className="app-shell">
      <section className="health-panel" aria-labelledby="page-title">
        <p className="eyebrow">Milestone 1</p>
        <h1 id="page-title">Restaurant Menu Importer</h1>
        <p className="intro">
          Dockerized React and FastAPI foundation for turning restaurant menu
          text, files, and URLs into validated JSON in later milestones.
        </p>
        <div className="status-row">
          <span className="status-badge" data-state={health}>
            {service}: {health}
          </span>
          <button type="button" onClick={checkHealth} disabled={health === "checking"}>
            Check API Health
          </button>
        </div>
      </section>
    </main>
  );
}
