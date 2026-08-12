import React, { useState } from "react";
import { ToolPermissionItem } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { Key, Shield, Network, RefreshCw } from "../common/Icons";

interface PermissionsPageProps {
  tools: ToolPermissionItem[] | null;
  isLoading: boolean;
  onUpdatePolicy: (toolName: string, policy: string) => void;
}

export const PermissionsPage: React.FC<PermissionsPageProps> = ({
  tools,
  isLoading,
  onUpdatePolicy,
}) => {
  const [localPolicies, setLocalPolicies] = useState<Record<string, string>>({});

  const handleSegmentChange = (toolName: string, policy: string) => {
    setLocalPolicies((prev) => ({ ...prev, [toolName]: policy }));
    onUpdatePolicy(toolName, policy);
  };

  if (isLoading && !tools) {
    return (
      <div className="page-container">
        <PageHeader
          title="Tool Permissions & Sandbox Policy"
          description="Control tool execution boundaries, network isolation, and approval requirements."
        />
        <LoadingSkeleton height="120px" count={3} />
      </div>
    );
  }

  const hasTools = tools !== null && tools.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Tool Permissions & Sandbox Policy"
        description="Control tool execution boundaries, network isolation, and approval requirements."
        meta={
          <span className="font-mono text-xs text-muted">
            {hasTools ? `${tools.length} Registered Tools` : "0 Tools"}
          </span>
        }
      />

      {!hasTools ? (
        <EmptyState
          title="No Tools Registered"
          description="No tool definitions were loaded from backend registry."
          icon={<Key size={32} />}
        />
      ) : (
        <div className="tool-permissions-list flex flex-col gap-4">
          {tools.map((tool) => {
            const activePolicy =
              localPolicies[tool.name] || tool.currentPolicy || "allow";

            return (
              <div key={tool.name} className="panel tool-permission-row">
                <div className="panel-body flex items-center justify-between gap-4">
                  <div className="tool-info flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-mono font-semibold text-sm">{tool.name}</h4>
                      <StatusPill status={tool.risk_tier} label={`${tool.risk_tier} risk`} size="sm" />
                    </div>
                    <p className="text-xs text-muted mb-2">{tool.description}</p>

                    <div className="flex items-center gap-3 text-xs font-mono text-muted">
                      <span>
                        <RefreshCw size={12} className="inline mr-1" />
                        {tool.reversible ? "Reversible" : "Irreversible"}
                      </span>
                      <span>
                        <Network size={12} className="inline mr-1" />
                        {tool.allow_network ? "Network Enabled" : "Network Blocked"}
                      </span>
                    </div>
                  </div>

                  {/* Segmented Control (Allow / Approval / Deny) */}
                  <div className="segmented-control">
                    <button
                      className={`segment-btn ${activePolicy === "allow" ? "active allow" : ""}`}
                      onClick={() => handleSegmentChange(tool.name, "allow")}
                    >
                      Allow
                    </button>
                    <button
                      className={`segment-btn ${activePolicy === "approval" ? "active approval" : ""}`}
                      onClick={() => handleSegmentChange(tool.name, "approval")}
                    >
                      Approval
                    </button>
                    <button
                      className={`segment-btn ${activePolicy === "deny" ? "active deny" : ""}`}
                      onClick={() => handleSegmentChange(tool.name, "deny")}
                    >
                      Deny
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
