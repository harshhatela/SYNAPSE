import React from 'react';
import { useScrambleEffect } from '../hooks/useScrambleEffect';

interface ScrambledTextProps {
  text: string;
}

export const ScrambledText: React.FC<ScrambledTextProps> = ({ text }) => {
  const scrambledText = useScrambleEffect(text);

  return (
    <pre className="whitespace-pre-wrap font-sans text-left text-gray-100">
      {scrambledText}
    </pre>
  );
};