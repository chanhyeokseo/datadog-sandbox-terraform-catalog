import { useState, useEffect } from 'react';
import { TerraformResource, ResourceType, ResourceStatus, SharedCluster } from '../types';
import { terraformApi, clusterShareApi } from '../services/api';

interface ResourceSidebarProps {
  onResourceSelect: (resource: TerraformResource | null) => void;
  selectedResourceId: string | null;
  refreshTrigger?: number;
  runningResources?: Map<string, string>;
  onResourcesLoaded?: (resources: TerraformResource[]) => void;
  onRequestClusterShare?: () => void;
  sharedClusterRefreshTrigger?: number;
  onOpenConfig?: () => void;
  onOpenConnections?: () => void;
  onOpenMcpGuide?: () => void;
  onOpenAuditLog?: () => void;
  onUpdateIP?: () => void;
  isDarkMode?: boolean;
  onToggleTheme?: () => void;
  activeView?: string;
}

const ResourceSidebar = ({
  onResourceSelect,
  selectedResourceId,
  refreshTrigger,
  runningResources,
  onResourcesLoaded,
  onRequestClusterShare,
  sharedClusterRefreshTrigger,
  onOpenConfig,
  onOpenConnections,
  onOpenMcpGuide,
  onOpenAuditLog,
  onUpdateIP,
  isDarkMode,
  onToggleTheme,
  activeView,
}: ResourceSidebarProps) => {
  const [resources, setResources] = useState<TerraformResource[]>([]);
  const [sharedClusters, setSharedClusters] = useState<SharedCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null);

  const getInitialExpandedSections = (): Set<string> => {
    const saved = localStorage.getItem('expanded_sections');
    if (saved) {
      try {
        return new Set(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse expanded sections:', e);
      }
    }
    return new Set(['ec2', 'eks']);
  };

  const [expandedSections, setExpandedSections] = useState<Set<string>>(getInitialExpandedSections());

  const loadResources = async (initial = true) => {
    try {
      if (initial) setLoading(true);
      const data = await terraformApi.getResources();
      setResources(data);
      sessionStorage.setItem('terraform_resources', JSON.stringify(data));
      if (onResourcesLoaded) onResourcesLoaded(data);
      if (selectedResourceId) {
        const updatedResource = data.find(r => r.id === selectedResourceId);
        if (updatedResource) onResourceSelect(updatedResource);
      }
    } catch (err) {
      console.error('Failed to load resources:', err);
    } finally {
      if (initial) setLoading(false);
    }
  };

  const loadSharedClusters = async () => {
    try {
      const shared = await clusterShareApi.getSharedClusters();
      setSharedClusters(shared);
    } catch (err) {
      console.error('Failed to load shared clusters:', err);
    }
  };

  const checkHealth = async () => {
    try {
      await terraformApi.checkHealth();
      setBackendHealthy(true);
    } catch {
      setBackendHealthy(false);
    }
  };

  useEffect(() => {
    loadResources(true);
    loadSharedClusters();
    checkHealth();
    const healthInterval = setInterval(checkHealth, 30000);
    return () => clearInterval(healthInterval);
  }, []);

  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) loadResources(false);
  }, [refreshTrigger]);

  useEffect(() => {
    loadSharedClusters();
  }, [sharedClusterRefreshTrigger]);

  const toggleSection = (type: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(type)) {
      newExpanded.delete(type);
    } else {
      newExpanded.add(type);
    }
    setExpandedSections(newExpanded);
    localStorage.setItem('expanded_sections', JSON.stringify(Array.from(newExpanded)));
  };

  const groupedResources = resources.reduce((acc, resource) => {
    if (!acc[resource.type]) acc[resource.type] = [];
    acc[resource.type].push(resource);
    return acc;
  }, {} as Record<string, TerraformResource[]>);

  const RESOURCE_TYPE_ORDER = ['ec2', 'eks', 'ecs', 'lambda', 'ecr', 'rds', 'security_group', 'test'];

  if (sharedClusters.length > 0 && !groupedResources['eks']) {
    groupedResources['eks'] = [];
  }

  const sortedResourceTypes = Object.keys(groupedResources).sort((a, b) => {
    const indexA = RESOURCE_TYPE_ORDER.indexOf(a);
    const indexB = RESOURCE_TYPE_ORDER.indexOf(b);
    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
    if (indexA !== -1) return -1;
    if (indexB !== -1) return 1;
    return a.localeCompare(b);
  });

  const getTypeIcon = (type: string): string => {
    const icons: Record<string, string> = {
      security_group: '🛡️',
      test: '🧪',
      ec2: '🖥️',
      rds: '🗄️',
      eks: '☸️',
      ecs: '🐳',
      ecr: '📦',
      lambda: '⚡',
    };
    return icons[type] || '📄';
  };

  return (
    <nav className="sidebar-nav">
      <div className="sidebar-nav-header">
        <img src="/logo.png" alt="DogSTAC" className="sidebar-nav-logo" />
        <span className="sidebar-nav-title">DogSTAC</span>
      </div>

      <div className="sidebar-nav-content">
        <div className="sidebar-nav-section">
          <div className="sidebar-nav-section-label">OVERVIEW</div>
          <div
            className="sidebar-nav-item"
            onClick={onOpenMcpGuide}
          >
            <span className="sidebar-nav-item-icon">🤖</span>
            <span className="sidebar-nav-item-text">MCP Server</span>
          </div>
          <div
            className={`sidebar-nav-item ${activeView === 'audit-log' ? 'active' : ''}`}
            onClick={onOpenAuditLog}
          >
            <span className="sidebar-nav-item-icon">📋</span>
            <span className="sidebar-nav-item-text">Audit Log</span>
          </div>
          <div
            className="sidebar-nav-item"
            onClick={() => loadResources(false)}
          >
            <span className="sidebar-nav-item-icon">🔄</span>
            <span className="sidebar-nav-item-text">Refresh Resources</span>
          </div>
        </div>

        <div className="sidebar-nav-section">
          <div className="sidebar-nav-section-label">INFRASTRUCTURE</div>
          {loading ? (
            <div className="sidebar-nav-loading">Loading...</div>
          ) : (
            sortedResourceTypes.map(type => {
              const items = groupedResources[type];
              return (
                <div key={type} className="sidebar-nav-group">
                  <div
                    className="section-header"
                    data-tutorial-section={type}
                    onClick={() => toggleSection(type)}
                  >
                    <span className="section-icon">{expandedSections.has(type) ? '▼' : '▶'}</span>
                    <span className="section-title">
                      {getTypeIcon(type)} {type.toUpperCase()}
                    </span>
                    <span className="section-count">{items.length + (type === 'eks' ? sharedClusters.length : 0)}</span>
                  </div>

                  {expandedSections.has(type) && (
                    <div className="section-items">
                      {items.map((resource) => (
                        <div
                          key={resource.id}
                          data-tutorial={`resource-${resource.id}`}
                          className={`sidebar-item ${selectedResourceId === resource.id ? 'selected' : ''} ${runningResources?.has(resource.id) ? 'running' : ''}`}
                          onClick={() => onResourceSelect(resource)}
                        >
                          <span className={`item-status ${runningResources?.has(resource.id) ? 'running' : resource.status === 'enabled' ? 'enabled' : 'disabled'}`} />
                          <div className="item-content">
                            <div className="item-name">{resource.description || resource.name}</div>
                          </div>
                        </div>
                      ))}
                      {type === 'eks' && sharedClusters.map((sc) => {
                        const sharedId = `shared-eks-${sc.cluster_arn}`;
                        return (
                          <div
                            key={sharedId}
                            className={`sidebar-item shared-item ${selectedResourceId === sharedId ? 'selected' : ''}`}
                            onClick={() => onResourceSelect({
                              id: sharedId,
                              name: sc.cluster_name,
                              type: ResourceType.EKS,
                              file_path: `Shared from ${sc.owner_prefix}`,
                              line_start: 0,
                              line_end: 0,
                              status: ResourceStatus.ENABLED,
                              description: `Shared EKS Cluster: ${sc.owner_prefix}`,
                              is_shared: true,
                              shared_from: sc.owner_prefix,
                            })}
                          >
                            <span className="item-status shared" />
                            <div className="item-content">
                              <div className="item-name">Shared EKS: {sc.owner_prefix}</div>
                            </div>
                          </div>
                        );
                      })}
                      {type === 'eks' && (
                        <div
                          className="sidebar-action-item"
                          onClick={() => onRequestClusterShare?.()}
                        >
                          <span className="action-icon">🔗</span>
                          <span className="action-label">Request Cluster Share</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="sidebar-nav-section">
          <div className="sidebar-nav-section-label">SETTINGS</div>
          <div className="sidebar-nav-item" onClick={onOpenConfig}>
            <span className="sidebar-nav-item-icon">⚙️</span>
            <span className="sidebar-nav-item-text">Configuration</span>
          </div>
          <div className="sidebar-nav-item" onClick={onOpenConnections}>
            <span className="sidebar-nav-item-icon">🔗</span>
            <span className="sidebar-nav-item-text">Connections</span>
          </div>
          <div className="sidebar-nav-item" onClick={onUpdateIP}>
            <span className="sidebar-nav-item-icon">🌐</span>
            <span className="sidebar-nav-item-text">Security Group</span>
          </div>
          <div className="sidebar-nav-item" onClick={onToggleTheme}>
            <span className="sidebar-nav-item-icon">{isDarkMode ? '☀️' : '🌙'}</span>
            <span className="sidebar-nav-item-text">{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
          </div>
        </div>
      </div>

      <div className="sidebar-nav-footer">
        <div className={`sidebar-nav-health ${backendHealthy === true ? 'healthy' : backendHealthy === false ? 'unhealthy' : ''}`}>
          <span className="sidebar-nav-health-dot" />
          <span className="sidebar-nav-health-text">
            {backendHealthy === null ? 'Checking...' : backendHealthy ? 'Backend Healthy' : 'Backend Unreachable'}
          </span>
        </div>
      </div>
    </nav>
  );
};

export default ResourceSidebar;
