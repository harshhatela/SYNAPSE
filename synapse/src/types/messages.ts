import type { StepStatus } from '../components/StepStatusIcon';

export type StepLog = {
  tool: string;
  phase: 'running' | 'done';
  raw?: string;
  prettyLine: string;
};

export type UserMessage = {
  kind: 'user';
  id: string;
  text: string;
};

export type AgentTextMessage = {
  kind: 'agent-text';
  id: string;
  text: string;
  streaming?: boolean;
};

export type AgentStepMessage = {
  kind: 'agent-step';
  id: string;
  requestId: string;
  stepId: number;
  description: string;
  intendedTool: string;
  status: StepStatus;
  logs: StepLog[];
  summary?: string;
};

export type AgentSummaryMessage = {
  kind: 'agent-summary';
  id: string;
  requestId: string;
  text: string;
  totalSteps: number;
  doneSteps: number;
  ok: boolean;
};

export type Message =
  | UserMessage
  | AgentTextMessage
  | AgentStepMessage
  | AgentSummaryMessage;
