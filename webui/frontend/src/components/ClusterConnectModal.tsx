import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ClusterInstance, ecsManageApi } from '../services/api';
import '../styles/ClusterConnectModal.css';

interface ClusterConnectModalProps {
  onClose: () => void;
}

const ClusterConnectModal = ({ onClose }: ClusterConnectModalProps) => {
  const [instances, setInstances] = useState<ClusterInstance[]>([]);
  const [clusterName, setClusterName] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadInstances();
  }, []);

  const loadInstances = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ecsManageApi.getContainerInstances();
      setClusterName(data.cluster_name);
      setInstances(data.instances);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(ax.response?.data?.detail ?? ax.message ?? 'Failed to load instances');
    } finally {
      setLoading(false);
    }
  };

  const handleSshConnect = (inst: ClusterInstance) => {
    const ip = inst.public_ip || inst.private_ip;
    if (!ip) {
      alert('No IP address available for this instance.');
      return;
    }

    const connectionId = `ecs_${inst.instance_id}_${Date.now()}`;
    sessionStorage.setItem(`ssh_${connectionId}`, JSON.stringify({
      resourceId: 'ecs_cluster',
      resourceName: inst.name || inst.instance_id,
      instanceId: inst.instance_id,
      hostname: ip,
      username: 'ec2-user',
    }));

    const w = window.open(`/terminal/${connectionId}`, `terminal_${connectionId}`);
    if (w) w.focus();
  };

  return createPortal(
    <div className="cluster-connect-overlay" onClick={onClose}>
      <div className="cluster-connect-modal" onClick={e => e.stopPropagation()}>
        <div className="cluster-connect-header">
          <h3>Container Instances</h3>
          {clusterName && <span className="cluster-connect-cluster-name">{clusterName}</span>}
          <button className="cluster-connect-close" onClick={onClose}>&times;</button>
        </div>

        <div className="cluster-connect-body">
          {loading && <div className="cluster-connect-loading">Loading instances...</div>}
          {error && <div className="cluster-connect-error">{error}</div>}
          {!loading && !error && instances.length === 0 && (
            <div className="cluster-connect-empty">
              No EC2 instances found. Make sure EC2 capacity provider is enabled.
            </div>
          )}
          {!loading && !error && instances.length > 0 && (
            <table className="cluster-connect-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Instance ID</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>Private IP</th>
                  <th>Public IP</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {instances.map(inst => (
                  <tr key={inst.instance_id}>
                    <td className="cluster-connect-name">{inst.name || '-'}</td>
                    <td><code>{inst.instance_id}</code></td>
                    <td>{inst.instance_type}</td>
                    <td>
                      <span className={`cluster-connect-state ${inst.state}`}>{inst.state}</span>
                    </td>
                    <td><code>{inst.private_ip || '-'}</code></td>
                    <td><code>{inst.public_ip || '-'}</code></td>
                    <td>
                      <button
                        className="cluster-connect-ssh-btn"
                        onClick={() => handleSshConnect(inst)}
                        disabled={inst.state !== 'running' || (!inst.public_ip && !inst.private_ip)}
                        title={inst.state !== 'running' ? 'Instance is not running' : 'Connect via SSH'}
                      >
                        SSH
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="cluster-connect-footer">
          <button className="cluster-connect-refresh-btn" onClick={loadInstances} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button className="cluster-connect-close-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ClusterConnectModal;
