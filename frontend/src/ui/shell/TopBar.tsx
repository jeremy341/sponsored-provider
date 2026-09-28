import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { ChevronDown, CircleHelp, LogOut, Menu, PanelLeft, X } from "lucide-react";
import { AllowancePill } from "./AllowancePill";
import { isPortalRole, signOut, type NavItem } from "./nav";

interface TopBarProps {
  title: string;
  role: "developer" | "operator";
  nav: NavItem[];
  userName: string | null;
  preview: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function TopBar({ title, role, nav, userName, preview, collapsed, onToggleCollapse }: TopBarProps) {
  const navigate = useNavigate();
  const path = useLocation().pathname;
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => setSheetOpen(false), [path]);

  function switchRole(event: React.ChangeEvent<HTMLSelectElement>) {
    const target = event.currentTarget.value;

    if (!isPortalRole(target)) return;
    navigate(target === "operator" ? "/operator?preview=operator" : "/developer?preview=developer");
  }

  return <header className="command-bar">
    <button type="button" className="icon-button command-collapse" aria-pressed={collapsed} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} onClick={onToggleCollapse}>
      <PanelLeft size={16} aria-hidden="true" />
    </button>
    {preview && <div className="portal-select-wrap command-workspace"><label className="sr-only" htmlFor="command-portal">Preview workspace</label><select id="command-portal" value={role} onChange={switchRole} aria-label="Preview workspace role"><option value="developer">Developer portal</option><option value="operator">Operator portal</option></select><ChevronDown size={14} aria-hidden="true" /></div>}
    <Dialog.Root open={sheetOpen} onOpenChange={setSheetOpen}>
      <Dialog.Trigger asChild>
        <button type="button" className="icon-button command-menu" aria-label="Open navigation"><Menu size={18} aria-hidden="true" /></button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="mobile-nav-sheet">
          <div className="sheet-heading"><Dialog.Title>Navigation</Dialog.Title><Dialog.Close asChild><button className="icon-button" aria-label="Close navigation"><X size={18} aria-hidden="true" /></button></Dialog.Close></div>
          {preview && <><label className="portal-label" htmlFor="mobile-portal">Workspace</label><div className="portal-select-wrap"><select id="mobile-portal" value={role} onChange={switchRole} aria-label="Choose portal"><option value="developer">Developer portal</option><option value="operator">Operator portal</option></select><ChevronDown size={14} aria-hidden="true" /></div></>}
          <nav className="sheet-nav">{nav.map((item) => <NavLink key={item.path} to={item.path} end={item.end} className={({ isActive }) => `nav-link${isActive ? " is-active" : ""}`}><item.icon size={17} aria-hidden="true" /><span>{item.label}</span></NavLink>)}</nav>
          <Dialog.Description className="muted-copy">{preview ? "Layout preview only. No account data is loaded." : `Signed in as ${userName ?? "your account"}.`}</Dialog.Description>
          {!preview && <button className="button button-quiet mobile-signout" type="button" onClick={signOut}><LogOut size={16} aria-hidden="true" /> Sign out</button>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
    <span className="command-title">{title}</span>
    <span className="command-spacer" aria-hidden="true" />
    {preview
      ? <span className="allowance-pill" role="status" aria-label="Layout preview"><CircleHelp size={15} aria-hidden="true" /><strong>···</strong></span>
      : <AllowancePill role={role} />}
  </header>;
}
