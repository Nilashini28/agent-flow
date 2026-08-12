import React from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  actions,
  meta,
}) => {
  return (
    <div className="page-header">
      <div className="page-header-info">
        <h2 className="page-title">{title}</h2>
        <p className="page-desc">{description}</p>
      </div>
      {(actions || meta) && (
        <div className="page-header-right">
          {meta && <div className="page-header-meta">{meta}</div>}
          {actions && <div className="page-header-actions">{actions}</div>}
        </div>
      )}
    </div>
  );
};
