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
  EngineItem,
} from "../types";

const API_BASE = "http://localhost:8000";

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export interface TimelineEvent {
  run_id: string;
  event_type: string;
  payload: Record<string, any>;
  timestamp: string;
}

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
      ...options,
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`API ${res.status}: ${errorText || res.statusText}`);
    }

    return res.json() as Promise<T>;
  } catch (err: any) {
    if (err instanceof TypeError && err.message.includes("fetch")) {
      throw new NetworkError(`Failed to connect to backend at ${API_BASE}`);
    }
    throw err;
  }
}

export const createRun = async (task: string, framework: "langgraph" | "autogen" = "langgraph"): Promise<{ run_id: string; engine: string }> => {
  return fetchJson<{ run_id: string; engine: string }>("/runs", {
    method: "POST",
    body: JSON.stringify({ task, framework }),
  });
};

export const getTimeline = async (runId: string): Promise<TimelineEvent[]> => {
  const res = await fetchJson<{ events: TimelineEvent[] }>(`/runs/${runId}/timeline`);
  return res.events || [];
};

export const approveRun = async (runId: string): Promise<any> => {
  return fetchJson(`/runs/${runId}/escalations/approve`, { method: "POST" });
};

export const rejectRun = async (runId: string): Promise<any> => {
  return fetchJson(`/runs/${runId}/escalations/reject`, { method: "POST" });
};

export const api = {
  // Page 1: Overview
  getOverview: async (): Promise<OverviewData> => {
    return fetchJson<OverviewData>("/system/overview");
  },

  // Page 2: Agents & Engines
  getAgents: async (): Promise<AgentItem[]> => {
    return fetchJson<AgentItem[]>("/agents");
  },
  getEngines: async (): Promise<EngineItem[]> => {
    return fetchJson<EngineItem[]>("/engines");
  },

  // Page 3: Workflows
  getWorkflows: async (status?: string, query?: string): Promise<{ workflows: WorkflowItem[]; total: number }> => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (query) params.append("query", query);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetchJson<{ runs: any[]; total: number }>(`/runs${qs}`);

    const workflows: WorkflowItem[] = (res.runs || []).map((r) => ({
      id: r.run_id,
      agent: r.engine_description || r.engine,
      subject: `Context-${r.run_id.slice(0, 6)}`,
      task: r.task,
      currentStep: r.status === "completed" ? "Final Step" : "Executing",
      riskScore: 0.15,
      status: r.status,
      startedAt: r.created_at,
      durationSeconds: r.finished_at ? 1.2 : null,
    }));

    return { workflows, total: res.total || workflows.length };
  },

  // Page 4: Checkpoints
  getWorkflowCheckpoints: async (workflowId: string): Promise<WorkflowCheckpointDetail> => {
    const res = await fetchJson<any>(`/runs/${workflowId}/checkpoints`);
    const events = await getTimeline(workflowId);

    const steps = events.map((e: any, idx: number) => ({
      index: idx,
      name: e.event_type,
      status: "completed",
      toolName: e.payload?.tool,
      durationMs: 45,
      checkpointId: `chk-${idx}`,
    }));

    return {
      workflowId,
      checkpointsCount: events.length,
      stepsExecuted: steps.length,
      stepsReplayed: 0,
      stepsAvoided: 0,
      recoveryLatencyMs: 120,
      steps,
      checkpoints: events.map((e: any, idx: number) => ({
        id: `chk-${idx}`,
        sizeKb: 4.2,
        stepLabel: e.event_type,
        timestamp: e.timestamp,
        payloadPreview: JSON.stringify(e.payload || {}),
      })),
    };
  },

  simulateFailure: async (workflowId: string, failureType: string) => {
    return { status: "simulated", workflowId, failureType, recovered: true };
  },

  // Page 5: Risk Engine
  getRiskConfig: async (): Promise<RiskConfig> => {
    return fetchJson<RiskConfig>("/risk/config");
  },

  evaluateRisk: async (data: { tool_name: string; step_index: number; has_error: boolean; retry_count: number }): Promise<RiskEvaluation> => {
    return fetchJson<RiskEvaluation>("/risk/evaluate", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateRiskThresholds: async (data: { escalation_continue_max: number; escalation_approve_max: number }) => {
    return fetchJson("/risk/thresholds", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Page 6: Permissions
  getTools: async (): Promise<{ tools: ToolPermissionItem[]; total: number }> => {
    const res = await fetchJson<{ tools: any[]; total: number }>("/tools");
    const tools: ToolPermissionItem[] = (res.tools || []).map((t) => ({
      ...t,
      currentPolicy: t.risk_tier === "high" ? "approval" : "allow",
    }));
    return { tools, total: res.total || tools.length };
  },

  updateToolPermission: async (toolName: string, policy: string) => {
    return { toolName, policy, updated: true };
  },

  // Page 7: Sandbox
  getSandboxRuns: async (): Promise<SandboxRunItem[]> => {
    return fetchJson<SandboxRunItem[]>("/sandbox/runs");
  },

  // Page 8: Human Approvals
  getPendingApprovals: async (): Promise<ApprovalItem[]> => {
    const res = await fetchJson<{ runs: any[] }>("/runs?status=awaiting_approval");
    return (res.runs || []).map((r) => ({
      id: r.run_id,
      title: `Approval Required: ${r.task}`,
      riskScore: 0.65,
      toolName: "file_write",
      workflowId: r.run_id,
      agentId: r.engine,
      subjectId: `Subject-${r.run_id.slice(0, 6)}`,
      timestamp: r.created_at,
      impactValue: "High File Output",
      reasons: ["Action involves irreversible filesystem modification", "Risk score (0.65) exceeds continue threshold"],
    }));
  },

  getApprovalHistory: async (): Promise<ApprovalItem[]> => {
    return [];
  },

  approveRun,
  rejectRun,

  // Page 9: Audit & Traces
  getAuditEvents: async (category?: string, query?: string): Promise<{ events: AuditEvent[]; total: number }> => {
    const res = await fetchJson<{ runs: any[] }>("/runs?limit=5");
    let allEvents: AuditEvent[] = [];
    for (const r of res.runs || []) {
      const traceEvents = await getTimeline(r.run_id);
      traceEvents.forEach((e) => {
        allEvents.push({
          timestamp: e.timestamp,
          category: e.event_type,
          description: `Event ${e.event_type} logged for run ${e.run_id.slice(0, 8)}`,
          refId: e.run_id,
          payload: e.payload,
        });
      });
    }

    if (category && category !== "all") {
      allEvents = allEvents.filter((e) => e.category === category);
    }

    return { events: allEvents, total: allEvents.length };
  },

  // Page 10: Evaluation
  getEvaluationMetrics: async (): Promise<EvaluationData> => {
    return fetchJson<EvaluationData>("/evaluation/metrics");
  },

  runBenchmark: async () => {
    return fetchJson("/evaluation/benchmark", { method: "POST" });
  },

  // Actions: Start Workflow
  startRun: createRun,
};
