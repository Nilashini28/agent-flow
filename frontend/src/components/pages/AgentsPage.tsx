import React, { useEffect, useState } from "react";
import { AgentItem, EngineItem } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { Users, Shield, Cpu, Wrench, Info, CheckCircle } from "../common/Icons";
import { api } from "../../api/client";

interface AgentsPageProps {
  agents: AgentItem[] | null;
  isLoading: boolean;
}

export const AgentsPage: React.FC<AgentsPageProps> = ({ agents, isLoading }) => {
  const [engines, setEngines] = useState<EngineItem[] | null>(null);

  useEffect(() => {
    api.getEngines().then(setEngines).catch(() => setEngines([]));
  }, []);

  if (isLoading) {
    return (
      <div className="page-container">
        <PageHeader
          title="Agents Registry & Integration"
          description="Autonomous AI agents and execution engines governed by AgentFlow control plane."
        />
        <LoadingSkeleton height="180px" count={3} className="mb-4" />
      </div>
    );
  }

  const hasAgents = agents !== null && agents.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Agents Registry & Integration"
        description="Autonomous AI agents and execution engines governed by AgentFlow control plane."
        meta={
          <span className="font-mono text-xs text-muted">
            {hasAgents ? `${agents.length} Agents Registered` : "0 Agents"}
          </span>
        }
      />

      {/* Info Panel: How to plug in a new agent */}
      <div className="panel p-4 mb-6 border-l-4 border-l-primary bg-near-black">
        <div className="flex items-start gap-3">
          <Info size={20} className="text-primary shrink-0 mt-0.5" />
          <div className="text-sm">
            <h4 className="font-semibold text-white mb-1">
              Plugging in an Autonomous Agent Engine
            </h4>
            <p className="text-muted text-xs leading-relaxed">
              AgentFlow works with any agent framework that implements our step-based execution contract.
              Adding a new engine requires no changes to checkpointing, sandboxing, or risk scoring.
            </p>
          </div>
        </div>
      </div>

      {/* Registered Execution Engines Cards */}
      {engines && engines.length > 0 && (
        <div className="mb-8">
          <h3 className="panel-title mb-3 text-sm text-muted font-mono uppercase tracking-wider">
            Registered Execution Engine Adapters
          </h3>
          <div className="grid-2 gap-6">
            {engines.map((eng) => (
              <div key={eng.id} className="panel p-5">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-base text-white">{eng.label}</h4>
                  <span className="badge badge-success text-xs font-mono flex items-center gap-1">
                    <CheckCircle size={12} /> Inherits Governance
                  </span>
                </div>
                <p className="text-xs text-muted mb-3">{eng.description}</p>
                <div className="text-xs font-mono text-primary bg-black/40 p-2.5 rounded border border-border">
                  <span className="text-muted block text-[10px] uppercase">Execution Pattern:</span>
                  {eng.executionPattern}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agents Cards */}
      <h3 className="panel-title mb-3 text-sm text-muted font-mono uppercase tracking-wider">
        Active Governed Agents
      </h3>
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
