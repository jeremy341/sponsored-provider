import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { api } from "../lib/api";
import { getLayoutPreviewRole } from "../lib/preview";
import { AuthPage } from "./AuthPage";
import { DeveloperHome } from "./developer/DeveloperHomePage";
import { KeysPage } from "./developer/KeysPage";
import { QuickstartPage } from "./developer/QuickstartPage";
import { ModelCatalogPage as ModelCatalogSurface } from "./developer/ModelCatalogPage";
import { ModelDetailPage } from "./developer/ModelDetailPage";
import { DeveloperActivityPage as DeveloperActivitySurface } from "./developer/DeveloperActivityPage";
import { DeveloperAnalyticsPage } from "./developer/DeveloperAnalyticsPage";
import { OperatorOverview } from "./operator/OperatorOverviewPage";
import { PeoplePage } from "./operator/PeoplePage";
import { GuardrailsPage } from "./operator/GuardrailsPage";
import { ProviderListPage as ProvidersSurface } from "./operator/providers/ProviderListPage";
import { ModelsPricingPage } from "./operator/models/ModelsPricingPage";
import { AuditLogPage } from "./operator/AuditLogPage";
import { OperatorUsagePage as OperatorUsageSurface } from "./operator/usage/OperatorUsagePage";
import { AppShell } from "./shell/AppShell";
import { developerNav, operatorNav } from "./shell/nav";
import { NavLink } from "react-router-dom";


type PortalRole = "developer" | "operator";

type SessionState =
  | { status: "loading" }
  | { status: "preview"; role: PortalRole }
  | { status: "ready"; role: PortalRole; displayName: string; email: string | null }
  | { status: "error"; message: string };

export function App() {
  return <BrowserRouter><PortalApp /></BrowserRouter>;
}

function PortalApp() {
  const location = useLocation();

  if (location.pathname === "/auth/login") return <AuthPage />;

  return <AuthenticatedPortal />;
}

function AuthenticatedPortal() {
  const session = usePortalSession();
  const location = useLocation();
  const requestedRole: PortalRole = location.pathname.startsWith("/operator") ? "operator" : "developer";
  const activeRole: PortalRole | null = session.status === "ready" || session.status === "preview" ? session.role : null;

  if (session.status === "loading") return <main className="session-screen" aria-live="polite"><div className="session-mark"><span className="brand-mark" aria-hidden="true" /> Sponsored Provider</div><p>Checking your session…</p></main>;

  if (session.status === "error") return <main className="session-screen"><div className="session-mark"><LockKeyhole size={18} aria-hidden="true" /> Sponsored Provider</div><h1>Sign-in required</h1><p>{session.message}</p><a className="button button-primary" href="/auth/login">Sign in <ArrowRight size={16} /></a></main>;

  // Redirect a signed-in (or previewing) role only when the path belongs to the
  // other portal's section; unknown paths fall through to the role's own 404.
  if (activeRole && requestedRole !== activeRole) {
    const otherSection = activeRole === "operator" ? "/developer" : "/operator";

    if (location.pathname.startsWith(otherSection)) {
      return <Navigate to={`${activeRole === "operator" ? "/operator" : "/developer"}${session.status === "preview" ? location.search : ""}`} replace />;
    }
  }

  const role = activeRole ?? requestedRole;

  return <PortalShell key={role} role={role} preview={session.status === "preview"} userName={session.status === "ready" ? session.displayName : null} email={session.status === "ready" ? session.email : null} />;
}

function PortalShell({ role, preview, userName, email }: { role: PortalRole; preview: boolean; userName: string | null; email: string | null }) {
  const nav = role === "operator" ? operatorNav : developerNav;
  const home = role === "operator" ? "/operator" : "/developer";
  const homeLabel = role === "operator" ? "Overview" : "Home";

  return <AppShell role={role} nav={nav} home={home} homeLabel={homeLabel} userName={userName} email={email} preview={preview}>
    <Routes>
      <Route path="/" element={<Navigate to={home} replace />} />
      <Route path="/developer" element={<DeveloperHome />} />
      <Route path="/developer/keys" element={<KeysPage />} />
      <Route path="/developer/models" element={<ModelCatalogSurface portalApi={api} />} />
      <Route path="/developer/models/*" element={<ModelDetailPage portalApi={api} />} />
      <Route path="/developer/activity" element={<DeveloperActivitySurface portalApi={api} />} />
      <Route path="/developer/analytics" element={<DeveloperAnalyticsPage />} />
      <Route path="/developer/quickstart" element={<QuickstartPage />} />
      <Route path="/operator" element={<OperatorOverview />} />
      <Route path="/operator/people" element={<PeoplePage />} />
      <Route path="/operator/providers" element={<ProvidersSurface portalApi={api} />} />
      <Route path="/operator/models" element={<ModelsPricingPage portalApi={api} />} />
      <Route path="/operator/usage" element={<OperatorUsageSurface portalApi={api} />} />
      <Route path="/operator/guardrails" element={<GuardrailsPage />} />
      <Route path="/operator/audit" element={<AuditLogPage />} />
      <Route path="*" element={<NotFound home={home} homeLabel={homeLabel} />} />
    </Routes>
  </AppShell>;
}

function NotFound({ home, homeLabel }: { home: string; homeLabel: string }) {
  return <section className="section-block notfound-block">
    <header className="page-header"><div><h1>Page not found</h1><p>That page isn’t part of this portal.</p></div></header>
    <NavLink className="button button-secondary" to={home}>Go to {homeLabel.toLowerCase()} <ArrowRight size={15} /></NavLink>
  </section>;
}

function usePortalSession(): SessionState {
  const [session, setSession] = useState<SessionState>({ status: "loading" });
  const location = useLocation();

  useEffect(() => {
    let current = true;

    const previewRole = getLayoutPreviewRole();

    if (previewRole) {
      setSession({ status: "preview", role: previewRole });

      return () => { current = false; };
    }

    api.getSession().then((result) => {
      if (current) setSession({ status: "ready", role: result.role, displayName: result.user.displayName, email: result.user.email });
    }).catch(() => {
      if (!current) return;

      setSession({ status: "error", message: "Could not load your account session. Check portal setup, sign in again, or contact the operator." });
    });

    return () => { current = false; };
  }, [location.search]);

  return session;
}
