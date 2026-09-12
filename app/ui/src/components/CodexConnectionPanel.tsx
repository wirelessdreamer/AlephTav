import { useState } from 'react';

import {
  useCancelCodexRun,
  useCodexModels,
  useCodexStatus,
  useConnectCodex,
  useCodexLogin,
  useCreateCodexSession,
  useSaveCodexCandidates,
  useStartCodexTurn,
} from '../hooks/useCodex';
import type { CodexRun, CodexStatusValue } from '../types';

const QUICK_ACTIONS: Array<{ label: string; layer: string; constraints: string[] }> = [
  { label: 'Create a literal translation', layer: 'literal', constraints: ['direct translation'] },
  {
    label: 'Create direct 6/8 lyric candidates',
    layer: 'metered_lyric',
    constraints: ['direct translation', 'do not force call-and-response'],
  },
  {
    label: 'Explain accuracy and liberties',
    layer: 'lyric',
    constraints: ['explain accuracy and creative liberties verse by verse'],
  },
  {
    label: 'Revise this line while preserving Hebrew imagery',
    layer: 'lyric',
    constraints: ['preserve Hebrew imagery', 'preserve divine-name policy'],
  },
];

/** Messages shown when Codex cannot be used, per the failure table. */
const UNAVAILABLE_DETAIL: Partial<Record<CodexStatusValue, string>> = {
  not_installed:
    'Codex is not installed on this computer. Install the Codex CLI, or keep using the local model providers.',
  not_signed_in:
    'Codex is installed but not signed in. Sign in through Codex itself — AlephTav never asks for an API key or a session token.',
  error: 'The local Codex app server reported an error. Other local providers remain usable.',
};

interface Props {
  psalmId: string | null;
  unitId: string | null;
}

export function CodexConnectionPanel({ psalmId, unitId }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [run, setRun] = useState<CodexRun | null>(null);
  const [model, setModel] = useState('');

  const { data: status } = useCodexStatus();
  const ready = status?.status === 'ready';
  const { data: models } = useCodexModels(Boolean(ready));
  const connect = useConnectCodex();
  const login = useCodexLogin();
  const createSession = useCreateCodexSession();
  const startTurn = useStartCodexTurn();
  const cancelRun = useCancelCodexRun();
  const saveCandidates = useSaveCodexCandidates();

  async function runQuickAction(layer: string, constraints: string[]) {
    if (!psalmId || !unitId) return;
    let activeSession = sessionId;
    if (!activeSession) {
      const session = await createSession.mutateAsync({
        psalm_id: psalmId,
        unit_id: unitId,
        layer,
        model,
      });
      activeSession = session.session_id;
      setSessionId(activeSession);
    }
    const result = await startTurn.mutateAsync({
      sessionId: activeSession,
      unit_id: unitId,
      layer,
      constraints,
    });
    setRun(result);
  }

  return (
    <section className="codex-panel" aria-label="Codex provider">
      <header className="codex-header">
        <h3>Codex</h3>
        <span className={`codex-status codex-status-${status?.status ?? 'unknown'}`}>
          {status?.status ?? 'checking…'}
        </span>
      </header>

      <p className="codex-detail">{status?.detail}</p>
      {status && UNAVAILABLE_DETAIL[status.status] && (
        <p className="codex-unavailable">{UNAVAILABLE_DETAIL[status.status]}</p>
      )}

      {status?.status === 'available' && (
        <button type="button" onClick={() => connect.mutate()} disabled={connect.isPending}>
          Connect Codex
        </button>
      )}
      {status?.status === 'not_signed_in' && (
        <button type="button" onClick={() => login.mutate()} disabled={login.isPending}>
          Sign in with ChatGPT through Codex
        </button>
      )}

      {ready && (
        <>
          <dl className="codex-account">
            <dt>Authentication</dt>
            <dd>{status?.auth_mode ?? 'chatgpt'}</dd>
            {status?.plan_type && (
              <>
                <dt>Plan</dt>
                <dd>{status.plan_type}</dd>
              </>
            )}
            <dt>Session</dt>
            <dd>{sessionId ?? 'not started'}</dd>
          </dl>

          <label className="codex-model">
            Model
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              <option value="">Codex default</option>
              {(models ?? []).map((item, index) => {
                const value = String(item.id ?? item.model ?? index);
                return (
                  <option key={value} value={value}>
                    {String(item.displayName ?? value)}
                  </option>
                );
              })}
            </select>
          </label>

          <div className="codex-actions">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                type="button"
                disabled={!unitId || startTurn.isPending}
                onClick={() => runQuickAction(action.layer, action.constraints)}
              >
                {action.label}
              </button>
            ))}
          </div>

          {startTurn.isPending && <p className="codex-progress">Generating…</p>}

          {run && (
            <div className="codex-run">
              <p>
                Run {run.run_id} — <strong>{run.status}</strong>
              </p>

              {run.status === 'running' && (
                <button type="button" onClick={() => cancelRun.mutate(run.run_id)}>
                  Stop generation
                </button>
              )}

              {run.status === 'invalid_output' && (
                <div className="codex-validation" role="alert">
                  <p>{run.error}</p>
                  <ul>
                    {(run.validation ?? []).map((item) => (
                      <li key={`${item.path}:${item.message}`}>
                        {item.path}: {item.message}
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={() => runQuickAction(run.layer, ['retry with valid JSON'])}
                  >
                    Retry
                  </button>
                </div>
              )}

              {run.denied_events.length > 0 && (
                <p className="codex-denied" role="alert">
                  Translation mode does not permit system changes. Denied{' '}
                  {run.denied_events.length} request(s):{' '}
                  {run.denied_events.map((event) => event.method).join(', ')}
                </p>
              )}

              {run.status === 'completed' && (
                <button
                  type="button"
                  onClick={() => saveCandidates.mutate({ runId: run.run_id })}
                  disabled={saveCandidates.isPending}
                >
                  Save candidates as proposed
                </button>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default CodexConnectionPanel;
