import React, { useEffect, useState } from 'react';
import { PlanPanel, type Plan } from './PlanPanel';
import type { StepStatus } from './StepStatusIcon';

interface Props {
  plan: Plan | null;
  statuses: Record<number, { status: StepStatus; message?: string }>;
}

export const PlanDrawer: React.FC<Props> = ({ plan, statuses }) => {
  const [open, setOpen] = useState(false);
  const runningCount = Object.values(statuses).filter((s) => s.status === 'running').length;
  const totalCount = plan?.steps.length ?? 0;
  const badge = plan && totalCount > 0
    ? `${Object.values(statuses).filter((s) => s.status === 'done').length}/${totalCount}`
    : null;

  // Close on Escape when open
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="fixed left-0 top-1/2 -translate-y-1/2 z-20 bg-black/60 border border-cyan-500/30 text-cyan-300 rounded-r-md px-2 py-3 text-xs uppercase tracking-widest hover:bg-cyan-500/10"
        aria-expanded={open}
        aria-controls="plan-drawer-panel"
        aria-label={open ? 'Hide plan panel' : 'Show plan panel'}
      >
        <div className="flex flex-col items-center gap-1">
          <span>{open ? '◀' : '▶'}</span>
          <span className="[writing-mode:vertical-rl] rotate-180">PLAN</span>
          {badge && <span className="text-[10px] text-cyan-200">{badge}</span>}
          {runningCount > 0 && <span className="text-[10px] text-cyan-200 animate-pulse">●</span>}
        </div>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-10 bg-black/30"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <aside
            id="plan-drawer-panel"
            className="fixed left-0 top-0 bottom-0 z-20 w-80 border-r border-cyan-500/20 bg-black/80 backdrop-blur-sm overflow-y-auto"
          >
            <PlanPanel plan={plan} statuses={statuses} />
          </aside>
        </>
      )}
    </>
  );
};
