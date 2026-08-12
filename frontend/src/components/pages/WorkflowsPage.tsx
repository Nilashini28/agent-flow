import React, { useState } from "react";
import { WorkflowItem } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { DataTable, Column } from "../common/DataTable";
import { StatusPill } from "../common/StatusPill";
import { RiskDot } from "../common/RiskDot";
import { Search, Plus } from "../common/Icons";

interface WorkflowsPageProps {
  workflows: WorkflowItem[] | null;
  isLoading: boolean;
  onSelectWorkflow: (id: string) => void;
  onLaunchWorkflow?: () => void;
}

const STATUS_FILTERS = ["all", "running", "completed", "awaiting_approval", "failed", "halted"];

export const WorkflowsPage: React.FC<WorkflowsPageProps> = ({
  workflows,
  isLoading,
  onSelectWorkflow,
  onLaunchWorkflow,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("all");

  const filteredWorkflows = (workflows || []).filter((wf) => {
    const matchesStatus =
      selectedStatus === "all" || wf.status.toLowerCase() === selectedStatus.toLowerCase();
    const matchesSearch =
      !searchQuery ||
      wf.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.task.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.agent.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.subject.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const columns: Column<WorkflowItem>[] = [
    {
      key: "id",
      header: "Workflow ID",
      render: (wf) => <span className="font-mono text-primary text-xs">{wf.id.slice(0, 12)}...</span>,
      width: "140px",
    },
    {
      key: "agent",
      header: "Agent Engine",
      render: (wf) => <span className="font-mono text-xs text-muted">{wf.agent}</span>,
    },
    {
      key: "subject",
      header: "Subject Context",
      render: (wf) => <span className="font-mono text-xs">{wf.subject}</span>,
    },
    {
      key: "task",
      header: "Task Intent",
      render: (wf) => <span className="text-sm font-medium">{wf.task}</span>,
    },
    {
      key: "currentStep",
      header: "Current Step",
      render: (wf) => <span className="font-mono text-xs text-muted">{wf.currentStep}</span>,
    },
    {
      key: "riskScore",
      header: "Risk Score",
      render: (wf) => <RiskDot score={wf.riskScore} />,
      width: "110px",
    },
    {
      key: "status",
      header: "Status",
      render: (wf) => <StatusPill status={wf.status} size="sm" />,
      width: "130px",
    },
    {
      key: "startedAt",
      header: "Started",
      render: (wf) => (
        <span className="font-mono text-xs text-muted">
          {wf.startedAt ? wf.startedAt.slice(11, 19) : "—"}
        </span>
      ),
      width: "100px",
    },
  ];

  return (
    <div className="page-container">
      <PageHeader
        title="Workflows & Executions"
        description="Monitor, govern, and trace all active and historical autonomous workflows."
        actions={
          onLaunchWorkflow && (
            <button className="btn btn-primary" onClick={onLaunchWorkflow}>
              <Plus size={14} />
              <span>New Workflow Run</span>
            </button>
          )
        }
      />

      {/* Filter Controls */}
      <div className="filter-bar mb-4">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input font-mono"
            placeholder="Search workflow ID, task, agent, subject..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="status-filter-pills">
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              onClick={() => setSelectedStatus(st)}
              className={`filter-pill ${selectedStatus === st ? "active" : ""}`}
            >
              {st.replace(/_/g, " ").toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Workflows Table */}
      <DataTable
        columns={columns}
        data={filteredWorkflows}
        isLoading={isLoading}
        emptyTitle="No Workflows Found"
        emptyDesc="No active or past workflows match the selected status and search criteria."
        onRowClick={(wf) => onSelectWorkflow(wf.id)}
        keyExtractor={(wf) => wf.id}
      />
    </div>
  );
};
