import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import ResourceSidebar from './components/ResourceSidebar';
import ActionPanel from './components/ActionPanel';
import ResultsPanel from './components/ResultsPanel';
import ConfigModal from './components/ConfigModal';
import ConnectionsModal from './components/ConnectionsModal';
import OnboardingModal from './components/OnboardingModal';
import DangerZoneModal from './components/DangerZoneModal';
import SSOLoginModal from './components/SSOLoginModal';
import IdleOverlay from './components/IdleOverlay';
import FeedbackFab from './components/FeedbackFab';
import ClusterShareModal from './components/ClusterShareModal';
import Tutorial, { TutorialStep } from './components/Tutorial';
import { TerraformResource, ResourceType } from './types';
import { terraformApi as api, OnboardingStatus } from './services/api';

const TUTORIAL_STEPS: TutorialStep[] = [
  {
    target: '[data-tutorial="resource-security_group"]',
    title: 'Select Security Group',
    description: 'Security Group is the foundational resource that other resources depend on. Click it to select.',
    placement: 'right',
    advanceOn: 'click',
  },
  {
    target: '[data-tutorial="btn-deploy"]',
    title: 'Deploy Security Group',
    description: 'Click Deploy to provision the Security Group. This creates firewall rules that protect your resources.',
    placement: 'bottom',
    advanceOn: 'click',
  },
  {
    target: '[data-tutorial="results-panel"]',
    title: 'Deploying...',
    description: 'Terraform is provisioning your Security Group. You can watch the real-time output in the Results panel.',
    placement: 'left',
    advanceOn: 'action-complete',
  },
  {
    target: '[data-tutorial="btn-plan"]',
    title: 'Plan (Optional)',
    description: 'Plan lets you preview what Terraform will change before applying. It is safe and makes no modifications to your infrastructure.',
    placement: 'bottom',
  },
  {
    target: '[data-tutorial="btn-destroy"]',
    title: 'Destroy',
    description: 'Destroy tears down the deployed AWS resources. Use it to clean up when you no longer need them.',
    placement: 'bottom',
  },
  {
    target: '[data-tutorial="resource-ec2_basic"]',
    title: 'Select EC2 Basic',
    description: 'Now let\'s try launching an EC2 instance. Click EC2 Basic to select it.',
    placement: 'right',
    advanceOn: 'click',
  },
  {
    target: '[data-tutorial="btn-deploy"]',
    title: 'Deploy EC2 Instance',
    description: 'Click Deploy to launch your first EC2 instance. This will take a minute or two.',
    placement: 'bottom',
    advanceOn: 'click',
  },
  {
    target: '[data-tutorial="results-panel"]',
    title: 'Deploying EC2...',
    description: 'Terraform is launching your EC2 instance. Watch the progress here — it may take a minute or two.',
    placement: 'left',
    advanceOn: 'action-complete',
  },
  {
    target: '[data-tutorial="btn-connect"]',
    title: 'Connect via SSH',
    description: 'Your instance is running! Click Connect to open an SSH terminal. A new window will open — you can try commands there, then come back to this tab to finish the tutorial.',
    placement: 'bottom',
    advanceOn: 'click',
    waitForSelector: '[data-tutorial="btn-connect"]',
  },
  {
    target: '[data-tutorial="btn-destroy"]',
    title: 'Clean Up',
    description: 'Great job! Now destroy the EC2 instance to clean up. Click Destroy.',
    placement: 'bottom',
    advanceOn: 'action-complete',
  },
];

interface CredentialError {
  type: 'profile_not_found' | 'expired';
  profile?: string;
  ssoCommand?: string;
  ssoConfigured?: boolean;
  message?: string;
}

const ProfileNotFoundScreen = ({ error, onRetry }: { error: CredentialError; onRetry: () => void }) => (
  <div className="app-loading-screen">
    <div className="app-loading-content">
      <img src="/logo.png" alt="DogSTAC" className="app-logo" />
      <h1 className="app-loading-title">DogSTAC</h1>
      <div className="credential-error-card">
        <p className="credential-error-title">AWS Profile Not Found</p>
        <p className="credential-error-desc">
          The AWS profile <strong>{error.profile}</strong> does not exist in <code>~/.aws/config</code>.
          Update <code>AWS_PROFILE</code> in your <code>.env</code> file and restart docker compose.
        </p>
        <pre className="credential-error-code">
{`# 1. Fix .env
AWS_PROFILE=your-valid-profile

# 2. Restart
docker compose down && docker compose up -d`}
        </pre>
        <button onClick={onRetry} className="credential-error-btn">
          Retry
        </button>
      </div>
    </div>
  </div>
);

const ProviderLoadingScreen = ({ progress, message }: { progress: number; message: string }) => (
  <div className="app-loading-screen">
    <div className="app-loading-content">
      <img src="/logo.png" alt="DogSTAC" className="app-logo" />
      <h1 className="app-loading-title">DogSTAC</h1>
      <div style={{ width: '280px', margin: '24px auto 16px' }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px',
        }}>
          <span style={{ fontSize: '0.9em', fontWeight: 600 }}>Downloading AWS Provider</span>
          <span style={{ fontSize: '0.85em', opacity: 0.7 }}>{progress}%</span>
        </div>
        <div style={{
          height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', width: `${progress}%`,
            background: 'linear-gradient(90deg, #4a9eff, #6c5ce7)',
            borderRadius: '4px', transition: 'width 0.6s ease',
          }} />
        </div>
      </div>
      <p className="app-loading-text" style={{ opacity: 0.6, fontSize: '0.8em' }}>
        {message || 'Preparing provider plugins...'}
      </p>
    </div>
  </div>
);
import './styles/App.css';
import './styles/Unified.css';
import './styles/DangerZone.css';

interface Result {
  id: string;
  action: string;
  status: 'running' | 'success' | 'error';
  message: string;
  timestamp: Date;
  output?: string;
}

function App() {
  const navigate = useNavigate();
  const [selectedResource, setSelectedResource] = useState<TerraformResource | null>(null);
  const [resources, setResources] = useState<TerraformResource[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showConnectionsModal, setShowConnectionsModal] = useState(false);
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);
  const [showDangerZone, setShowDangerZone] = useState(false);
  const [showClusterShareModal, setShowClusterShareModal] = useState(false);
  const [sharedClusterRefreshTrigger, setSharedClusterRefreshTrigger] = useState(0);
  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatus | null>(null);
  const [resourceRefreshTrigger, setResourceRefreshTrigger] = useState(0);
  const [runningResources, setRunningResources] = useState<Map<string, string>>(new Map());
  type LoadPhase = 'config_check' | 'loading' | 'ready';
  const [initialLoadPhase, setInitialLoadPhase] = useState<LoadPhase>('config_check');
  const [credentialError, setCredentialError] = useState<CredentialError | null>(null);
  const [showSSOModal, setShowSSOModal] = useState(false);
  const [showIdleOverlay, setShowIdleOverlay] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const healthRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const idleSinceRef = useRef<number>(0);
  const [providerReady, setProviderReady] = useState<boolean | null>(null);
  const [providerProgress, setProviderProgress] = useState({ progress: 0, message: '' });
  const [feedbackFabPulse, setFeedbackFabPulse] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const showTutorialRef = useRef(false);
  const [showCongrats, setShowCongrats] = useState(false);
  const [showMcpGuide, setShowMcpGuide] = useState(false);
  const [tutorialActionEvent, setTutorialActionEvent] = useState<string | undefined>(undefined);
  const [initTrigger, setInitTrigger] = useState(0);

  useEffect(() => { showTutorialRef.current = showTutorial; }, [showTutorial]);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
      setIsDarkMode(false);
      document.body.classList.add('light-mode');
    }
    let cancelled = false;
    const run = async () => {
      const extractCredentialError = (err: any): CredentialError => {
        const detail = err?.response?.data?.detail;
        if (detail?.error_type === 'profile_not_found') {
          return { type: 'profile_not_found', profile: detail.aws_profile || '', message: detail.message };
        }
        return {
          type: 'expired',
          ssoCommand: detail?.sso_command || 'aws sso login',
          ssoConfigured: detail?.sso_configured ?? false,
        };
      };
      try {
        await api.checkCredentials();
      } catch (err: any) {
        if (cancelled) return;
        if (err?.response?.status === 401) {
          setCredentialError(extractCredentialError(err));
          return;
        }
      }
      if (cancelled) return;
      try {
        await api.ensureData();
      } catch (err) {
        console.warn('ensureData failed, continuing:', err);
      }
      if (cancelled) return;
      let reachedLoading = false;
      try {
        const configStatus = await api.getConfigOnboardingStatus();
        if (cancelled) return;
        if (configStatus.credential_expired) {
          setCredentialError({ type: 'expired', ssoConfigured: true });
          return;
        }
        const hasUnfilledStep = configStatus.steps?.some((s: { filled: boolean }) => !s.filled) ?? false;
        if (configStatus.config_onboarding_required && hasUnfilledStep) {
          navigate('/onboarding', { replace: true });
          return;
        }
        setInitialLoadPhase('loading');
        reachedLoading = true;
        await api.getResources();
        if (cancelled) return;
        const status = await api.getOnboardingStatus();
        setOnboardingStatus(status);
        const dismissed = localStorage.getItem('onboarding_dismissed');
        if (status.onboarding_required && !dismissed) {
          setShowOnboardingModal(true);
        }
        setInitialLoadPhase('ready');
      } catch (err: any) {
        if (cancelled) return;
        if (err?.response?.status === 401) {
          setCredentialError(extractCredentialError(err));
          return;
        }
        if (!reachedLoading) setInitialLoadPhase('loading');
        const id = setInterval(async () => {
          if (cancelled) return;
          try {
            await api.checkCredentials();
          } catch (credErr: any) {
            if (credErr?.response?.status === 401) {
              clearInterval(id);
              setCredentialError(extractCredentialError(credErr));
            }
            return;
          }
          try {
            await api.ensureData();
          } catch (_) {}
          try {
            const configStatus = await api.getConfigOnboardingStatus();
            if (cancelled) return;
            clearInterval(id);
            const hasUnfilled = configStatus.steps?.some((s: { filled: boolean }) => !s.filled) ?? false;
            if (configStatus.config_onboarding_required && hasUnfilled) {
              navigate('/onboarding', { replace: true });
              return;
            }
            await api.getResources();
            if (cancelled) return;
            const status = await api.getOnboardingStatus();
            setOnboardingStatus(status);
            const dismissed = localStorage.getItem('onboarding_dismissed');
            if (status.onboarding_required && !dismissed) {
              setShowOnboardingModal(true);
            }
            setInitialLoadPhase('ready');
          } catch (_) {
            // keep polling
          }
        }, 2000);
        intervalRef.current = id;
      }
    };
    run();
    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [initTrigger]);

  useEffect(() => {
    let cancelled = false;
    let pollId: ReturnType<typeof setInterval> | null = null;
    const check = async () => {
      try {
        const s = await api.getProviderCacheStatus();
        if (cancelled) return;
        setProviderProgress({ progress: s.progress, message: s.message });
        if (s.ready) {
          setProviderReady(true);
          return;
        }
        setProviderReady(false);
        pollId = setInterval(async () => {
          try {
            const s = await api.getProviderCacheStatus();
            if (cancelled) return;
            setProviderProgress({ progress: s.progress, message: s.message });
            if (s.ready) {
              setProviderReady(true);
              if (pollId) clearInterval(pollId);
            }
          } catch {}
        }, 2000);
      } catch {
        if (!cancelled) {
          pollId = setInterval(async () => {
            try {
              const s = await api.getProviderCacheStatus();
              if (cancelled) return;
              setProviderProgress({ progress: s.progress, message: s.message });
              if (s.ready) {
                setProviderReady(true);
                if (pollId) clearInterval(pollId);
              } else {
                setProviderReady(false);
              }
            } catch {}
          }, 2000);
        }
      }
    };
    check();
    return () => { cancelled = true; if (pollId) clearInterval(pollId); };
  }, []);

  useEffect(() => {
    if (initialLoadPhase !== 'ready') return;
    let lastCheckTs = 0;
    const DEBOUNCE_MS = 5000;
    const IDLE_THRESHOLD_MS = 300_000;
    const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart'] as const;

    const checkHealth = async () => {
      const now = Date.now();
      if (now - lastCheckTs < DEBOUNCE_MS) return;
      lastCheckTs = now;
      try {
        const health = await api.getCredentialHealth();
        if (health.status === 'expiring_soon' || health.status === 'expired') {
          try {
            await api.checkCredentials();
          } catch (err: any) {
            if (err?.response?.status === 401) {
              const detail = err?.response?.data?.detail;
              setCredentialError({
                type: 'expired',
                ssoCommand: detail?.sso_command || 'aws sso login',
                ssoConfigured: detail?.sso_configured ?? health.sso_configured,
              });
              setShowSSOModal(true);
            }
          }
        }
      } catch {}
    };

    let idleTimer: ReturnType<typeof setTimeout> | null = null;

    const markIdle = () => {
      idleSinceRef.current = Date.now();
      setShowIdleOverlay(true);
    };

    const resetIdleTimer = () => {
      if (idleSinceRef.current) return;
      if (idleTimer) clearTimeout(idleTimer);
      idleTimer = setTimeout(markIdle, IDLE_THRESHOLD_MS);
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        if (idleTimer) clearTimeout(idleTimer);
        if (!idleSinceRef.current) idleSinceRef.current = Date.now();
        idleTimer = setTimeout(markIdle, Math.max(0, IDLE_THRESHOLD_MS - (Date.now() - idleSinceRef.current)));
      } else if (document.visibilityState === 'visible') {
        if (idleSinceRef.current && Date.now() - idleSinceRef.current >= IDLE_THRESHOLD_MS) {
          setShowIdleOverlay(true);
        } else {
          resetIdleTimer();
        }
      }
    };

    resetIdleTimer();
    for (const evt of ACTIVITY_EVENTS) document.addEventListener(evt, resetIdleTimer, { passive: true });
    document.addEventListener('visibilitychange', onVisibilityChange);
    healthRef.current = setInterval(checkHealth, 300000);

    return () => {
      if (idleTimer) clearTimeout(idleTimer);
      for (const evt of ACTIVITY_EVENTS) document.removeEventListener(evt, resetIdleTimer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      if (healthRef.current) clearInterval(healthRef.current);
    };
  }, [initialLoadPhase]);

  useEffect(() => {
    const handleCredExpired = async () => {
      try {
        await api.checkCredentials();
      } catch (err: any) {
        if (err?.response?.status === 401) {
          const detail = err?.response?.data?.detail;
          setCredentialError({
            type: 'expired',
            ssoCommand: detail?.sso_command || 'aws sso login',
            ssoConfigured: detail?.sso_configured ?? false,
          });
          setShowSSOModal(true);
        }
      }
    };
    window.addEventListener('sso-credential-expired', handleCredExpired);
    return () => window.removeEventListener('sso-credential-expired', handleCredExpired);
  }, []);

  useEffect(() => {
    if (initialLoadPhase !== 'ready') return;
    let cancelled = false;
    const resumeActiveOps = async () => {
      try {
        const ops = await api.getActiveOperations();
        if (cancelled || !ops || Object.keys(ops).length === 0) return;
        for (const [resourceId, info] of Object.entries(ops)) {
          const action = info.operation === 'apply' ? 'deploy' : 'destroy';
          const resultId = Date.now().toString() + '_' + resourceId;
          setResults(prev => [{
            id: resultId,
            action: action.toUpperCase(),
            status: 'running' as const,
            message: `Reconnected to running ${action}...`,
            timestamp: new Date(),
            output: '',
          }, ...prev]);
          setRunningResources(prev => new Map(prev).set(resourceId, action));
          const streamFn = info.operation === 'apply'
            ? api.streamApplyResource
            : api.streamDestroyResource;
          streamFn(
            resourceId,
            false,
            (chunk) => {
              setResults(prev => {
                const updated = [...prev];
                const idx = updated.findIndex(r => r.id === resultId);
                if (idx !== -1) {
                  updated[idx] = { ...updated[idx], output: (updated[idx].output || '') + chunk };
                }
                return updated;
              });
            },
            (success) => {
              if (!success && action === 'destroy') {
                setFeedbackFabPulse(true);
              }
              if (success && action === 'destroy') {
                setFeedbackFabPulse(false);
              }
              setResults(prev => {
                const updated = [...prev];
                const idx = updated.findIndex(r => r.id === resultId);
                if (idx !== -1) {
                  updated[idx] = {
                    ...updated[idx],
                    status: success ? 'success' : 'error',
                    message: success ? `${action.toUpperCase()} completed successfully` : `${action.toUpperCase()} failed`,
                  };
                }
                return updated;
              });
              setRunningResources(prev => {
                const m = new Map(prev);
                m.delete(resourceId);
                return m;
              });
              if (success) {
                setResourceRefreshTrigger(prev => prev + 1);
              }
            },
          );
        }
      } catch (err) {
        console.warn('Failed to check active operations:', err);
      }
    };
    resumeActiveOps();
    return () => { cancelled = true; };
  }, [initialLoadPhase]);

  const finishLoadingAndRefresh = async () => {
    try {
      const configStatus = await api.getConfigOnboardingStatus();
      if (configStatus.config_onboarding_required) {
        navigate('/onboarding', { replace: true });
        return;
      }
      const status = await api.getOnboardingStatus();
      setOnboardingStatus(status);
      const dismissed = localStorage.getItem('onboarding_dismissed');
      if (status.onboarding_required && !dismissed) {
        setShowOnboardingModal(true);
      }
    } catch (error) {
      console.error('Failed to check onboarding status:', error);
    }
  };

  const toggleTheme = () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    
    if (newMode) {
      document.body.classList.remove('light-mode');
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.classList.add('light-mode');
      localStorage.setItem('theme', 'light');
    }
  };

  const handleActionStart = (action: string, resourceId?: string) => {
    const newResult: Result = {
      id: Date.now().toString(),
      action: action.toUpperCase(),
      status: 'running',
      message: `Running ${action}...`,
      timestamp: new Date(),
      output: ''
    };
    setResults(prev => [newResult, ...prev]);
    
    if (resourceId) {
      setRunningResources(prev => new Map(prev).set(resourceId, action));
    }
    
    return newResult.id;
  };

  const handleActionUpdate = (id: string, outputChunk: string) => {
    setResults(prev => {
      const updated = [...prev];
      const index = updated.findIndex(r => r.id === id);
      if (index !== -1) {
        updated[index] = {
          ...updated[index],
          output: (updated[index].output || '') + outputChunk
        };
      }
      return updated;
    });
  };

  const handleActionComplete = (id: string, success: boolean, action: string, resourceId?: string) => {
    const a = action.toLowerCase();
    if (!success && (a === 'plan' || a === 'destroy')) {
      setFeedbackFabPulse(true);
    }
    if (success && (a === 'plan' || a === 'destroy')) {
      setFeedbackFabPulse(false);
    }
    setResults(prev => {
      const updated = [...prev];
      const index = updated.findIndex(r => r.id === id);
      if (index !== -1) {
        updated[index] = {
          ...updated[index],
          status: success ? 'success' : 'error',
          message: success ? `${action.toUpperCase()} completed successfully` : `${action.toUpperCase()} failed`
        };
      }
      return updated;
    });

    if (resourceId) {
      setRunningResources(prev => {
        const newMap = new Map(prev);
        newMap.delete(resourceId);
        return newMap;
      });
    }

    if (showTutorialRef.current && success) {
      setTutorialActionEvent(`${a}-success-${Date.now()}`);
    }
  };

  const handleClearResults = () => {
    setResults([]);
  };

  const handleConfigSave = (message: string) => {
    const newResult: Result = {
      id: Date.now().toString(),
      action: 'CONFIG',
      status: 'success',
      message: message,
      timestamp: new Date(),
      output: ''
    };
    setResults(prev => [newResult, ...prev]);
  };

  const handleResourcesNeedRefresh = () => {
    setResourceRefreshTrigger(prev => prev + 1);
    
    setTimeout(() => {
      finishLoadingAndRefresh();
    }, 1000);
  };

  const handleSelectShared = () => {
    const tutorialDone = localStorage.getItem('tutorial_completed') === 'true';
    setShowOnboardingModal(false);

    if (!tutorialDone) {
      setTimeout(() => setShowTutorial(true), 200);
    } else {
      const sharedResource = resources.find(r =>
        r.id === 'security_group' || r.name === 'security_group' || r.id.includes('shared')
      );
      if (sharedResource) {
        setTimeout(() => {
          setSelectedResource(sharedResource);
          const successResult: Result = {
            id: Date.now().toString(),
            action: 'ONBOARDING',
            status: 'success',
            message: 'Security Group resource selected! Click PLAN to preview, and DEPLOY to deploy.',
            timestamp: new Date(),
            output: ''
          };
          setResults(prev => [successResult, ...prev]);
        }, 100);
      }
    }
  };

  const handleTutorialComplete = () => {
    setShowTutorial(false);
    localStorage.setItem('tutorial_completed', 'true');
    setShowCongrats(true);
  };

  const handleTutorialSkip = () => {
    setShowTutorial(false);
    localStorage.setItem('tutorial_completed', 'true');
  };

  const handleOpenConnections = () => {
    setShowConnectionsModal(true);
  };

  const handleUpdateIP = () => {
    const securityGroupResource = resources.find((r: TerraformResource) => 
      r.type === ResourceType.SECURITY_GROUP || r.id.includes('security_group')
    );
    
    if (securityGroupResource) {
      setSelectedResource(securityGroupResource);
    } else {
      alert('❌ Security Group resource not found');
    }
  };

  const handleCredentialRetry = useCallback(() => {
    setCredentialError(null);
    setShowSSOModal(false);
    setInitialLoadPhase('config_check');
    setInitTrigger(prev => prev + 1);
  }, []);

  const handleSSOSuccess = useCallback(() => {
    setCredentialError(null);
    setShowSSOModal(false);
    setInitialLoadPhase('config_check');
    setInitTrigger(prev => prev + 1);
  }, []);

  const handleIdleResume = useCallback(async () => {
    try {
      const health = await api.getCredentialHealth();
      if (health.status === 'expiring_soon' || health.status === 'expired') {
        await api.checkCredentials();
      }
      idleSinceRef.current = 0;
      setShowIdleOverlay(false);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        const detail = err?.response?.data?.detail;
        idleSinceRef.current = 0;
        setShowIdleOverlay(false);
        setCredentialError({
          type: 'expired',
          ssoCommand: detail?.sso_command || 'aws sso login',
          ssoConfigured: detail?.sso_configured ?? false,
        });
        setShowSSOModal(true);
        return;
      }
      throw err;
    }
  }, []);

  if (credentialError?.type === 'profile_not_found') {
    return <ProfileNotFoundScreen error={credentialError} onRetry={handleCredentialRetry} />;
  }

  if (credentialError && initialLoadPhase !== 'ready') {
    return (
      <SSOLoginModal
        ssoConfigured={credentialError.ssoConfigured ?? false}
        ssoCommand={credentialError.ssoCommand || 'aws sso login'}
        onSuccess={handleSSOSuccess}
        onRetry={handleCredentialRetry}
      />
    );
  }

  if (initialLoadPhase === 'config_check') {
    return (
      <div className="app-loading-screen app-loading-minimal">
        <p className="app-loading-text">Checking configuration...</p>
      </div>
    );
  }

  if (initialLoadPhase === 'loading') {
    if (providerReady === false) {
      return <ProviderLoadingScreen progress={providerProgress.progress} message={providerProgress.message} />;
    }
    return (
      <div className="app-loading-screen">
        <div className="app-loading-content">
          <img src="/logo.png" alt="DogSTAC" className="app-logo" />
          <h1 className="app-loading-title">DogSTAC</h1>
          <div className="app-loading-spinner" />
          <p className="app-loading-text">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      {providerReady !== true && (
        providerReady === false
          ? <ProviderLoadingScreen progress={providerProgress.progress} message={providerProgress.message} />
          : (
            <div className="app-loading-screen">
              <div className="app-loading-content">
                <img src="/logo.png" alt="DogSTAC" className="app-logo" />
                <h1 className="app-loading-title">DogSTAC</h1>
                <div className="app-loading-spinner" />
                <p className="app-loading-text">Loading...</p>
              </div>
            </div>
          )
      )}
      <header className="app-header">
        <div className="header-content">
          <img src="/logo.png" alt="DogSTAC" className="app-logo-header" />
          <h1>DogSTAC</h1>
        </div>
        <div className="header-actions">
          <button onClick={() => setShowMcpGuide(true)} className="config-button">
            🤖 MCP Server
          </button>
          <button onClick={handleOpenConnections} className="config-button">
            🔗 Connections
          </button>
          <button onClick={handleUpdateIP} className="config-button">
            🌐 Security Group
          </button>
          <button onClick={() => setShowConfigModal(true)} className="config-button">
            ⚙️ Config
          </button>
          <button onClick={toggleTheme} className="theme-toggle">
            {isDarkMode ? '☀️ Light Mode' : '🌙 Dark Mode'}
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="three-panel-layout">
          <ResourceSidebar
            onResourceSelect={setSelectedResource}
            selectedResourceId={selectedResource?.id || null}
            refreshTrigger={resourceRefreshTrigger}
            runningResources={runningResources}
            onResourcesLoaded={setResources}
            onRequestClusterShare={() => setShowClusterShareModal(true)}
            sharedClusterRefreshTrigger={sharedClusterRefreshTrigger}
          />
          <ActionPanel
            selectedResource={selectedResource}
            onActionStart={handleActionStart}
            onActionUpdate={handleActionUpdate}
            onActionComplete={handleActionComplete}
            onResourcesNeedRefresh={handleResourcesNeedRefresh}
            runningAction={selectedResource ? runningResources.get(selectedResource.id) : undefined}
          />
          <ResultsPanel
            results={results}
            onClear={handleClearResults}
          />
        </div>
      </main>

      {showConfigModal && (
        <ConfigModal 
          onClose={() => setShowConfigModal(false)}
          onSave={handleConfigSave}
        />
      )}

      {showConnectionsModal && (
        <ConnectionsModal 
          onClose={() => setShowConnectionsModal(false)}
        />
      )}

      {showOnboardingModal && onboardingStatus && (
        <OnboardingModal
          status={onboardingStatus}
          onClose={() => setShowOnboardingModal(false)}
          onSelectShared={handleSelectShared}
        />
      )}

      {showDangerZone && (
        <DangerZoneModal
          onClose={() => setShowDangerZone(false)}
          onResourcesNeedRefresh={handleResourcesNeedRefresh}
        />
      )}

      {showClusterShareModal && (
        <ClusterShareModal
          onClose={() => setShowClusterShareModal(false)}
          onSharedClustersChanged={() => setSharedClusterRefreshTrigger(prev => prev + 1)}
        />
      )}

      {showSSOModal && credentialError?.type === 'expired' && (
        <SSOLoginModal
          ssoConfigured={credentialError.ssoConfigured ?? false}
          ssoCommand={credentialError.ssoCommand || 'aws sso login'}
          onSuccess={handleSSOSuccess}
          onRetry={handleCredentialRetry}
        />
      )}

      {showIdleOverlay && <IdleOverlay onResume={handleIdleResume} />}

      <FeedbackFab
        selectedResourceId={selectedResource?.id ?? null}
        latestResultAction={results[0]?.action ?? null}
        latestResultStatus={results[0]?.status ?? null}
        emphasizePulse={feedbackFabPulse}
        onOpenModal={() => setFeedbackFabPulse(false)}
      />

      <button
        type="button"
        className="danger-zone-fab"
        onClick={() => setShowDangerZone(true)}
        aria-label="Danger Zone"
      >
        <span className="danger-zone-fab-icon" aria-hidden>
          ⚠
        </span>
        <span className="danger-zone-fab-label">Danger Zone</span>
      </button>

      <Tutorial
        steps={TUTORIAL_STEPS}
        isActive={showTutorial}
        actionCompleted={tutorialActionEvent}
        onComplete={handleTutorialComplete}
        onSkip={handleTutorialSkip}
      />

      {(showCongrats || showMcpGuide) && (
        <div className="tutorial-congrats-overlay" onClick={() => { setShowCongrats(false); setShowMcpGuide(false); }}>
          <div className="tutorial-congrats-modal tutorial-congrats-modal--wide" onClick={e => e.stopPropagation()}>
            {showCongrats && (
              <>
                <div className="tutorial-congrats-icon">🎉</div>
                <h2 className="tutorial-congrats-title">
                  Congratulations! You completed the DogSTAC tutorial.
                </h2>
                <p className="tutorial-congrats-body">
                  You have deployed a Security Group, launched and connected to an EC2 instance,
                  and cleaned up resources with Destroy. You are ready to explore everything DogSTAC has to offer.
                </p>
              </>
            )}
            <div className="tutorial-congrats-mcp">
              <p className="tutorial-congrats-mcp-heading">
                <strong>Connect the DogSTAC MCP Server to your IDE</strong>
              </p>
              <p>
                DogSTAC ships with an MCP server that lets AI assistants manage your
                infrastructure directly. Add the following to your MCP config:
              </p>
              <pre className="tutorial-congrats-code">{`{
  "mcpServers": {
    "dogstac": {
      "type": "sse",
      "url": "http://localhost:7622/sse"
    }
  }
}`}</pre>
              <p className="tutorial-congrats-mcp-sub">
                The MCP server starts automatically with <code>docker-compose up</code> on
                port <strong>7622</strong>. To use a custom port, set <code>MCP_PORT</code> in
                your <code>.env</code> file.
              </p>
              <img
                src="/dogstac-mcp-demo.gif"
                alt="DogSTAC MCP Demo"
                className="tutorial-congrats-gif"
              />
            </div>
            <div className="tutorial-congrats-mcp tutorial-congrats-examples">
              <p>
                Complex implementations are also possible! For example:
              </p>
              <ol>
                <li>Set up Oracle DB with DBM, then generate slow query example data via a load generator</li>
                <li>Configure Squid Proxy metric collection environment</li>
                <li>Set up Windows Security Events collection with Datadog Agent on a Windows Host</li>
              </ol>
              <p className="tutorial-congrats-examples-cta">
                Skeptical? Try it yourself :)
              </p>
            </div>
            <button className="tutorial-btn-start" onClick={() => { setShowCongrats(false); setShowMcpGuide(false); }}>
              {showCongrats ? 'Get Started' : 'Close'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
