import React from "react";

interface IconProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

const baseProps = (size = 18, className = "", style?: React.CSSProperties) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  className,
  style,
});

export const LayoutDashboard: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <rect x="3" y="3" width="7" height="9" />
    <rect x="14" y="3" width="7" height="5" />
    <rect x="14" y="12" width="7" height="9" />
    <rect x="3" y="16" width="7" height="5" />
  </svg>
);

export const Users: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

export const GitMerge: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <circle cx="18" cy="18" r="3" />
    <circle cx="6" cy="6" r="3" />
    <path d="M6 21V9a9 9 0 0 0 9 9" />
  </svg>
);

export const History: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M12 7v5l4 2" />
  </svg>
);

export const ShieldAlert: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

export const Key: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
  </svg>
);

export const Box: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />
  </svg>
);

export const CheckSquare: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="9 11 12 14 22 4" />
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
  </svg>
);

export const FileText: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

export const BarChart3: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

export const Activity: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);

export const Play: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

export const Sparkles: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3z" />
  </svg>
);

export const Check: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export const X: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export const ChevronDown: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

export const ChevronUp: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="18 15 12 9 6 15" />
  </svg>
);

export const AlertTriangle: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

export const Search: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

export const Plus: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

export const RotateCcw: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
  </svg>
);

export const CheckCircle: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

export const CheckCircle2: React.FC<IconProps> = CheckCircle;

export const ShieldOff: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M19.69 14a6.9 6.9 0 0 0 .31-2V5l-8-3-3.11 1.17" />
    <path d="M4.73 4.73 4 5v7c0 6 8 10 8 10a20.29 20.29 0 0 0 5.62-4.38" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

export const Lock: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

export const ArrowRight: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </svg>
);

export const Cpu: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
    <rect x="9" y="9" width="6" height="6" />
    <line x1="9" y1="1" x2="9" y2="4" />
    <line x1="15" y1="1" x2="15" y2="4" />
    <line x1="9" y1="20" x2="9" y2="23" />
    <line x1="15" y1="20" x2="15" y2="23" />
    <line x1="20" y1="9" x2="23" y2="9" />
    <line x1="20" y1="15" x2="23" y2="15" />
    <line x1="1" y1="9" x2="4" y2="9" />
    <line x1="1" y1="15" x2="4" y2="15" />
  </svg>
);

export const Shield: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

export const Wrench: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </svg>
);

export const Zap: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

export const ShieldCheck: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <polyline points="9 12 11 14 15 10" />
  </svg>
);

export const Code: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="16 18 22 12 16 6" />
    <polyline points="8 6 2 12 8 18" />
  </svg>
);

export const Sliders: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <line x1="4" y1="21" x2="4" y2="14" />
    <line x1="4" y1="10" x2="4" y2="3" />
    <line x1="12" y1="21" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12" y2="3" />
    <line x1="20" y1="21" x2="20" y2="16" />
    <line x1="20" y1="12" x2="20" y2="3" />
    <line x1="1" y1="14" x2="7" y2="14" />
    <line x1="9" y1="8" x2="15" y2="8" />
    <line x1="17" y1="16" x2="23" y2="16" />
  </svg>
);

export const Save: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </svg>
);

export const Network: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <rect x="9" y="2" width="6" height="6" rx="1" />
    <rect x="16" y="16" width="6" height="6" rx="1" />
    <rect x="2" y="16" width="6" height="6" rx="1" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="5" y1="12" x2="19" y2="12" />
    <line x1="5" y1="12" x2="5" y2="16" />
    <line x1="19" y1="12" x2="19" y2="16" />
  </svg>
);

export const RefreshCw: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

export const HardDrive: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <line x1="22" y1="12" x2="2" y2="12" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    <line x1="6" y1="16" x2="6.01" y2="16" />
    <line x1="10" y1="16" x2="10.01" y2="16" />
  </svg>
);

export const Terminal: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="4 17 10 11 4 5" />
    <line x1="12" y1="19" x2="20" y2="19" />
  </svg>
);

export const Inbox: React.FC<IconProps> = ({ size, className, style }) => (
  <svg {...baseProps(size, className, style)}>
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </svg>
);
