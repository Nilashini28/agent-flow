import React from "react";
import { SandboxRunItem } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { Box, Cpu, HardDrive, Terminal } from "../common/Icons";

interface SandboxPageProps {
  runs: SandboxRunItem[] | null;
  isLoading: boolean;
}

const STAGES = ["Created", "Running", "Executing", "Completed", "Destroyed"];

export const SandboxPage: React.FC<SandboxPageProps> = ({ runs, isLoading }) => {
  if (isLoading && !runs) {
    return (
      <div className="page-container">
        <PageHeader
          title="Sandbox Execution Environment"
          description="Isolated subprocess and Docker container runtime policy enforcement."
        />
        <LoadingSkeleton height="220px" count={2} />
      </div>
    );
  }

  const hasRuns = runs !== null && runs.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Sandbox Execution Environment"
        description="Isolated subprocess and Docker container runtime policy enforcement."
        meta={
          <span className="font-mono text-xs text-muted">
            {hasRuns ? `${runs.length} Active Container Subprocesses` : "0 Runs"}
          </span>
        }
      />

      {!hasRuns ? (
        <EmptyState
          title="No Sandbox Executions"
          description="No tools have executed inside isolated sandbox containers."
          icon={<Box size={36} />}
        />
      ) : (
        <div className="flex flex-col gap-6">
          {runs.map((run) => {
            const currentStageIdx = STAGES.indexOf(run.lifecycleStage) !== -1
              ? STAGES.indexOf(run.lifecycleStage)
              : 3;

            return (
              <div key={run.id} className="panel sandbox-run-card">
                <div className="panel-header">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-semibold text-primary">{run.id}</span>
                    <span className="font-mono text-xs text-muted">Tool: {run.toolName}</span>
                    <span className="font-mono text-xs text-muted">Workflow: {run.workflowId.slice(0, 8)}</span>
                  </div>
                  <StatusPill status={run.status} />
                </div>

                <div className="panel-body">
                  {/* Lifecycle Stepper */}
                  <div className="lifecycle-stepper mb-4">
                    {STAGES.map((stage, idx) => {
                      const isPast = idx <= currentStageIdx;
                      const isCurrent = idx === currentStageIdx;

                      return (
                        <div key={stage} className="lifecycle-item flex-1">
                          <div className={`lifecycle-dot ${isCurrent ? "current" : isPast ? "completed" : ""}`} />
                          <span className="lifecycle-label font-mono text-xs mt-1">{stage}</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Resource & Runtime Specs */}
                  <div className="grid-4 gap-4 p-3 bg-card-dark rounded-md mb-4 font-mono text-xs">
                    <div>
                      <span className="text-muted block">Image:</span>
                      <span className="text-primary">{run.runtimeImage}</span>
                    </div>
                    <div>
                      <span className="text-muted block">CPU / Mem:</span>
                      <span>{run.cpu} / {run.memory}</span>
                    </div>
                    <div>
                      <span className="text-muted block">Network / Secrets:</span>
                      <span>{run.network} / {run.secrets}</span>
                    </div>
                    <div>
                      <span className="text-muted block">Elapsed / Exit Code:</span>
                      <span>{run.elapsedMs}ms (code {run.exitCode})</span>
                    </div>
                  </div>

                  {/* Log Block */}
                  <div className="log-block bg-near-black p-3 rounded-md border border-border">
                    <div className="flex items-center gap-2 mb-2 text-xs font-mono text-muted">
                      <Terminal size={14} />
                      <span>Subprocess Terminal Logs</span>
                    </div>
                    <div className="font-mono text-xs text-muted space-y-1">
                      {run.logs && run.logs.map((line, idx) => (
                        <div key={idx} className="log-line">{line}</div>
                      ))}
                    </div>
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
