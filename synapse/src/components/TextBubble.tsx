import React from 'react';
import { ScrambledText } from './ScrambledText';
import type { AgentTextMessage } from '../types/messages';

interface Props { msg: AgentTextMessage; }

export const TextBubble: React.FC<Props> = ({ msg }) => (
  <div className="mb-4 flex justify-start">
    <div className="max-w-prose">
      <p className="text-sm mb-1 text-left text-gray-400">{'SYNAPSE'}</p>
      <div
        className="inline-block p-4 rounded-xl shadow-lg bg-gray-800/70 border border-gray-500/60"
        style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
      >
        <ScrambledText text={msg.text} />
      </div>
    </div>
  </div>
);
