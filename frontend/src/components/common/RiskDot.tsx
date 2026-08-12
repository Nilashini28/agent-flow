import React from "react";
import { getRiskScoreTheme } from "../../utils/status";

interface RiskDotProps {
  score: number;
  showValue?: boolean;
  continueMax?: number;
  approveMax?: number;
}

export const RiskDot: React.FC<RiskDotProps> = ({
  score,
  showValue = true,
  continueMax = 0.35,
  approveMax = 0.7,
}) => {
  const theme = getRiskScoreTheme(score, continueMax, approveMax);

  return (
    <span className="risk-dot-container">
      <span className="risk-dot" style={{ backgroundColor: theme.dot }} />
      {showValue && (
        <span className="risk-value font-mono" style={{ color: theme.text }}>
          {score.toFixed(2)}
        </span>
      )}
    </span>
  );
};
