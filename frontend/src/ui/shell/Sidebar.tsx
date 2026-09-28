import { NavLink } from "react-router-dom";
import { CircleHelp, LogOut } from "lucide-react";
import { signOut, type NavItem } from "./nav";

interface SidebarProps {
  home: string;
  nav: NavItem[];
  role: "developer" | "operator";
  userName: string | null;
  email: string | null;
  preview: boolean;
  collapsed: boolean;
}

export function Sidebar({ home, nav, role, userName, email, preview, collapsed }: SidebarProps) {
  return <aside className="sidebar" aria-label="Site">
    <a className="brand sidebar-brand" href={home} aria-label="Sponsored Provider console home">
      <span className="brand-mark" aria-hidden="true" />
      <span className="brand-word">sponsored<span className="brand-dot">_</span>provider</span>
    </a>
    <span className="portal-label" aria-hidden="true">{role === "operator" ? "Operator console" : "Developer console"}</span>
    <nav id="primary-nav" className="sidebar-nav" aria-label="Primary navigation">
      {nav.map((item) => <NavLink key={item.path} to={item.path} end={item.end} className={({ isActive }) => `nav-link${isActive ? " is-active" : ""}`} title={collapsed ? item.label : undefined}>
        <item.icon size={16} strokeWidth={1.75} aria-hidden="true" /><span>{item.label}</span>
      </NavLink>)}
    </nav>
    <div className="sidebar-footer">
      <span className="account-avatar" aria-hidden="true">{userName ? userName.slice(0, 1).toUpperCase() : "P"}</span>
      <span className="account-copy"><strong>{userName ?? "Layout preview"}</strong><small>{preview ? "No account data" : (email ?? "Signed in")}</small></span>
      {preview
        ? <CircleHelp size={16} aria-label="Preview only" />
        : <button className="icon-button" type="button" aria-label="Sign out" onClick={signOut}><LogOut size={16} aria-hidden="true" /></button>}
    </div>
  </aside>;
}
