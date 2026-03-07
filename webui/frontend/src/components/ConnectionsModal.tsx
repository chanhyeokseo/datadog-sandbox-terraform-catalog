import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

interface Connection {
  id: string;
  hostname: string;
  username: string;
}

interface ConnectionsModalProps {
  onClose: () => void;
}

const ConnectionsModal = ({ onClose }: ConnectionsModalProps) => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    try {
      const response = await fetch('/api/ssh/connections');
      const data = await response.json();
      setConnections(data.connections || []);
    } catch (error) {
      console.error('Failed to load connections:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenConnection = (connectionId: string) => {
    const terminalWindow = window.open(`/terminal/${connectionId}`, `terminal_${connectionId}`);
    if (terminalWindow) {
      terminalWindow.focus();
    }
  };

  const modal = createPortal(
    <div className="config-modal-overlay" onClick={onClose}>
      <div className="config-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Active SSH Connections</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>
        
        <div className="config-body">
          {loading ? (
            <div className="loading-state">Loading connections...</div>
          ) : connections.length === 0 ? (
            <div className="empty-state">
              <p>No active SSH connections.</p>
              <p className="empty-state-hint">Click the "Connect" button on a resource to start an SSH session.</p>
            </div>
          ) : (
            <div className="connections-list">
              {connections.map((conn) => (
                <div key={conn.id} className="connection-item">
                  <div className="connection-info">
                    <div className="connection-status">Connected</div>
                    <div className="connection-details">
                      <strong>{conn.username}@{conn.hostname}</strong>
                      <span className="connection-id">{conn.id}</span>
                    </div>
                  </div>
                  <div className="connection-actions">
                    <button
                      onClick={() => handleOpenConnection(conn.id)}
                      className="btn-connection-action btn-open"
                    >
                      Open
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );

  return modal;
};

export default ConnectionsModal;
