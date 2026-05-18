import React, { useState } from 'react';
import { StepStatusIcon } from './StepStatusIcon';
import type { AgentStepMessage } from '../types/messages';

interface Props { msg: AgentStepMessage; }

export const StepBubble: React.FC<Props> = ({ msg }) => {
  const [expanded, setExpanded] = useState(false);
  const hasLogs = msg.logs.length > 0 || !!msg.summary;

  return (
    <div className="mb-4 flex justify-start">
      <div className="max-w-prose w-full">
        <p className="text-sm mb-1 text-left text-gray-400">{`SYNAPSE · step ${msg.stepId}`}</p>
        <div
          className="inline-block p-4 rounded-xl shadow-lg bg-gray-800/70 border border-gray-500/60 w-full"
          style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
        >
          <div className="flex items-start gap-2">
            <StepStatusIcon status={msg.status} />
            <span className="text-sm text-gray-100 flex-1">{msg.description}</span>
            {hasLogs && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="text-cyan-300 text-xs px-2 py-0.5 rounded hover:bg-cyan-500/10"
                aria-expanded={expanded}
                aria-label={expanded ? 'Hide step details' : 'Show step details'}
              >
                {expanded ? '▾' : '▸'}
              </button>
            )}
          </div>
          <div className="mt-1 ml-6 flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider bg-cyan-900/40 text-cyan-200 px-2 py-0.5 rounded">
              {msg.intendedTool}
            </span>
          </div>
          {expanded && hasLogs && (
            <div className="mt-3 ml-6 space-y-1">
              {msg.logs.map((log, i) => (
                <div key={i} className="text-xs">
                  <div className="text-gray-200">
                    <span className="text-cyan-300">→</span> {log.prettyLine}
                  </div>
                  {log.raw && (
                    <div className="text-[10px] text-gray-500 truncate pl-3">{log.raw}</div>
                  )}
                </div>
              ))}
              {msg.summary && (
                <div className="text-xs italic text-gray-300 pt-1 border-t border-gray-700/60">
                  {msg.summary}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
