import React, { useState } from "react";
import { X, Play } from "./Icons";

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
              <option value="langgraph">Execution Engine A</option>
              <option value="autogen">Execution Engine B</option>
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
