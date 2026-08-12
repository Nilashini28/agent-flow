import React, { useEffect, useState } from "react";
import { X, Play } from "./Icons";
import { EngineItem } from "../../types";
import { api } from "../../api/client";

interface LaunchWorkflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLaunch: (task: string, framework: "langgraph" | "autogen") => void;
}

export const LaunchWorkflowModal: React.FC<LaunchWorkflowModalProps> = ({
  isOpen,
  onClose,
  onLaunch,
}) => {
  const [task, setTask] = useState("");
  const [framework, setFramework] = useState<"langgraph" | "autogen">("langgraph");
  const [engines, setEngines] = useState<EngineItem[]>([]);

  useEffect(() => {
    if (isOpen) {
      api.getEngines().then((res) => {
        if (res && res.length > 0) {
          setEngines(res);
        }
      }).catch(() => {
        // Fallback default neutral engines
        setEngines([
          { id: "langgraph", label: "Execution Engine A", description: "", executionPattern: "", inheritsGovernance: true },
          { id: "autogen", label: "Execution Engine B", description: "", executionPattern: "", inheritsGovernance: true },
        ]);
      });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (task.trim()) {
      onLaunch(task.trim(), framework);
      setTask("");
      onClose();
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-content panel">
        <div className="panel-header">
          <h3 className="panel-title">Launch Autonomous Workflow</h3>
          <button className="btn btn-sm btn-ghost" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="panel-body">
          <div className="form-group mb-4">
            <label className="form-label text-xs font-mono mb-1 block">Task Description / Prompt:</label>
            <input
              type="text"
              className="search-input font-mono w-full"
              placeholder="e.g. Perform web search and write summary report to output/summary.txt"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              required
            />
          </div>

          <div className="form-group mb-6">
            <label className="form-label text-xs font-mono mb-1 block">Execution Engine:</label>
            <select
              className="select-input font-mono w-full"
              value={framework}
              onChange={(e) => setFramework(e.target.value as any)}
            >
              {engines.map((eng) => (
                <option key={eng.id} value={eng.id}>
                  {eng.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-3">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              <Play size={14} />
              <span>Launch Workflow</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
