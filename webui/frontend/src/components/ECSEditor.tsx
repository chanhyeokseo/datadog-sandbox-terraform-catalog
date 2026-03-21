import { useState, useEffect } from 'react';
import '../styles/EKSEditor.css';

interface ECSConfig {
  enable_fargate: boolean;
  enable_ec2: boolean;
  ec2_instance_type: string;
  ec2_min_size: number;
  ec2_max_size: number;
  ec2_desired_capacity: number;
}

interface ECSEditorProps {
  onClose: () => void;
  onSave: () => void;
}

const EC2_INSTANCE_TYPES = [
  't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
  't3a.micro', 't3a.small', 't3a.medium', 't3a.large', 't3a.xlarge',
  'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge',
  'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge',
];

const ECSEditor = ({ onClose, onSave }: ECSEditorProps) => {
  const [config, setConfig] = useState<ECSConfig>({
    enable_fargate: true,
    enable_ec2: false,
    ec2_instance_type: 't3.medium',
    ec2_min_size: 1,
    ec2_max_size: 3,
    ec2_desired_capacity: 1,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'ec2' | 'fargate'>('fargate');
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig();
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/terraform/ecs/config');
      const data = await response.json();
      if (data.error) {
        setConfigError(data.error);
      } else {
        setConfig(prev => ({ ...prev, ...data }));
      }
    } catch (error) {
      setConfigError(`Failed to load ECS config: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await fetch('/api/terraform/ecs/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to save ECS configuration');
      alert('ECS configuration saved successfully!\n\nClick APPLY to deploy with the new settings.');
      onSave();
      onClose();
    } catch (error) {
      alert(`Failed to save: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateDefault = async () => {
    try {
      setSaving(true);
      const response = await fetch('/api/terraform/ecs/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to create ECS configuration');
      setConfigError(null);
    } catch (error) {
      alert(`Failed to create: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (updates: Partial<ECSConfig>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  if (loading) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="eks-editor loading">Loading ECS configuration...</div>
      </div>
    );
  }

  if (configError) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="eks-editor" onClick={(e) => e.stopPropagation()}>
          <div className="editor-header">
            <h2>ECS Configuration</h2>
            <button onClick={onClose} className="close-button">&times;</button>
          </div>
          <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <p style={{ marginBottom: '12px' }}>No ECS configuration found.</p>
            <p style={{ fontSize: '13px' }}>Deploy the ECS resource first, or click Save to create a default configuration.</p>
            <button className="btn-primary" style={{ marginTop: '20px' }} onClick={handleCreateDefault} disabled={saving}>
              {saving ? 'Creating...' : 'Create Default Config'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="eks-editor" onClick={(e) => e.stopPropagation()}>
        <div className="editor-header">
          <h2>ECS Cluster Configuration</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>

        <div className="editor-tabs">
          <button
            className={`tab ${activeTab === 'fargate' ? 'active' : ''}`}
            onClick={() => setActiveTab('fargate')}
          >
            Fargate
          </button>
          <button
            className={`tab ${activeTab === 'ec2' ? 'active' : ''}`}
            onClick={() => setActiveTab('ec2')}
          >
            EC2 Capacity
          </button>
        </div>

        <div className="editor-content">
          {activeTab === 'fargate' && (
            <div className="config-section">
              <div className="section-toggle">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.enable_fargate}
                    onChange={(e) => updateConfig({ enable_fargate: e.target.checked })}
                  />
                  <span>Enable Fargate Capacity Provider</span>
                </label>
              </div>
              {config.enable_fargate && (
                <div className="form-group">
                  <small>Fargate runs tasks without managing EC2 instances. FARGATE and FARGATE_SPOT capacity providers will be enabled.</small>
                </div>
              )}
            </div>
          )}

          {activeTab === 'ec2' && (
            <div className="config-section">
              <div className="section-toggle">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.enable_ec2}
                    onChange={(e) => updateConfig({ enable_ec2: e.target.checked })}
                  />
                  <span>Enable EC2 Capacity Provider</span>
                </label>
              </div>

              {config.enable_ec2 && (
                <>
                  <div className="form-group">
                    <label>Instance Type</label>
                    <select
                      value={config.ec2_instance_type}
                      onChange={(e) => updateConfig({ ec2_instance_type: e.target.value })}
                    >
                      {EC2_INSTANCE_TYPES.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    <small>EC2 instance type for ECS container instances</small>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Desired Capacity</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.ec2_desired_capacity}
                        onChange={(e) => updateConfig({ ec2_desired_capacity: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Min Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.ec2_min_size}
                        onChange={(e) => updateConfig({ ec2_min_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Max Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.ec2_max_size}
                        onChange={(e) => updateConfig({ ec2_max_size: parseInt(e.target.value) })}
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="editor-footer">
          <div className="footer-info">
            <span>Changes require APPLY to take effect</span>
          </div>
          <div className="footer-actions">
            <button onClick={onClose} className="btn-cancel">Cancel</button>
            <button onClick={handleSave} className="btn-save" disabled={saving}>
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ECSEditor;
