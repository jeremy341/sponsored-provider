export type LayoutPreviewRole = "developer" | "operator";

export function getLayoutPreviewRole(): LayoutPreviewRole | null {
  if (!import.meta.env.DEV) return null;

  const requestedRole = new URLSearchParams(window.location.search).get("preview");

  return requestedRole === "developer" || requestedRole === "operator" ? requestedRole : null;
}
