import React from 'react';

export type StepStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'retry'
  | 'replanned';

const STYLES: Record<StepStatus, { glyph: string; cls: string }> = {
  pending:    { glyph: '○', cls: 'text-gray-500' },
  running:    { glyph: '◐', cls: 'text-cyan-300 animate-pulse' },
  done:       { glyph: '✓', cls: 'text-green-400' },
  failed:     { glyph: '✗', cls: 'text-red-400' },
  retry:      { glyph: '↻', cls: 'text-amber-300' },
  replanned:  { glyph: '★', cls: 'text-purple-400' },
};

interface Props { status: StepStatus; }

export const StepStatusIcon: React.FC<Props> = ({ status }) => {
  const s = STYLES[status] ?? STYLES.pending;
  return <span className={`font-mono text-sm ${s.cls}`}>{s.glyph}</span>;
};
