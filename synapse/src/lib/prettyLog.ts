export type LogPhase = 'running' | 'done';

const MAX_CMD = 50;

const truncate = (s: string, max: number): string =>
  s.length > max ? s.slice(0, max - 1) + '…' : s;

export function prettyLog(tool: string, phase: LogPhase, payload?: string): string {
  const cmd = (payload ?? '').trim();

  switch (tool) {
    case 'RunDockerCommand':
      if (phase === 'done') return 'Docker command finished';
      if (!cmd) return 'Running Docker: (no input)';
      if (/^\s*ps\b/.test(cmd)) return 'Listing Docker containers...';
      return `Running Docker: ${truncate(cmd, MAX_CMD)}`;

    case 'RunShellCommand':
      if (phase === 'done') return 'Server command finished';
      return `Running on the server: ${truncate(cmd, MAX_CMD)}`;

    case 'RunPowerShellCommand':
      if (phase === 'done') return 'PowerShell command finished';
      return `Running PowerShell: ${truncate(cmd, MAX_CMD)}`;

    case 'RunKubectlCommand':
      if (phase === 'done') return 'kubectl command finished';
      return `kubectl: ${truncate(cmd, MAX_CMD)}`;

    case 'RunAWSCommand':
      if (phase === 'done') return 'AWS command finished';
      return `AWS: ${truncate(cmd, MAX_CMD)}`;

    case 'CreateRemoteFile':
      return phase === 'done'
        ? 'File written on the server'
        : 'Writing a file on the server...';

    case 'SendEmailNotification':
    case 'SendSMSNotification':
    case 'SendTelegramNotification':
      return phase === 'done' ? 'Notification sent' : 'Sending notification...';

    case 'TrainStartupModel':
      return phase === 'done' ? 'Model trained' : 'Training the model...';

    case 'GitHubActions':
      return phase === 'done' ? 'GitHub Actions call finished' : 'Talking to GitHub Actions...';

    default:
      if (phase === 'done') return `${tool} finished`;
      return cmd ? `${tool}: ${truncate(cmd, MAX_CMD)}` : `${tool}...`;
  }
}
