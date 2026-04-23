import React, { useState } from 'react';

interface InputBarProps {
  onSendMessage: (message: string) => void;
}

export const InputBar: React.FC<InputBarProps> = ({ onSendMessage }) => {
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (inputValue.trim()) {
      onSendMessage(inputValue);
      setInputValue('');
    }
  };

  return (
    <div className="p-4 border-t border-cyan-500/20 bg-black/30" style={{ backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Command your agent..."
          className="w-full p-3 bg-gray-900/50 border border-gray-600 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 transition-all duration-300"
        />
      </form>
    </div>
  );
};