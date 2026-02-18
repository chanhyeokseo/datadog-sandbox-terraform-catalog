import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { dangerZoneApi, DangerZoneStatus } from '../services/api';
import ConfirmModal from './ConfirmModal';
import '../styles/DangerZone.css';

interface DangerZoneModalProps {
  onClose: () => void;
  onResourcesNeedRefresh?: () => void;
}

const DangerZoneModal = ({ onClose, onResourcesNeedRefresh }: DangerZoneModalProps) => {
  const [status, setStatus] = useState<DangerZoneStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [destroying, setDestroying] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [log, setLog] = useState('');
  const [resetDone, setResetDone] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<'destroy' | 'reset' | null>(null);
  const logRef = useRef<HTMLPreElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const s = await dangerZoneApi.getStatus();
      setStatus(s);
    } catch (err) {
      console.error('Failed to fetch danger zone status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    return () => { abortRef.current?.abort(); };
  }, [fetchStatus]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  const handleDestroyAll = async () => {
    setPendingConfirm(null);
    setDestroying(true);
    setLog('');
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await dangerZoneApi.streamDestroyAll(
        (chunk) => setLog((prev) => prev + chunk),
        async (success) => {
          abortRef.current = null;
          setDestroying(false);
          if (success && onResourcesNeedRefresh) onResourcesNeedRefresh();
          await fetchStatus();
        },
        controller.signal,
      );
    } catch (err) {
      setLog((prev) => prev + `\nError: ${err}\n`);
      setDestroying(false);
    }
  };

  const handleHardReset = async () => {
    setPendingConfirm(null);
    setResetting(true);
    setLog('');

    try {
      const result = await dangerZoneApi.hardReset();
      let output = `Hard Reset ${result.success ? 'completed' : 'completed with errors'}.\n\n`;
      for (const [key, detail] of Object.entries(result.details)) {
        output += `[${detail.success ? 'OK' : 'FAIL'}] ${key}\n`;
        for (const action of detail.actions) {
          output += `  - ${action}\n`;
        }
        if (detail.error) output += `  Error: ${detail.error}\n`;
        output += '\n';
      }
      setLog(output);
      setResetDone(true);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = ax.response?.data?.detail ?? ax.message ?? String(err);
      setLog(`Hard Reset failed: ${msg}\n`);
    } finally {
      setResetting(false);
    }
  };

  const busy = destroying || resetting;

  return createPortal(
    <div className="modal-overlay" onClick={busy ? undefined : onClose}>
      <div className="danger-zone-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="danger-zone-title">Danger Zone</h3>

        <div className="danger-zone-warning">
          These actions are irreversible. Proceed with extreme caution.
        </div>

        <div className="danger-zone-section">
          <p className="danger-zone-section-title">Destroy All Resources</p>
          <p className="danger-zone-section-desc">
            Run <code>terraform destroy</code> on every active resource sequentially.
            {status && status.enabled_count > 0 && (
              <> Currently <strong>{status.enabled_count}</strong> resource(s) active.</>
            )}
            {status && status.enabled_count === 0 && ' No active resources.'}
          </p>
          <div className="danger-zone-btn-row">
            <button
              className="danger-zone-btn destroy-all"
              disabled={busy || loading || (status?.enabled_count === 0)}
              onClick={() => setPendingConfirm('destroy')}
            >
              {destroying ? 'Destroying...' : 'Destroy All Resources'}
            </button>
          </div>
        </div>

        <div className="danger-zone-divider" />

        <div className="danger-zone-section">
          <p className="danger-zone-section-title">
            Hard Reset
            {status && (
              <span className={`danger-zone-status-badge ${status.hard_reset_available ? 'available' : 'blocked'}`}>
                {status.hard_reset_available ? 'Available' : 'Blocked'}
              </span>
            )}
          </p>
          <p className="danger-zone-section-desc">
            {status?.hard_reset_available
              ? 'Remove all user-scoped cloud & local data:'
              : 'Destroy all resources first to enable Hard Reset.'}
          </p>
          {status?.hard_reset_available && (
            <ul className="danger-zone-reset-list">
              <li>SSH PEM key files (local + AWS EC2 Key Pair)</li>
              <li>S3 bucket (Terraform state)</li>
              <li>Parameter Store parameters</li>
              <li>DynamoDB table (state locks)</li>
              <li>Local terraform-data directory (full reset to onboarding)</li>
            </ul>
          )}
          <div className="danger-zone-btn-row">
            <button
              className="danger-zone-btn hard-reset"
              disabled={busy || loading || !status?.hard_reset_available}
              onClick={() => setPendingConfirm('reset')}
            >
              {resetting ? 'Resetting...' : 'Hard Reset'}
            </button>
          </div>
        </div>

        {log && <pre className="danger-zone-log" ref={logRef}>{log}</pre>}

        {resetDone && (
          <div className="danger-zone-restart-notice">
            <strong>Hard Reset complete.</strong> Please restart docker-compose to re-initialize:
            <code className="danger-zone-restart-cmd">docker-compose down && docker-compose up -d</code>
          </div>
        )}

        <div className="danger-zone-actions">
          <button className="danger-zone-close-btn" onClick={onClose} disabled={busy}>
            Close
          </button>
        </div>
      </div>

      {pendingConfirm === 'destroy' && (
        <ConfirmModal
          title="Destroy All Resources"
          message={`This will run terraform destroy on ${status?.enabled_count ?? 0} active resource(s). This action cannot be undone. Continue?`}
          confirmLabel="Destroy All"
          danger
          onConfirm={handleDestroyAll}
          onCancel={() => setPendingConfirm(null)}
        />
      )}

      {pendingConfirm === 'reset' && (
        <ConfirmModal
          title="Hard Reset"
          message="This will permanently delete your SSH keys, S3 bucket, Parameter Store, DynamoDB table, and local terraform data. This cannot be undone. Continue?"
          confirmLabel="Reset Everything"
          danger
          onConfirm={handleHardReset}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
    </div>,
    document.body,
  );
};

export default DangerZoneModal;
