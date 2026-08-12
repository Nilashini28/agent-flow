import React, { useState } from "react";
import { AuditEvent } from "../../types";
import { PageHeader } from "../common/PageHeader";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { EmptyState } from "../common/EmptyState";
import { Search, FileText, Code } from "../common/Icons";

interface AuditPageProps {
  events: AuditEvent[] | null;
  total: number;
  isLoading: boolean;
  onFilterChange: (category: string, query: string) => void;
}

const CATEGORIES = ["all", "node_start", "node_complete", "sandbox_dispatch", "checkpoint_saved", "escalation_decision"];

export const AuditPage: React.FC<AuditPageProps> = ({
  events,
  total,
  isLoading,
  onFilterChange,
}) => {
  const [selectedCat, setSelectedCat] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const handleCatChange = (cat: string) => {
    setSelectedCat(cat);
    onFilterChange(cat, searchQuery);
  };

  const handleSearchChange = (q: string) => {
    setSearchQuery(q);
    onFilterChange(selectedCat, q);
  };

  if (isLoading && !events) {
    return (
      <div className="page-container">
        <PageHeader
          title="System Audit & Traces Log"
          description="Replayable, structured event log for compliance, debugging, and auditability."
        />
        <LoadingSkeleton height="60px" count={5} />
      </div>
    );
  }

  const hasEvents = events !== null && events.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="System Audit & Traces Log"
        description="Replayable, structured event log for compliance, debugging, and auditability."
        meta={
          <span className="font-mono text-xs text-muted">
            Total Logged Events: {total}
          </span>
        }
      />

      {/* Filter & Search Controls */}
      <div className="filter-bar mb-4">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input font-mono"
            placeholder="Filter by ref ID, description, category..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>

        <div className="status-filter-pills">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => handleCatChange(cat)}
              className={`filter-pill ${selectedCat === cat ? "active" : ""}`}
            >
              {cat.replace(/_/g, " ").toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Events List */}
      {!hasEvents ? (
        <EmptyState
          title="No Audit Events Found"
          description="No telemetry events match the filter parameters."
          icon={<FileText size={36} />}
        />
      ) : (
        <div className="audit-events-list flex flex-col gap-2">
          {events.map((evt, idx) => (
            <div key={idx} className="panel audit-event-row p-3">
              <div className="flex items-center justify-between font-mono text-xs mb-1">
                <div className="flex items-center gap-3">
                  <span className="text-muted">{evt.timestamp}</span>
                  <span className="text-primary font-semibold">{evt.category}</span>
                </div>
                <span className="text-muted">Ref: {evt.refId.slice(0, 12)}</span>
              </div>
              <p className="text-sm font-medium">{evt.description}</p>
              {evt.payload && Object.keys(evt.payload).length > 0 && (
                <div className="mt-2 text-xs font-mono bg-near-black p-2 rounded text-muted">
                  <Code size={12} className="inline mr-1" />
                  {JSON.stringify(evt.payload)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
