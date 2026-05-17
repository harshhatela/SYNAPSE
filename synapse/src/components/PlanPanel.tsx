import React from 'react';
import { StepStatusIcon, type StepStatus } from './StepStatusIcon';

export interface PlanStep {
  step_id: number;
  description: string;
  intended_tool: string;
  success_criteria: string;
}

export interface Plan {
  steps: PlanStep[];
  reasoning: string;
}

interface Props {
  plan: Plan | null;
  statuses: Record<number, { status: StepStatus; message?: string }>;
}

export const PlanPanel: React.FC<Props> = ({ plan, statuses }) => {
  if (!plan) {
    return (
      <div className="p-4 text-xs text-gray-500 uppercase tracking-widest">
        No plan yet — send a multi-step command to generate one.
      </div>
    );
  }

  return (
    <div className="p-4 overflow-y-auto h-full">
      <h2 className="font-orbitron text-cyan-400 text-sm tracking-widest mb-3">
        PLAN
      </h2>
      <p className="text-xs text-gray-400 mb-4 italic">{plan.reasoning}</p>
      <ol className="space-y-3">
        {plan.steps.map((step) => {
          const st = statuses[step.step_id]?.status ?? 'pending';
          const msg = statuses[step.step_id]?.message;
          return (
            <li
              key={step.step_id}
              className="border-l-2 border-cyan-500/30 pl-3 py-1"
            >
              <div className="flex items-start gap-2">
                <StepStatusIcon status={st} />
                <span className="text-xs text-gray-500 mt-0.5">
                  {step.step_id}.
                </span>
                <span className="text-sm text-gray-100 flex-1">
                  {step.description}
                </span>
              </div>
              <div className="mt-1 ml-6 flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider bg-cyan-900/40 text-cyan-200 px-2 py-0.5 rounded">
                  {step.intended_tool}
                </span>
                {msg && (
                  <span className="text-[10px] text-gray-400 truncate">{msg}</span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
};
