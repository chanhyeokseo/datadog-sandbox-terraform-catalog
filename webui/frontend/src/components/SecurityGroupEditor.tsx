import { useState, useEffect } from 'react';
import '../styles/SecurityGroupEditor.css';

interface SecurityGroupRule {
  description: string;
  from_port: number;
  to_port: number;
  protocol: string;
  cidr_blocks: string[];
  readonly?: boolean;
  use_my_ip?: boolean;
  original_cidr?: string;
}

interface SecurityGroupEditorProps {
  onClose: () => void;
  onSave: (ingressRules: SecurityGroupRule[], egressRules: SecurityGroupRule[]) => void;
}

const COMMON_PORTS = {
  'SSH': { port: 22, protocol: 'tcp' },
  'RDP': { port: 3389, protocol: 'tcp' },
  'HTTP': { port: 80, protocol: 'tcp' },
  'HTTPS': { port: 443, protocol: 'tcp' },
  'MySQL/Aurora': { port: 3306, protocol: 'tcp' },
  'PostgreSQL': { port: 5432, protocol: 'tcp' },
  'Custom TCP': { port: 0, protocol: 'tcp' },
  'Custom UDP': { port: 0, protocol: 'udp' },
  'All Traffic': { port: 0, protocol: '-1' },
};

const SecurityGroupEditor = ({ onClose, onSave }: SecurityGroupEditorProps) => {
  const [ingressRules, setIngressRules] = useState<SecurityGroupRule[]>([]);
  const [egressRules, setEgressRules] = useState<SecurityGroupRule[]>([]);
  const [activeTab, setActiveTab] = useState<'inbound' | 'outbound'>('inbound');
  const [loading, setLoading] = useState(true);
  const [myIp, setMyIp] = useState<string>('');

  useEffect(() => {
    const init = async () => {
      await fetchMyIp();
    };
    init();
    
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  useEffect(() => {
    if (myIp) {
      loadRules();
    }
  }, [myIp]);

  const fetchMyIp = async () => {
    try {
      const response = await fetch('https://ifconfig.me/ip');
      const ip = await response.text();
      setMyIp(ip.trim());
    } catch (error) {
      console.error('Failed to fetch my IP:', error);
    }
  };

  const loadRules = async () => {
    try {
      const response = await fetch('/api/terraform/security-group/rules');
      const data = await response.json();
      
      let ingress = data.ingress_rules || [];
      
      if (myIp) {
        ingress = ingress.map((rule: SecurityGroupRule) => {
          if (rule.from_port === 22 || rule.from_port === 3389) {
            return {
              ...rule,
              use_my_ip: true,
              cidr_blocks: [`${myIp}/32`],
              original_cidr: rule.cidr_blocks[0] || '0.0.0.0/0'
            };
          }
          if (rule.use_my_ip) {
            return {
              ...rule,
              cidr_blocks: [`${myIp}/32`]
            };
          }
          return rule;
        });
      }
      
      setIngressRules(ingress);
      setEgressRules(data.egress_rules || []);
    } catch (error) {
      console.error('Failed to load rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const addRule = (type: 'inbound' | 'outbound') => {
    const newRule: SecurityGroupRule = {
      description: '',
      from_port: 22,
      to_port: 22,
      protocol: 'tcp',
      cidr_blocks: myIp ? [`${myIp}/32`] : ['0.0.0.0/0'],
    };

    if (type === 'inbound') {
      setIngressRules([...ingressRules, newRule]);
    } else {
      setEgressRules([...egressRules, newRule]);
    }
  };

  const removeRule = (type: 'inbound' | 'outbound', index: number) => {
    if (type === 'inbound') {
      setIngressRules(ingressRules.filter((_, i) => i !== index));
    } else {
      setEgressRules(egressRules.filter((_, i) => i !== index));
    }
  };

  const updateRule = (type: 'inbound' | 'outbound', index: number, field: keyof SecurityGroupRule, value: any) => {
    const updateRuleInArray = (rules: SecurityGroupRule[]) => {
      const newRules = [...rules];
      if (field === 'cidr_blocks') {
        newRules[index] = { 
          ...newRules[index], 
          [field]: [value],
          use_my_ip: false
        };
      } else {
        newRules[index] = { ...newRules[index], [field]: value };
      }
      return newRules;
    };

    if (type === 'inbound') {
      setIngressRules(updateRuleInArray(ingressRules));
    } else {
      setEgressRules(updateRuleInArray(egressRules));
    }
  };

  const toggleMyIp = (type: 'inbound' | 'outbound', index: number) => {
    const rules = type === 'inbound' ? ingressRules : egressRules;
    const rule = rules[index];
    
    if (!myIp) return;
    
    const newRules = [...rules];
    if (rule.use_my_ip) {
      newRules[index] = {
        ...rule,
        use_my_ip: false,
        cidr_blocks: [rule.original_cidr || '0.0.0.0/0']
      };
    } else {
      newRules[index] = {
        ...rule,
        use_my_ip: true,
        original_cidr: rule.cidr_blocks[0] || '0.0.0.0/0',
        cidr_blocks: [`${myIp}/32`]
      };
    }
    
    if (type === 'inbound') {
      setIngressRules(newRules);
    } else {
      setEgressRules(newRules);
    }
  };

  const applyCommonPort = (type: 'inbound' | 'outbound', index: number, portType: string) => {
    const portConfig = COMMON_PORTS[portType as keyof typeof COMMON_PORTS];
    if (!portConfig) return;

    if (portConfig.protocol === '-1') {
      updateRule(type, index, 'from_port', 0);
      updateRule(type, index, 'to_port', 0);
      updateRule(type, index, 'protocol', '-1');
    } else {
      updateRule(type, index, 'from_port', portConfig.port);
      updateRule(type, index, 'to_port', portConfig.port);
      updateRule(type, index, 'protocol', portConfig.protocol);
    }
  };

  const handleSave = async () => {
    try {
      const response = await fetch('/api/terraform/security-group/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ingress_rules: ingressRules,
          egress_rules: egressRules,
        }),
      });

      const result = await response.json();
      
      if (result.success) {
        alert('✅ Security Group rules saved! Click UPDATE to apply changes.');
        onSave(ingressRules, egressRules);
        onClose();
      } else {
        alert('❌ Failed to save rules');
      }
    } catch (error) {
      alert(`❌ Error: ${(error as Error).message}`);
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const renderRuleTable = (rules: SecurityGroupRule[], type: 'inbound' | 'outbound') => (
    <div className="rules-table-container">
      <table className="rules-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Protocol</th>
            <th>Port Range</th>
            <th>Source/Destination</th>
            <th>Description</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.length === 0 ? (
            <tr>
              <td colSpan={6} className="empty-rules">
                No {type} rules configured. Click "Add Rule" to create one.
              </td>
            </tr>
          ) : (
            rules.map((rule, index) => (
              <tr key={index} className={rule.readonly ? 'readonly-row' : ''}>
                <td>
                  <select
                    value={
                      Object.entries(COMMON_PORTS).find(
                        ([_, config]) =>
                          config.port === rule.from_port &&
                          config.protocol === rule.protocol
                      )?.[0] || 'Custom TCP'
                    }
                    onChange={(e) => applyCommonPort(type, index, e.target.value)}
                    className="rule-input rule-select"
                    disabled={rule.readonly}
                  >
                    {Object.keys(COMMON_PORTS).map((portType) => (
                      <option key={portType} value={portType}>
                        {portType}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="text"
                    value={rule.protocol}
                    onChange={(e) => updateRule(type, index, 'protocol', e.target.value)}
                    className="rule-input"
                    placeholder="tcp"
                    disabled={rule.readonly}
                  />
                </td>
                <td>
                  <div className="port-range">
                    <input
                      type="number"
                      value={rule.from_port}
                      onChange={(e) => updateRule(type, index, 'from_port', parseInt(e.target.value))}
                      className="rule-input port-input"
                      placeholder="From"
                      disabled={rule.readonly}
                    />
                    <span>-</span>
                    <input
                      type="number"
                      value={rule.to_port}
                      onChange={(e) => updateRule(type, index, 'to_port', parseInt(e.target.value))}
                      className="rule-input port-input"
                      placeholder="To"
                      disabled={rule.readonly}
                    />
                  </div>
                </td>
                <td>
                  <div className="cidr-input-container">
                    <input
                      type="text"
                      value={rule.cidr_blocks[0] || ''}
                      onChange={(e) => updateRule(type, index, 'cidr_blocks', e.target.value)}
                      className="rule-input"
                      placeholder="0.0.0.0/0"
                      disabled={rule.readonly || rule.use_my_ip}
                      style={rule.use_my_ip ? { background: 'rgba(0, 123, 255, 0.2)' } : {}}
                    />
                    {myIp && !rule.readonly && (
                      <button
                        onClick={() => toggleMyIp(type, index)}
                        className={`btn-my-ip ${rule.use_my_ip ? 'active' : ''}`}
                        title={rule.use_my_ip ? 'Disable auto-update with My IP' : 'Enable auto-update with My IP'}
                      >
                        {rule.use_my_ip ? '✓ My IP' : 'My IP'}
                      </button>
                    )}
                  </div>
                </td>
                <td>
                  <input
                    type="text"
                    value={rule.description}
                    onChange={(e) => updateRule(type, index, 'description', e.target.value)}
                    className="rule-input"
                    placeholder="Description"
                    disabled={rule.readonly}
                  />
                </td>
                <td>
                  {!rule.readonly && (
                    <button
                      onClick={() => removeRule(type, index)}
                      className="btn-remove"
                      title="Remove rule"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      <button onClick={() => addRule(type)} className="btn-add-rule">
        + Add Rule
      </button>
    </div>
  );

  if (loading) {
    return (
      <div className="modal-overlay" onClick={handleOverlayClick}>
        <div className="sg-modal" onClick={(e) => e.stopPropagation()}>
          <div className="loading-spinner">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="sg-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sg-modal-header">
          <h2>🛡️ Customize Security Group Rules</h2>
          <button onClick={onClose} className="close-button">&times;</button>
        </div>

        <div className="sg-tabs">
          <button
            className={`sg-tab ${activeTab === 'inbound' ? 'active' : ''}`}
            onClick={() => setActiveTab('inbound')}
          >
            Inbound Rules ({ingressRules.length})
          </button>
          <button
            className={`sg-tab ${activeTab === 'outbound' ? 'active' : ''}`}
            onClick={() => setActiveTab('outbound')}
          >
            Outbound Rules ({egressRules.length})
          </button>
        </div>

        <div className="sg-modal-body">
          {activeTab === 'inbound' ? renderRuleTable(ingressRules, 'inbound') : renderRuleTable(egressRules, 'outbound')}
        </div>

        <div className="sg-modal-footer">
          <button onClick={onClose} className="btn-sg-cancel">
            Cancel
          </button>
          <button onClick={handleSave} className="btn-sg-save">
            Save Rules
          </button>
        </div>
      </div>
    </div>
  );
};

export default SecurityGroupEditor;
