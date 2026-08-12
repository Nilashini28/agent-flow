import React, { useState } from "react";
import { WorkflowItem, WorkflowCheckpointDetail } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatCard } from "../common/StatCard";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { History, Zap, CheckCircle2, RotateCcw, ShieldCheck, Code } from "../common/Icons";

interface CheckpointsPageProps {
  workflows: WorkflowItem[] | null;
  selectedDetail: WorkflowCheckpointDetail | null;
  isLoading: boolean;
  onSelectWorkflow: (id: string) => void;
  onSimulateFailure: (workflowId: string, failureType: string) => void;
}

const FAILURE_TYPES = [
  { id: "process_kill", label: "Hard Process Kill (SIGKILL)" },
  { id: "network_timeout", label: "Sandbox Network Timeout" },
  { id: "out_of_memory", label: "Sandbox Memory Limit Exceeded" },
  { id: "unhandled_exception", label: "Unhandled Node Exception" },
];

export const CheckpointsPage: React.FC<CheckpointsPageProps> = ({
  workflows,
  selectedDetail,
  isLoading,
  onSelectWorkflow,
  onSimulateFailure,
}) => {
  const [selectedWfId, setSelectedWfId] = useState<string>(
    workflows && workflows.length > 0 ? workflows[0].id : ""
  );
  const [selectedFailure, setSelectedFailure] = useState(FAILURE_TYPES[0].id);

  const handleSelectWf = (id: string) => {
    setSelectedWfId(id);
    onSelectWorkflow(id);
  };

  const handleSimulate = () => {
    if (selectedWfId) {
      onSimulateFailure(selectedWfId, selectedFailure);
    }
  };

  if (isLoading && !selectedDetail) {
    return (
      <div className="page-container">
        <PageHeader
          title="Checkpoints & Crash Recovery"
          description="Every node transition is persisted to disk. Zero work lost on process restart."
        />
        <LoadingSkeleton height="200px" count={2} />
      </div>
    );
  }

  const hasDetail = selectedDetail !== null;

  return (
    <div className="page-container">
      <PageHeader
        title="Checkpoints & Crash Recovery"
        description="Every node transition is persisted to disk. Zero work lost on process restart."
      />

      {/* Control Bar: Selector + Failure Injection */}
      <div className="panel mb-6">
        <div className="panel-body flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            <label className="text-xs font-mono text-muted">Select Workflow:</label>
            <select
              className="select-input font-mono flex-1"
              value={selectedWfId}
              onChange={(e) => handleSelectWf(e.target.value)}
            >
              {workflows && workflows.length > 0 ? (
                workflows.map((wf) => (
                  <option key={wf.id} value={wf.id}>
                    {wf.id.slice(0, 12)}... — {wf.task} ({wf.status})
                  </option>
                ))
              ) : (
                <option value="">No workflows available</option>
              )}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <select
              className="select-input font-mono"
              value={selectedFailure}
              onChange={(e) => setSelectedFailure(e.target.value)}
            >
              {FAILURE_TYPES.map((ft) => (
                <option key={ft.id} value={ft.id}>
                  {ft.label}
                </option>
              ))}
            </select>

            <button
              className="btn btn-danger"
              disabled={!selectedWfId}
              onClick={handleSimulate}
            >
              <Zap size={14} />
              <span>Simulate Failure</span>
            </button>
          </div>
        </div>
      </div>

      {/* Stat Row */}
      <div className="stats-grid grid-5 mb-6">
        <StatCard
          label="Checkpoints Count"
          value={hasDetail ? selectedDetail.checkpointsCount : null}
          icon={<History size={16} />}
        />
        <StatCard
          label="Steps Executed"
          value={hasDetail ? selectedDetail.stepsExecuted : null}
          icon={<CheckCircle2 size={16} />}
          variant="success"
        />
        <StatCard
          label="Steps Replayed"
          value={hasDetail ? selectedDetail.stepsReplayed : null}
          icon={<RotateCcw size={16} />}
          variant="primary"
        />
        <StatCard
          label="Steps Avoided"
          value={hasDetail ? selectedDetail.stepsAvoided : null}
          icon={<ShieldCheck size={16} />}
          variant="success"
        />
        <StatCard
          label="Recovery Latency"
          value={hasDetail ? `${selectedDetail.recoveryLatencyMs} ms` : null}
          icon={<Zap size={16} />}
        />
      </div>

      {/* 2-Column Split: Timeline Stepper & Checkpoint Store */}
      <div className="grid-2 gap-6">
        {/* Timeline Stepper */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Execution Timeline Stepper</h3>
            <span className="text-xs text-muted font-mono">
              {hasDetail ? `${selectedDetail.steps.length} Steps` : "0 Steps"}
            </span>
          </div>
          <div className="panel-body">
            {hasDetail && selectedDetail.steps.length > 0 ? (
              <div className="timeline-stepper">
                {selectedDetail.steps.map((step, idx) => (
                  <div key={idx} className="stepper-item">
                    <div className="stepper-left">
                      <div className="stepper-badge font-mono">{step.index}</div>
                      {idx < selectedDetail.steps.length - 1 && (
                        <div className="stepper-line" />
                      )}
                    </div>
                    <div className="stepper-content">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm font-semibold">{step.name}</span>
                        <StatusPill status={step.status} size="sm" />
                      </div>
                      {step.toolName && (
                        <span className="text-xs font-mono text-primary mt-1 block">
                          Tool: {step.toolName}
                        </span>
                      )}
                      <span className="text-xs font-mono text-muted mt-1 block">
                        {step.checkpointId ? `Checkpoint: ${step.checkpointId}` : "No checkpoint"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No Steps Found" description="Select a workflow to inspect timeline." />
            )}
          </div>
        </div>

        {/* Checkpoint Store Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Checkpoint Store State</h3>
            <span className="text-xs text-muted font-mono">SQLite / Postgres Storage</span>
          </div>
          <div className="panel-body">
            {hasDetail && selectedDetail.checkpoints.length > 0 ? (
              <div className="checkpoint-list">
                {selectedDetail.checkpoints.map((chk) => (
                  <div key={chk.id} className="checkpoint-card">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs text-primary">{chk.id}</span>
                      <span className="font-mono text-xs text-muted">{chk.sizeKb} KB</span>
                    </div>
                    <div className="text-xs font-mono mb-2">{chk.stepLabel}</div>
                    <div className="json-preview-box">
                      <Code size={12} className="inline mr-1 text-muted" />
                      <pre className="font-mono text-xs">{chk.payloadPreview}</pre>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No Checkpoints Stored" description="No state checkpoints written." />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
