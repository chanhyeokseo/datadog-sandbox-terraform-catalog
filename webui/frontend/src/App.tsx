import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ResourceSidebar from './components/ResourceSidebar';
import ActionPanel from './components/ActionPanel';
import ResultsPanel from './components/ResultsPanel';
import ConfigModal from './components/ConfigModal';
import ConnectionsModal from './components/ConnectionsModal';
import OnboardingModal from './components/OnboardingModal';
import DangerZoneModal from './components/DangerZoneModal';
import { TerraformResource, ResourceType } from './types';
import { terraformApi as api, OnboardingStatus } from './services/api';

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
  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatus | null>(null);
  const [resourceRefreshTrigger, setResourceRefreshTrigger] = useState(0);
  const [runningResources, setRunningResources] = useState<Map<string, string>>(new Map());
  type LoadPhase = 'config_check' | 'loading' | 'ready';
  const [initialLoadPhase, setInitialLoadPhase] = useState<LoadPhase>('config_check');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [providerReady, setProviderReady] = useState<boolean | null>(null);
  const [providerProgress, setProviderProgress] = useState({ progress: 0, message: '' });

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
      setIsDarkMode(false);
      document.body.classList.add('light-mode');
    }
    let cancelled = false;
    const run = async () => {
      try {
        const configStatus = await api.getConfigOnboardingStatus();
        if (cancelled) return;
        const hasUnfilledStep = configStatus.steps?.some((s: { filled: boolean }) => !s.filled) ?? false;
        if (configStatus.config_onboarding_required && hasUnfilledStep) {
          navigate('/onboarding', { replace: true });
          return;
        }
        setInitialLoadPhase('loading');
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
        if (cancelled) return;
        setInitialLoadPhase('loading');
        const id = setInterval(async () => {
          if (cancelled) return;
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
  }, []);

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
        if (!cancelled) setProviderReady(true);
      }
    };
    check();
    return () => { cancelled = true; if (pollId) clearInterval(pollId); };
  }, []);

  const finishLoadingAndRefresh = async () => {
    try {
      const configStatus = await api.getConfigOnboardingStatus();
      if (configStatus.config_onboarding_required) {
        navigate('/onboarding', { replace: true });
        return;
      }
      await api.getResources();
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
    const sharedResource = resources.find(r => {
      return r.id === 'security_group' || r.name === 'security_group' || r.id.includes('shared');
    });
    
    if (sharedResource) {
      setShowOnboardingModal(false);
      
      setTimeout(() => {
        setSelectedResource(sharedResource);
        
        const successResult: Result = {
          id: Date.now().toString(),
          action: 'ONBOARDING',
          status: 'success',
          message: '✅ Security Group resource selected! Click PLAN to preview, and DEPLOY to deploy.',
          timestamp: new Date(),
          output: ''
        };
        setResults(prev => [successResult, ...prev]);
      }, 100);
    } else {
      console.error('Shared resource not found in resources:', resources);
      alert('⚠️ Shared resource not found. Resources available: ' + resources.map(r => r.id).join(', '));
    }
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

  if (initialLoadPhase === 'config_check') {
    return (
      <div className="app-loading-screen app-loading-minimal">
        <p className="app-loading-text">Checking configuration...</p>
      </div>
    );
  }

  if (initialLoadPhase === 'loading' || (initialLoadPhase === 'ready' && providerReady !== true)) {
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
      <header className="app-header">
        <div className="header-content">
          <img src="/logo.png" alt="DogSTAC" className="app-logo-header" />
          <h1>DogSTAC</h1>
        </div>
        <div className="header-actions">
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

      <button
        className="danger-zone-fab"
        onClick={() => setShowDangerZone(true)}
        title="Danger Zone"
      >
        ⚠
      </button>
    </div>
  );
}

export default App;
