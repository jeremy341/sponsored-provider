import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { PixelIcon } from "../../icons/PixelIcon";
import { ApiError } from "../../../lib/api";
import type { PortalApi } from "../../../contracts/api";

export function ConnectionDialog({ portalApi, onCreated }: { portalApi: PortalApi; onCreated: (summary: string) => void }) {
  const [open, setOpen] = useState(false);
  const [brandName, setBrandName] = useState("");
  const [brandSlug, setBrandSlug] = useState("");
  const [label, setLabel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (!open) { setSecret(""); setError(null); } }, [open]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);

    try {
      const result = await portalApi.createProvider({ name: brandName.trim(), brandSlug: brandSlug.trim(), connectionLabel: label.trim(), baseUrl: baseUrl.trim(), apiKey: secret });
      setSecret("");

      const status = "sync" in result
        ? `Connection test: ${result.sync.tested ? "passed" : "failed"}. Model discovery: ${result.sync.error ? `failed — ${result.sync.error}` : `${result.sync.discovered} models found`}.`
        : `Connection test passed. Discovery found ${result.models.length} models.`;

      onCreated(status);
      setOpen(false);
    } catch (caught) {
      setSecret("");

      if (caught instanceof ApiError && caught.status === 502) {
        onCreated(`Connection saved. Initial /models test and discovery failed: ${caught.message}`);
        setOpen(false);
      } else {
        setError(caught instanceof Error ? caught.message : "Connection could not be created. The credential has been cleared; enter it again to retry.");
      }
    } finally { setBusy(false); }
  }

  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger asChild><button className="button button-primary" type="button"><PixelIcon name="add" /> Add connection</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content" aria-describedby="connection-description">
      <div className="dialog-title-row"><div><Dialog.Title>Add provider connection</Dialog.Title><Dialog.Description id="connection-description">Add an OpenAI compatible endpoint. The server tests the credential and performs its initial model sync as part of creation.</Dialog.Description></div><Dialog.Close asChild><button type="button" className="icon-button" aria-label="Close connection form"><PixelIcon name="close" /></button></Dialog.Close></div>
      <form className="dialog-form" onSubmit={(event) => { void submit(event); }}>
        <label><span className="field-label">Provider brand</span><input required value={brandName} onChange={(event) => { setBrandName(event.target.value); setBrandSlug(event.target.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")); }} placeholder="Acme AI" /></label>
        <label><span className="field-label">Brand ID</span><input required value={brandSlug} onChange={(event) => setBrandSlug(event.target.value)} placeholder="acme-ai" /></label>
        <label><span className="field-label">Private connection label</span><input required value={label} onChange={(event) => setLabel(event.target.value)} placeholder="EU primary" /></label>
        <label><span className="field-label">OpenAI compatible HTTPS URL</span><input required type="url" pattern="https://.*" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" /></label>
        <label><span className="field-label">Provider credential</span><span className="secret-field"><input required type="password" autoComplete="new-password" value={secret} onChange={(event) => setSecret(event.target.value)} /><PixelIcon name="key" /></span></label>
        <p className="field-help">The raw credential is sent only in this request, never saved in browser storage, and erased from this form after the request completes.</p>
        {error && <div role="alert" className="inline-notice notice-error"><PixelIcon name="shield" /><span>{error}</span></div>}
        <div className="dialog-actions"><Dialog.Close asChild><button className="button button-quiet" type="button">Cancel</button></Dialog.Close><button className="button button-primary" disabled={busy}>{busy ? "Testing and discovering…" : "Test & fetch models"}</button></div>
      </form>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}
