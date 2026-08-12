import React from "react";
import { AgentItem } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { Users, Shield, Cpu, Wrench } from "../common/Icons";

interface AgentsPageProps {
  agents: AgentItem[] | null;
  isLoading: boolean;
}

export const AgentsPage: React.FC<AgentsPageProps> = ({ agents, isLoading }) => {
  if (isLoading) {
    return (
      <div className="page-container">
        <PageHeader
          title="Agents Registry"
          description="Autonomous AI agents governed by AgentFlow control plane."
        />
        <LoadingSkeleton height="180px" count={3} className="mb-4" />
      </div>
    );
  }

  const hasAgents = agents !== null && agents.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Agents Registry"
        description="Autonomous AI agents governed by AgentFlow control plane."
        meta={
          <span className="font-mono text-xs text-muted">
            {hasAgents ? `${agents.length} Agents Registered` : "0 Agents"}
          </span>
        }
      />

      {!hasAgents ? (
        <EmptyState
          title="No Registered Agents"
          description="No autonomous agents have registered with the control plane."
          icon={<Users size={36} />}
        />
      ) : (
        <div className="grid-2 gap-6">
          {agents.map((agent) => (
            <div key={agent.id} className="agent-card panel">
              <div className="agent-card-header">
                <div>
                  <h3 className="agent-name">{agent.name}</h3>
                  <span className="agent-id font-mono text-xs text-muted">{agent.id}</span>
                </div>
                <StatusPill status={agent.status} />
              </div>

              <div className="agent-card-body">
                <div className="agent-meta-row">
                  <span className="meta-label">
                    <Cpu size={14} /> Model:
                  </span>
                  <span className="meta-value font-mono">{agent.model}</span>
                </div>

                <div className="agent-meta-row">
                  <span className="meta-label">
                    <Shield size={14} /> Risk Policy:
                  </span>
                  <span className="meta-value font-mono text-primary">
                    {agent.assignedRiskPolicy}
                  </span>
                </div>

                <div className="agent-stats-grid grid-4 mt-3">
                  <div className="stat-mini">
                    <span className="stat-mini-label">Tools</span>
                    <span className="stat-mini-val font-mono">{agent.toolCount}</span>
                  </div>
                  <div className="stat-mini">
                    <span className="stat-mini-label">Workflows</span>
                    <span className="stat-mini-val font-mono">{agent.workflowCount}</span>
                  </div>
                  <div className="stat-mini">
                    <span className="stat-mini-label">Active Now</span>
                    <span className="stat-mini-val font-mono">{agent.activeNowCount}</span>
                  </div>
                  <div className="stat-mini">
                    <span className="stat-mini-label">Success Rate</span>
                    <span className="stat-mini-val font-mono text-success">
                      {(agent.successRate * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <div className="agent-tools-chips mt-4">
                  <span className="text-xs text-muted font-mono mb-2 block">
                    <Wrench size={12} className="inline mr-1" /> Assigned Tools:
                  </span>
                  <div className="chips-wrapper">
                    {agent.tools && agent.tools.map((toolName, idx) => (
                      <span key={idx} className="tool-chip font-mono">
                        {toolName}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
