import React from "react";
import {
  LayoutDashboard,
  Users,
  GitMerge,
  History,
  ShieldAlert,
  Key,
  Box,
  CheckSquare,
  FileText,
  BarChart3,
  Activity,
} from "./Icons";
import { NavItemConfig } from "../../types";

export const NAV_CONFIG: NavItemConfig[] = [
  { id: "overview", label: "Overview", iconName: "LayoutDashboard", path: "/" },
  { id: "agents", label: "Agents", iconName: "Users", path: "/agents" },
  { id: "workflows", label: "Workflows", iconName: "GitMerge", path: "/workflows", badgeKey: "runningWorkflows" },
  { id: "checkpoints", label: "Checkpoints & Recovery", iconName: "History", path: "/checkpoints" },
  { id: "risk", label: "Risk Engine", iconName: "ShieldAlert", path: "/risk" },
  { id: "permissions", label: "Tool Permissions", iconName: "Key", path: "/permissions" },
  { id: "sandbox", label: "Sandbox", iconName: "Box", path: "/sandbox" },
  { id: "approvals", label: "Human Approvals", iconName: "CheckSquare", path: "/approvals", badgeKey: "pendingApprovals" },
  { id: "audit", label: "Audit & Traces", iconName: "FileText", path: "/audit" },
  { id: "evaluation", label: "Evaluation", iconName: "BarChart3", path: "/evaluation" },
];

const ICON_MAP: Record<string, React.ReactNode> = {
  LayoutDashboard: <LayoutDashboard size={18} />,
  Users: <Users size={18} />,
  GitMerge: <GitMerge size={18} />,
  History: <History size={18} />,
  ShieldAlert: <ShieldAlert size={18} />,
  Key: <Key size={18} />,
  Box: <Box size={18} />,
  CheckSquare: <CheckSquare size={18} />,
  FileText: <FileText size={18} />,
  BarChart3: <BarChart3 size={18} />,
};

interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  badges?: Record<string, number>;
  systemStatus?: "healthy" | "degraded" | "warning" | "failed";
  versionString?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath,
  onNavigate,
  badges = {},
  systemStatus = "healthy",
  versionString = "v0.1.0-prod",
}) => {
  return (
    <aside className="sidebar">
      {/* Brand / Logo */}
      <div className="sidebar-brand">
        <div className="brand-logo font-mono">
          <Activity className="brand-icon" size={22} />
          <span>AF</span>
        </div>
        <div className="brand-info">
          <h1 className="brand-title">AgentFlow</h1>
          <span className="brand-subtitle">Reliability Control Plane</span>
        </div>
      </div>

      {/* Navigation items rendered dynamically from NAV_CONFIG */}
      <nav className="sidebar-nav">
        {NAV_CONFIG.map((item) => {
          const isActive = currentPath === item.path;
          const badgeValue = item.badgeKey ? badges[item.badgeKey] : undefined;

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.path)}
              className={`nav-item ${isActive ? "active" : ""}`}
            >
              <span className="nav-icon">{ICON_MAP[item.iconName]}</span>
              <span className="nav-label">{item.label}</span>
              {badgeValue !== undefined && badgeValue > 0 && (
                <span className="nav-badge font-mono">{badgeValue}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div className="sidebar-footer">
        <div className="system-status-indicator">
          <span className={`status-dot ${systemStatus}`} />
          <span className="status-label">
            System {systemStatus.toUpperCase()}
          </span>
        </div>
        <div className="build-version font-mono">{versionString}</div>
      </div>
    </aside>
  );
};
