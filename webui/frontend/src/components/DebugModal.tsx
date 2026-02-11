import { useState, useEffect } from 'react';
import { terraformApi } from '../services/api';
import '../styles/DebugModal.css';

interface DebugModalProps {
  resourceId: string;
  resourceName: string;
  resourceFilePath: string;
  onClose: () => void;
  onActionStart: (action: string) => string;
  onActionUpdate: (id: string, chunk: string) => void;
  onActionComplete: (id: string, success: boolean, action: string) => void;
}

const DebugModal = ({ resourceId, resourceName, resourceFilePath, onClose, onActionStart, onActionUpdate, onActionComplete }: DebugModalProps) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [initialized, setInitialized] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    terraformApi.getInitStatus(resourceId)
      .then((res) => {
        setInitialized(res.initialized);
        if (res.initialized) {
          const cache = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
          if (!cache[resourceId]) {
            cache[resourceId] = { initialized: true, timestamp: new Date().toISOString() };
            localStorage.setItem('terraform_init_status', JSON.stringify(cache));
          }
        }
      })
      .catch(() => {
        const cache = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
        setInitialized(!!cache[resourceId]?.initialized);
      })
      .finally(() => setLoading(false));
  }, [resourceId]);

  const handleInit = async () => {
    setIsProcessing(true);
    const resultId = onActionStart('init');
    
    try {
      const result = await terraformApi.initResource(resourceId);
      onActionUpdate(resultId, result.output || 'Terraform initialized successfully');
      onActionComplete(resultId, result.success, 'init');
      
      if (result.success) {
        setInitialized(true);
        const cache = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
        cache[resourceId] = { initialized: true, timestamp: new Date().toISOString() };
        localStorage.setItem('terraform_init_status', JSON.stringify(cache));
        
        setTimeout(() => {
          onClose();
        }, 1000);
      }
    } catch (err) {
      onActionUpdate(resultId, `Failed to initialize: ${(err as Error).message}`);
      onActionComplete(resultId, false, 'init');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClearInitCache = () => {
    const cache = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
    delete cache[resourceId];
    localStorage.setItem('terraform_init_status', JSON.stringify(cache));
    terraformApi.getInitStatus(resourceId)
      .then((res) => setInitialized(res.initialized))
      .catch(() => setInitialized(false));
  };

  const getCachedTimestamp = () => {
    const cache = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
    return cache[resourceId]?.timestamp;
  };

  const cachedTimestamp = getCachedTimestamp();

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="debug-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Debug & Maintenance</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>

        <div className="debug-content">
          <div className="resource-info">
            <h3>{resourceName}</h3>
            <p className="resource-id">{resourceFilePath}</p>
          </div>

          <div className="debug-section">
            <h4>🔧 Initialization</h4>
            <div className="status-info">
              {loading ? (
                <div className="status-card warning">
                  <span className="status-icon">⏳</span>
                  <div className="status-details">
                    <div className="status-label">Checking...</div>
                  </div>
                </div>
              ) : initialized ? (
                <div className="status-card success">
                  <span className="status-icon">✓</span>
                  <div className="status-details">
                    <div className="status-label">Initialized</div>
                    <div className="status-time">
                      {cachedTimestamp
                        ? new Date(cachedTimestamp).toLocaleString()
                        : '.terraform directory exists'}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="status-card warning">
                  <span className="status-icon">⚠</span>
                  <div className="status-details">
                    <div className="status-label">Not initialized</div>
                    <div className="status-time">Run init to setup terraform</div>
                  </div>
                </div>
              )}
            </div>

            <div className="debug-actions">
              <button
                onClick={handleInit}
                disabled={isProcessing || loading}
                className="debug-btn primary"
              >
                {isProcessing ? '⏳ Initializing...' : '▶️ Run Init'}
              </button>
              {initialized && (
                <button
                  onClick={handleClearInitCache}
                  disabled={isProcessing}
                  className="debug-btn secondary"
                >
                  🗑️ Clear Init Cache
                </button>
              )}
            </div>

            <div className="info-box">
              <p><strong>What does Init do?</strong></p>
              <ul>
                <li>Downloads required provider plugins (AWS, etc.)</li>
                <li>Initializes backend configuration</li>
                <li>Sets up module dependencies</li>
                <li>Upgrades providers to latest compatible versions</li>
              </ul>
            </div>
          </div>

          <div className="debug-section">
            <h4>📊 Cache Status</h4>
            <div className="cache-info">
              <div className="cache-item">
                <span className="cache-label">Init Status:</span>
                <span className="cache-value">{loading ? 'Checking...' : initialized ? 'Initialized' : 'Not Initialized'}</span>
              </div>
              <div className="cache-item">
                <span className="cache-label">Auto-skip Init:</span>
                <span className="cache-value">{loading ? 'Checking...' : initialized ? 'Enabled ✓' : 'Disabled'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="debug-footer">
          <p className="footer-note">💡 Changes take effect immediately</p>
          <button onClick={onClose} className="btn-close-debug">Close</button>
        </div>
      </div>
    </div>
  );
};

export default DebugModal;
