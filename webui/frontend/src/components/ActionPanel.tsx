import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { TerraformResource, TerraformVariable, ResourceType } from '../types';
import { terraformApi } from '../services/api';
import SecurityGroupEditor from './SecurityGroupEditor';
import EKSEditor from './EKSEditor';
import DebugModal from './DebugModal';
import DescriptionModal from './DescriptionModal';
import ConfirmModal from './ConfirmModal';

interface ActionPanelProps {
  selectedResource: TerraformResource | null;
  onActionStart: (action: string, resourceId?: string) => string;
  onActionUpdate: (id: string, outputChunk: string) => void;
  onActionComplete: (id: string, success: boolean, action: string, resourceId?: string) => void;
  onResourcesNeedRefresh?: () => void;
  runningAction?: string;
}

export interface OutputData {
  resourceId: string;
  resourceName: string;
  timestamp: string;
  output: string;
}

const ActionPanel = ({ selectedResource, onActionStart, onActionUpdate, onActionComplete, onResourcesNeedRefresh, runningAction }: ActionPanelProps) => {
  const abortControllerRef = useRef<AbortController | null>(null);
  const [outputs, setOutputs] = useState<OutputData[]>([]);
  const [collapsedOutputs, setCollapsedOutputs] = useState<Set<number>>(new Set());
  const [variables, setVariables] = useState<TerraformVariable[]>([]);
  const [editingVar, setEditingVar] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [showSGEditor, setShowSGEditor] = useState(false);
  const [showEKSEditor, setShowEKSEditor] = useState(false);
  const [showDebugModal, setShowDebugModal] = useState(false);
  const [showDescriptionModal, setShowDescriptionModal] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<{ type: string; onConfirm: () => void } | null>(null);
  const [rdpInfo, setRdpInfo] = useState<{ ip: string; username: string; password: string } | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('terraform_outputs');
    if (saved) {
      try {
        setOutputs(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse outputs:', e);
      }
    }
  }, []);

  useEffect(() => {
    if (selectedResource) {
      loadVariables(selectedResource.id);
    } else {
      setVariables([]);
    }
  }, [selectedResource]);

  const loadVariables = async (resourceId: string) => {
    try {
      const vars = await terraformApi.getResourceVariables(resourceId);
      setVariables(vars);
    } catch (err) {
      console.error('Failed to load variables:', err);
      setVariables([]);
    }
  };

  const parseResourceOutput = (fullOutput: string): string => {
    try {
      const parsed = JSON.parse(fullOutput);
      
      const resourceOutputs: { [key: string]: any } = {};
      
      for (const [key, value] of Object.entries(parsed)) {
        // Extract the actual value from Terraform output format
        if (typeof value === 'object' && value !== null && 'value' in value) {
          resourceOutputs[key] = (value as any).value;
        } else {
          resourceOutputs[key] = value;
        }
      }
      
      if (Object.keys(resourceOutputs).length > 0) {
        return JSON.stringify(resourceOutputs, null, 2);
      }
      
      return JSON.stringify({}, null, 2);
    } catch (e) {
      return fullOutput;
    }
  };

  const saveOutput = (resourceId: string, resourceName: string, output: string) => {
    const filteredOutput = parseResourceOutput(output);
    
    const newOutput: OutputData = {
      resourceId,
      resourceName,
      timestamp: new Date().toISOString(),
      output: filteredOutput
    };
    const updated = [newOutput, ...outputs.slice(0, 9)]; // Keep last 10
    setOutputs(updated);
    localStorage.setItem('terraform_outputs', JSON.stringify(updated));
  };

  const toggleOutputCollapse = (index: number) => {
    const newCollapsed = new Set(collapsedOutputs);
    if (newCollapsed.has(index)) {
      newCollapsed.delete(index);
    } else {
      newCollapsed.add(index);
    }
    setCollapsedOutputs(newCollapsed);
  };

  const handleDeploy = async () => {
    if (!selectedResource) return;

    // Check if resource is already initialized in localStorage
    const initStatus = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
    const skipInit = initStatus[selectedResource.id]?.initialized || false;

    const resultId = onActionStart('deploy', selectedResource.id);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      await terraformApi.streamApplyResource(
        selectedResource.id,
        true,
        (chunk) => onActionUpdate(resultId, chunk),
        async (success) => {
          abortControllerRef.current = null;
          onActionComplete(resultId, success, 'deploy', selectedResource.id);
          if (success && onResourcesNeedRefresh) {
            onResourcesNeedRefresh();
          }
          if (success) {
            try {
              const outputResult = await terraformApi.output(selectedResource.id);
              if (outputResult.success && outputResult.output) {
                saveOutput(selectedResource.id, selectedResource.name, outputResult.output);
              }
            } catch (err) {
              console.error('Failed to get outputs:', err);
            }
          }
        },
        skipInit,
        controller.signal
      );
    } catch (err) {
      abortControllerRef.current = null;
      onActionUpdate(resultId, `\n${(err as Error).name === 'AbortError' ? 'Cancelled.' : (err as Error).message}\n`);
      onActionComplete(resultId, false, 'deploy', selectedResource.id);
    }
  };

  const handlePlan = async () => {
    if (!selectedResource) return;

    // Check if resource is already initialized in localStorage
    const initStatus = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
    const skipInit = initStatus[selectedResource.id]?.initialized || false;

    const resultId = onActionStart('plan');
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      await terraformApi.streamPlanResource(
        selectedResource.id,
        (chunk) => onActionUpdate(resultId, chunk),
        (success) => {
          abortControllerRef.current = null;
          onActionComplete(resultId, success, 'plan');
        },
        skipInit,
        controller.signal
      );
    } catch (err) {
      abortControllerRef.current = null;
      onActionUpdate(resultId, `\n${(err as Error).name === 'AbortError' ? 'Cancelled.' : (err as Error).message}\n`);
      onActionComplete(resultId, false, 'plan');
    }
  };

  const handleDestroy = async () => {
    if (!selectedResource) return;

    const doDestroy = async () => {
      const initStatus = JSON.parse(localStorage.getItem('terraform_init_status') || '{}');
      const skipInit = initStatus[selectedResource.id]?.initialized || false;

      const resultId = onActionStart('destroy', selectedResource.id);
      const controller = new AbortController();
      abortControllerRef.current = controller;
      try {
        await terraformApi.streamDestroyResource(
          selectedResource.id,
          true,
          (chunk) => onActionUpdate(resultId, chunk),
          (success) => {
            abortControllerRef.current = null;
            onActionComplete(resultId, success, 'destroy', selectedResource.id);
            if (success && onResourcesNeedRefresh) {
              onResourcesNeedRefresh();
            }
          },
          skipInit,
          controller.signal
        );
      } catch (err) {
        abortControllerRef.current = null;
        onActionUpdate(resultId, `\n${(err as Error).name === 'AbortError' ? 'Cancelled.' : (err as Error).message}\n`);
        onActionComplete(resultId, false, 'destroy', selectedResource.id);
      }
    };

    setPendingConfirm({
      type: 'destroy',
      onConfirm: () => { setPendingConfirm(null); doDestroy(); },
    });
  };

  const handleGetOutputs = async () => {
    if (!selectedResource) return;

    const resultId = onActionStart('outputs');
    try {
      const result = await terraformApi.output(selectedResource.id);
      onActionUpdate(resultId, result.output || '');
      onActionComplete(resultId, result.success, 'outputs');
      
      if (result.success && result.output) {
        saveOutput(selectedResource.id, selectedResource.name, result.output);
      }
    } catch (err) {
      onActionUpdate(resultId, (err as Error).message);
      onActionComplete(resultId, false, 'outputs');
    }
  };

  const isWindowsInstance = (resourceId: string): boolean => {
    return resourceId.startsWith('ec2_windows');
  };

  const handleConnect = async () => {
    if (!selectedResource) return;

    try {
      const resourceOutput = outputs.find(o => o.resourceId === selectedResource.id);
      
      if (!resourceOutput || !resourceOutput.output) {
        alert(`No output information available.\n\nPlease click "Get Outputs" button first to fetch the outputs.`);
        return;
      }

      let outputData: any;
      try {
        outputData = JSON.parse(resourceOutput.output);
      } catch (e) {
        alert(`Failed to parse output data.`);
        return;
      }

      let sshCommand: string | null = null;
      let instanceId: string | null = null;
      let publicIp: string | null = null;
      let windowsPassword: string | null = null;
      
      for (const [key, value] of Object.entries(outputData)) {
        const keyLower = key.toLowerCase();
        const strVal = value != null ? String(value) : '';
        if (!strVal) continue;
        if (sshCommand == null && (keyLower === 'ssh_command' || keyLower === 'ec2_ssh' || keyLower.includes('ssh_command'))) {
          sshCommand = strVal;
        } else if (instanceId == null && (keyLower === 'instance_id' || keyLower === 'ec2_id' || keyLower.includes('instance_id'))) {
          instanceId = strVal;
        } else if (publicIp == null && (keyLower === 'public_ip' || keyLower === 'ec2_ip' || keyLower.includes('public_ip'))) {
          publicIp = strVal;
        } else if (windowsPassword == null && keyLower === 'windows_password') {
          windowsPassword = strVal;
        }
      }

      if (isWindowsInstance(selectedResource.id)) {
        if (!publicIp) {
          alert(`Public IP not found.\n\nPlease click "Get Outputs" to fetch the outputs.`);
          return;
        }
        setRdpInfo({
          ip: publicIp,
          username: 'Administrator',
          password: windowsPassword || '',
        });
        return;
      }

      if (!sshCommand) {
        alert(`SSH command not found.\n\nResource: ${selectedResource.name}`);
        return;
      }

      const match = sshCommand.match(/@([^\s]+)/);
      const hostname = match ? match[1] : publicIp;

      if (!hostname) {
        alert(`Hostname not found.`);
        return;
      }

      let keyFilename: string | undefined;
      try {
        const vars = await terraformApi.getVariables();
        const ec2Key = vars.find((v) => v.name === 'ec2_key_name')?.value?.trim();
        if (ec2Key) keyFilename = `keys/${ec2Key}.pem`;
      } catch (_) {}

      const connectionId = `${selectedResource.id}_${Date.now()}`;
      sessionStorage.setItem(`ssh_${connectionId}`, JSON.stringify({
        resourceId: selectedResource.id,
        resourceName: selectedResource.name,
        instanceId: instanceId,
        hostname: hostname,
        username: 'ec2-user',
        ...(keyFilename && { keyFilename }),
      }));

      const terminalWindow = window.open(`/terminal/${connectionId}`, `terminal_${connectionId}`);
      if (terminalWindow) {
        terminalWindow.focus();
      }
    } catch (err) {
      alert(`Connection preparation failed: ${(err as Error).message}`);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const clearOutputs = () => {
    setOutputs([]);
    localStorage.removeItem('terraform_outputs');
  };

  const handleEditVariable = (varName: string, currentValue: string) => {
    setEditingVar(varName);
    setEditValue(currentValue);
  };

  const handleSaveVariable = async (varName: string) => {
    if (!selectedResource) return;
    const resultId = onActionStart('update-variable');
    try {
      await terraformApi.updateInstanceVariable(selectedResource.id, varName, editValue);
      await loadVariables(selectedResource.id);
      setEditingVar(null);
      onActionUpdate(resultId, `Variable ${varName} updated successfully`);
      onActionComplete(resultId, true, 'update-variable');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = ax.response?.data?.detail ?? ax.message ?? String(err);
      onActionUpdate(resultId, `Failed to update variable: ${msg}`);
      onActionComplete(resultId, false, 'update-variable');
    }
  };

  const handleRestoreVariables = async () => {
    if (!selectedResource) return;
    const doRestore = async () => {
      const resultId = onActionStart('restore-variables');
      try {
        await terraformApi.restoreResourceVariables(selectedResource.id);
        await loadVariables(selectedResource.id);
        onActionUpdate(resultId, 'Instance variables restored to defaults');
        onActionComplete(resultId, true, 'restore-variables');
      } catch (err) {
        onActionUpdate(resultId, `Failed to restore: ${(err as Error).message}`);
        onActionComplete(resultId, false, 'restore-variables');
      }
    };
    setPendingConfirm({
      type: 'restore',
      onConfirm: () => { setPendingConfirm(null); doRestore(); },
    });
  };

  const handleCancelEdit = () => {
    setEditingVar(null);
    setEditValue('');
  };


  return (
    <div className="action-panel">
      <div className="action-header">
        <div className="action-header-left">
          <h2>Actions</h2>
          {selectedResource && (
            <div className="selected-resource-info">
              <span className="selected-label">Selected:</span>
              <span className="selected-name">{selectedResource.name}</span>
            </div>
          )}
        </div>
        {selectedResource && (
          <div className="action-header-buttons">
            <button
              onClick={() => setShowDescriptionModal(true)}
              disabled={!!runningAction}
              className="btn-init"
              title="View resource description"
            >
              DESCRIPTION
            </button>
            <button
              onClick={() => setShowDebugModal(true)}
              disabled={!!runningAction}
              className="btn-init"
              title="Debug & maintenance tools"
            >
              DEBUG
            </button>
          </div>
        )}
      </div>

      <div className="action-buttons-container">
        <div className="action-section">
          <h3>Resource Actions</h3>
          
          {selectedResource?.type === ResourceType.SECURITY_GROUP && selectedResource?.status === 'enabled' && !runningAction && (
            <div className="ip-update-hint">
              <div className="hint-icon">💡</div>
              <div className="hint-text">
                Click <strong>Update</strong> below to allow inbound access from your current IP address!
              </div>
            </div>
          )}
          
          <div className="action-buttons-grid">
            {runningAction ? (
              <button
                disabled
                className="btn btn-stop"
                title={`${runningAction} is in progress for this resource`}
              >
                {runningAction === 'plan'
                  ? 'Planning...'
                  : runningAction === 'deploy'
                    ? (selectedResource?.status === 'enabled' ? 'Updating...' : 'Deploying...')
                    : 'Destroying...'}
              </button>
            ) : (
              <>
                <button
                  onClick={handleDeploy}
                  disabled={!selectedResource || !!runningAction}
                  className={`btn ${selectedResource?.status === 'enabled' ? 'btn-update' : 'btn-deploy'}`}
                  title={!selectedResource ? 'Select a resource first' : runningAction ? `${runningAction} is running for this resource` : selectedResource.status === 'enabled' ? 'Update deployed resource' : 'Deploy resource'}
                >
                  {selectedResource?.status === 'enabled' ? 'Update' : 'Deploy'}
                </button>
                <button
                  onClick={handlePlan}
                  disabled={!selectedResource || !!runningAction}
                  className="btn btn-plan"
                  title={!selectedResource ? 'Select a resource first' : runningAction ? `${runningAction} is running for this resource` : 'Preview changes before deploying/destroying'}
                >
                  Plan
                </button>
                <button
                  onClick={handleDestroy}
                  disabled={!selectedResource || selectedResource.status === 'disabled' || !!runningAction}
                  className="btn btn-destroy"
                  title={!selectedResource ? 'Select a resource first' : runningAction ? `${runningAction} is running for this resource` : selectedResource.status === 'disabled' ? 'Not deployed yet' : 'Destroy resource'}
                >
                  Destroy
                </button>
                {selectedResource && selectedResource.status === 'enabled' && selectedResource.type === ResourceType.EC2 && (
                  <button
                    onClick={handleConnect}
                    className="btn btn-connect"
                    disabled={!!runningAction}
                    title={runningAction ? `${runningAction} is running for this resource` : isWindowsInstance(selectedResource.id) ? 'Show RDP connection info' : 'Open terminal and connect via SSH'}
                  >
                    Connect
                  </button>
                )}
                
                {selectedResource && selectedResource.type === ResourceType.SECURITY_GROUP && (
                  <button
                    onClick={() => setShowSGEditor(true)}
                    className="btn btn-configure"
                    disabled={!!runningAction}
                    title={runningAction ? `${runningAction} is running for this resource` : 'Customize Security Group rules'}
                  >
                    Customize Rules
                  </button>
                )}
                
                {selectedResource && selectedResource.type === ResourceType.EKS && (
                  <button
                    onClick={() => setShowEKSEditor(true)}
                    className="btn btn-configure"
                    disabled={!!runningAction}
                    title={runningAction ? `${runningAction} is running for this resource` : 'Configure EKS cluster settings'}
                  >
                    Configure Cluster
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {selectedResource?.type !== ResourceType.EKS && (
          <div className="action-section variables-section">
            <div className="section-header-flex">
              <h3>Resource Variables</h3>
              {selectedResource && (
                <div className="variables-header-actions">
                  <button onClick={() => loadVariables(selectedResource.id)} className="btn-refresh-small">Refresh</button>
                  <button onClick={handleRestoreVariables} className="btn-restore-small" title="Clear instance variables and use global/defaults">Restore variables</button>
                </div>
              )}
            </div>
            <div className="variables-list">
              {!selectedResource ? (
                <p className="no-variables">Select a resource to view its variables</p>
              ) : variables.length === 0 ? (
                <p className="no-variables">No variables for this resource</p>
              ) : (
                variables.map((variable) => (
                  <div key={variable.name} className="variable-item">
                    <div className="variable-name">{variable.name}</div>
                    {editingVar === variable.name ? (
                      <div className="variable-edit">
                        <input
                          type={variable.sensitive ? 'password' : 'text'}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="variable-input"
                          autoFocus
                        />
                        <div className="variable-actions">
                          <button onClick={() => handleSaveVariable(variable.name)} className="btn-save-small">Save</button>
                          <button onClick={handleCancelEdit} className="btn-cancel-small">Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div className="variable-view">
                        <span className="variable-value">
                          {variable.sensitive ? '***' : variable.value || '(empty)'}
                        </span>
                        <button 
                          onClick={() => handleEditVariable(variable.name, variable.value || '')} 
                          className="btn-edit-small"
                          title="Edit variable"
                        >
                          Edit
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {selectedResource && selectedResource.status === 'enabled' && (
        <div className="saved-outputs">
          <div className="outputs-header">
            <h3>Resource Outputs</h3>
            <div className="outputs-header-actions">
              <button
                onClick={handleGetOutputs}
                className="btn-outputs-small"
                title="Fetch latest outputs"
              >
                Get Outputs
              </button>
              {outputs.filter(o => o.resourceId === selectedResource.id).length > 0 && (
                <button onClick={clearOutputs} className="btn-clear-small">Clear</button>
              )}
            </div>
          </div>
          <div className="outputs-list">
            {(() => {
              const resourceOutputs = outputs.filter(output => output.resourceId === selectedResource.id);
              
              if (resourceOutputs.length === 0) {
                return (
                  <div className="no-outputs">
                    <p>No outputs yet</p>
                    <p className="hint">Click "Outputs" button to fetch resource outputs</p>
                  </div>
                );
              }
              
              const latestOutput = resourceOutputs[0];
              const index = 0;
              const isCollapsed = collapsedOutputs.has(index);
              
              return (
                <div 
                  key={index} 
                  className="output-item"
                >
                  <div 
                    className="output-header-item clickable"
                    onClick={() => toggleOutputCollapse(index)}
                    title="Click to collapse/expand"
                  >
                    <span className="expand-icon">{isCollapsed ? '▶' : '▼'}</span>
                    <span className="output-resource">{latestOutput.resourceName}</span>
                    <span className="output-time">{new Date(latestOutput.timestamp).toLocaleString()}</span>
                  </div>
                  {!isCollapsed && (
                    <pre className="output-content expanded">
                      {latestOutput.output}
                    </pre>
                  )}
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {!selectedResource && (
        <div className="no-selection">
          <p>👈 Select a resource from the left panel to perform actions</p>
        </div>
      )}
      
      {showSGEditor && createPortal(
        <SecurityGroupEditor
          onClose={() => setShowSGEditor(false)}
          onSave={() => {
            setShowSGEditor(false);
          }}
        />,
        document.body
      )}
      
      {showEKSEditor && createPortal(
        <EKSEditor
          onClose={() => setShowEKSEditor(false)}
          onSave={() => {
            setShowEKSEditor(false);
          }}
        />,
        document.body
      )}
      
      {showDescriptionModal && selectedResource && createPortal(
        <DescriptionModal
          resourceId={selectedResource.id}
          resourceName={selectedResource.description || selectedResource.name}
          onClose={() => setShowDescriptionModal(false)}
        />,
        document.body
      )}
      {showDebugModal && selectedResource && createPortal(
        <DebugModal
          resourceId={selectedResource.id}
          resourceName={selectedResource.name}
          resourceFilePath={selectedResource.file_path}
          onClose={() => setShowDebugModal(false)}
          onActionStart={onActionStart}
          onActionUpdate={onActionUpdate}
          onActionComplete={onActionComplete}
        />,
        document.body
      )}
      {pendingConfirm && (
        <ConfirmModal
          title={pendingConfirm.type === 'destroy' ? 'Destroy Resource' : 'Restore Variables'}
          message={
            pendingConfirm.type === 'destroy'
              ? `This will DELETE the AWS resources for ${selectedResource?.name}. Are you sure?`
              : 'Clear all instance-specific variables for this resource? Values will fall back to global or defaults.'
          }
          confirmLabel={pendingConfirm.type === 'destroy' ? 'Destroy' : 'Restore'}
          danger={pendingConfirm.type === 'destroy'}
          onConfirm={pendingConfirm.onConfirm}
          onCancel={() => setPendingConfirm(null)}
        />
      )}
      {rdpInfo && createPortal(
        <div className="modal-overlay" onClick={() => setRdpInfo(null)}>
          <div className="rdp-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="rdp-modal-title">Windows RDP Connection</h3>
            <div className="rdp-modal-fields">
              <div className="rdp-field">
                <label className="rdp-field-label">Host IP</label>
                <div className="rdp-field-value-row">
                  <code className="rdp-field-value">{rdpInfo.ip}</code>
                  <button className="rdp-copy-btn" onClick={() => copyToClipboard(rdpInfo.ip)}>Copy</button>
                </div>
              </div>
              <div className="rdp-field">
                <label className="rdp-field-label">Username</label>
                <div className="rdp-field-value-row">
                  <code className="rdp-field-value">{rdpInfo.username}</code>
                  <button className="rdp-copy-btn" onClick={() => copyToClipboard(rdpInfo.username)}>Copy</button>
                </div>
              </div>
              <div className="rdp-field">
                <label className="rdp-field-label">Password</label>
                {rdpInfo.password ? (
                  <div className="rdp-field-value-row">
                    <code className="rdp-field-value">{rdpInfo.password}</code>
                    <button className="rdp-copy-btn" onClick={() => copyToClipboard(rdpInfo.password)}>Copy</button>
                  </div>
                ) : (
                  <div className="rdp-field-hint">
                    Password not yet available. Windows instances take ~4 minutes to generate the password after launch. Click "Update" to refresh.
                  </div>
                )}
              </div>
            </div>
            <div className="rdp-modal-actions">
              <button className="confirm-modal-btn cancel" onClick={() => setRdpInfo(null)}>Close</button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

export default ActionPanel;
