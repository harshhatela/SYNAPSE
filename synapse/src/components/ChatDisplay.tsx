import React, { useEffect, useRef } from 'react';
import { TypingIndicator } from './TypingIndicator';
import { ScrambledText } from './ScrambledText';

export interface Message {
  user: 'You' | 'Agent';
  text: string;
}

interface ChatDisplayProps {
  messages: Message[];
  isTyping: boolean;
}

export const ChatDisplay: React.FC<ChatDisplayProps> = ({ messages, isTyping }) => {
  const endOfMessagesRef = useRef<null | HTMLDivElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  return (
    <div className="flex-1 p-4 overflow-y-auto">
      {messages.map((msg, index) => (
        <div key={index} className={`mb-4 flex ${msg.user === 'You' ? 'justify-end' : 'justify-start'}`}>
          <div className="max-w-prose">
            <p className={`text-sm mb-1 ${msg.user === 'You' ? 'text-right' : 'text-left'} text-gray-400`}>
              {msg.user}
            </p>
            <div
              className={`inline-block p-4 rounded-xl shadow-lg
                ${msg.user === 'You'
                  ? 'bg-blue-600/30 border border-blue-500/50'
                  : 'bg-gray-700/30 border border-gray-500/50'
                }`}
              style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
            >
              {msg.user === 'Agent' ? (
                <ScrambledText text={msg.text} />
              ) : (
                // This is the line that has been changed
                <p className="font-orbitron text-left text-gray-100">{msg.text}</p>
              )}
            </div>
          </div>
        </div>
      ))}
      {isTyping && (
        <div className="mb-4">
          <div
            className="inline-block p-4 rounded-lg shadow-lg bg-gray-700/30 border border-gray-500/50"
            style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
          >
            <TypingIndicator />
          </div>
        </div>
      )}
      <div ref={endOfMessagesRef} />
    </div>
  );
};
