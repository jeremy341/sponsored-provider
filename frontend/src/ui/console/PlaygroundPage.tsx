import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleSlash, Copy, Eraser, RotateCcw, Square } from "lucide-react";
import { ApiError, api, streamPlayground } from "../../lib/api";
import type { ApiKeyRecord, ModelRecord, PlaygroundMessage, PlaygroundTelemetry } from "../../contracts/api";
import { SelectMenu } from "../SelectMenu";
import { DataNotice, PageHeader } from "../shared";

const IDLE_TELEMETRY: PlaygroundTelemetry = {
  status: "idle", model: null, provider: null, ttftMs: null, latencyMs: null,
  inputTokens: null, outputTokens: null, costUsd: null, costSource: null, error: null, errorCode: null,
};

interface DraftParams {
  keyId: string;
  modelId: string;
  system: string;
  temperature: number;
  maxTokens: number;
  stream: boolean;
}

function estimateCostUsd(model: ModelRecord | undefined, inputTokens: number, outputTokens: number): number | null {
  if (!model?.inputUsdPerMillion || !model?.outputUsdPerMillion) return null;
  return (inputTokens / 1_000_000) * Number(model.inputUsdPerMillion) + (outputTokens / 1_000_000) * Number(model.outputUsdPerMillion);
}

function formatMs(value: number | null): string {
  return value == null ? "—" : `${Math.round(value).toLocaleString("en-US")} ms`;
}

function formatCost(value: number | null): string {
  return value == null ? "—" : `$${value.toFixed(8).replace(/0+$/, "").replace(/\.$/, "")}`;
}

export function PlaygroundPage() {
  const [keys, setKeys] = useState<ApiKeyRecord[] | null>(null);
  const [models, setModels] = useState<ModelRecord[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [telemetry, setTelemetry] = useState<PlaygroundTelemetry>(IDLE_TELEMETRY);
  const [params, setParams] = useState<DraftParams>({ keyId: "", modelId: "", system: "", temperature: 0.7, maxTokens: 512, stream: true });
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);

  const activeKeys = useMemo(() => (keys ?? []).filter((key) => key.status === "active"), [keys]);

  useEffect(() => {
    let active = true;
    Promise.all([api.listKeys(), api.listModels()])
      .then(([keyList, modelList]) => {
        if (!active) return;
        setKeys(keyList);
        setModels(modelList);
        setParams((previous) => ({
          ...previous,
          keyId: previous.keyId || keyList.find((key) => key.status === "active")?.id || "",
          modelId: previous.modelId || modelList[0]?.id || "",
        }));
      })
      .catch(() => {
        if (active) setLoadError("The portal API could not load your keys or the model catalog.");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => () => { abortRef.current?.abort(); }, []);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread && typeof thread.scrollTo === "function") thread.scrollTo({ top: thread.scrollHeight });
  }, [messages]);

  const selectedModel = useMemo(() => (models ?? []).find((model) => model.id === params.modelId), [models, params.modelId]);

  const run = useCallback(async (history: PlaygroundMessage[]) => {
    const keyId = params.keyId;
    const modelId = params.modelId;
    if (!keyId || !modelId || telemetry.status === "running") return;

    const payload: Record<string, unknown> = {
      model: modelId,
      stream: params.stream,
      temperature: params.temperature,
      max_tokens: params.maxTokens,
      messages: [
        ...(params.system.trim() ? [{ role: "system", content: params.system.trim() }] : []),
        ...history.map((message) => ({ role: message.role, content: message.content })),
      ],
    };

    const controller = new AbortController();
    abortRef.current = controller;
    const started = performance.now();
    setTelemetry({ ...IDLE_TELEMETRY, status: "running", model: modelId, provider: selectedModel?.providerName ?? null });

    try {
      const result = await streamPlayground({
        keyId,
        payload,
        signal: controller.signal,
        onTelemetry: (event) => {
          setTelemetry((previous) => ({
            ...previous,
            ttftMs: event.ttftMs ?? previous.ttftMs,
            error: event.error ?? previous.error,
            errorCode: event.errorCode ?? previous.errorCode,
            status: event.error ? "error" : previous.status,
          }));
        },
      });
      const latencyMs = performance.now() - started;
      setMessages((previous) => [...previous, { role: "assistant", content: result.text || (result.error ? "" : "(empty response)") }]);
      setTelemetry((previous) => {
        if (result.error) {
          return { ...previous, status: "error", latencyMs, error: result.error, errorCode: result.errorCode };
        }
        // Non-stream responses carry real reported usage; streams settle after
        // completion and are recorded metadata-only in Logs.
        const inputTokens = result.usage?.input ?? null;
        const outputTokens = result.usage?.output ?? null;
        const costUsd = inputTokens != null && outputTokens != null ? estimateCostUsd(selectedModel, inputTokens, outputTokens) : null;
        return {
          ...previous,
          status: "success",
          latencyMs,
          inputTokens,
          outputTokens,
          costUsd,
          costSource: params.stream ? "settling" : costUsd != null ? "estimate" : null,
        };
      });
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        setTelemetry((previous) => ({ ...previous, status: "stopped", latencyMs: performance.now() - started }));
      } else {
        const apiError = error as ApiError;
        setTelemetry((previous) => ({ ...previous, status: "error", latencyMs: performance.now() - started, error: apiError.message, errorCode: apiError.code }));
      }
    } finally {
      abortRef.current = null;
    }
  }, [params, selectedModel, telemetry.status]);

  async function submit() {
    const content = draft.trim();
    if (!content || telemetry.status === "running") return;
    const history: PlaygroundMessage[] = [...messages, { role: "user", content }];
    setMessages(history);
    setDraft("");
    await run(history);
  }

  function stop() {
    abortRef.current?.abort();
  }

  function retry() {
    if (telemetry.status === "running") return;
    // Drop the trailing assistant placeholder so the last exchange re-runs.
    const trimmed = [...messages];
    while (trimmed.length && trimmed[trimmed.length - 1].role === "assistant") trimmed.pop();
    if (!trimmed.length) return;
    setMessages(trimmed);
    void run(trimmed);
  }

  function clearThread() {
    if (telemetry.status === "running") return;
    setMessages([]);
    setTelemetry(IDLE_TELEMETRY);
  }

  async function copyLastResponse() {
    const last = [...messages].reverse().find((message) => message.role === "assistant");
    if (!last?.content) return;
    try {
      await navigator.clipboard.writeText(last.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard denied: leave the button state unchanged.
    }
  }

  const running = telemetry.status === "running";

  return <section className="page playground-page" aria-label="Playground">
    <PageHeader
      title="Playground"
      description="Run one real sponsored request through the gateway. Conversations stay in memory only and are never stored."
      action={<span className="inline-notice notice-info playground-privacy"><CircleSlash size={15} /><span>Not stored</span></span>}
    />
    <DataNotice error={loadError} />
    <div className="playground-layout">
      <div className="playground-thread-pane">
        <div ref={threadRef} className="playground-thread" aria-live="polite">
          {messages.length === 0 && <div className="playground-empty">
            <p>Send a prompt to run a live request against your selected model and API key.</p>
            <p className="small">Normal allowance, key policy, rate limits, and routing apply. Usage appears in Activity and Logs.</p>
          </div>}
          {messages.map((message, index) => <article key={index} className={`playground-message playground-message-${message.role}`}>
            <span className="playground-message-role">{message.role === "user" ? "You" : "Assistant"}</span>
            <p>{message.content || <span className="small muted">No response content.</span>}</p>
          </article>)}
          {running && <div className="playground-message playground-message-assistant playground-message-running"><span className="playground-message-role">Assistant</span><p className="small muted">Streaming…</p></div>}
        </div>
        <div className="playground-composer">
          <label className="sr-only" htmlFor="playground-prompt">Prompt</label>
          <textarea
            id="playground-prompt"
            value={draft}
            placeholder="Ask something…"
            rows={3}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                void submit();
              }
            }}
          />
          <div className="playground-composer-actions">
            <button type="button" className="button button-primary" onClick={() => void submit()} disabled={!draft.trim() || running || !params.keyId || !params.modelId}>Send</button>
            {running
              ? <button type="button" className="button button-danger" onClick={stop}><Square size={15} />Stop</button>
              : <button type="button" className="button button-secondary" onClick={retry} disabled={!messages.some((message) => message.role === "assistant")}><RotateCcw size={15} />Retry</button>}
            <button type="button" className="button button-secondary" onClick={() => void copyLastResponse()} disabled={!messages.some((message) => message.role === "assistant" && message.content)}><Copy size={15} />{copied ? "Copied" : "Copy"}</button>
            <button type="button" className="button button-ghost" onClick={clearThread} disabled={running || !messages.length}><Eraser size={15} />Clear</button>
          </div>
        </div>
        <footer className="playground-telemetry" aria-label="Request telemetry">
          <span data-testid="playground-status"><StatusLabelInline status={telemetry.status} /></span>
          <span><small>Model</small>{telemetry.model ?? "—"}</span>
          <span><small>Provider</small>{telemetry.provider ?? "—"}</span>
          <span><small>TTFT</small>{formatMs(telemetry.ttftMs)}</span>
          <span><small>Latency</small>{formatMs(telemetry.latencyMs)}</span>
          <span><small>Tokens in/out</small>{telemetry.inputTokens == null && telemetry.outputTokens == null ? "—" : `${telemetry.inputTokens ?? "?"} / ${telemetry.outputTokens ?? "?"}`}</span>
          <span><small>Cost</small>{telemetry.costUsd == null ? (telemetry.costSource === "settling" ? "Settling in Logs" : "—") : formatCost(telemetry.costUsd)}<small className="muted">{telemetry.costSource === "estimate" ? " · published-rate estimate" : ""}</small></span>
        </footer>
        {telemetry.error && <div className="inline-notice notice-error" role="alert"><span>{telemetry.error}{telemetry.errorCode ? ` (${telemetry.errorCode})` : ""}</span></div>}
      </div>
      <aside className="playground-config" aria-label="Request configuration">
        <div className="config-field">
          <label htmlFor="playground-key">API key</label>
          {activeKeys.length
            ? <SelectMenu
                ariaLabel="API key"
                id="playground-key"
                value={params.keyId}
                onValueChange={(value) => setParams((previous) => ({ ...previous, keyId: value }))}
                options={activeKeys.map((key) => ({ value: key.id, label: `${key.label} · ${key.prefix}…` }))}
              />
            : <p className="small muted">No active API keys. Create one under API Keys.</p>}
        </div>
        <div className="config-field">
          <label htmlFor="playground-model">Model</label>
          <SelectMenu
            ariaLabel="Model"
            id="playground-model"
            value={params.modelId}
            onValueChange={(value) => setParams((previous) => ({ ...previous, modelId: value }))}
            options={(models ?? []).map((model) => ({ value: model.id, label: model.displayName || model.id }))}
          />
          {selectedModel && <p className="small muted">
            {selectedModel.providerName} · {selectedModel.inputUsdPerMillion == null ? "pricing unavailable" : `$${selectedModel.inputUsdPerMillion}/M in`} · {selectedModel.outputUsdPerMillion == null ? "pricing unavailable" : `$${selectedModel.outputUsdPerMillion}/M out`}
          </p>}
        </div>
        <div className="config-field">
          <label htmlFor="playground-system">System message</label>
          <textarea id="playground-system" rows={3} value={params.system} onChange={(event) => setParams((previous) => ({ ...previous, system: event.target.value }))} placeholder="Optional system instructions" />
        </div>
        <div className="config-field config-field-inline">
          <label htmlFor="playground-temperature">Temperature <output>{params.temperature.toFixed(1)}</output></label>
          <input id="playground-temperature" type="range" min={0} max={2} step={0.1} value={params.temperature} onChange={(event) => setParams((previous) => ({ ...previous, temperature: Number(event.target.value) }))} />
        </div>
        <div className="config-field">
          <label htmlFor="playground-max-tokens">Max tokens</label>
          <input id="playground-max-tokens" className="text-input" type="number" min={1} max={8192} value={params.maxTokens} onChange={(event) => setParams((previous) => ({ ...previous, maxTokens: Math.max(1, Math.floor(Number(event.target.value) || 1)) }))} />
        </div>
        <div className="config-field config-field-inline config-field-check">
          <input id="playground-stream" type="checkbox" checked={params.stream} onChange={(event) => setParams((previous) => ({ ...previous, stream: event.target.checked }))} />
          <label htmlFor="playground-stream">Stream response</label>
        </div>
        <p className="small muted playground-config-note">Requests run through the same gateway pipeline as /v1: key policy, rate limits, allowance reservation, and provider routing.</p>
      </aside>
    </div>
  </section>;
}

function StatusLabelInline({ status }: { status: PlaygroundTelemetry["status"] }) {
  return <span className={`status-label status-${status}`}><span className="status-dot" aria-hidden="true" />{status}</span>;
}
