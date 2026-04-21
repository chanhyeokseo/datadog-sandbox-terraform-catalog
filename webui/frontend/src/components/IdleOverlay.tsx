import { useState } from 'react';
import { createPortal } from 'react-dom';
import '../styles/IdleOverlay.css';

interface IdleOverlayProps {
  onResume: () => Promise<void>;
}

type Phase = 'idle' | 'checking' | 'error';

const IdleOverlay = ({ onResume }: IdleOverlayProps) => {
  const [phase, setPhase] = useState<Phase>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const handleResume = async () => {
    setPhase('checking');
    setErrorMsg('');
    try {
      await onResume();
    } catch (err: any) {
      setPhase('error');
      setErrorMsg(err?.message || 'Failed to verify credentials');
    }
  };

  return createPortal(
    <div className="idle-overlay">
      <div className="idle-overlay-card" onClick={(e) => e.stopPropagation()}>
        <img src="/logo.png" alt="DogSTAC" className="idle-overlay-logo" />
        <h2 className="idle-overlay-title">Session Paused</h2>
        <p className="idle-overlay-desc">
          Your session was inactive. Click below to verify credentials and resume.
        </p>

        {phase === 'idle' && (
          <button className="idle-overlay-btn" onClick={handleResume}>
            Resume DogSTAC
          </button>
        )}

        {phase === 'checking' && (
          <div className="idle-overlay-status">
            <div className="idle-overlay-spinner" />
            <span>Verifying credentials...</span>
          </div>
        )}

        {phase === 'error' && (
          <div className="idle-overlay-error">
            <p className="idle-overlay-error-msg">{errorMsg}</p>
            <button className="idle-overlay-btn" onClick={handleResume}>
              Retry
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};

export default IdleOverlay;
