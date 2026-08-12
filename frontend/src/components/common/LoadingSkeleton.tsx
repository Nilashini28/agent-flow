import React from "react";

interface SkeletonProps {
  height?: string;
  width?: string;
  count?: number;
  className?: string;
}

export const LoadingSkeleton: React.FC<SkeletonProps> = ({
  height = "20px",
  width = "100%",
  count = 1,
  className = "",
}) => {
  return (
    <div className={`skeleton-wrapper ${className}`}>
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="skeleton-pulse"
          style={{ height, width }}
        />
      ))}
    </div>
  );
};
