import { useEffect, useState } from "react";
import { socket } from "../socket";

const COLORS: Record<string, string> = {
  groq: "bg-emerald-500",
  gemini: "bg-blue-500",
  cerebras: "bg-orange-500",
  ollama: "bg-slate-500",
};

const LABELS: Record<string, string> = {
  groq: "Groq · Llama 3.3 70B",
  gemini: "Gemini 2.0 Flash",
  cerebras: "Cerebras · Llama 3.1 70B",
  ollama: "Ollama · Local",
};

export function ModelIndicator() {
  const [provider, setProvider] = useState<string>("auto");

  useEffect(() => {
    socket.on("provider_update", (data: { provider: string }) => {
      setProvider(data.provider ?? "auto");
    });
    return () => { socket.off("provider_update"); };
  }, []);

  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      <div className={`w-2 h-2 rounded-full ${COLORS[provider] ?? "bg-gray-500"}`} />
      <span>{LABELS[provider] ?? "Selecting provider…"}</span>
    </div>
  );
}
