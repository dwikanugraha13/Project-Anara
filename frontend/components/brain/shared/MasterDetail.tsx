"use client";

import React, {
  Children,
  type CSSProperties,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
  useRef,
  useState,
  useEffect,
} from "react";

// Monospace capability pill (tool name, category, etc.)
export function ToolChip({
  children,
  title,
  count,
}: {
  children: ReactNode;
  title?: string;
  count?: number | string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-2 py-0.5 font-mono text-[11px] text-slate-300 border border-white/[0.07] shadow-sm select-none"
      title={title}
    >
      <span>{children}</span>
      {count !== undefined && (
        <span className="text-slate-500 font-semibold tabular-nums">
          ×{typeof count === "number" ? (count >= 1000 ? `${(count / 1000).toFixed(1)}k` : count) : count}
        </span>
      )}
    </span>
  );
}

const SPLIT_MIN_LEFT_PX = 200;
const SPLIT_MIN_RIGHT_PX = 320;
const DEFAULT_LEFT_PX = 270;

export interface MasterDetailProps {
  children: ReactNode;
  pane?: ReactNode;
  resizeId?: string;
  defaultLeftWidth?: number;
}

export function MasterDetail({
  children,
  pane,
  resizeId,
  defaultLeftWidth = DEFAULT_LEFT_PX,
}: MasterDetailProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [leftWidth, setLeftWidth] = useState<number>(() => {
    if (typeof window !== "undefined" && resizeId) {
      const saved = localStorage.getItem(`anara_md_split_${resizeId}`);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= SPLIT_MIN_LEFT_PX) return parsed;
      }
    }
    return defaultLeftWidth;
  });
  const [dragging, setDragging] = useState(false);

  const startSplitDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const grid = gridRef.current;
    if (!grid || event.button !== 0) return;

    event.preventDefault();
    const startX = event.clientX;
    const startWidth = leftWidth;
    const max = Math.max(SPLIT_MIN_LEFT_PX, grid.getBoundingClientRect().width - SPLIT_MIN_RIGHT_PX);
    setDragging(true);

    const onMove = (move: MouseEvent) => {
      const newWidth = Math.round(
        Math.min(max, Math.max(SPLIT_MIN_LEFT_PX, startWidth + (move.clientX - startX)))
      );
      setLeftWidth(newWidth);
      if (resizeId && typeof window !== "undefined") {
        try {
          localStorage.setItem(`anara_md_split_${resizeId}`, String(newWidth));
        } catch {}
      }
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragging(false);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const handleDoubleClick = () => {
    setLeftWidth(defaultLeftWidth);
    if (resizeId && typeof window !== "undefined") {
      try {
        localStorage.removeItem(`anara_md_split_${resizeId}`);
      } catch {}
    }
  };

  const [list, ...rest] = Children.toArray(children);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden relative">
      <div
        ref={gridRef}
        className="flex min-h-0 flex-1 w-full overflow-hidden relative"
      >
        {/* Left List Column */}
        <div
          style={{ width: `${leftWidth}px` }}
          className="h-full shrink-0 flex flex-col border-r border-white/[0.08] bg-[#050811]/90 backdrop-blur-xl overflow-hidden select-none relative"
        >
          {list}
        </div>

        {/* Resizer Vertical Sash */}
        <div
          onPointerDown={startSplitDrag}
          onDoubleClick={handleDoubleClick}
          className="group/vsash relative z-20 w-1.5 -ml-[3px] shrink-0 cursor-col-resize select-none hover:bg-cyan-500/20 transition-colors"
          title="Drag to resize panel, double-click to reset"
        >
          <div
            className={`w-[1px] h-full mx-auto transition-colors ${
              dragging ? "bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)]" : "bg-transparent group-hover/vsash:bg-white/20"
            }`}
          />
        </div>

        {/* Right Detail Column */}
        <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden bg-[#060913]/95 relative">
          {rest}
        </div>
      </div>

      {/* Docked Bottom Drawer (e.g. Monaco/Textarea code editor) */}
      {pane}
    </div>
  );
}

export function ListColumn({
  children,
  header,
}: {
  children: ReactNode;
  header?: ReactNode;
}) {
  return (
    <aside className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {header && <div className="shrink-0 p-2.5 border-b border-white/[0.06]">{header}</div>}
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2 space-y-0.5 custom-scrollbar font-sans">
        {children}
      </div>
    </aside>
  );
}

export function DetailColumn({
  actionBar,
  children,
  footer,
}: {
  actionBar?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-6 custom-scrollbar font-sans">
        <div className="mx-auto max-w-3xl space-y-5">{children}</div>
      </div>
      {footer && (
        <div className="mx-auto w-full max-w-3xl shrink-0 px-6 pb-3 pt-1.5 text-right text-[11px] font-mono text-slate-500">
          {footer}
        </div>
      )}
      {actionBar && (
        <footer className="shrink-0 border-t border-white/[0.08] bg-[#070b16]/95 backdrop-blur-xl px-6 py-3">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-2">{actionBar}</div>
        </footer>
      )}
    </main>
  );
}

export interface CapRowProps {
  title: string;
  subtitle?: ReactNode;
  active: boolean;
  enabled: boolean;
  meta?: ReactNode;
  action?: ReactNode;
  onSelect: () => void;
  onToggle?: (checked: boolean) => void;
  toggleLabel?: string;
  busy?: boolean;
}

export function CapRow({
  title,
  subtitle,
  active,
  enabled,
  meta,
  action,
  onSelect,
  onToggle,
  toggleLabel,
  busy = false,
}: CapRowProps) {
  return (
    <div
      onClick={onSelect}
      className={`group/row flex w-full shrink-0 items-center justify-between rounded-lg px-2.5 transition-all cursor-pointer select-none border ${
        subtitle ? "h-11" : "h-8"
      } ${
        active
          ? "bg-white/[0.08] border-white/[0.14] text-white shadow-sm"
          : "border-transparent text-slate-300 hover:text-white hover:bg-white/[0.04]"
      }`}
    >
      <div className="min-w-0 flex-1 flex flex-col justify-center pr-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            className={`truncate text-xs tracking-tight ${
              enabled ? "font-semibold text-white" : "font-normal text-slate-400"
            }`}
          >
            {title}
          </span>
          {meta !== undefined && meta !== null && (
            <span className="shrink-0 rounded bg-white/[0.05] px-1.5 py-0.2 font-mono text-[10px] text-slate-400 tabular-nums border border-white/[0.04]">
              {meta}
            </span>
          )}
        </div>
        {subtitle && (
          <div className="flex min-w-0 items-center gap-1 text-[10px] text-slate-500 font-sans truncate">
            {subtitle}
          </div>
        )}
      </div>

      {action ? (
        <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
          {action}
        </div>
      ) : onToggle ? (
        <div
          className="shrink-0"
          onClick={(e) => {
            e.stopPropagation();
            if (!busy) onToggle(!enabled);
          }}
          title={toggleLabel || (enabled ? "Disable" : "Enable")}
        >
          <div
            className={`w-8 h-4.5 rounded-full p-0.5 transition-colors duration-200 ease-in-out relative ${
              enabled ? "bg-emerald-500" : "bg-slate-700/80"
            } ${busy ? "opacity-50" : ""}`}
          >
            <div
              className={`w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                enabled ? "translate-x-3.5" : "translate-x-0"
              }`}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function SortButton({
  desc,
  onToggle,
  label = "Usage",
}: {
  desc: boolean;
  onToggle: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10.5px] font-mono text-slate-400 hover:text-white bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] transition-colors cursor-pointer select-none"
      title={`Sort by ${label} (${desc ? "highest first" : "A-Z"})`}
    >
      <span>{label}</span>
      <svg
        className={`w-3 h-3 text-slate-400 transition-transform ${desc ? "rotate-180" : ""}`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </button>
  );
}

export interface DetailPaneProps {
  id: string;
  title: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  onClose?: () => void;
  defaultHeight?: number;
}

export function DetailPane({
  title,
  actions,
  children,
  onClose,
  defaultHeight = 320,
}: DetailPaneProps) {
  const [height, setHeight] = useState(defaultHeight);
  const [dragging, setDragging] = useState(false);

  const startResizeDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const startY = e.clientY;
    const startH = height;
    setDragging(true);

    const onMove = (move: MouseEvent) => {
      const newH = Math.max(140, Math.min(window.innerHeight * 0.75, startH - (move.clientY - startY)));
      setHeight(Math.round(newH));
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setDragging(false);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  return (
    <div
      style={{ height: `${height}px` }}
      className="shrink-0 w-full flex flex-col bg-[#050811] border-t border-white/[0.12] shadow-2xl relative z-30 select-none"
    >
      {/* Top Resize Sash */}
      <div
        onPointerDown={startResizeDrag}
        className="w-full h-1.5 -mt-1 cursor-row-resize absolute top-0 inset-x-0 z-40 group/hsash hover:bg-cyan-500/20 transition-colors"
      >
        <div
          className={`h-[1px] w-full transition-colors ${
            dragging ? "bg-cyan-400" : "bg-transparent group-hover/hsash:bg-white/20"
          }`}
        />
      </div>

      {/* Pane Header */}
      <div className="h-9 px-4 shrink-0 bg-[#070b16] border-b border-white/[0.08] flex items-center justify-between font-mono text-xs">
        <div className="flex items-center gap-2 font-semibold text-white truncate">{title}</div>
        <div className="flex items-center gap-2">
          {actions}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              title="Close drawer"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Pane Content */}
      <div className="flex-1 min-h-0 overflow-hidden relative">{children}</div>
    </div>
  );
}
