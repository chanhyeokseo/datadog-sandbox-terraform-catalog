import { useState, useEffect, useRef } from 'react';
import '../styles/DockerAgentEditor.css';

interface DockerAgentConfig {
  docker_run_command: string;
  resource_status: string;
  placeholders: Record<string, string>;
}

interface DockerAgentEditorProps {
  onClose: () => void;
  onSave: () => void;
}

const DockerAgentEditor = ({ onClose, onSave }: DockerAgentEditorProps) => {
  const [command, setCommand] = useState('');
  const [resourceStatus, setResourceStatus] = useState('disabled');
  const [placeholders, setPlaceholders] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchConfig();

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [command]);

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/terraform/docker-agent/config');
      const data: DockerAgentConfig & { error?: string } = await response.json();
      if (data.error) {
        setConfigError(data.error);
      } else {
        setCommand(data.docker_run_command);
        setResourceStatus(data.resource_status);
        setPlaceholders(data.placeholders || {});
      }
    } catch (error) {
      setConfigError(`Failed to load config: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setResult(null);
      const response = await fetch('/api/terraform/docker-agent/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ docker_run_command: command }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save configuration');
      }

      setResult({ success: data.success, message: data.message });
      if (data.success) {
        onSave();
      }
    } catch (error) {
      setResult({ success: false, message: (error as Error).message });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="docker-agent-editor loading">Loading Docker Agent configuration...</div>
      </div>
    );
  }

  if (configError) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="docker-agent-editor" onClick={(e) => e.stopPropagation()}>
          <div className="editor-header">
            <h2>Configure Container</h2>
            <button onClick={onClose} className="close-button">&times;</button>
          </div>
          <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <p>{configError}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="docker-agent-editor" onClick={(e) => e.stopPropagation()}>
        <div className="editor-header">
          <h2>Configure Container</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>

        <div className="editor-content">
          <div className="config-section">
            <div className="da-status-badge-row">
              <span className={`da-status-badge ${resourceStatus === 'enabled' ? 'deployed' : 'not-deployed'}`}>
                {resourceStatus === 'enabled' ? 'Deployed' : 'Not Deployed'}
              </span>
              <span className="da-status-hint">
                {resourceStatus === 'enabled'
                  ? 'Changes will be applied via SSH (container restart)'
                  : 'Changes will be saved to Terraform config (apply on Deploy)'}
              </span>
            </div>

            <div className="form-group">
              <label>Docker Run Command</label>
              <textarea
                ref={textareaRef}
                className="da-command-textarea"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                spellCheck={false}
              />
              <small>
                Use placeholders: {'{{DD_API_KEY}}'}, {'{{DD_SITE}}'}, {'{{DD_AGENT_IMAGE}}'}, {'{{DD_TAGS}}'}
              </small>
            </div>

            {Object.keys(placeholders).length > 0 && (
              <div className="da-placeholders">
                <label>Placeholder Values</label>
                <div className="da-placeholder-list">
                  {Object.entries(placeholders).map(([key, value]) => (
                    <div key={key} className="da-placeholder-item">
                      <code>{`{{${key}}}`}</code>
                      <span>{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result && (
              <div className={`da-result ${result.success ? 'success' : 'error'}`}>
                {result.message}
              </div>
            )}
          </div>
        </div>

        <div className="editor-footer">
          <div className="footer-info">
            {resourceStatus === 'enabled'
              ? 'Will stop dd-agent and restart with new command'
              : 'Changes require Deploy to take effect'}
          </div>
          <div className="footer-actions">
            <button onClick={onClose} className="btn-cancel">Cancel</button>
            <button onClick={handleSave} className="btn-save" disabled={saving || !command.trim()}>
              {saving ? 'Applying...' : 'Save & Apply Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DockerAgentEditor;
