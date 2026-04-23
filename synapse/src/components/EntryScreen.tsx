import React from 'react';

interface EntryScreenProps {
  onEnter: () => void;
}

export const EntryScreen: React.FC<EntryScreenProps> = ({ onEnter }) => {
  return (
    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#020418] animate-fade-in">
      <div className="text-center">
        <h1 className="font-orbitron text-7xl md:text-9xl font-bold text-cyan-400 drop-shadow-[0_0_15px_rgba(0,255,255,0.7)]">
          SYNAPSE
        </h1>
        <p className="text-gray-400 mt-4 text-sm md:text-base tracking-widest">
          Systemic Nexus of Adaptive Processing & Self-Execution
        </p>
        <button
          onClick={onEnter}
          className="mt-12 font-orbitron text-lg border-2 border-cyan-400 text-cyan-400 px-8 py-3 rounded-lg hover:bg-cyan-400 hover:text-black transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,255,0.5)]"
        >
          [ ENTER ]
        </button>
      </div>
    </div>
  );
};