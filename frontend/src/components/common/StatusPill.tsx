import React from "react";
import { getStatusTheme } from "../../utils/status";

interface StatusPillProps {
  status: string | null | undefined;
  label?: string;
  size?: "sm" | "md";
}

export const StatusPill: React.FC<StatusPillProps> = ({ status, label, size = "md" }) => {
  const theme = getStatusTheme(status);
  const displayText = label || (status ? status.replace(/_/g, " ").toUpperCase() : "UNKNOWN");

  return (
    <span
      className={`status-pill status-pill-${size}`}
      style={{
        backgroundColor: theme.bg,
        color: theme.text,
        borderColor: theme.border,
      }}
    >
      <span className="status-pill-dot" style={{ backgroundColor: theme.dot }} />
      {displayText}
    </span>
  );
};
