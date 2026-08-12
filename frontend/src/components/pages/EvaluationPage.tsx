import React from "react";
import { EvaluationData } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatCard } from "../common/StatCard";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { BarChart3, Play, Zap, CheckCircle2, RotateCcw } from "../common/Icons";

interface EvaluationPageProps {
  data: EvaluationData | null;
  isLoading: boolean;
  onRunBenchmark: () => void;
}

export const EvaluationPage: React.FC<EvaluationPageProps> = ({
  data,
  isLoading,
  onRunBenchmark,
}) => {
  if (isLoading && !data) {
    return (
      <div className="page-container">
        <PageHeader
          title="Reliability Benchmark & Evaluation"
          description="Comparative empirical evaluation: Unassisted Baseline vs. AgentFlow Reliability Layer."
        />
        <LoadingSkeleton height="200px" count={2} />
      </div>
    );
  }

  const hasData = data !== null;

  return (
    <div className="page-container">
      <PageHeader
        title="Reliability Benchmark & Evaluation"
        description="Comparative empirical evaluation: Unassisted Baseline vs. AgentFlow Reliability Layer."
        actions={
          <button className="btn btn-primary" onClick={onRunBenchmark}>
            <Play size={14} />
            <span>Run Benchmark Suite</span>
          </button>
        }
      />

      {/* Stat Row */}
      <div className="stats-grid grid-4 mb-6">
        <StatCard
          label="Workflows Per Arm"
          value={hasData ? data.workflowsPerArm : null}
          icon={<BarChart3 size={16} />}
        />
        <StatCard
          label="Injected Failures"
          value={hasData ? data.injectedFailures : null}
          icon={<Zap size={16} />}
          variant="warning"
        />
        <StatCard
          label="Completion Rate"
          value={hasData ? `${(data.completionRate * 100).toFixed(0)}%` : null}
          icon={<CheckCircle2 size={16} />}
          variant="success"
        />
        <StatCard
          label="Avg Recovery Time"
          value={hasData ? `${data.avgRecoveryTimeMs} ms` : null}
          icon={<RotateCcw size={16} />}
          variant="primary"
        />
      </div>

      {/* Baseline vs AgentFlow Comparison Panel */}
      <div className="panel">
        <div className="panel-header">
          <h3 className="panel-title">Baseline vs AgentFlow Reliability Comparison</h3>
          <span className="text-xs text-muted font-mono">Empirical Benchmark Data</span>
        </div>
        <div className="panel-body">
          {hasData && data.metrics && data.metrics.length > 0 ? (
            <div className="metrics-comparison-list space-y-6">
              {data.metrics.map((m, idx) => (
                <div key={idx} className="metric-comparison-item">
                  <div className="flex justify-between items-center mb-2 font-mono text-xs">
                    <span className="font-semibold text-sm">{m.name}</span>
                    <span className="text-muted">Unit: {m.unit}</span>
                  </div>

                  {/* Paired Bars */}
                  <div className="space-y-2">
                    {/* Baseline Bar */}
                    <div className="bar-row flex items-center gap-3">
                      <span className="font-mono text-xs text-muted w-24">Baseline:</span>
                      <div className="bar-bg flex-1">
                        <div
                          className="bar-fill bg-muted"
                          style={{ width: `${Math.min(100, (m.baselineValue / Math.max(m.baselineValue, m.agentflowValue, 1)) * 100)}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs font-semibold w-16 text-right">
                        {m.baselineValue} {m.unit}
                      </span>
                    </div>

                    {/* AgentFlow Bar */}
                    <div className="bar-row flex items-center gap-3">
                      <span className="font-mono text-xs text-primary font-semibold w-24">AgentFlow:</span>
                      <div className="bar-bg flex-1">
                        <div
                          className="bar-fill bg-primary"
                          style={{ width: `${Math.min(100, (m.agentflowValue / Math.max(m.baselineValue, m.agentflowValue, 1)) * 100)}%` }}
                        />
                      </div>
                      <span className="font-mono text-xs font-semibold text-primary w-16 text-right">
                        {m.agentflowValue} {m.unit}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No Evaluation Data" description="Run a benchmark to populate comparison metrics." />
          )}
        </div>
      </div>
    </div>
  );
};
