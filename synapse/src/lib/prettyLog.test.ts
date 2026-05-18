import { describe, it, expect } from 'vitest';
import { prettyLog } from './prettyLog';

describe('prettyLog', () => {
  it('describes RunDockerCommand running with a command', () => {
    expect(prettyLog('RunDockerCommand', 'running', 'ps -a'))
      .toBe('Listing Docker containers...');
  });

  it('describes RunDockerCommand running with an unknown command', () => {
    expect(prettyLog('RunDockerCommand', 'running', 'inspect abc'))
      .toBe('Running Docker: inspect abc');
  });

  it('describes RunDockerCommand done', () => {
    expect(prettyLog('RunDockerCommand', 'done', 'some output'))
      .toBe('Docker command finished');
  });

  it('describes RunShellCommand running', () => {
    expect(prettyLog('RunShellCommand', 'running', 'cat /etc/os-release'))
      .toBe('Running on the server: cat /etc/os-release');
  });

  it('truncates very long RunShellCommand commands', () => {
    const long = 'a'.repeat(120);
    expect(prettyLog('RunShellCommand', 'running', long).length)
      .toBeLessThanOrEqual(80);
  });

  it('describes RunShellCommand done', () => {
    expect(prettyLog('RunShellCommand', 'done'))
      .toBe('Server command finished');
  });

  it('describes RunPowerShellCommand running', () => {
    expect(prettyLog('RunPowerShellCommand', 'running', 'Get-Process'))
      .toBe('Running PowerShell: Get-Process');
  });

  it('describes RunKubectlCommand running', () => {
    expect(prettyLog('RunKubectlCommand', 'running', 'get pods'))
      .toBe('kubectl: get pods');
  });

  it('describes RunAWSCommand running', () => {
    expect(prettyLog('RunAWSCommand', 'running', 's3 ls'))
      .toBe('AWS: s3 ls');
  });

  it('describes CreateRemoteFile running', () => {
    expect(prettyLog('CreateRemoteFile', 'running'))
      .toBe('Writing a file on the server...');
  });

  it('describes notifications done', () => {
    expect(prettyLog('SendEmailNotification', 'done')).toBe('Notification sent');
    expect(prettyLog('SendSMSNotification', 'done')).toBe('Notification sent');
    expect(prettyLog('SendTelegramNotification', 'done')).toBe('Notification sent');
  });

  it('describes TrainStartupModel running', () => {
    expect(prettyLog('TrainStartupModel', 'running'))
      .toBe('Training the model...');
  });

  it('describes GitHubActions running', () => {
    expect(prettyLog('GitHubActions', 'running'))
      .toBe('Talking to GitHub Actions...');
  });

  it('falls back to a generic line for unknown tools', () => {
    expect(prettyLog('SomeUnknownTool', 'running', 'foo bar'))
      .toBe('SomeUnknownTool: foo bar');
  });

  it('falls back without a payload for unknown tools', () => {
    expect(prettyLog('SomeUnknownTool', 'done'))
      .toBe('SomeUnknownTool finished');
  });

  it('handles undefined payload gracefully', () => {
    expect(prettyLog('RunDockerCommand', 'running'))
      .toBe('Running Docker: (no input)');
  });
});
