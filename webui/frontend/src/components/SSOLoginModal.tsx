import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { terraformApi } from '../services/api';
import '../styles/SSOLoginModal.css';

interface SSOLoginModalProps {
  ssoConfigured: boolean;
  ssoCommand: string;
  onSuccess: () => void;
  onRetry: () => void;
}

type SSOPhase = 'idle' | 'starting' | 'waiting' | 'complete' | 'error';

const SSOLoginModal = ({ ssoConfigured, ssoCommand, onSuccess, onRetry }: SSOLoginModalProps) => {
  const [phase, setPhase] = useState<SSOPhase>('idle');
  const [verificationUri, setVerificationUri] = useState('');
  const [userCode, setUserCode] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [copied, setCopied] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  const handleStartSSO = async () => {
    setPhase('starting');
    setErrorMsg('');
    cancelledRef.current = false;
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);

    try {
      const result = await terraformApi.startSSOLogin();
      setVerificationUri(result.verification_uri);
      setUserCode(result.user_code);
      setPhase('waiting');

      const pollOnce = async () => {
        if (cancelledRef.current) return;
        try {
          const status = await terraformApi.getSSOStatus(result.session_id);
          if (cancelledRef.current) return;
          if (status.status === 'complete') {
            setPhase('complete');
            setTimeout(() => onSuccess(), 1000);
            return;
          } else if (status.status === 'expired' || status.status === 'error') {
            setPhase('error');
            setErrorMsg(status.message || 'SSO login failed');
            return;
          }
        } catch {
          if (cancelledRef.current) return;
          setPhase('error');
          setErrorMsg('Failed to check SSO status');
          return;
        }
        pollTimerRef.current = setTimeout(pollOnce, 3000);
      };
      pollTimerRef.current = setTimeout(pollOnce, 3000);
    } catch (err: any) {
      setPhase('error');
      setErrorMsg(err?.response?.data?.detail || 'Failed to start SSO login');
    }
  };

  const handleCopyCommand = () => {
    navigator.clipboard.writeText(ssoCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return createPortal(
    <div className="modal-overlay">
      <div className="sso-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sso-modal-header">
          <h3 className="sso-modal-title">AWS Credentials Expired</h3>
          <p className="sso-modal-desc">
            Your AWS session has expired. Re-authenticate to continue.
          </p>
        </div>

        {ssoConfigured && (
          <div className="sso-modal-section">
            <div className="sso-section-label">SSO Login</div>

            {phase === 'idle' && (
              <button className="sso-start-btn" onClick={handleStartSSO}>
                Start SSO Login
              </button>
            )}

            {phase === 'starting' && (
              <div className="sso-status-row">
                <div className="sso-spinner" />
                <span>Starting SSO authorization...</span>
              </div>
            )}

            {phase === 'waiting' && (
              <div className="sso-auth-block">
                <p className="sso-auth-instruction">
                  Click the link below to authorize in your browser:
                </p>
                <a
                  href={verificationUri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="sso-auth-link"
                >
                  {verificationUri}
                </a>
                {userCode && (
                  <div className="sso-user-code">
                    <span className="sso-user-code-label">Code:</span>
                    <code className="sso-user-code-value">{userCode}</code>
                  </div>
                )}
                <div className="sso-status-row">
                  <div className="sso-spinner" />
                  <span>Waiting for authorization...</span>
                </div>
              </div>
            )}

            {phase === 'complete' && (
              <div className="sso-status-row sso-success">
                <span>SSO login successful. Refreshing...</span>
              </div>
            )}

            {phase === 'error' && (
              <div className="sso-error-block">
                <p className="sso-error-msg">{errorMsg}</p>
                <button className="sso-start-btn" onClick={handleStartSSO}>
                  Retry SSO Login
                </button>
              </div>
            )}
          </div>
        )}

        <div className="sso-modal-section">
          <div className="sso-section-label">
            {ssoConfigured ? 'Or run manually' : 'Run the following command'}
          </div>
          <div className="sso-command-row">
            <code className="sso-command-value">{ssoCommand}</code>
            <button className="sso-copy-btn" onClick={handleCopyCommand}>
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>

        <div className="sso-modal-actions">
          <button className="sso-retry-btn" onClick={onRetry}>
            Retry
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default SSOLoginModal;
