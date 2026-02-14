import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  terraformApi,
  backendApi,
  keysApi,
  ConfigOnboardingStatus,
  ConfigOnboardingStep,
  ConfigOnboardingPhase,
  AwsVpc,
  AwsSubnet,
} from '../services/api';
import '../styles/App.css';
import '../styles/Unified.css';
import '../styles/OnboardingPage.css';

const AWS_REGIONS = [
  'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3', 'ap-south-1', 'ap-south-2',
  'ap-southeast-1', 'ap-southeast-2', 'ap-southeast-3', 'ap-southeast-4', 'ca-central-1',
  'ca-west-1', 'eu-central-1', 'eu-central-2', 'eu-north-1', 'eu-south-1', 'eu-south-2',
  'eu-west-1', 'eu-west-2', 'eu-west-3', 'il-central-1', 'me-central-1', 'me-south-1',
  'sa-east-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
];

function getPlaceholder(v: ConfigOnboardingStep): string | undefined {
  if (v.sensitive) return '••••••••';
  if (v.name === 'creator') return 'firstname.lastname';
  if (v.name === 'team') return 'technical-support-engineering';
  if (v.name === 'aws_session_token') return 'Optional';
  return undefined;
}

function OnboardingPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConfigOnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);
  const [phaseValues, setPhaseValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vpcs, setVpcs] = useState<AwsVpc[]>([]);
  const [subnets, setSubnets] = useState<AwsSubnet[]>([]);
  const [vpcLoading, setVpcLoading] = useState(false);
  const [keyResult, setKeyResult] = useState<{ key_name: string; private_key: string; key_path: string; ssh_hint: string } | null>(null);
  const [keyGenerating, setKeyGenerating] = useState(false);
  const [backendSetup, setBackendSetup] = useState<{
    status: 'idle' | 'setting_up' | 'complete' | 'error';
    message?: string;
  }>({ status: 'idle' });

  const phases: ConfigOnboardingPhase[] = status?.phases ?? [];
  const shouldRedirect = !loading && !!(status && (!status.config_onboarding_required || (status.phases?.length === 0 && status.steps?.length === 0)));

  useEffect(() => {
    document.body.classList.add('onboarding-route');
    return () => document.body.classList.remove('onboarding-route');
  }, []);

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    if (!shouldRedirect) return;
    navigate('/', { replace: true });
    const t = setTimeout(() => window.location.replace('/'), 800);
    return () => clearTimeout(t);
  }, [shouldRedirect, navigate]);

  const loadVpcs = async () => {
    const vars = await terraformApi.getVariables();
    const region = vars.find(v => v.name === 'region')?.value?.trim() || '';
    if (!region) return;
    setVpcLoading(true);
    setError(null);
    try {
      const d = await terraformApi.getAwsVpcs(region);
      setVpcs(d.vpcs);
    } catch (err) {
      setError((err as Error).message);
      setVpcs([]);
    } finally {
      setVpcLoading(false);
    }
  };

  useEffect(() => {
    if (currentPhaseIndex !== 2 || !status) return;
    loadVpcs();
  }, [currentPhaseIndex, status]);

  const loadStatus = async () => {
    try {
      const data = await terraformApi.getConfigOnboardingStatus();
      if (!data.config_onboarding_required) {
        window.location.replace('/');
        return;
      }
      setStatus(data);
      setLoading(false);
      const firstIncomplete = data.phases?.findIndex(p => !p.all_filled) ?? 0;
      setCurrentPhaseIndex(firstIncomplete >= 0 ? firstIncomplete : 0);
      const teamVar = data.steps?.find(s => s.name === 'team');
      if (teamVar && !teamVar.filled) {
        setPhaseValues(prev => ({ ...prev, team: 'technical-support-engineering' }));
      }
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  const saveAndNextPhase = async () => {
    const phase = phases[currentPhaseIndex];
    if (!phase || !status) return;
    setError(null);
    setSaving(true);
    try {
      for (const v of phase.variables) {
        const val = phaseValues[v.name];
        if (val === undefined && v.filled) continue;
        await terraformApi.updateRootVariable(v.name, (val ?? '').trim());
      }
      setPhaseValues({});
      const updated = await terraformApi.getConfigOnboardingStatus();
      setStatus(updated);
      if (!updated.config_onboarding_required) {
        // Sync tfvars to all instances
        await terraformApi.syncTfvarsToInstances().catch(() => {});

        // Sync configuration to Parameter Store (for persistence)
        await terraformApi.syncToParameterStore().catch((err) => {
          console.warn('Failed to sync to Parameter Store:', err);
        });

        // Setup backend infrastructure automatically
        await setupBackendInfrastructure();

        localStorage.removeItem('onboarding_dismissed');
        navigate('/', { replace: true });
        return;
      }
      const nextIncomplete = updated.phases?.findIndex(p => !p.all_filled) ?? currentPhaseIndex + 1;
      setCurrentPhaseIndex(nextIncomplete >= 0 ? nextIncomplete : phases.length - 1);
      if (currentPhaseIndex === 2) setSubnets([]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const setupBackendInfrastructure = async () => {
    setBackendSetup({ status: 'setting_up', message: 'Setting up S3 backend...' });
    try {
      // Get variables for bucket name
      const vars = await terraformApi.getVariables();
      const creator = vars.find(v => v.name === 'creator')?.value || 'default';
      const team = vars.find(v => v.name === 'team')?.value || 'default';
      const region = vars.find(v => v.name === 'region')?.value || 'ap-northeast-2';

      // Get suggested bucket and table names from backend (uses AWS credential hash)
      const { bucket_name: bucketName, table_name: tableName } = await backendApi.getSuggestedBucketName(creator, team);

      // Setup backend
      const result = await backendApi.setupBackend({
        bucket_name: bucketName,
        table_name: tableName,
        region: region
      });

      if (result.success) {
        setBackendSetup({
          status: 'complete',
          message: `Backend configured! S3: ${bucketName}`
        });

        // Upload SSH keys to Parameter Store if they exist
        if (keyResult) {
          try {
            await keysApi.uploadKey({
              key_name: keyResult.key_name,
              private_key_content: keyResult.private_key,
              description: 'Auto-uploaded during onboarding'
            });
          } catch (keyErr) {
            console.warn('Failed to upload key to Parameter Store:', keyErr);
          }
        }
      } else {
        setBackendSetup({
          status: 'error',
          message: 'Backend setup failed. You can configure it later in Settings.'
        });
      }
    } catch (err) {
      console.error('Backend setup error:', err);
      setBackendSetup({
        status: 'error',
        message: 'Backend setup failed. You can configure it later in Settings.'
      });
    }
  };

  const handleVpcSelect = (vpcId: string) => {
    setPhaseValues((prev: Record<string, string>) => ({ ...prev, vpc_id: vpcId }));
    const getRegion = async () => {
      const vars = await terraformApi.getVariables();
      return vars.find(v => v.name === 'region')?.value?.trim() || '';
    };
    setSubnets([]);
    getRegion().then(region => {
      if (region && vpcId) terraformApi.getAwsSubnets(region, vpcId).then(d => setSubnets(d.subnets));
    });
  };

  const isPhaseComplete = () => {
    const phase = phases[currentPhaseIndex];
    if (!phase) return false;
    if (currentPhaseIndex === 1) {
      return !!phase.variables.find(v => v.name === 'ec2_key_name')?.filled;
    }
    if (currentPhaseIndex === 2) {
      return !!(
        (phaseValues.vpc_id || phase.variables.find(v => v.name === 'vpc_id')?.filled) &&
        (phaseValues.public_subnet_id || phase.variables.find(v => v.name === 'public_subnet_id')?.filled) &&
        (phaseValues.public_subnet2_id || phase.variables.find(v => v.name === 'public_subnet2_id')?.filled) &&
        (phaseValues.private_subnet_id || phase.variables.find(v => v.name === 'private_subnet_id')?.filled)
      );
    }
    return phase.variables.every((v: ConfigOnboardingStep) => {
      const val = phaseValues[v.name];
      if (v.name === 'aws_session_token') return true;
      return (val !== undefined && val.trim() !== '') || v.filled;
    });
  };

  if (loading) {
    return (
      <div className="onboarding-page">
        <div className="onboarding-page-loading">Loading...</div>
      </div>
    );
  }

  if (shouldRedirect || !status || !phases.length) {
    return (
      <div className="onboarding-page">
        <div className="onboarding-page-loading">Redirecting...</div>
      </div>
    );
  }

  const phase = phases[currentPhaseIndex];
  const totalPhases = phases.length;
  const completedPhases = phases.filter(p => p.all_filled).length;
  const progressPercent = totalPhases ? (completedPhases / totalPhases) * 100 : 0;
  const isLastPhase = currentPhaseIndex === totalPhases - 1;
  const isKeyPhase = currentPhaseIndex === 1;
  const isVpcPhase = currentPhaseIndex === 2;

  const handleGenerateKeyPair = async () => {
    setError(null);
    setKeyGenerating(true);
    try {
      const result = await terraformApi.createAwsKeyPair();
      setKeyResult(result);
      const updated = await terraformApi.getConfigOnboardingStatus();
      setStatus(updated);
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(ax?.response?.data?.detail ?? (err as Error).message);
    } finally {
      setKeyGenerating(false);
    }
  };

  const keyFilled = !!phase?.variables.find(v => v.name === 'ec2_key_name')?.filled;

  return (
    <div className="onboarding-page">
      <h1 className="onboarding-page-welcome">Welcome to DogSTAC</h1>
      <div className="onboarding-page-card">
        <h2 className="onboarding-page-title">{phase?.name ?? 'Configuration'}</h2>
        <p className="onboarding-page-subtitle">Phase {currentPhaseIndex + 1} of {totalPhases}</p>

        {isKeyPhase ? (
          <div className="onboarding-step onboarding-phase-key">
            {!keyFilled && !keyResult ? (
              <>
                <p className="onboarding-step-loading">Generate an EC2 key pair for SSH access. The private key will be saved in the project and used by Terraform.</p>
                <button type="button" className="onboarding-btn-primary" onClick={handleGenerateKeyPair} disabled={keyGenerating}>
                  {keyGenerating ? 'Generating...' : 'Generate key pair'}
                </button>
              </>
            ) : keyResult ? (
              <>
                <p className="onboarding-key-saved">Key pair created. Save the private key below for manual SSH access (it is also saved to <strong>{keyResult.key_path}</strong>).</p>
                <div className="onboarding-step-field">
                  <div className="onboarding-step-label-row">
                    <label className="onboarding-step-label">Private key (copy and save securely)</label>
                    <button
                      type="button"
                      className="onboarding-btn-refresh"
                      onClick={() => navigator.clipboard.writeText(keyResult.private_key)}
                    >
                      Copy
                    </button>
                  </div>
                  <textarea
                    className="onboarding-step-input onboarding-key-textarea"
                    readOnly
                    value={keyResult.private_key}
                    onClick={(e) => (e.target as HTMLTextAreaElement).select()}
                  />
                </div>
                <p className="onboarding-ssh-hint">{keyResult.ssh_hint}</p>
              </>
            ) : (
              <p className="onboarding-step-loading">EC2 key pair is configured. Key file is in the <strong>keys/</strong> directory. For manual SSH: <code>ssh -i keys/&lt;key-name&gt;.pem ec2-user@&lt;instance-ip&gt;</code></p>
            )}
          </div>
        ) : isVpcPhase ? (
          <div className="onboarding-step onboarding-phase-vpc">
            {vpcLoading ? (
              <p className="onboarding-step-loading">Loading VPCs...</p>
            ) : (
              <>
                <div className="onboarding-step-field">
                  <div className="onboarding-step-label-row">
                    <label className="onboarding-step-label">VPC</label>
                    <button type="button" className="onboarding-btn-refresh" onClick={loadVpcs} title="Refresh VPC list">Refresh</button>
                  </div>
                  <select
                    className="onboarding-step-input onboarding-select"
                    value={phaseValues.vpc_id ?? ''}
                    onChange={(e) => handleVpcSelect(e.target.value)}
                  >
                    <option value="">Select VPC</option>
                    {vpcs.map(v => (
                      <option key={v.id} value={v.id}>{v.name || v.id} ({v.cidr})</option>
                    ))}
                  </select>
                </div>
                <p className="onboarding-subnet-requirement">DogSTAC requires at least 2 public subnets and 1 private subnet.</p>
                {subnets.length > 0 && (
                  <>
                    <div className="onboarding-step-field">
                      <label className="onboarding-step-label">Public Subnet 1</label>
                      <select
                        className="onboarding-step-input onboarding-select"
                        value={phaseValues.public_subnet_id ?? ''}
                        onChange={(e) => setPhaseValues(p => ({ ...p, public_subnet_id: e.target.value }))}
                      >
                        <option value="">Select subnet</option>
                        {subnets.map(s => (
                          <option key={s.id} value={s.id}>{s.name || s.id} ({s.cidr}, {s.az})</option>
                        ))}
                      </select>
                    </div>
                    <div className="onboarding-step-field">
                      <label className="onboarding-step-label">Public Subnet 2</label>
                      <select
                        className="onboarding-step-input onboarding-select"
                        value={phaseValues.public_subnet2_id ?? ''}
                        onChange={(e) => setPhaseValues(p => ({ ...p, public_subnet2_id: e.target.value }))}
                      >
                        <option value="">Select subnet</option>
                        {subnets.map(s => (
                          <option key={s.id} value={s.id}>{s.name || s.id} ({s.cidr}, {s.az})</option>
                        ))}
                      </select>
                    </div>
                    <div className="onboarding-step-field">
                      <label className="onboarding-step-label">Private Subnet</label>
                      <select
                        className="onboarding-step-input onboarding-select"
                        value={phaseValues.private_subnet_id ?? ''}
                        onChange={(e) => setPhaseValues(p => ({ ...p, private_subnet_id: e.target.value }))}
                      >
                        <option value="">Select subnet</option>
                        {subnets.map(s => (
                          <option key={s.id} value={s.id}>{s.name || s.id} ({s.cidr}, {s.az})</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        ) : (
          <div className="onboarding-step">
            {phase?.variables.map((variable: ConfigOnboardingStep) => (
              <div key={variable.name} className="onboarding-step-field">
                <label className="onboarding-step-label">{variable.label}</label>
                {variable.name === 'region' ? (
                  <>
                    <input
                      type="text"
                      list="onboarding-regions"
                      value={phaseValues[variable.name] ?? ''}
                      onChange={(e) => setPhaseValues(p => ({ ...p, [variable.name]: e.target.value }))}
                      className="onboarding-step-input"
                      placeholder="Select or type region (e.g. us-east-1)"
                      autoComplete="off"
                    />
                    <datalist id="onboarding-regions">
                      {AWS_REGIONS.map((r) => (
                        <option key={r} value={r} />
                      ))}
                    </datalist>
                  </>
                ) : (
                  <input
                    type={variable.sensitive ? 'password' : 'text'}
                    value={phaseValues[variable.name] ?? ''}
                    onChange={(e) => setPhaseValues(p => ({ ...p, [variable.name]: e.target.value }))}
                    className="onboarding-step-input"
                    placeholder={getPlaceholder(variable) ?? `Enter ${variable.label.toLowerCase()}`}
                  />
                )}
              </div>
            ))}
            {currentPhaseIndex === 0 && (
              <p className="onboarding-resource-naming-note">
                Resources will be named with the prefix <strong>{'{project_name}-{project_env}'}</strong> (e.g. myproject-dev). Tags and name_prefix use this format across instances.
              </p>
            )}
          </div>
        )}

        {error && <p className="onboarding-step-error">{error}</p>}

        {backendSetup.status !== 'idle' && (
          <div className={`onboarding-backend-status onboarding-backend-${backendSetup.status}`}>
            {backendSetup.status === 'setting_up' && '⏳ '}
            {backendSetup.status === 'complete' && '✅ '}
            {backendSetup.status === 'error' && '⚠️ '}
            {backendSetup.message}
          </div>
        )}

        <div className="onboarding-step-actions">
          <button
            onClick={saveAndNextPhase}
            disabled={saving || !isPhaseComplete() || backendSetup.status === 'setting_up'}
            className="onboarding-btn-primary"
          >
            {backendSetup.status === 'setting_up' ? 'Setting up backend...' : saving ? 'Saving...' : isLastPhase && isPhaseComplete() ? 'Complete' : 'Next'}
          </button>
        </div>

        <div className="onboarding-progress-wrap">
          <div className="onboarding-progress-bar">
            <div className="onboarding-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <p className="onboarding-progress-text">{completedPhases} of {totalPhases} phases completed</p>
        </div>
      </div>
    </div>
  );
}

export default OnboardingPage;
