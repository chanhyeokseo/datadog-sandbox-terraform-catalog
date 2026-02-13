import { useState, useEffect } from 'react';
import { terraformApi, backendApi } from '../services/api';
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
  const [rebuildingBackend, setRebuildingBackend] = useState(false);
  const [recreatingBucket, setRecreatingBucket] = useState(false);

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

  const handleRebuildBackend = async () => {
    setRebuildingBackend(true);
    const resultId = onActionStart('rebuild-backend');

    try {
      // Get current configuration
      const vars = await terraformApi.getVariables();
      const creator = vars.find(v => v.name === 'creator')?.value || 'default';
      const team = vars.find(v => v.name === 'team')?.value || 'default';
      const region = vars.find(v => v.name === 'region')?.value || 'ap-northeast-2';

      onActionUpdate(resultId, 'Fetching suggested backend configuration...\n');

      // Get suggested bucket and table names from backend (uses AWS credential hash)
      const { bucket_name: bucketName, table_name: tableName } = await backendApi.getSuggestedBucketName(creator, team);

      onActionUpdate(resultId, `Using bucket: ${bucketName}\n`);
      onActionUpdate(resultId, `Using DynamoDB table: ${tableName}\n`);
      onActionUpdate(resultId, `Regenerating backend.tf for ${resourceId}...\n`);

      // Rebuild backend for this instance
      const result = await backendApi.rebuildBackendForInstance(resourceId, {
        bucket_name: bucketName,
        table_name: tableName,
        region: region
      });

      if (result.success) {
        onActionUpdate(resultId, `\n✓ Backend configuration regenerated successfully!\n`);
        onActionUpdate(resultId, `File: ${result.backend_file}\n`);
        onActionComplete(resultId, true, 'rebuild-backend');

        setTimeout(() => {
          onClose();
        }, 2000);
      } else {
        onActionUpdate(resultId, '\n✗ Failed to regenerate backend configuration\n');
        onActionComplete(resultId, false, 'rebuild-backend');
      }
    } catch (err) {
      onActionUpdate(resultId, `\n✗ Error: ${(err as Error).message}\n`);
      onActionComplete(resultId, false, 'rebuild-backend');
    } finally {
      setRebuildingBackend(false);
    }
  };

  const handleRecreateBucket = async () => {
    setRecreatingBucket(true);
    const resultId = onActionStart('recreate-bucket');

    try {
      // Get current configuration
      const vars = await terraformApi.getVariables();
      const creator = vars.find(v => v.name === 'creator')?.value || 'default';
      const team = vars.find(v => v.name === 'team')?.value || 'default';
      const region = vars.find(v => v.name === 'region')?.value || 'ap-northeast-2';

      onActionUpdate(resultId, '🔄 Starting S3 bucket recreation...\n\n');
      onActionUpdate(resultId, 'Step 1: Generating backend names with AWS credential hash...\n');

      // Get suggested bucket and table names from backend (uses AWS credential hash)
      const { bucket_name: bucketName, table_name: tableName } = await backendApi.getSuggestedBucketName(creator, team);

      onActionUpdate(resultId, `✓ Bucket name: ${bucketName}\n`);
      onActionUpdate(resultId, `✓ DynamoDB table name: ${tableName}\n\n`);
      onActionUpdate(resultId, 'Step 2: Creating S3 bucket and DynamoDB table...\n');

      // Setup backend infrastructure (creates bucket + DynamoDB + backend.tf for all instances)
      const result = await backendApi.setupBackend({
        bucket_name: bucketName,
        table_name: tableName,
        region: region
      });

      if (result.success) {
        onActionUpdate(resultId, `\n✓ S3 bucket created: ${bucketName}\n`);
        onActionUpdate(resultId, `✓ DynamoDB table created: ${tableName}\n`);

        if (result.details?.backend_files_generated) {
          onActionUpdate(resultId, `✓ Generated backend.tf for ${result.details.backend_files_generated} instances\n`);
        }

        onActionUpdate(resultId, '\n🎉 Backend infrastructure successfully recreated!\n');
        onActionComplete(resultId, true, 'recreate-bucket');

        setTimeout(() => {
          onClose();
        }, 2000);
      } else {
        onActionUpdate(resultId, '\n✗ Failed to recreate backend infrastructure\n');
        onActionComplete(resultId, false, 'recreate-bucket');
      }
    } catch (err) {
      onActionUpdate(resultId, `\n✗ Error: ${(err as Error).message}\n`);
      onActionComplete(resultId, false, 'recreate-bucket');
    } finally {
      setRecreatingBucket(false);
    }
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

          <div className="debug-section">
            <h4>🔄 Backend Configuration</h4>

            <div className="info-box">
              <p><strong>S3 Backend Management</strong></p>
              <p>Manage your Terraform backend infrastructure (S3 bucket + DynamoDB table for state locking).</p>
            </div>

            <div className="debug-actions">
              <button
                onClick={handleRecreateBucket}
                disabled={recreatingBucket || rebuildingBackend || loading}
                className="debug-btn primary"
                style={{ marginBottom: '8px' }}
              >
                {recreatingBucket ? '⏳ Creating...' : '🪣 Recreate S3 Bucket & DynamoDB'}
              </button>

              <button
                onClick={handleRebuildBackend}
                disabled={rebuildingBackend || recreatingBucket || loading}
                className="debug-btn secondary"
              >
                {rebuildingBackend ? '⏳ Rebuilding...' : '📄 Rebuild Backend.tf (This Instance Only)'}
              </button>
            </div>

            <div className="info-box" style={{ marginTop: '12px', fontSize: '0.85em' }}>
              <p><strong>💡 When to use:</strong></p>
              <ul style={{ marginTop: '4px', paddingLeft: '20px' }}>
                <li><strong>Recreate S3 Bucket:</strong> Creates new S3 bucket, DynamoDB table, and backend.tf for ALL instances</li>
                <li><strong>Rebuild Backend.tf:</strong> Regenerates backend.tf for THIS instance only (if bucket already exists)</li>
              </ul>
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
