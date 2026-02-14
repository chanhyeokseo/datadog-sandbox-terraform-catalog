import { useState, useEffect } from 'react';
import '../styles/EKSEditor.css';

interface EKSConfig {
  enable_node_group: boolean;
  node_instance_types: string[];
  node_desired_size: number;
  node_min_size: number;
  node_max_size: number;
  node_disk_size: number;
  node_capacity_type: string;
  
  enable_windows_node_group: boolean;
  windows_node_instance_types: string[];
  windows_node_ami_type: string;
  windows_node_desired_size: number;
  windows_node_min_size: number;
  windows_node_max_size: number;
  windows_node_disk_size: number;
  windows_node_capacity_type: string;
  
  enable_fargate: boolean;
  fargate_namespaces: string[];
  
  endpoint_public_access: boolean;
  endpoint_private_access: boolean;
}

interface EKSEditorProps {
  onClose: () => void;
  onSave: () => void;
}

const INSTANCE_TYPES = [
  't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
  't3a.small', 't3a.medium', 't3a.large', 't3a.xlarge', 't3a.2xlarge',
  'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge',
  'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge',
];

const WINDOWS_AMI_TYPES = [
  'WINDOWS_CORE_2019_x86_64',
  'WINDOWS_FULL_2019_x86_64',
  'WINDOWS_CORE_2022_x86_64',
  'WINDOWS_FULL_2022_x86_64',
];

const EKSEditor = ({ onClose, onSave }: EKSEditorProps) => {
  const [config, setConfig] = useState<EKSConfig>({
    enable_node_group: true,
    node_instance_types: ['t3.medium'],
    node_desired_size: 2,
    node_min_size: 1,
    node_max_size: 4,
    node_disk_size: 20,
    node_capacity_type: 'ON_DEMAND',
    
    enable_windows_node_group: false,
    windows_node_instance_types: ['t3.medium'],
    windows_node_ami_type: 'WINDOWS_FULL_2022_x86_64',
    windows_node_desired_size: 2,
    windows_node_min_size: 1,
    windows_node_max_size: 4,
    windows_node_disk_size: 50,
    windows_node_capacity_type: 'ON_DEMAND',
    
    enable_fargate: false,
    fargate_namespaces: ['default', 'kube-system'],
    
    endpoint_public_access: true,
    endpoint_private_access: true,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'linux' | 'windows' | 'fargate' | 'cluster'>('linux');

  useEffect(() => {
    fetchConfig();
    
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const [configError, setConfigError] = useState<string | null>(null);

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/terraform/eks/config');
      const data = await response.json();
      if (data.error) {
        setConfigError(data.error);
      } else {
        setConfig(data);
      }
    } catch (error) {
      setConfigError(`Failed to load EKS config: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await fetch('/api/terraform/eks/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      
      if (!response.ok) {
        throw new Error('Failed to save EKS configuration');
      }
      
      alert('✅ EKS configuration saved successfully!\n\nClick APPLY to deploy with the new settings.');
      onSave();
      onClose();
    } catch (error) {
      alert(`❌ Failed to save: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateDefault = async () => {
    try {
      setSaving(true);
      const response = await fetch('/api/terraform/eks/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error('Failed to create EKS configuration');
      }

      setConfigError(null);
    } catch (error) {
      alert(`❌ Failed to create: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (updates: Partial<EKSConfig>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  if (loading) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="eks-editor loading">Loading EKS configuration...</div>
      </div>
    );
  }

  if (configError) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="eks-editor" onClick={(e) => e.stopPropagation()}>
          <div className="editor-header">
            <h2>EKS Configuration</h2>
            <button onClick={onClose} className="close-button">&times;</button>
          </div>
          <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <p style={{ marginBottom: '12px' }}>No EKS configuration found.</p>
            <p style={{ fontSize: '13px' }}>Deploy the EKS resource first, or click Save to create a default configuration.</p>
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
          <h2>⚙️ EKS Cluster Configuration</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>

        <div className="editor-tabs">
          <button
            className={`tab ${activeTab === 'linux' ? 'active' : ''}`}
            onClick={() => setActiveTab('linux')}
          >
            🐧 Linux Nodes
          </button>
          <button
            className={`tab ${activeTab === 'windows' ? 'active' : ''}`}
            onClick={() => setActiveTab('windows')}
          >
            🪟 Windows Nodes
          </button>
          <button
            className={`tab ${activeTab === 'fargate' ? 'active' : ''}`}
            onClick={() => setActiveTab('fargate')}
          >
            ☁️ Fargate
          </button>
          <button
            className={`tab ${activeTab === 'cluster' ? 'active' : ''}`}
            onClick={() => setActiveTab('cluster')}
          >
            🔧 Cluster
          </button>
        </div>

        <div className="editor-content">
          {activeTab === 'linux' && (
            <div className="config-section">
              <div className="section-toggle">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.enable_node_group}
                    onChange={(e) => updateConfig({ enable_node_group: e.target.checked })}
                  />
                  <span>Enable Linux Node Group</span>
                </label>
              </div>

              {config.enable_node_group && (
                <>
                  <div className="form-group">
                    <label>Instance Types</label>
                    <select
                      value={config.node_instance_types[0]}
                      onChange={(e) => updateConfig({ node_instance_types: [e.target.value] })}
                    >
                      {INSTANCE_TYPES.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    <small>EC2 instance type for worker nodes</small>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Desired Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.node_desired_size}
                        onChange={(e) => updateConfig({ node_desired_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Min Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.node_min_size}
                        onChange={(e) => updateConfig({ node_min_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Max Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.node_max_size}
                        onChange={(e) => updateConfig({ node_max_size: parseInt(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Disk Size (GB)</label>
                      <input
                        type="number"
                        min="20"
                        max="1000"
                        value={config.node_disk_size}
                        onChange={(e) => updateConfig({ node_disk_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Capacity Type</label>
                      <select
                        value={config.node_capacity_type}
                        onChange={(e) => updateConfig({ node_capacity_type: e.target.value })}
                      >
                        <option value="ON_DEMAND">On-Demand</option>
                        <option value="SPOT">Spot</option>
                      </select>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'windows' && (
            <div className="config-section">
              <div className="section-toggle">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.enable_windows_node_group}
                    onChange={(e) => updateConfig({ enable_windows_node_group: e.target.checked })}
                  />
                  <span>Enable Windows Node Group</span>
                </label>
              </div>

              {config.enable_windows_node_group && (
                <>
                  <div className="warning-box">
                    ⚠️ Windows nodes require Linux nodes for CoreDNS. Linux node group will be automatically enabled.
                  </div>

                  <div className="form-group">
                    <label>Instance Types</label>
                    <select
                      value={config.windows_node_instance_types[0]}
                      onChange={(e) => updateConfig({ windows_node_instance_types: [e.target.value] })}
                    >
                      {INSTANCE_TYPES.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Windows AMI Type</label>
                    <select
                      value={config.windows_node_ami_type}
                      onChange={(e) => updateConfig({ windows_node_ami_type: e.target.value })}
                    >
                      {WINDOWS_AMI_TYPES.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    <small>Windows Server version and edition</small>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Desired Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.windows_node_desired_size}
                        onChange={(e) => updateConfig({ windows_node_desired_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Min Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.windows_node_min_size}
                        onChange={(e) => updateConfig({ windows_node_min_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Max Size</label>
                      <input
                        type="number"
                        min="0"
                        max="20"
                        value={config.windows_node_max_size}
                        onChange={(e) => updateConfig({ windows_node_max_size: parseInt(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Disk Size (GB)</label>
                      <input
                        type="number"
                        min="30"
                        max="1000"
                        value={config.windows_node_disk_size}
                        onChange={(e) => updateConfig({ windows_node_disk_size: parseInt(e.target.value) })}
                      />
                    </div>
                    <div className="form-group">
                      <label>Capacity Type</label>
                      <select
                        value={config.windows_node_capacity_type}
                        onChange={(e) => updateConfig({ windows_node_capacity_type: e.target.value })}
                      >
                        <option value="ON_DEMAND">On-Demand</option>
                        <option value="SPOT">Spot (Not recommended for Windows)</option>
                      </select>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'fargate' && (
            <div className="config-section">
              <div className="section-toggle">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.enable_fargate}
                    onChange={(e) => updateConfig({ enable_fargate: e.target.checked })}
                  />
                  <span>Enable Fargate Profiles</span>
                </label>
              </div>

              {config.enable_fargate && (
                <>

                  <div className="form-group">
                    <label>Fargate Namespaces</label>
                    <div className="namespace-list">
                      {config.fargate_namespaces.map((ns, index) => (
                        <div key={index} className="namespace-item">
                          <input
                            type="text"
                            value={ns}
                            onChange={(e) => {
                              const newNamespaces = [...config.fargate_namespaces];
                              newNamespaces[index] = e.target.value;
                              updateConfig({ fargate_namespaces: newNamespaces });
                            }}
                          />
                          <button
                            onClick={() => {
                              const newNamespaces = config.fargate_namespaces.filter((_, i) => i !== index);
                              updateConfig({ fargate_namespaces: newNamespaces });
                            }}
                            className="btn-remove-small"
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={() => {
                        updateConfig({ fargate_namespaces: [...config.fargate_namespaces, 'new-namespace'] });
                      }}
                      className="btn-add-small"
                    >
                      + Add Namespace
                    </button>
                    <small>Namespaces where Fargate will run pods</small>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'cluster' && (
            <div className="config-section">
              <div className="form-group">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.endpoint_public_access}
                    onChange={(e) => updateConfig({ endpoint_public_access: e.target.checked })}
                  />
                  <span>Public API Endpoint</span>
                </label>
                <small>Allow access to Kubernetes API from the internet</small>
              </div>

              <div className="form-group">
                <label className="toggle-label">
                  <input
                    type="checkbox"
                    checked={config.endpoint_private_access}
                    onChange={(e) => updateConfig({ endpoint_private_access: e.target.checked })}
                  />
                  <span>Private API Endpoint</span>
                </label>
                <small>Allow access to Kubernetes API from within VPC</small>
              </div>
            </div>
          )}
        </div>

        <div className="editor-footer">
          <div className="footer-info">
            <span>💡 Changes require APPLY to take effect</span>
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

export default EKSEditor;
