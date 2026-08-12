import React, { useState } from "react";
import { ApprovalItem } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { RiskDot } from "../common/RiskDot";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { CheckSquare, Check, X, ChevronDown, ChevronUp, AlertTriangle } from "../common/Icons";

interface ApprovalsPageProps {
  pending: ApprovalItem[] | null;
  history: ApprovalItem[] | null;
  isLoading: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({
  pending,
  history,
  isLoading,
  onApprove,
  onReject,
}) => {
  const [showHistory, setShowHistory] = useState(false);

  if (isLoading && !pending) {
    return (
      <div className="page-container">
        <PageHeader
          title="Human-in-the-Loop Governance Approvals"
          description="High-risk tool calls and boundary escalations awaiting human sign-off."
        />
        <LoadingSkeleton height="180px" count={2} />
      </div>
    );
  }

  const hasPending = pending !== null && pending.length > 0;
  const hasHistory = history !== null && history.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Human-in-the-Loop Governance Approvals"
        description="High-risk tool calls and boundary escalations awaiting human sign-off."
        meta={
          <span className="font-mono text-xs text-warning font-semibold">
            {hasPending ? `${pending.length} Pending Review` : "0 Pending"}
          </span>
        }
      />

      {/* Pending Review List */}
      {!hasPending ? (
        <EmptyState
          title="No Pending Approvals"
          description="All autonomous workflow executions are within safe risk thresholds."
          icon={<CheckSquare size={36} />}
        />
      ) : (
        <div className="flex flex-col gap-4 mb-8">
          {pending.map((item) => (
            <div key={item.id} className="panel approval-card border-l-4 border-l-warning">
              <div className="panel-body flex items-start justify-between gap-6">
                <div className="approval-info flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h4 className="font-semibold text-base">{item.title}</h4>
                    <RiskDot score={item.riskScore} />
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono text-muted mb-3">
                    <span>Tool: {item.toolName}</span>
                    <span>Workflow: {item.workflowId.slice(0, 8)}</span>
                    <span>Subject: {item.subjectId}</span>
                    {item.impactValue && (
                      <span className="text-warning font-semibold">
                        Impact: {item.impactValue}
                      </span>
                    )}
                  </div>

                  {item.reasons && item.reasons.length > 0 && (
                    <div className="reasons-box bg-near-black p-2 rounded border border-border text-xs text-muted mb-2">
                      <div className="font-mono font-semibold text-warning mb-1 flex items-center gap-1">
                        <AlertTriangle size={12} /> Escalation Reasons:
                      </div>
                      <ul className="list-disc list-inside space-y-1">
                        {item.reasons.map((r, idx) => (
                          <li key={idx}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="approval-actions flex items-center gap-2">
                  <button
                    className="btn btn-success"
                    onClick={() => onApprove(item.id)}
                  >
                    <Check size={14} />
                    <span>Approve</span>
                  </button>

                  <button
                    className="btn btn-danger"
                    onClick={() => onReject(item.id)}
                  >
                    <X size={14} />
                    <span>Reject</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Decision History Section (Collapsible) */}
      <div className="panel">
        <div
          className="panel-header cursor-pointer flex items-center justify-between"
          onClick={() => setShowHistory(!showHistory)}
        >
          <h3 className="panel-title">Decision History Log</h3>
          <button className="btn btn-sm btn-ghost">
            {showHistory ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        {showHistory && (
          <div className="panel-body">
            {!hasHistory ? (
              <EmptyState
                title="No Historical Decisions"
                description="No previous approval/rejection actions recorded."
              />
            ) : (
              <div className="history-list space-y-2">
                {history.map((h) => (
                  <div key={h.id} className="history-item p-2 bg-card-dark rounded flex justify-between text-xs font-mono">
                    <span>{h.title}</span>
                    <span className="text-muted">{h.timestamp}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
