import React from 'react';
import type { UserMessage } from '../types/messages';

interface Props { msg: UserMessage; }

export const UserBubble: React.FC<Props> = ({ msg }) => (
  <div className="mb-4 flex justify-end">
    <div className="max-w-prose">
      <p className="text-sm mb-1 text-right text-gray-400">{'You'}</p>
      <div
        className="inline-block p-4 rounded-xl shadow-lg bg-blue-600/60 border border-blue-500/70"
        style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
      >
        <p className="font-sans text-left text-white">{msg.text}</p>
      </div>
    </div>
  </div>
);
