import React from "react";
import { Play, Sparkles } from "./Icons";

interface TopBarProps {
  tagline?: string;
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
  onNewWorkflow?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  tagline = "Reliable Runtime for Autonomous AI · Recoverable. Governed. Observable.",
  isDemoMode,
  onToggleDemoMode,
  onNewWorkflow,
}) => {
  return (
    <header className="topbar">
      <div className="topbar-tagline font-mono">{tagline}</div>

      <div className="topbar-controls">
        {onNewWorkflow && (
          <button className="btn btn-primary" onClick={onNewWorkflow}>
            <Play size={14} />
            <span>Launch Workflow</span>
          </button>
        )}

        <button
          onClick={onToggleDemoMode}
          className={`demo-toggle-btn ${isDemoMode ? "active" : ""}`}
        >
          <Sparkles size={14} />
          <span>Demo Mode: {isDemoMode ? "ON" : "OFF"}</span>
        </button>
      </div>
    </header>
  );
};
