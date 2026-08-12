/**
 * Centralised status & risk-score mappings for colors and labels.
 * Pure functional mapping layer — reusable across all components.
 */

export interface ColorTheme {
  bg: string;
  text: string;
  border: string;
  dot: string;
}

const DEFAULT_THEME: ColorTheme = {
  bg: "rgba(107, 114, 128, 0.15)",
  text: "#9ca3af",
  border: "rgba(107, 114, 128, 0.3)",
  dot: "#9ca3af",
};

const STATUS_MAP: Record<string, ColorTheme> = {
  // Positive / Healthy / Completed
  completed: {
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dot: "#10b981",
  },
  healthy: {
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dot: "#10b981",
  },
  active: {
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dot: "#10b981",
  },
  recovered: {
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dot: "#10b981",
  },
  allow: {
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dot: "#10b981",
  },
  approved: {
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dot: "#10b981",
  },

  // Active / Running / In-progress
  running: {
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dot: "#3b82f6",
  },
  executing: {
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dot: "#3b82f6",
  },

  // Warnings / Pending / Approval Needed
  awaiting_approval: {
    bg: "rgba(245, 158, 11, 0.15)",
    text: "#fbbf24",
    border: "rgba(245, 158, 11, 0.35)",
    dot: "#f59e0b",
  },
  request_approval: {
    bg: "rgba(245, 158, 11, 0.15)",
    text: "#fbbf24",
    border: "rgba(245, 158, 11, 0.35)",
    dot: "#f59e0b",
  },
  approval: {
    bg: "rgba(245, 158, 11, 0.15)",
    text: "#fbbf24",
    border: "rgba(245, 158, 11, 0.35)",
    dot: "#f59e0b",
  },
  warning: {
    bg: "rgba(245, 158, 11, 0.15)",
    text: "#fbbf24",
    border: "rgba(245, 158, 11, 0.35)",
    dot: "#f59e0b",
  },
  degraded: {
    bg: "rgba(245, 158, 11, 0.15)",
    text: "#fbbf24",
    border: "rgba(245, 158, 11, 0.35)",
    dot: "#f59e0b",
  },

  // Negative / Failed / Deny / Halted
  failed: {
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#f87171",
    border: "rgba(239, 68, 68, 0.35)",
    dot: "#ef4444",
  },
  halted: {
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#f87171",
    border: "rgba(239, 68, 68, 0.35)",
    dot: "#ef4444",
  },
  halt: {
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#f87171",
    border: "rgba(239, 68, 68, 0.35)",
    dot: "#ef4444",
  },
  deny: {
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#f87171",
    border: "rgba(239, 68, 68, 0.35)",
    dot: "#ef4444",
  },
  rejected: {
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#f87171",
    border: "rgba(239, 68, 68, 0.35)",
    dot: "#ef4444",
  },
};

export function getStatusTheme(status: string | null | undefined): ColorTheme {
  if (!status) return DEFAULT_THEME;
  const key = status.toLowerCase().replace(/[-\s]/g, "_");
  return STATUS_MAP[key] || DEFAULT_THEME;
}

export function getRiskScoreTheme(score: number, continueMax = 0.35, approveMax = 0.70): ColorTheme {
  if (score <= continueMax) {
    return STATUS_MAP["completed"]; // green / low risk
  }
  if (score <= approveMax) {
    return STATUS_MAP["awaiting_approval"]; // amber / medium risk
  }
  return STATUS_MAP["failed"]; // red / high risk
}
