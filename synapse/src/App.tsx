import { useState, useEffect } from 'react';
import { socket } from './socket';
import { ChatDisplay } from './components/ChatDisplay';
import type { Message } from './components/ChatDisplay';
import { InputBar } from './components/InputBar';
import { EntryScreen } from './components/EntryScreen';
import { ParticleBackground } from './components/ParticleBackground';

function App() {
  const [showEntryScreen, setShowEntryScreen] = useState(true);
  const [isConnected, setIsConnected] = useState(socket.connected);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  const handleSendMessage = (message: string) => {
    if (message.trim() === '') return;
    socket.emit('execute_natural_command', { command: message });
    setMessages(prev => [...prev, { text: message, user: 'You' }]);
    setIsTyping(true);
  };

  useEffect(() => {
    function onConnect() { setIsConnected(true); }
    function onDisconnect() { setIsConnected(false); }
    function onCommandOutput(data: { data: string }) {
      setIsTyping(false);
      setMessages(prev => [...prev, { text: data.data, user: 'SYNAPSE' }]);
    }

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('command_output', onCommandOutput);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('command_output', onCommandOutput);
    };
  }, []);

  return (
    <>
      <ParticleBackground />
      {showEntryScreen ? (
        <EntryScreen onEnter={() => setShowEntryScreen(false)} />
      ) : (
        <div className="flex flex-col h-screen bg-transparent text-gray-200 animate-fade-in">
          <header className="p-4 text-center border-b border-cyan-500/20 bg-black/30 backdrop-blur-sm">
            <h1 className="font-orbitron text-2xl font-bold text-cyan-400 drop-shadow-[0_0_8px_rgba(0,255,255,0.6)]">
              S Y N A P S E
            </h1>
            <p className={`text-xs uppercase tracking-widest ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
              {isConnected ? '● SYSTEM ONLINE' : '● CONNECTION LOST'}
            </p>
          </header>
          <ChatDisplay messages={messages} isTyping={isTyping} />
          <InputBar onSendMessage={handleSendMessage} />
        </div>
      )}
    </>
  );
}

export default App;
