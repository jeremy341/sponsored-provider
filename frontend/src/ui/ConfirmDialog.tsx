import * as Dialog from "@radix-ui/react-dialog";

export interface ConfirmRequest {
  title: string;
  body: string;
  confirmLabel: string;
  destructive?: boolean;
}

interface ConfirmDialogProps {
  request: ConfirmRequest | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({ request, busy, onCancel, onConfirm }: ConfirmDialogProps) {
  return <Dialog.Root open={request != null} onOpenChange={(open) => { if (!open) onCancel(); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="dialog-overlay" />
      <Dialog.Content className="dialog-content" aria-describedby="confirm-dialog-description" onEscapeKeyDown={(event) => { if (busy) event.preventDefault(); }} onPointerDownOutside={(event) => { if (busy) event.preventDefault(); }}>
        <div className="dialog-title-row"><div>
          <Dialog.Title>{request?.title ?? "Confirm"}</Dialog.Title>
          <Dialog.Description id="confirm-dialog-description">{request?.body ?? ""}</Dialog.Description>
        </div></div>
        <div className="dialog-actions">
          <Dialog.Close asChild><button type="button" className="button button-quiet" disabled={busy}>Cancel</button></Dialog.Close>
          <button type="button" className={`button ${request?.destructive ? "button-destructive" : "button-primary"}`} disabled={busy} onClick={onConfirm}>{busy ? "Working…" : (request?.confirmLabel ?? "Confirm")}</button>
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
