import { useEffect, useState } from "react";
import { socket } from "../socket";

const COLORS: Record<string, string> = {
  groq: "bg-emerald-500",
  groq_2: "bg-emerald-400",
  groq_3: "bg-emerald-300",
  groq_4: "bg-emerald-300",
  groq_5: "bg-emerald-300",
  gemini: "bg-blue-500",
  gemini_2: "bg-blue-400",
  gemini_3: "bg-blue-300",
  gemini_4: "bg-blue-300",
  gemini_5: "bg-blue-300",
  cerebras: "bg-orange-500",
  ollama: "bg-slate-500",
  ollama_1: "bg-slate-500",
  ollama_2: "bg-slate-400",
};

const LABELS: Record<string, string> = {
  groq: "Groq · Llama 3.3 70B (key 1)",
  groq_2: "Groq · Llama 3.3 70B (key 2)",
  groq_3: "Groq · Llama 3.3 70B (key 3)",
  groq_4: "Groq · Llama 3.3 70B (key 4)",
  groq_5: "Groq · Llama 3.3 70B (key 5)",
  gemini: "Gemini 2.5 Flash (key 1)",
  gemini_2: "Gemini 2.5 Flash (key 2)",
  gemini_3: "Gemini 2.5 Flash (key 3)",
  gemini_4: "Gemini 2.5 Flash (key 4)",
  gemini_5: "Gemini 2.5 Flash (key 5)",
  cerebras: "Cerebras · Llama 3.1 70B",
  ollama: "Ollama · Local",
  ollama_1: "Ollama · Local 1",
  ollama_2: "Ollama · Local 2",
};

export function ModelIndicator() {
  const [provider, setProvider] = useState<string>("auto");
  const [status, setStatus] = useState<string>("idle");

  useEffect(() => {
    const onProviderUpdate = (data: { provider: string; status?: string }) => {
      setProvider(data.provider ?? "auto");
      setStatus(data.status ?? "active");
    };
    socket.on("provider_update", onProviderUpdate);
    return () => { socket.off("provider_update", onProviderUpdate); };
  }, []);

  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      <div className={`w-2 h-2 rounded-full ${COLORS[provider] ?? "bg-gray-500"}`} />
      <span>
        {LABELS[provider] ?? "Selecting provider..."}
        {status === "rate_limited" ? " · rate limited" : ""}
      </span>
    </div>
  );
}
