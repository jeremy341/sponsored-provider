import { NavLink } from "react-router-dom";
import { CircleHelp, Gauge, LogOut } from "lucide-react";
import type { NavItem } from "./nav";
import { signOut } from "./nav";

interface SidebarProps {
  home: string;
  nav: NavItem[];
  userName: string | null;
  email: string | null;
  preview: boolean;
  collapsed: boolean;
}

export function Sidebar({ home, nav, userName, email, preview, collapsed }: SidebarProps) {
  return <aside className="sidebar" aria-label="Site">
    <a className="brand sidebar-brand" href={home}>
      <span className="brand-symbol"><Gauge size={16} aria-hidden="true" /></span>
      <span className="brand-word">provider<span className="brand-dot">.</span></span>
    </a>
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
