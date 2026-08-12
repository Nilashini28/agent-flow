import React, { useEffect, useState } from "react";
import { api } from "./api/client";
import {
  OverviewData,
  AgentItem,
  WorkflowItem,
  WorkflowCheckpointDetail,
  RiskConfig,
  RiskEvaluation,
  ToolPermissionItem,
  SandboxRunItem,
  ApprovalItem,
  AuditEvent,
  EvaluationData,
} from "./types";

import { Sidebar } from "./components/common/Sidebar";
import { TopBar } from "./components/common/TopBar";
import { LaunchWorkflowModal } from "./components/common/LaunchWorkflowModal";

import { OverviewPage } from "./components/pages/OverviewPage";
import { AgentsPage } from "./components/pages/AgentsPage";
import { WorkflowsPage } from "./components/pages/WorkflowsPage";
import { CheckpointsPage } from "./components/pages/CheckpointsPage";
import { RiskEnginePage } from "./components/pages/RiskEnginePage";
import { PermissionsPage } from "./components/pages/PermissionsPage";
import { SandboxPage } from "./components/pages/SandboxPage";
import { ApprovalsPage } from "./components/pages/ApprovalsPage";
import { AuditPage } from "./components/pages/AuditPage";
import { EvaluationPage } from "./components/pages/EvaluationPage";

export default function App() {
  const [currentPath, setCurrentPath] = useState<string>("/");
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // Centralized State
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [agents, setAgents] = useState<AgentItem[] | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowItem[] | null>(null);
  const [checkpointDetail, setCheckpointDetail] = useState<WorkflowCheckpointDetail | null>(null);
  const [riskConfig, setRiskConfig] = useState<RiskConfig | null>(null);
  const [riskEvaluation, setRiskEvaluation] = useState<RiskEvaluation | null>(null);
  const [tools, setTools] = useState<ToolPermissionItem[] | null>(null);
  const [sandboxRuns, setSandboxRuns] = useState<SandboxRunItem[] | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalItem[] | null>(null);
  const [approvalHistory, setApprovalHistory] = useState<ApprovalItem[] | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[] | null>(null);
  const [auditTotal, setAuditTotal] = useState<number>(0);
  const [evaluationData, setEvaluationData] = useState<EvaluationData | null>(null);

  // Loading States
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Load Data on Path Change / Mount
  const loadData = async () => {
    setIsLoading(true);
    try {
      if (currentPath === "/") {
        const data = await api.getOverview();
        setOverviewData(data);
      } else if (currentPath === "/agents") {
        const data = await api.getAgents();
        setAgents(data);
      } else if (currentPath === "/workflows") {
        const data = await api.getWorkflows();
        setWorkflows(data.workflows);
      } else if (currentPath === "/checkpoints") {
        const wfList = await api.getWorkflows();
        setWorkflows(wfList.workflows);
        if (wfList.workflows.length > 0) {
          const detail = await api.getWorkflowCheckpoints(wfList.workflows[0].id);
          setCheckpointDetail(detail);
        }
      } else if (currentPath === "/risk") {
        const cfg = await api.getRiskConfig();
        setRiskConfig(cfg);
        const evalRes = await api.evaluateRisk({
          tool_name: "file_write",
          step_index: 1,
          has_error: false,
          retry_count: 0,
        });
        setRiskEvaluation(evalRes);
      } else if (currentPath === "/permissions") {
        const res = await api.getTools();
        setTools(res.tools);
      } else if (currentPath === "/sandbox") {
        const res = await api.getSandboxRuns();
        setSandboxRuns(res);
      } else if (currentPath === "/approvals") {
        const pending = await api.getPendingApprovals();
        const hist = await api.getApprovalHistory();
        setPendingApprovals(pending);
        setApprovalHistory(hist);
      } else if (currentPath === "/audit") {
        const res = await api.getAuditEvents();
        setAuditEvents(res.events);
        setAuditTotal(res.total);
      } else if (currentPath === "/evaluation") {
        const res = await api.getEvaluationMetrics();
        setEvaluationData(res);
      }
    } catch (err) {
      console.warn("API load info/fallback:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // 5s auto-refresh
    return () => clearInterval(interval);
  }, [currentPath]);

  // Handler functions
  const handleLaunchWorkflow = async (task: string, framework: "langgraph" | "autogen") => {
    try {
      await api.startRun(task, framework);
      loadData();
    } catch (e) {
      console.error("Failed to launch workflow:", e);
    }
  };

  const handleSelectWorkflowCheckpoints = async (id: string) => {
    setIsLoading(true);
    try {
      const detail = await api.getWorkflowCheckpoints(id);
      setCheckpointDetail(detail);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSimulateFailure = async (workflowId: string, failureType: string) => {
    try {
      await api.simulateFailure(workflowId, failureType);
      handleSelectWorkflowCheckpoints(workflowId);
    } catch (e) {
      console.error(e);
    }
  };

  const handleEvaluateRisk = async (data: { tool_name: string; step_index: number; has_error: boolean; retry_count: number }) => {
    try {
      const res = await api.evaluateRisk(data);
      setRiskEvaluation(res);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateThresholds = async (data: { escalation_continue_max: number; escalation_approve_max: number }) => {
    try {
      await api.updateRiskThresholds(data);
      const cfg = await api.getRiskConfig();
      setRiskConfig(cfg);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateToolPolicy = async (toolName: string, policy: string) => {
    try {
      await api.updateToolPermission(toolName, policy);
    } catch (e) {
      console.error(e);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await api.approveRun(id);
      loadData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await api.rejectRun(id);
      loadData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAuditFilter = async (category: string, query: string) => {
    try {
      const res = await api.getAuditEvents(category, query);
      setAuditEvents(res.events);
      setAuditTotal(res.total);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunBenchmark = async () => {
    try {
      await api.runBenchmark();
      const res = await api.getEvaluationMetrics();
      setEvaluationData(res);
    } catch (e) {
      console.error(e);
    }
  };

  // Badges count for Sidebar
  const sidebarBadges = {
    pendingApprovals: pendingApprovals ? pendingApprovals.length : (overviewData?.pendingApprovals || 0),
    runningWorkflows: overviewData?.runningWorkflows || (workflows ? workflows.filter((w) => w.status === "running").length : 0),
    blockedActions: overviewData?.blockedActions || 0,
  };

  return (
    <div className="app-container">
      <Sidebar
        currentPath={currentPath}
        onNavigate={setCurrentPath}
        badges={sidebarBadges}
        systemStatus="healthy"
        versionString="v0.1.0-prod"
      />

      <div className="main-content">
        <TopBar
          isDemoMode={isDemoMode}
          onToggleDemoMode={() => setIsDemoMode(!isDemoMode)}
          onNewWorkflow={() => setIsModalOpen(true)}
        />

        <main className="page-content">
          {currentPath === "/" && (
            <OverviewPage
              data={overviewData}
              isLoading={isLoading}
              onNavigate={setCurrentPath}
            />
          )}

          {currentPath === "/agents" && (
            <AgentsPage agents={agents} isLoading={isLoading} />
          )}

          {currentPath === "/workflows" && (
            <WorkflowsPage
              workflows={workflows}
              isLoading={isLoading}
              onSelectWorkflow={(id) => {
                setCurrentPath("/checkpoints");
                handleSelectWorkflowCheckpoints(id);
              }}
              onLaunchWorkflow={() => setIsModalOpen(true)}
            />
          )}

          {currentPath === "/checkpoints" && (
            <CheckpointsPage
              workflows={workflows}
              selectedDetail={checkpointDetail}
              isLoading={isLoading}
              onSelectWorkflow={handleSelectWorkflowCheckpoints}
              onSimulateFailure={handleSimulateFailure}
            />
          )}

          {currentPath === "/risk" && (
            <RiskEnginePage
              config={riskConfig}
              evaluation={riskEvaluation}
              isLoading={isLoading}
              onEvaluate={handleEvaluateRisk}
              onUpdateThresholds={handleUpdateThresholds}
            />
          )}

          {currentPath === "/permissions" && (
            <PermissionsPage
              tools={tools}
              isLoading={isLoading}
              onUpdatePolicy={handleUpdateToolPolicy}
            />
          )}

          {currentPath === "/sandbox" && (
            <SandboxPage runs={sandboxRuns} isLoading={isLoading} />
          )}

          {currentPath === "/approvals" && (
            <ApprovalsPage
              pending={pendingApprovals}
              history={approvalHistory}
              isLoading={isLoading}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          )}

          {currentPath === "/audit" && (
            <AuditPage
              events={auditEvents}
              total={auditTotal}
              isLoading={isLoading}
              onFilterChange={handleAuditFilter}
            />
          )}

          {currentPath === "/evaluation" && (
            <EvaluationPage
              data={evaluationData}
              isLoading={isLoading}
              onRunBenchmark={handleRunBenchmark}
            />
          )}
        </main>
      </div>

      <LaunchWorkflowModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onLaunch={handleLaunchWorkflow}
      />
    </div>
  );
}
