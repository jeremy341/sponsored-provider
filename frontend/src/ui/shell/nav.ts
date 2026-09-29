import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Boxes,
  ChartNoAxesColumn,
  KeyRound,
  LayoutDashboard,
  MessageSquareCode,
  MonitorCog,
  Network,
  ScrollText,
  Settings,
  Shield,
  Ticket,
  Users,
} from "lucide-react";
import { api } from "../../lib/api";

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export const developerNav: NavItem[] = [
  { path: "/developer", label: "Overview", icon: LayoutDashboard, end: true },
  { path: "/developer/models", label: "Models", icon: Boxes },
  { path: "/developer/playground", label: "Playground", icon: MessageSquareCode },
  { path: "/developer/activity", label: "Activity", icon: Activity },
  { path: "/developer/logs", label: "Logs", icon: ScrollText },
  { path: "/developer/analytics", label: "Usage", icon: ChartNoAxesColumn },
  { path: "/developer/providers", label: "Providers", icon: Network },
  { path: "/developer/keys", label: "API Keys", icon: KeyRound },
  { path: "/developer/settings", label: "Settings", icon: Settings },
];

export const operatorNav: NavItem[] = [
  { path: "/operator", label: "Overview", icon: LayoutDashboard, end: true },
  { path: "/operator/people", label: "Users", icon: Users },
  { path: "/operator/invites", label: "Invites", icon: Ticket },
  { path: "/operator/providers", label: "Providers", icon: Network },
  { path: "/operator/models", label: "Models", icon: Boxes },
  { path: "/operator/usage", label: "Usage", icon: ChartNoAxesColumn },
  { path: "/operator/requests", label: "Requests", icon: ScrollText },
  { path: "/operator/guardrails", label: "Guardrails", icon: Shield },
  { path: "/operator/system", label: "System", icon: MonitorCog },
  { path: "/operator/settings", label: "Settings", icon: Settings },
];

export function isPortalRole(value: string): value is "developer" | "operator" {
  return value === "developer" || value === "operator";
}

export function signOut(): void {
  void api.logout().then(() => window.location.assign("/")).catch(() => window.location.reload());
}
