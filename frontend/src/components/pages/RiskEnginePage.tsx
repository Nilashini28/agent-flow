import React, { useState } from "react";
import { RiskConfig, RiskEvaluation } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { ShieldAlert, Sliders, Play, Save } from "../common/Icons";

interface RiskEnginePageProps {
  config: RiskConfig | null;
  evaluation: RiskEvaluation | null;
  isLoading: boolean;
  onEvaluate: (data: { tool_name: string; step_index: number; has_error: boolean; retry_count: number }) => void;
  onUpdateThresholds: (data: { escalation_continue_max: number; escalation_approve_max: number }) => void;
}

export const RiskEnginePage: React.FC<RiskEnginePageProps> = ({
  config,
  evaluation,
  isLoading,
  onEvaluate,
  onUpdateThresholds,
}) => {
  const [selectedTool, setSelectedTool] = useState("file_write");
  const [stepIndex, setStepIndex] = useState(1);
  const [hasError, setHasError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const [continueMax, setContinueMax] = useState(
    config ? config.escalation_continue_max : 0.35
  );
  const [approveMax, setApproveMax] = useState(
    config ? config.escalation_approve_max : 0.70
  );

  const handleTestEvaluate = () => {
    onEvaluate({
      tool_name: selectedTool,
      step_index: stepIndex,
      has_error: hasError,
      retry_count: retryCount,
    });
  };

  const handleSaveThresholds = () => {
    onUpdateThresholds({
      escalation_continue_max: continueMax,
      escalation_approve_max: approveMax,
    });
  };

  if (isLoading && !evaluation) {
    return (
      <div className="page-container">
        <PageHeader
          title="Risk Engine & Governance Policy"
          description="Evaluate composite risk scores, factor weightings, and escalation boundaries."
        />
        <LoadingSkeleton height="240px" count={2} />
      </div>
    );
  }

  const hasEval = evaluation !== null;
  const scorePct = hasEval ? Math.min(100, Math.round(evaluation.compositeScore * 100)) : 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Risk Engine & Governance Policy"
        description="Evaluate composite risk scores, factor weightings, and escalation boundaries."
      />

      <div className="grid-2 gap-6 mb-6">
        {/* Decision Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Evaluated Decision Outcome</h3>
            <span className="text-xs text-muted font-mono">Live Evaluator</span>
          </div>
          <div className="panel-body">
            {hasEval ? (
              <div className="flex flex-col items-center justify-center p-4">
                {/* Circular Gauge */}
                <div className="gauge-container mb-4">
                  <svg className="gauge-svg" viewBox="0 0 100 100">
                    <circle className="gauge-bg" cx="50" cy="50" r="40" />
                    <circle
                      className="gauge-progress"
                      cx="50"
                      cy="50"
                      r="40"
                      style={{
                        strokeDasharray: 251,
                        strokeDashoffset: 251 - (251 * scorePct) / 100,
                        stroke: scorePct > 70 ? "#ef4444" : scorePct > 35 ? "#f59e0b" : "#10b981",
                      }}
                    />
                  </svg>
                  <div className="gauge-center font-mono">
                    <span className="gauge-value">{evaluation.compositeScore.toFixed(2)}</span>
                    <span className="gauge-label text-muted text-xs">Risk Score</span>
                  </div>
                </div>

                <div className="text-center mb-3">
                  <h4 className="font-semibold text-lg">{evaluation.actionLabel}</h4>
                  {evaluation.amount !== null && (
                    <span className="text-xs font-mono text-muted">Amount: {evaluation.amount}</span>
                  )}
                </div>

                <StatusPill status={evaluation.decisionOutcome} />
              </div>
            ) : (
              <EmptyState title="No Evaluation Result" description="Run a test evaluation below." />
            )}
          </div>
        </div>

        {/* Contributing Factors Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Contributing Risk Factors</h3>
            <span className="text-xs text-muted font-mono">Weight Breakdown</span>
          </div>
          <div className="panel-body">
            {hasEval && evaluation.factors && evaluation.factors.length > 0 ? (
              <div className="factor-list">
                {evaluation.factors.map((f, idx) => (
                  <div key={idx} className="factor-row">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs">{f.name}</span>
                      <span className="font-mono text-xs text-primary">
                        +{(f.contribution).toFixed(2)} (w={f.weight})
                      </span>
                    </div>
                    <div className="factor-bar-bg">
                      <div
                        className="factor-bar-fill"
                        style={{ width: `${Math.min(100, f.value * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}

                <div className="factor-total-row mt-4 pt-3 border-t border-border flex justify-between">
                  <span className="font-mono text-xs font-bold">Total Composite Score:</span>
                  <span className="font-mono text-xs font-bold text-primary">
                    {evaluation.compositeScore.toFixed(2)}
                  </span>
                </div>
              </div>
            ) : (
              <EmptyState title="No Factors Calculated" description="Factor breakdown offline." />
            )}
          </div>
        </div>
      </div>

      <div className="grid-2 gap-6">
        {/* Test Action Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Interactive Test Evaluator</h3>
            <button className="btn btn-sm btn-primary" onClick={handleTestEvaluate}>
              <Play size={12} />
              <span>Evaluate Action</span>
            </button>
          </div>
          <div className="panel-body">
            <div className="form-group mb-4">
              <label className="form-label text-xs font-mono">Tool Name:</label>
              <select
                className="select-input font-mono w-full"
                value={selectedTool}
                onChange={(e) => setSelectedTool(e.target.value)}
              >
                <option value="file_write">file_write (high risk, irreversible)</option>
                <option value="web_search">web_search (low risk, reversible)</option>
                <option value="stub-executor">stub-executor (medium risk)</option>
              </select>
            </div>

            <div className="form-group mb-4">
              <label className="form-label text-xs font-mono flex justify-between">
                <span>Step Index Depth:</span>
                <span className="text-primary">{stepIndex}</span>
              </label>
              <input
                type="range"
                min="1"
                max="10"
                value={stepIndex}
                onChange={(e) => setStepIndex(Number(e.target.value))}
                className="range-input"
              />
            </div>

            <div className="form-group mb-4">
              <label className="form-label text-xs font-mono flex justify-between">
                <span>Retry Count:</span>
                <span className="text-primary">{retryCount}</span>
              </label>
              <input
                type="range"
                min="0"
                max="5"
                value={retryCount}
                onChange={(e) => setRetryCount(Number(e.target.value))}
                className="range-input"
              />
            </div>

            <div className="form-group flex items-center gap-2">
              <input
                type="checkbox"
                id="hasError"
                checked={hasError}
                onChange={(e) => setHasError(e.target.checked)}
                className="checkbox-input"
              />
              <label htmlFor="hasError" className="text-xs font-mono cursor-pointer">
                Inject Execution Error Output
              </label>
            </div>
          </div>
        </div>

        {/* Decision Thresholds Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Decision Threshold Configuration</h3>
            <button className="btn btn-sm btn-ghost" onClick={handleSaveThresholds}>
              <Save size={12} />
              <span>Apply Thresholds</span>
            </button>
          </div>
          <div className="panel-body">
            <div className="form-group mb-4">
              <label className="form-label text-xs font-mono flex justify-between">
                <span>Auto-Approve Max (Continue Threshold):</span>
                <span className="text-success">{continueMax.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={continueMax}
                onChange={(e) => setContinueMax(Number(e.target.value))}
                className="range-input"
              />
              <span className="text-xs text-muted block mt-1">
                Risk score &le; {continueMax.toFixed(2)} executes automatically.
              </span>
            </div>

            <div className="form-group mb-4">
              <label className="form-label text-xs font-mono flex justify-between">
                <span>Human-Approval Max Threshold:</span>
                <span className="text-warning">{approveMax.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={approveMax}
                onChange={(e) => setApproveMax(Number(e.target.value))}
                className="range-input"
              />
              <span className="text-xs text-muted block mt-1">
                Risk score &gt; {approveMax.toFixed(2)} triggers automatic HALT.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
