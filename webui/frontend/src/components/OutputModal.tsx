import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { OutputData } from './ActionPanel';

interface OutputModalProps {
  output: OutputData;
  onClose: () => void;
}

const OutputModal = ({ output, onClose }: OutputModalProps) => {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return createPortal(
    <div className="output-modal-overlay" onClick={handleOverlayClick}>
      <div className="output-modal">
        <div className="modal-header">
          <div className="modal-title">
            <h3>{output.resourceName}</h3>
            <span className="modal-subtitle">
              {new Date(output.timestamp).toLocaleString()}
            </span>
          </div>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>
        <div className="modal-body">
          <pre className="modal-output-content">{output.output}</pre>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default OutputModal;
