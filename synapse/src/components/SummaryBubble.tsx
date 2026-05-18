import React from 'react';
import { ScrambledText } from './ScrambledText';
import type { AgentSummaryMessage } from '../types/messages';

interface Props { msg: AgentSummaryMessage; }

const stripPlanExecutedHeader = (text: string): string => {
  // Backend's compose_final_answer starts with: "**Plan executed** (n/m steps completed)\n\n"
  const lines = text.split('\n');
  if (lines[0]?.startsWith('**Plan executed**')) {
    let i = 1;
    while (i < lines.length && lines[i].trim() === '') i++;
    return lines.slice(i).join('\n');
  }
  return text;
};

export const SummaryBubble: React.FC<Props> = ({ msg }) => {
  const body = stripPlanExecutedHeader(msg.text);
  const accent = msg.ok ? 'border-l-green-400' : 'border-l-red-400';
  const headerColor = msg.ok ? 'text-green-400' : 'text-red-400';
  const headerGlyph = msg.ok ? '✓' : '✗';
  const headerVerb = msg.ok ? 'Plan complete' : 'Plan failed';

  return (
    <div className="mb-4 flex justify-start">
      <div className="max-w-prose">
        <p className="text-sm mb-1 text-left text-gray-400">{'SYNAPSE'}</p>
        <div
          className={`inline-block p-4 rounded-xl shadow-lg bg-gray-800/70 border border-gray-500/60 border-l-4 ${accent}`}
          style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
        >
          <div className={`font-orbitron text-sm tracking-wider mb-2 ${headerColor}`}>
            {headerGlyph} {headerVerb} ({msg.doneSteps}/{msg.totalSteps})
          </div>
          <ScrambledText text={body} />
        </div>
      </div>
    </div>
  );
};
