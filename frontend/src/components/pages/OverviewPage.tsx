import React from "react";
import { OverviewData } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { StatCard } from "../common/StatCard";
import { StatusPill } from "../common/StatusPill";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import {
  Users,
  GitMerge,
  CheckCircle,
  RotateCcw,
  AlertTriangle,
  ShieldOff,
  Lock,
  Box,
  ArrowRight,
} from "../common/Icons";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface OverviewPageProps {
  data: OverviewData | null;
  isLoading: boolean;
  onNavigate: (path: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  data,
  isLoading,
  onNavigate,
}) => {
  if (isLoading) {
    return (
      <div className="page-container">
        <PageHeader
          title="Control Center"
          description="System-wide autonomous agent execution health, governance & recovery timeline."
        />
        <LoadingSkeleton height="100px" count={2} className="mb-6" />
        <LoadingSkeleton height="300px" count={1} />
      </div>
    );
  }

  const hasData = data !== null;

  return (
    <div className="page-container">
      <PageHeader
        title="Control Center"
        description="System-wide autonomous agent execution health, governance & recovery timeline."
        meta={
          <span className="font-mono text-xs text-muted">
            Live Feed · Updated Just Now
          </span>
        }
      />

      {/* Row of Stat Cards */}
      <div className="stats-grid grid-4">
        <StatCard
          label="Active Agents"
          value={hasData ? data.activeAgents : null}
          icon={<Users size={16} />}
          variant="primary"
        />
        <StatCard
          label="Running Workflows"
          value={hasData ? data.runningWorkflows : null}
          icon={<GitMerge size={16} />}
          variant="primary"
        />
        <StatCard
          label="Completed Workflows"
          value={hasData ? data.completedWorkflows : null}
          icon={<CheckCircle size={16} />}
          variant="success"
        />
        <StatCard
          label="Recoveries"
          value={hasData ? data.recoveriesCount : null}
          icon={<RotateCcw size={16} />}
          variant="success"
        />
        <StatCard
          label="Pending Approvals"
          value={hasData ? data.pendingApprovals : null}
          icon={<AlertTriangle size={16} />}
          variant={data && data.pendingApprovals > 0 ? "warning" : "default"}
        />
        <StatCard
          label="High-Risk Actions"
          value={hasData ? data.highRiskActions : null}
          icon={<ShieldOff size={16} />}
          variant="warning"
        />
        <StatCard
          label="Blocked Actions"
          value={hasData ? data.blockedActions : null}
          icon={<Lock size={16} />}
          variant="danger"
        />
        <StatCard
          label="Sandbox Runs"
          value={hasData ? data.sandboxRuns : null}
          icon={<Box size={16} />}
        />
      </div>

      <div className="grid-2 gap-6 mt-6">
        {/* Workflow Health Chart */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Workflow Execution Health</h3>
            <span className="text-xs text-muted font-mono">Time-series</span>
          </div>
          <div className="panel-body chart-container" style={{ height: 260 }}>
            {hasData && data.chartData && data.chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.chartData}>
                  <defs>
                    <linearGradient id="colorCompleted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                  <XAxis dataKey="time" stroke="#737373" fontSize={12} />
                  <YAxis stroke="#737373" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#171717",
                      borderColor: "#262626",
                      borderRadius: "6px",
                      fontSize: "12px",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="completed"
                    stroke="#10b981"
                    fillOpacity={1}
                    fill="url(#colorCompleted)"
                  />
                  <Area
                    type="monotone"
                    dataKey="recovered"
                    stroke="#3b82f6"
                    fillOpacity={1}
                    fill="url(#colorRecovered)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="No Chart Data" description="No metrics recorded yet." />
            )}
          </div>
        </div>

        {/* System Subsystems Health Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">System Subsystem Health</h3>
            <span className="text-xs text-muted font-mono">5 Subsystems</span>
          </div>
          <div className="panel-body">
            {hasData && data.subsystems && data.subsystems.length > 0 ? (
              <div className="subsystem-list">
                {data.subsystems.map((sub, idx) => (
                  <div key={idx} className="subsystem-row">
                    <span className="subsystem-name font-mono">{sub.name}</span>
                    <StatusPill status={sub.status} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No Subsystem Info" description="Subsystem telemetry offline." />
            )}
          </div>
        </div>
      </div>

      <div className="grid-2 gap-6 mt-6">
        {/* Recent Activity Feed */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Recent Activity Feed</h3>
            <button
              className="btn btn-sm btn-ghost text-xs"
              onClick={() => onNavigate("/audit")}
            >
              <span>Full Audit Logs</span>
              <ArrowRight size={12} />
            </button>
          </div>
          <div className="panel-body">
            {hasData && data.recentActivity && data.recentActivity.length > 0 ? (
              <div className="activity-feed">
                {data.recentActivity.map((evt, idx) => (
                  <div key={idx} className="activity-item">
                    <div className="activity-time font-mono">{evt.timestamp.slice(11, 19)}</div>
                    <div className="activity-details">
                      <span className="activity-cat font-mono">{evt.category}</span>
                      <span className="activity-desc">{evt.description}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No Recent Activity" description="No events logged in system feed." />
            )}
          </div>
        </div>

        {/* Recent Recoveries Panel */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Recent Recoveries</h3>
            <button
              className="btn btn-sm btn-ghost text-xs"
              onClick={() => onNavigate("/checkpoints")}
            >
              <span>Checkpoints & Timeline</span>
              <ArrowRight size={12} />
            </button>
          </div>
          <div className="panel-body">
            {hasData && data.recentRecoveries && data.recentRecoveries.length > 0 ? (
              <div className="recovery-list">
                {data.recentRecoveries.map((rec, idx) => (
                  <div key={idx} className="recovery-item">
                    <div className="recovery-header">
                      <span className="font-mono text-sm text-primary">{rec.workflowId}</span>
                      <StatusPill status={rec.status} size="sm" />
                    </div>
                    <div className="recovery-stats text-xs font-mono text-muted mt-1">
                      Replayed: {rec.replayedCount} · Avoided: {rec.avoidedCount} · Latency: {rec.durationMs}ms
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No Recoveries Recorded" description="Zero crash recoveries triggered." />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
