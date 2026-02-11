import { useState, useEffect } from 'react';
import { TerraformResource } from '../types';
import { terraformApi } from '../services/api';

interface ResourceSidebarProps {
  onResourceSelect: (resource: TerraformResource | null) => void;
  selectedResourceId: string | null;
  refreshTrigger?: number;
  runningResources?: Map<string, string>;
  onResourcesLoaded?: (resources: TerraformResource[]) => void;
}

const ResourceSidebar = ({ onResourceSelect, selectedResourceId, refreshTrigger, runningResources, onResourcesLoaded }: ResourceSidebarProps) => {
  const [resources, setResources] = useState<TerraformResource[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Load expanded sections from localStorage or use defaults
  const getInitialExpandedSections = (): Set<string> => {
    const saved = localStorage.getItem('expanded_sections');
    if (saved) {
      try {
        return new Set(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse expanded sections:', e);
      }
    }
    // Default: expand EC2 and EKS only
    return new Set(['ec2', 'eks']);
  };
  
  const [expandedSections, setExpandedSections] = useState<Set<string>>(getInitialExpandedSections());

  const loadResources = async (showLoading = true) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      const data = await terraformApi.getResources();
      setResources(data);
      
      sessionStorage.setItem('terraform_resources', JSON.stringify(data));
      
      if (onResourcesLoaded) {
        onResourcesLoaded(data);
      }
      
      if (selectedResourceId) {
        const updatedResource = data.find(r => r.id === selectedResourceId);
        if (updatedResource) {
          onResourceSelect(updatedResource);
        }
      }
    } catch (err) {
      console.error('Failed to load resources:', err);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadResources(true);
  }, []);

  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      loadResources(false);
    }
  }, [refreshTrigger]);

  const toggleSection = (type: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(type)) {
      newExpanded.delete(type);
    } else {
      newExpanded.add(type);
    }
    setExpandedSections(newExpanded);
    
    // Save to localStorage
    localStorage.setItem('expanded_sections', JSON.stringify(Array.from(newExpanded)));
  };

  const groupedResources = resources.reduce((acc, resource) => {
    if (!acc[resource.type]) {
      acc[resource.type] = [];
    }
    acc[resource.type].push(resource);
    return acc;
  }, {} as Record<string, TerraformResource[]>);

  // Define the display order of resource types
  const RESOURCE_TYPE_ORDER = [
    'ec2',
    'eks',
    'ecs',
    'dbm',
    'lambda',
    'ecr',
    'rds',
    'security_group',
    'test',
  ];

  // Sort grouped resources by defined order
  const sortedResourceTypes = Object.keys(groupedResources).sort((a, b) => {
    const indexA = RESOURCE_TYPE_ORDER.indexOf(a);
    const indexB = RESOURCE_TYPE_ORDER.indexOf(b);
    
    // If both are in the order list, sort by their index
    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
    // If only A is in the list, A comes first
    if (indexA !== -1) return -1;
    // If only B is in the list, B comes first
    if (indexB !== -1) return 1;
    // If neither is in the list, sort alphabetically
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
      dbm: '📊',
    };
    return icons[type] || '📄';
  };

  if (loading) {
    return (
      <div className="sidebar">
        <div className="sidebar-loading">Loading resources...</div>
      </div>
    );
  }

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Resources</h2>
        <button onClick={() => loadResources(false)} className="btn-refresh-small" title="Refresh resources">Refresh</button>
      </div>

      <div className="sidebar-sections">
        {sortedResourceTypes.map(type => {
          const items = groupedResources[type];
          return (
          <div key={type} className="sidebar-section">
            <div
              className="section-header"
              onClick={() => toggleSection(type)}
            >
              <span className="section-icon">{expandedSections.has(type) ? '▼' : '▶'}</span>
              <span className="section-title">
                {getTypeIcon(type)} {type.toUpperCase()}
              </span>
              <span className="section-count">{items.length}</span>
            </div>

            {expandedSections.has(type) && (
              <div className="section-items">
                {items.map((resource) => (
                  <div
                    key={resource.id}
                    className={`sidebar-item ${selectedResourceId === resource.id ? 'selected' : ''} ${runningResources?.has(resource.id) ? 'running' : ''}`}
                    onClick={() => onResourceSelect(resource)}
                  >
                    <span className={`item-status ${runningResources?.has(resource.id) ? 'running' : resource.status === 'enabled' ? 'enabled' : 'disabled'}`} />
                    <div className="item-content">
                      <div className="item-name">{resource.description || resource.name}</div>
                      <div className="item-file">{resource.file_path}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
        })}
      </div>
    </div>
  );
};

export default ResourceSidebar;
