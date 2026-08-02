"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api/client";
import { getLiveness, getReadiness } from "@/lib/api/rag";
import type { HealthResponse, RetrievalStrategy } from "@/lib/api/types";

const STRATEGY_KEY = "rag-chat:default-strategy";
const TOP_K_KEY = "rag-chat:default-top-k";
const SERVICE_CONFIG = [
  { label: "FastAPI", value: process.env.NEXT_PUBLIC_FASTAPI_URL },
  { label: "Flower", value: process.env.NEXT_PUBLIC_FLOWER_URL },
  { label: "Prometheus", value: process.env.NEXT_PUBLIC_PROMETHEUS_URL },
  { label: "Grafana", value: process.env.NEXT_PUBLIC_GRAFANA_URL },
  { label: "Langfuse", value: process.env.NEXT_PUBLIC_LANGFUSE_URL },
  { label: "PostgreSQL", value: process.env.NEXT_PUBLIC_POSTGRESQL_URL },
  { label: "RabbitMQ", value: process.env.NEXT_PUBLIC_RABBITMQ_URL },
  { label: "Redis", value: process.env.NEXT_PUBLIC_REDIS_URL },
  { label: "Celery worker", value: process.env.NEXT_PUBLIC_CELERY_WORKER_URL },
  { label: "Qdrant", value: process.env.NEXT_PUBLIC_QDRANT_URL },
] as const;

export default function AdminSettingsPage() {
  const [liveness, setLiveness] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<RetrievalStrategy>("hybrid");
  const [topK, setTopK] = useState(5);

  const refreshHealth = useCallback(async () => {
    setHealthError(null);
    setLiveness(null);
    setReadiness(null);
    try {
      const live = await getLiveness();
      setLiveness(live);
      try {
        setReadiness(await getReadiness());
      } catch (err) {
        setReadiness({ status: "error", checks: { readiness: err instanceof Error ? err.message : "unavailable" } });
      }
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "Backend is not reachable");
    }
  }, []);

  useEffect(() => {
    const savedStrategy = window.localStorage.getItem(STRATEGY_KEY) as RetrievalStrategy | null;
    const savedTopK = Number(window.localStorage.getItem(TOP_K_KEY) || 5);
    if (savedStrategy) setStrategy(savedStrategy);
    if (Number.isFinite(savedTopK)) setTopK(savedTopK);
    refreshHealth();
  }, [refreshHealth]);

  function saveDefaults() {
    window.localStorage.setItem(STRATEGY_KEY, strategy);
    window.localStorage.setItem(TOP_K_KEY, String(topK));
  }

  return (
    <div className="admin-page">
      <header className="admin-page-header">
        <div>
          <h1>Settings</h1>
          <p>Check service health and set local UI defaults. These settings are stored in this browser for now.</p>
        </div>
        <button className="secondary-button" type="button" onClick={refreshHealth}>Refresh health</button>
      </header>

      <div className="admin-grid two-columns">
        <section className="admin-card">
          <h2>Backend health</h2>
          {healthError ? <div className="error-box compact">{healthError}</div> : null}
          <div className="status-list">
            <StatusRow label="Backend liveness" value={liveness?.status || "unknown"} ok={liveness?.status === "ok"} />
            <StatusRow label="Readiness" value={readiness?.status || "unknown"} ok={readiness?.status === "ok"} />
            {Object.entries(readiness?.checks || {}).map(([key, value]) => (
              <StatusRow key={key} label={key} value={value} ok={value === "ok"} />
            ))}
          </div>
        </section>

        <section className="admin-card">
          <h2>Frontend API config</h2>
          <div className="settings-list">
            <div><strong>API base URL</strong><span>{getApiBaseUrl()}</span></div>
            <div><strong>API key configured</strong><span>{process.env.NEXT_PUBLIC_API_KEY ? "yes" : "no"}</span></div>
          </div>
        </section>

        <section className="admin-card">
          <h2>Chat defaults</h2>
          <div className="admin-form standalone">
            <label>
              Default retrieval strategy
              <select value={strategy} onChange={(event) => setStrategy(event.target.value as RetrievalStrategy)}>
                <option value="hybrid">Hybrid</option>
                <option value="vector">Vector</option>
                <option value="bm25">BM25</option>
              </select>
            </label>
            <label>
              Default top K
              <input type="number" min={1} max={50} value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
            </label>
            <button type="button" onClick={saveDefaults}>Save defaults</button>
          </div>
        </section>

        <section className="admin-card">
          <h2>Required services</h2>
          <div className="settings-list">
            {SERVICE_CONFIG.map((service) => <ServiceConfigRow key={service.label} {...service} />)}
          </div>
        </section>
      </div>
    </div>
  );
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <strong className={ok ? "ok" : "bad"}>{value}</strong>
    </div>
  );
}

function ServiceConfigRow({ label, value }: { label: string; value: string | undefined }) {
  const displayValue = value?.trim();
  const href = displayValue ? getSafeExternalUrl(displayValue) : null;

  return (
    <div>
      <strong>{label}</strong>
      {!displayValue ? <span>Not configured</span> : null}
      {displayValue && href ? <a href={href} target="_blank" rel="noopener noreferrer">{href}</a> : null}
      {displayValue && !href ? <span>{displayValue}</span> : null}
    </div>
  );
}

function getSafeExternalUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch (error) {
    if (error instanceof TypeError) return null;
    throw error;
  }
}
