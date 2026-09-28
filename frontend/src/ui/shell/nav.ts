import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Boxes,
  ChartNoAxesColumn,
  Code2,
  KeyRound,
  LayoutDashboard,
  Network,
  ScrollText,
  Shield,
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
  { path: "/developer", label: "Home", icon: LayoutDashboard, end: true },
  { path: "/developer/keys", label: "API keys", icon: KeyRound },
  { path: "/developer/models", label: "Models", icon: Boxes },
  { path: "/developer/activity", label: "Activity", icon: Activity },
  { path: "/developer/analytics", label: "Analytics", icon: ChartNoAxesColumn },
  { path: "/developer/quickstart", label: "Quickstart", icon: Code2 },
];

export const operatorNav: NavItem[] = [
  { path: "/operator", label: "Overview", icon: LayoutDashboard, end: true },
  { path: "/operator/people", label: "People & keys", icon: Users },
  { path: "/operator/providers", label: "Providers", icon: Network },
  { path: "/operator/models", label: "Models & pricing", icon: Boxes },
  { path: "/operator/usage", label: "Usage", icon: ChartNoAxesColumn },
  { path: "/operator/guardrails", label: "Guardrails", icon: Shield },
  { path: "/operator/audit", label: "Audit log", icon: ScrollText },
];

export function isPortalRole(value: string): value is "developer" | "operator" {
  return value === "developer" || value === "operator";
}

export function signOut(): void {
  void api.logout().then(() => window.location.assign("/")).catch(() => window.location.reload());
}
