import React from "react";

export interface StatCardProps {
  label: string;
  value: string | number | null | undefined;
  icon?: React.ReactNode;
  trend?: string;
  subtext?: string;
  variant?: "default" | "primary" | "warning" | "danger" | "success";
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  icon,
  trend,
  subtext,
  variant = "default",
}) => {
  const displayVal = value !== null && value !== undefined ? value : "—";

  return (
    <div className={`stat-card stat-card-${variant}`}>
      <div className="stat-card-header">
        <span className="stat-card-label">{label}</span>
        {icon && <div className="stat-card-icon">{icon}</div>}
      </div>
      <div className="stat-card-value font-mono">{displayVal}</div>
      {(trend || subtext) && (
        <div className="stat-card-footer">
          {trend && <span className="stat-card-trend">{trend}</span>}
          {subtext && <span className="stat-card-subtext">{subtext}</span>}
        </div>
      )}
    </div>
  );
};
