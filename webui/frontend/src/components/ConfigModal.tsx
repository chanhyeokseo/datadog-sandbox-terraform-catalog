import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { TerraformVariable } from '../types';
import { terraformApi } from '../services/api';

interface ConfigModalProps {
  onClose: () => void;
  onSave: (message: string) => void;
}

const ConfigModal = ({ onClose, onSave }: ConfigModalProps) => {
  const [commonVars, setCommonVars] = useState<TerraformVariable[]>([]);
  const [editingVar, setEditingVar] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadVariables();
  }, []);

  const loadVariables = async () => {
    try {
      const vars = await terraformApi.getVariables();
      const common = vars.filter(v => v.is_common);
      setCommonVars(common);
      setLoading(false);
    } catch (err) {
      console.error('Failed to load variables:', err);
      setLoading(false);
    }
  };

  const handleEditVariable = (varName: string, currentValue: string) => {
    setEditingVar(varName);
    setEditValue(currentValue);
  };

  const handleSaveVariable = async (varName: string) => {
    try {
      await terraformApi.updateRootVariable(varName, editValue);
      await loadVariables();
      setEditingVar(null);
      onSave(`Variable ${varName} updated successfully`);
    } catch (err) {
      alert(`Failed to update variable: ${(err as Error).message}`);
    }
  };

  const handleCancelEdit = () => {
    setEditingVar(null);
    setEditValue('');
  };

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      if (editingVar) {
        handleCancelEdit();
      } else {
        onClose();
      }
    }
  };

  return createPortal(
    <div className="config-modal-overlay" onClick={handleOverlayClick} onKeyDown={handleKeyDown}>
      <div className="config-modal">
        <div className="modal-header">
          <h2>⚙️ Global Configurations</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>
        <div className="modal-body config-body">
          {loading ? (
            <p className="loading-text">Loading...</p>
          ) : (
            <div className="config-variables-list">
              {commonVars.length === 0 ? (
                <p className="no-variables">No configuration variables found</p>
              ) : (
                commonVars.map((variable) => (
                  <div key={variable.name} className="config-variable-item">
                    <div className="config-variable-name">{variable.name}</div>
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
                          <button onClick={() => handleSaveVariable(variable.name)} className="btn-save-small">💾</button>
                          <button onClick={handleCancelEdit} className="btn-cancel-small">❌</button>
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
                          ✏️
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ConfigModal;
