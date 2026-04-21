import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { clusterShareApi } from '../services/api';
import { EKSClusterInfo, ClusterShareRequest } from '../types';
import '../styles/ClusterShareModal.css';

interface ClusterShareModalProps {
  onClose: () => void;
  onSharedClustersChanged?: () => void;
}

type TabId = 'request' | 'manage';

const ClusterShareModal = ({ onClose, onSharedClustersChanged }: ClusterShareModalProps) => {
  const [activeTab, setActiveTab] = useState<TabId>('request');
  const [clusters, setClusters] = useState<EKSClusterInfo[]>([]);
  const [myPrefix, setMyPrefix] = useState('');
  const [requestedArns, setRequestedArns] = useState<Record<string, string>>({});
  const [clustersLoading, setClustersLoading] = useState(false);
  const [incoming, setIncoming] = useState<ClusterShareRequest[]>([]);
  const [outgoing, setOutgoing] = useState<ClusterShareRequest[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadClusters = useCallback(async () => {
    setClustersLoading(true);
    setError(null);
    try {
      const data = await clusterShareApi.listClusters();
      setClusters(data.clusters);
      setMyPrefix(data.my_prefix);
      setRequestedArns(data.requested_arns || {});
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load EKS clusters');
    } finally {
      setClustersLoading(false);
    }
  }, []);

  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    setError(null);
    try {
      const [inc, out] = await Promise.all([
        clusterShareApi.getIncomingRequests(),
        clusterShareApi.getOutgoingRequests(),
      ]);
      setIncoming(inc);
      setOutgoing(out);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load requests');
    } finally {
      setRequestsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'request') loadClusters();
    else loadRequests();
  }, [activeTab, loadClusters, loadRequests]);

  useEffect(() => {
    if (activeTab !== 'manage') return;
    const id = setInterval(loadRequests, 30000);
    return () => clearInterval(id);
  }, [activeTab, loadRequests]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const handleRefresh = () => {
    if (activeTab === 'request') loadClusters();
    else loadRequests();
  };

  const handleRequestShare = async (cluster: EKSClusterInfo) => {
    if (!cluster.owner_prefix) {
      setError('Cannot determine cluster owner');
      return;
    }
    setActionLoading(cluster.arn);
    setError(null);
    setSuccess(null);
    try {
      await clusterShareApi.createRequest(cluster.name, cluster.arn, cluster.owner_prefix);
      await loadClusters();
      setSuccess(`Share request sent for ${cluster.name}`);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to send share request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleApprove = async (requestId: string) => {
    setActionLoading(requestId);
    setError(null);
    try {
      await clusterShareApi.approveRequest(requestId);
      await loadRequests();
      onSharedClustersChanged?.();
      setSuccess('Request approved');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to approve request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeny = async (requestId: string) => {
    setActionLoading(requestId);
    setError(null);
    try {
      await clusterShareApi.denyRequest(requestId);
      await loadRequests();
      setSuccess('Request denied');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to deny request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (requestId: string) => {
    setActionLoading(requestId);
    setError(null);
    try {
      await clusterShareApi.deleteRequest(requestId);
      await loadRequests();
      onSharedClustersChanged?.();
      setSuccess('Request deleted');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to delete request');
    } finally {
      setActionLoading(null);
    }
  };

  const statusBadge = (status: string) => {
    const cls = status === 'approved' ? 'badge-approved' : status === 'denied' ? 'badge-denied' : 'badge-pending';
    return <span className={`cs-badge ${cls}`}>{status}</span>;
  };

  const renderRequestTab = () => (
    <div className="cs-tab-content">
      <p className="cs-description">
        DogSTAC-managed EKS clusters available for sharing. You can share clusters within the same region.
      </p>
      {clustersLoading ? (
        <div className="cs-loading">Loading EKS clusters...</div>
      ) : clusters.length === 0 ? (
        <div className="cs-empty">No shareable EKS clusters found in this AWS account.</div>
      ) : (
        <div className="cs-cluster-list">
          {clusters.map(cluster => (
            <div key={cluster.arn} className="cs-cluster-item">
              <div className="cs-cluster-info">
                <div className="cs-cluster-name">{cluster.name}</div>
                <div className="cs-cluster-meta">
                  <span className={`cs-cluster-status ${cluster.status === 'ACTIVE' ? 'active' : ''}`}>
                    {cluster.status}
                  </span>
                  {cluster.owner_prefix && (
                    <span className="cs-cluster-owner">Owner: {cluster.owner_prefix}</span>
                  )}
                </div>
                <div className="cs-cluster-arn">{cluster.arn}</div>
              </div>
              {cluster.owner_prefix === myPrefix ? (
                <span className="cs-own-label">Your cluster</span>
              ) : requestedArns[cluster.arn] ? (
                <span className={`cs-own-label cs-requested-label ${requestedArns[cluster.arn]}`}>
                  {requestedArns[cluster.arn] === 'pending' ? 'Pending' : 'Shared'}
                </span>
              ) : (
                <button
                  className="btn btn-deploy cs-request-btn"
                  onClick={() => handleRequestShare(cluster)}
                  disabled={actionLoading === cluster.arn}
                  title="Request cluster share"
                >
                  {actionLoading === cluster.arn ? 'Sending...' : 'Request Share'}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const pendingIncoming = incoming.filter(r => r.status === 'pending');
  const resolvedIncoming = incoming.filter(r => r.status !== 'pending');

  const renderManageTab = () => (
    <div className="cs-tab-content">
      <div className="cs-section">
        <h3>Incoming Requests {pendingIncoming.length > 0 && <span className="cs-count">{pendingIncoming.length}</span>}</h3>
        {requestsLoading ? (
          <div className="cs-loading">Loading requests...</div>
        ) : pendingIncoming.length === 0 && resolvedIncoming.length === 0 ? (
          <div className="cs-empty">No incoming requests.</div>
        ) : (
          <div className="cs-request-list">
            {pendingIncoming.map(req => (
              <div key={req.id} className="cs-request-item">
                <div className="cs-request-info">
                  <div className="cs-request-title">
                    <strong>{req.requester_prefix}</strong> wants to share <strong>{req.cluster_name}</strong>
                  </div>
                  <div className="cs-request-meta">
                    {statusBadge(req.status)} &middot; {new Date(req.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="cs-request-actions">
                  <button
                    className="btn btn-deploy cs-action-btn"
                    onClick={() => handleApprove(req.id)}
                    disabled={actionLoading === req.id}
                  >
                    {actionLoading === req.id ? '...' : 'Approve'}
                  </button>
                  <button
                    className="btn btn-destroy cs-action-btn"
                    onClick={() => handleDeny(req.id)}
                    disabled={actionLoading === req.id}
                  >
                    {actionLoading === req.id ? '...' : 'Deny'}
                  </button>
                </div>
              </div>
            ))}
            {resolvedIncoming.map(req => (
              <div key={req.id} className="cs-request-item resolved">
                <div className="cs-request-info">
                  <div className="cs-request-title">
                    <strong>{req.requester_prefix}</strong> &mdash; <strong>{req.cluster_name}</strong>
                  </div>
                  <div className="cs-request-meta">
                    {statusBadge(req.status)} &middot; {new Date(req.updated_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  className="btn cs-action-btn cs-delete-btn"
                  onClick={() => handleDelete(req.id)}
                  disabled={actionLoading === req.id}
                  title="Remove this request"
                >
                  {actionLoading === req.id ? '...' : 'Remove'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="cs-section">
        <h3>My Outgoing Requests</h3>
        {requestsLoading ? (
          <div className="cs-loading">Loading...</div>
        ) : outgoing.length === 0 ? (
          <div className="cs-empty">No outgoing requests.</div>
        ) : (
          <div className="cs-request-list">
            {outgoing.map(req => (
              <div key={req.id} className="cs-request-item">
                <div className="cs-request-info">
                  <div className="cs-request-title">
                    <strong>{req.cluster_name}</strong> from <strong>{req.owner_prefix}</strong>
                  </div>
                  <div className="cs-request-meta">
                    {statusBadge(req.status)} &middot; {new Date(req.created_at).toLocaleDateString()}
                  </div>
                </div>
                {(req.status === 'pending' || req.status === 'approved') && (
                  <button
                    className="btn cs-action-btn cs-delete-btn"
                    onClick={() => handleDelete(req.id)}
                    disabled={actionLoading === req.id}
                    title={req.status === 'pending' ? 'Cancel this request' : 'Leave this shared cluster'}
                  >
                    {actionLoading === req.id ? '...' : req.status === 'pending' ? 'Cancel' : 'Leave'}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content cs-modal" onClick={e => e.stopPropagation()}>
        <div className="cs-header">
          <h2>Cluster Share</h2>
          <div className="cs-header-actions">
            <button
              className="modal-header-refresh"
              onClick={handleRefresh}
              disabled={clustersLoading || requestsLoading}
              title="Refresh"
            >
              ↻
            </button>
            <button className="cs-close" onClick={onClose}>&times;</button>
          </div>
        </div>

        <div className="cs-tabs">
          <button
            className={`cs-tab ${activeTab === 'request' ? 'active' : ''}`}
            onClick={() => setActiveTab('request')}
          >
            Request Share
          </button>
          <button
            className={`cs-tab ${activeTab === 'manage' ? 'active' : ''}`}
            onClick={() => setActiveTab('manage')}
          >
            Manage Requests
            {pendingIncoming.length > 0 && <span className="cs-tab-badge">{pendingIncoming.length}</span>}
          </button>
        </div>

        {(error || success) && (
          <div className={`cs-alert ${error ? 'cs-alert-error' : 'cs-alert-success'}`}>
            {error || success}
          </div>
        )}

        <div className="cs-body">
          {activeTab === 'request' ? renderRequestTab() : renderManageTab()}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ClusterShareModal;
