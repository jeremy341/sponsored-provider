import { useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { CircleHelp } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import type { NavItem } from "./nav";

const COLLAPSE_KEY = "provider.sidebar.collapsed";

function titleFor(pathname: string, nav: NavItem[], fallback: string): string {
  const match = [...nav]
    .sort((a, b) => b.path.length - a.path.length)
    .find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`));

  return match?.label ?? fallback;
}

interface AppShellProps {
  role: "developer" | "operator";
  nav: NavItem[];
  home: string;
  homeLabel: string;
  userName: string | null;
  email: string | null;
  preview: boolean;
  children: ReactNode;
}

export function AppShell({ role, nav, home, homeLabel, userName, email, preview, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });

  const title = titleFor(useLocation().pathname, nav, homeLabel);

  function toggleCollapse() {
    setCollapsed((previous) => {
      const next = !previous;

      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // Private browsing or disabled storage: collapse lasts for this session only.
      }

      return next;
    });
  }

  return <div className="app-frame app-shell" data-collapsed={collapsed ? "true" : "false"}>
    <a href="#main-content" className="skip-link">Skip to content</a>
    <Sidebar home={home} nav={nav} userName={userName} email={email} preview={preview} collapsed={collapsed} />
    <div className="shell-main">
      <TopBar title={title} role={role} nav={nav} userName={userName} preview={preview} collapsed={collapsed} onToggleCollapse={toggleCollapse} />
      <main id="main-content" className="main-content" tabIndex={-1}>
        {preview && <div className="preview-notice"><CircleHelp size={15} aria-hidden="true" /><span>Layout preview · portal data is not connected, so no usage, keys, or models are shown.</span></div>}
        {children}
        <footer className="page-footer"><span>Sponsored Provider</span><span>OpenAI-compatible gateway</span></footer>
      </main>
    </div>
  </div>;
}
