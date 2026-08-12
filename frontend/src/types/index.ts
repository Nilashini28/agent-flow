/**
 * AgentFlow TypeScript Data Schemas & Interfaces
 * Pure presentation & API interface layer — no hardcoded business logic.
 */

export type StatusType =
  | "running"
  | "completed"
  | "failed"
  | "halted"
  | "awaiting_approval"
  | "healthy"
  | "warning"
  | "degraded"
  | "active"
  | "recovered"
  | "executing"
  | string;

export interface NavItemConfig {
  id: string;
  label: string;
  iconName: string;
  path: string;
  badgeKey?: "pendingApprovals" | "runningWorkflows" | "blockedActions";
}

export interface SubsystemHealth {
  name: string;
  status: "healthy" | "warning" | "degraded" | "failed" | string;
}

export interface ActivityItem {
  timestamp: string;
  category: string;
  description: string;
  refId: string;
}

export interface RecoveryItem {
  workflowId: string;
  status: string;
  replayedCount: number;
  avoidedCount: number;
  durationMs: number;
  timestamp: string;
}

export interface HealthChartPoint {
  time: string;
  completed: number;
  recovered: number;
  failed: number;
}

export interface OverviewData {
  activeAgents: number;
  runningWorkflows: number;
  completedWorkflows: number;
  recoveriesCount: number;
  pendingApprovals: number;
  highRiskActions: number;
  blockedActions: number;
  sandboxRuns: number;
  subsystems: SubsystemHealth[];
  chartData: HealthChartPoint[];
  recentActivity: ActivityItem[];
  recentRecoveries: RecoveryItem[];
}

export interface AgentItem {
  id: string;
  name: string;
  status: string;
  model: string;
  assignedRiskPolicy: string;
  toolCount: number;
  workflowCount: number;
  activeNowCount: number;
  successRate: number;
  tools: string[];
}

export interface WorkflowItem {
  id: string;
  agent: string;
  subject: string;
  task: string;
  currentStep: string;
  riskScore: number;
  status: StatusType;
  startedAt: string;
  durationSeconds?: number | null;
}

export interface CheckpointStep {
  index: number;
  name: string;
  status: string;
  toolName?: string;
  durationMs?: number;
  checkpointId?: string;
}

export interface CheckpointItem {
  id: string;
  sizeKb: number;
  stepLabel: string;
  timestamp: string;
  payloadPreview: string;
}

export interface WorkflowCheckpointDetail {
  workflowId: string;
  checkpointsCount: number;
  stepsExecuted: number;
  stepsReplayed: number;
  stepsAvoided: number;
  recoveryLatencyMs: number;
  steps: CheckpointStep[];
  checkpoints: CheckpointItem[];
}

export interface RiskFactorItem {
  name: string;
  value: number;
  weight: number;
  contribution: number;
}

export interface RiskEvaluation {
  actionLabel: string;
  amount: number | null;
  compositeScore: number;
  decisionOutcome: "CONTINUE" | "REQUEST_APPROVAL" | "HALT" | string;
  factors: RiskFactorItem[];
}

export interface RiskConfigField {
  name: string;
  min: number;
  max: number;
  current: number;
  label: string;
}

export interface RiskConfig {
  escalation_continue_max: number;
  escalation_approve_max: number;
  test_fields: RiskConfigField[];
}

export interface ToolPermissionItem {
  name: string;
  description: string;
  risk_tier: "low" | "medium" | "high" | string;
  reversible: boolean;
  allow_network: boolean;
  tags: string[];
  currentPolicy: "allow" | "approval" | "deny" | string;
  input_schema?: Record<string, any>;
}

export interface AgentToolsGroup {
  agentId: string;
  agentName: string;
  tools: ToolPermissionItem[];
}

export interface SandboxRunItem {
  id: string;
  toolName: string;
  runtimeImage: string;
  status: string;
  cpu: string;
  memory: string;
  network: string;
  secrets: string;
  lifecycleStage: "Created" | "Running" | "Executing" | "Completed" | "Destroyed" | string;
  elapsedMs: number;
  exitCode: number;
  networkCallCount: number;
  fileCount: number;
  logs: string[];
  startedAt: string;
  workflowId: string;
}

export interface ApprovalItem {
  id: string;
  title: string;
  riskScore: number;
  toolName: string;
  workflowId: string;
  agentId: string;
  subjectId: string;
  timestamp: string;
  impactValue?: string | number | null;
  reasons: string[];
}

export interface AuditEvent {
  timestamp: string;
  category: string;
  description: string;
  refId: string;
  payload?: Record<string, any>;
}

export interface BenchmarkMetric {
  name: string;
  baselineValue: number;
  agentflowValue: number;
  unit: string;
}

export interface EvaluationData {
  workflowsPerArm: number;
  injectedFailures: number;
  completionRate: number;
  avgRecoveryTimeMs: number;
  metrics: BenchmarkMetric[];
}
