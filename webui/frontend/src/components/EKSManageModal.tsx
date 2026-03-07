import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  DndContext, DragOverlay, useDroppable,
  PointerSensor, useSensor, useSensors, closestCorners,
  type DragEndEvent, type DragStartEvent, type DragOverEvent,
} from '@dnd-kit/core';
import {
  SortableContext, useSortable, verticalListSortingStrategy, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { eksManageApi, EKSPreset, TreeNode, TreeFolder, DeploymentInfo } from '../services/api';
import '../styles/EKSManageModal.css';

interface EKSManageModalProps {
  onClose: () => void;
  connectInfo: {
    kubeconfigCommand: string;
    clusterName: string;
    ssoCommand: string;
  } | null;
}

type TabId = 'connection' | 'presets' | 'editor' | 'deploy' | 'run';

const STORAGE_KEY = 'eks-last-preset';

const highlightYaml = (text: string): string => {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return text.split('\n').map(line => {
    if (/^\s*#/.test(line)) return `<span class="hl-comment">${esc(line)}</span>`;
    if (/^\s*-\s/.test(line)) {
      const m = line.match(/^(\s*-\s)(.*)/);
      if (m) return `<span class="hl-punct">${esc(m[1])}</span>${esc(m[2])}`;
    }
    const kv = line.match(/^(\s*)([\w.\-/]+)(:)(.*)/);
    if (kv) {
      const [, indent, key, colon, val] = kv;
      let valHtml = esc(val);
      const trimmed = val.trim();
      if (/^['"]/.test(trimmed)) valHtml = `<span class="hl-string">${esc(val)}</span>`;
      else if (/^(true|false|null|~)$/i.test(trimmed)) valHtml = `<span class="hl-bool">${esc(val)}</span>`;
      else if (/^\d[\d.]*$/.test(trimmed)) valHtml = `<span class="hl-number">${esc(val)}</span>`;
      return `${esc(indent)}<span class="hl-key">${esc(key)}</span><span class="hl-punct">${esc(colon)}</span>${valHtml}`;
    }
    return esc(line);
  }).join('\n');
};

const SortablePreset = ({ id, children }: { id: string; children: React.ReactNode }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition: transition ?? undefined,
    opacity: isDragging ? 0.4 : 1,
  };
  return <div ref={setNodeRef} style={style} {...listeners} {...attributes}>{children}</div>;
};

const DroppableFolder = ({ id, children }: { id: string; children: React.ReactNode }) => {
  const { isOver, setNodeRef } = useDroppable({ id });
  return (
    <div ref={setNodeRef} className={`eks-tree-folder ${isOver ? 'drop-target' : ''}`}>
      {children}
    </div>
  );
};

const RootDropZone = ({ id }: { id: string }) => {
  const { isOver, setNodeRef } = useDroppable({ id });
  return (
    <div ref={setNodeRef} className={`eks-tree-root-drop ${isOver ? 'drop-target' : ''}`}>
      Drop here to move to root
    </div>
  );
};

const EKSManageModal = ({ onClose, connectInfo }: EKSManageModalProps) => {
  const [activeTab, setActiveTab] = useState<TabId>(connectInfo ? 'connection' : 'presets');
  const [presets, setPresets] = useState<EKSPreset[]>([]);
  const [loadingPresets, setLoadingPresets] = useState(false);

  const [editorPreset, setEditorPreset] = useState<string>('');
  const [editorDescription, setEditorDescription] = useState<string>('');
  const [editorDescDirty, setEditorDescDirty] = useState(false);
  const [editorFiles, setEditorFiles] = useState<string[]>([]);
  const [editorActiveFile, setEditorActiveFile] = useState<string>('');
  const [editorContent, setEditorContent] = useState<string>('');
  const [editorDirty, setEditorDirty] = useState(false);
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorMode, setEditorMode] = useState<'files' | 'commands'>('files');
  const [cmdDeploy, setCmdDeploy] = useState('');
  const [cmdUpdate, setCmdUpdate] = useState('');
  const [cmdUndeploy, setCmdUndeploy] = useState('');
  const [cmdDirty, setCmdDirty] = useState(false);
  const [cmdSaving, setCmdSaving] = useState(false);

  const [deployPreset, setDeployPreset] = useState<string>('');
  const [deployLog, setDeployLog] = useState<string>('');
  const [deploying, setDeploying] = useState(false);
  const [deployStatus, setDeployStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [deployedPresets, setDeployedPresets] = useState<Record<string, DeploymentInfo>>({});
  const deployLogRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const highlightRef = useRef<HTMLPreElement>(null);

  const [runCommand, setRunCommand] = useState('');
  const [runOutput, setRunOutput] = useState('');
  const [runRunning, setRunRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const runLogRef = useRef<HTMLDivElement>(null);
  const runAbortRef = useRef<AbortController | null>(null);
  const [runHistory, setRunHistory] = useState<string[]>([]);
  const [runHistoryIdx, setRunHistoryIdx] = useState(-1);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');

  const [treeLayout, setTreeLayout] = useState<TreeNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['ootb']));
  const [dragActiveId, setDragActiveId] = useState<string | null>(null);
  const presetsMap = useRef<Record<string, EKSPreset>>({});
  const dndSensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const loadDeployments = useCallback(async () => {
    try {
      const data = await eksManageApi.getDeployments();
      setDeployedPresets(data);
    } catch (e) {
      console.error('Failed to load deployments:', e);
    }
  }, []);

  const loadPresets = useCallback(async () => {
    setLoadingPresets(true);
    try {
      const { presets: list } = await eksManageApi.listPresets();
      setPresets(list);
      presetsMap.current = Object.fromEntries(list.map(p => [p.name, p]));
      const saved = localStorage.getItem(STORAGE_KEY);
      const fallback = saved && list.some(p => p.name === saved) ? saved : list[0]?.name || '';
      if (!deployPreset) setDeployPreset(fallback);
      try {
        const layout = await eksManageApi.getLayout();
        setTreeLayout(layout);
      } catch { /* layout will be generated server-side on next call */ }
      await loadDeployments();
    } catch (e) {
      console.error('Failed to load presets:', e);
    } finally {
      setLoadingPresets(false);
    }
  }, [deployPreset, loadDeployments]);

  useEffect(() => {
    loadPresets();
  }, [loadPresets]);

  useEffect(() => {
    if (presets.length === 0) return;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && presets.some(p => p.name === saved) && !editorPreset) {
      handleSelectPresetForEditor(saved);
    }
  }, [presets]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleSelectPresetForEditor = async (name: string) => {
    if (editorDirty || cmdDirty || editorDescDirty) {
      if (!window.confirm('Unsaved changes will be lost. Continue?')) return;
    }
    setEditorPreset(name);
    setDeployPreset(name);
    localStorage.setItem(STORAGE_KEY, name);
    setEditorActiveFile('');
    setEditorContent('');
    setEditorDirty(false);
    setCmdDirty(false);
    setEditorDescDirty(false);
    try {
      const preset = await eksManageApi.getPreset(name);
      setEditorDescription(preset.description || '');
      setEditorFiles(preset.files || []);
      setCmdDeploy((preset.deploy_commands || []).join('\n'));
      setCmdUpdate((preset.update_commands || []).join('\n'));
      setCmdUndeploy((preset.undeploy_commands || []).join('\n'));
      if (preset.files?.length > 0) {
        await loadFile(name, preset.files[0]);
      }
    } catch (e) {
      console.error('Failed to load preset for editing:', e);
    }
  };

  const handleAddFile = async () => {
    if (!editorPreset) return;
    const filename = window.prompt('New file name:');
    if (!filename?.trim()) return;
    try {
      await eksManageApi.updatePresetFile(editorPreset, filename.trim(), '');
      const preset = await eksManageApi.getPreset(editorPreset);
      setEditorFiles(preset.files || []);
      await loadFile(editorPreset, filename.trim());
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to add file');
    }
  };

  const loadFile = async (preset: string, filename: string) => {
    try {
      const { content } = await eksManageApi.getPresetFile(preset, filename);
      setEditorActiveFile(filename);
      setEditorContent(content);
      setEditorDirty(false);
    } catch (e) {
      console.error('Failed to load file:', e);
      setEditorContent(`Error loading file: ${filename}`);
    }
  };

  const handleFileSelect = async (filename: string) => {
    if (editorDirty) {
      if (!window.confirm('Unsaved changes will be lost. Continue?')) return;
    }
    await loadFile(editorPreset, filename);
  };

  const handleSaveFile = async () => {
    if (!editorPreset || !editorActiveFile) return;
    setEditorSaving(true);
    try {
      await eksManageApi.updatePresetFile(editorPreset, editorActiveFile, editorContent);
      setEditorDirty(false);
    } catch (e) {
      console.error('Failed to save file:', e);
      alert('Failed to save file');
    } finally {
      setEditorSaving(false);
    }
  };

  const linesToCmds = (text: string): string[] =>
    text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  const handleSaveManifest = async () => {
    if (!editorPreset) return;
    setCmdSaving(true);
    try {
      const data: Partial<EKSPreset> = {
        description: editorDescription,
        deploy_commands: linesToCmds(cmdDeploy),
        update_commands: linesToCmds(cmdUpdate),
        undeploy_commands: linesToCmds(cmdUndeploy),
      };
      await eksManageApi.updatePresetManifest(editorPreset, data);
      setCmdDirty(false);
      setEditorDescDirty(false);
      await loadPresets();
    } catch {
      alert('Failed to save');
    } finally {
      setCmdSaving(false);
    }
  };

  const handleCreatePreset = async () => {
    if (!createName.trim()) return;
    try {
      await eksManageApi.createPreset({
        name: createName.trim(),
        description: createDesc,
      });
      setShowCreateForm(false);
      setCreateName('');
      setCreateDesc('');
      await loadPresets();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to create preset');
    }
  };

  const handleDeletePreset = async (name: string) => {
    if (!window.confirm(`Delete preset "${name}"?`)) return;
    try {
      await eksManageApi.deletePreset(name);
      if (editorPreset === name) {
        setEditorPreset('');
        setEditorFiles([]);
        setEditorActiveFile('');
        setEditorContent('');
      }
      await loadPresets();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to delete preset');
    }
  };

  const handleClonePreset = async (name: string) => {
    const targetName = window.prompt(`Clone "${name}" as:`, `${name}-custom`);
    if (!targetName?.trim()) return;
    try {
      await eksManageApi.clonePreset(name, targetName.trim());
      await loadPresets();
      handleSelectPresetForEditor(targetName.trim());
      setActiveTab('editor');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to clone preset');
    }
  };

  const isOotb = (name: string): boolean => {
    return presets.find(p => p.name === name)?.built_in ?? false;
  };

  const handleDeploy = async () => {
    if (!deployPreset || deploying) return;
    setDeploying(true);
    setDeployLog('');
    setDeployStatus('running');
    abortRef.current = new AbortController();
    try {
      await eksManageApi.streamDeploy(
        deployPreset,
        (chunk) => {
          setDeployLog(prev => prev + chunk);
          if (deployLogRef.current) {
            deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight;
          }
        },
        (success) => {
          setDeployStatus(success ? 'success' : 'error');
          setDeploying(false);
          if (success) loadDeployments();
        },
        abortRef.current.signal,
      );
    } catch (e) {
      setDeployStatus('error');
      setDeploying(false);
      setDeployLog(prev => prev + `\nError: ${e}\n`);
    }
  };

  const handleUndeploy = async () => {
    if (!deployPreset || deploying) return;
    if (!window.confirm(`Undeploy preset "${deployPreset}" from the cluster?`)) return;
    setDeploying(true);
    setDeployLog('');
    setDeployStatus('running');
    abortRef.current = new AbortController();
    try {
      await eksManageApi.streamUndeploy(
        deployPreset,
        (chunk) => {
          setDeployLog(prev => prev + chunk);
          if (deployLogRef.current) {
            deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight;
          }
        },
        (success) => {
          setDeployStatus(success ? 'success' : 'error');
          setDeploying(false);
          if (success) loadDeployments();
        },
        abortRef.current.signal,
      );
    } catch (e) {
      setDeployStatus('error');
      setDeploying(false);
      setDeployLog(prev => prev + `\nError: ${e}\n`);
    }
  };

  const handleUpdate = async () => {
    if (!deployPreset || deploying) return;
    setDeploying(true);
    setDeployLog('');
    setDeployStatus('running');
    abortRef.current = new AbortController();
    try {
      await eksManageApi.streamUpdate(
        deployPreset,
        (chunk) => {
          setDeployLog(prev => prev + chunk);
          if (deployLogRef.current) {
            deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight;
          }
        },
        (success) => {
          setDeployStatus(success ? 'success' : 'error');
          setDeploying(false);
        },
        abortRef.current.signal,
      );
    } catch (e) {
      setDeployStatus('error');
      setDeploying(false);
      setDeployLog(prev => prev + `\nError: ${e}\n`);
    }
  };

  const handleEditorKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.target as HTMLTextAreaElement;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const newValue = editorContent.substring(0, start) + '  ' + editorContent.substring(end);
      setEditorContent(newValue);
      setEditorDirty(true);
      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      });
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      handleSaveFile();
    }
  };

  const findContainer = useCallback((itemId: string): string | null => {
    for (const node of treeLayout) {
      if (node.type === 'folder' && (node as TreeFolder).children.includes(itemId)) return node.id;
      if (node.type === 'preset' && node.id === itemId) return '__root__';
    }
    if (treeLayout.some(n => n.type === 'folder' && n.id === itemId)) return '__root__';
    return null;
  }, [treeLayout]);

  const cloneLayout = (layout: TreeNode[]): TreeNode[] =>
    layout.map(n => n.type === 'folder' ? { ...n, children: [...(n as TreeFolder).children] } : { ...n });

  const removeItem = (layout: TreeNode[], id: string) => {
    for (const n of layout) {
      if (n.type === 'folder') (n as TreeFolder).children = (n as TreeFolder).children.filter(c => c !== id);
    }
    return layout.filter(n => !(n.type === 'preset' && n.id === id));
  };

  const handleTreeDragStart = (e: DragStartEvent) => setDragActiveId(String(e.active.id));

  const handleTreeDragOver = (e: DragOverEvent) => {
    const { active, over } = e;
    if (!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);
    if (activeId === overId) return;

    const activeContainer = findContainer(activeId);
    let overContainer = findContainer(overId);

    const isFolder = treeLayout.some(n => n.type === 'folder' && n.id === overId);
    if (isFolder) overContainer = overId;
    if (overId === '__root__') overContainer = '__root__';

    if (!activeContainer || !overContainer || activeContainer === overContainer) return;

    setTreeLayout(prev => {
      const next = removeItem(cloneLayout(prev), activeId);
      if (overContainer === '__root__') {
        const idx = overId !== '__root__' ? next.findIndex(n => n.id === overId) : -1;
        if (idx >= 0) next.splice(idx + 1, 0, { id: activeId, type: 'preset' });
        else next.push({ id: activeId, type: 'preset' });
      } else {
        const folder = next.find(n => n.id === overContainer) as TreeFolder | undefined;
        if (folder) {
          const overIdx = folder.children.indexOf(overId);
          if (overIdx >= 0) folder.children.splice(overIdx + 1, 0, activeId);
          else folder.children.push(activeId);
        }
      }
      return next;
    });
  };

  const handleTreeDragEnd = (e: DragEndEvent) => {
    setDragActiveId(null);
    const { active, over } = e;
    if (!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);

    if (activeId === overId) {
      setTreeLayout(prev => { eksManageApi.saveLayout(prev).catch(() => {}); return prev; });
      return;
    }

    const activeContainer = findContainer(activeId);
    const overContainer = findContainer(overId);

    if (activeContainer && activeContainer === overContainer) {
      setTreeLayout(prev => {
        const next = cloneLayout(prev);
        if (activeContainer === '__root__') {
          const oldIdx = next.findIndex(n => n.id === activeId);
          const newIdx = next.findIndex(n => n.id === overId);
          if (oldIdx >= 0 && newIdx >= 0) {
            const [item] = next.splice(oldIdx, 1);
            next.splice(newIdx, 0, item);
          }
        } else {
          const folder = next.find(n => n.id === activeContainer) as TreeFolder | undefined;
          if (folder) {
            const oldIdx = folder.children.indexOf(activeId);
            const newIdx = folder.children.indexOf(overId);
            if (oldIdx >= 0 && newIdx >= 0) {
              folder.children = arrayMove(folder.children, oldIdx, newIdx);
            }
          }
        }
        eksManageApi.saveLayout(next).catch(() => {});
        return next;
      });
    } else {
      setTreeLayout(prev => { eksManageApi.saveLayout(prev).catch(() => {}); return prev; });
    }
  };

  const toggleFolder = (folderId: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      next.has(folderId) ? next.delete(folderId) : next.add(folderId);
      return next;
    });
  };

  const handleCreateFolder = () => {
    const name = window.prompt('Folder name:');
    if (!name?.trim()) return;
    const id = name.trim().toLowerCase().replace(/\s+/g, '-');
    if (treeLayout.some(n => n.id === id)) { alert('Name already exists'); return; }
    const next: TreeNode[] = [...treeLayout, { id, type: 'folder', name: name.trim(), children: [] }];
    setTreeLayout(next);
    setExpandedFolders(prev => new Set(prev).add(id));
    eksManageApi.saveLayout(next).catch(() => {});
  };

  const handleDeleteFolder = (folderId: string) => {
    const folder = treeLayout.find(n => n.id === folderId && n.type === 'folder') as TreeFolder | undefined;
    if (!folder) return;
    if (!window.confirm(`Delete folder "${folder.name}"? Presets inside will move to root.`)) return;
    const next: TreeNode[] = [
      ...treeLayout.filter(n => n.id !== folderId),
      ...folder.children.map(c => ({ id: c, type: 'preset' as const })),
    ];
    setTreeLayout(next);
    eksManageApi.saveLayout(next).catch(() => {});
  };

  const renderConnectionTab = () => {
    if (!connectInfo) {
      return (
        <div className="eks-manage-loading">
          No connection info available. Deploy the EKS cluster first and fetch outputs.
        </div>
      );
    }
    return (
      <div className="eks-connect-section">
        <div className="eks-connect-field">
          <label>Cluster Name</label>
          <div className="eks-connect-value-row">
            <code>{connectInfo.clusterName}</code>
            <button className="eks-copy-btn" onClick={() => copyToClipboard(connectInfo.clusterName)}>Copy</button>
          </div>
        </div>
        {connectInfo.ssoCommand && (
          <div className="eks-connect-field">
            <label>Step 1: SSO Login</label>
            <div className="hint">Run this command first to authenticate via SSO:</div>
            <div className="eks-connect-value-row">
              <code>{connectInfo.ssoCommand}</code>
              <button className="eks-copy-btn" onClick={() => copyToClipboard(connectInfo.ssoCommand)}>Copy</button>
            </div>
          </div>
        )}
        <div className="eks-connect-field">
          <label>{connectInfo.ssoCommand ? 'Step 2: Update Kubeconfig' : 'Update Kubeconfig'}</label>
          <div className="hint">Run this command in your terminal to configure kubectl access:</div>
          <div className="eks-connect-value-row">
            <code>{connectInfo.kubeconfigCommand}</code>
            <button className="eks-copy-btn" onClick={() => copyToClipboard(connectInfo.kubeconfigCommand)}>Copy</button>
          </div>
        </div>
        <div className="eks-connect-field">
          <label>Verify Connection</label>
          <div className="hint">After running the above, verify with:</div>
          <div className="eks-connect-value-row">
            <code>kubectl get nodes</code>
            <button className="eks-copy-btn" onClick={() => copyToClipboard('kubectl get nodes')}>Copy</button>
          </div>
        </div>
      </div>
    );
  };

  const renderPresetNode = (presetId: string) => {
    const p = presetsMap.current[presetId];
    if (!p) return null;
    return (
      <SortablePreset key={presetId} id={presetId}>
        <div
          className={`eks-tree-preset ${editorPreset === presetId ? 'selected' : ''}`}
          onClick={() => { handleSelectPresetForEditor(presetId); setActiveTab('editor'); }}
        >
          <span className="eks-tree-preset-name">{p.name}</span>
          <span className={`eks-preset-badge ${p.built_in ? 'built-in' : 'custom'}`}>
            {p.built_in ? 'OOTB' : 'Custom'}
          </span>
          <span className="eks-tree-preset-desc">{p.description}</span>
          <span className="eks-tree-actions">
            <button onClick={(e) => { e.stopPropagation(); setDeployPreset(p.name); localStorage.setItem(STORAGE_KEY, p.name); setActiveTab('deploy'); }}>Deploy</button>
            <button onClick={(e) => { e.stopPropagation(); handleClonePreset(p.name); }}>Clone</button>
            {!p.built_in && <button className="danger" onClick={(e) => { e.stopPropagation(); handleDeletePreset(p.name); }}>Delete</button>}
          </span>
        </div>
      </SortablePreset>
    );
  };

  const renderPresetsTab = () => {
    if (loadingPresets) {
      return <div className="eks-manage-loading">Loading presets...</div>;
    }
    return (
      <DndContext
        sensors={dndSensors}
        collisionDetection={closestCorners}
        onDragStart={handleTreeDragStart}
        onDragOver={handleTreeDragOver}
        onDragEnd={handleTreeDragEnd}
      >
        <div className="eks-presets-toolbar">
          <button className="eks-btn-create" onClick={() => setShowCreateForm(!showCreateForm)}>
            {showCreateForm ? 'Cancel' : '+ New Preset'}
          </button>
          <button className="eks-btn-create" onClick={handleCreateFolder} style={{ marginLeft: 8 }}>
            + New Folder
          </button>
        </div>

        {showCreateForm && (
          <div className="eks-create-form">
            <h4>Create New Preset</h4>
            <input type="text" placeholder="Preset name (e.g. my-custom-agent)" value={createName} onChange={e => setCreateName(e.target.value)} />
            <input type="text" placeholder="Description" value={createDesc} onChange={e => setCreateDesc(e.target.value)} />
            <div className="eks-create-form-actions">
              <button className="eks-btn-create" onClick={handleCreatePreset} disabled={!createName.trim()}>Create</button>
            </div>
          </div>
        )}

        <SortableContext items={treeLayout.filter(n => n.type === 'preset').map(n => n.id)} strategy={verticalListSortingStrategy}>
          <div className="eks-tree">
            {treeLayout.map(node => {
              if (node.type === 'folder') {
                const folder = node as TreeFolder;
                const expanded = expandedFolders.has(folder.id);
                return (
                  <DroppableFolder key={folder.id} id={folder.id}>
                    <div className="eks-tree-folder-header" onClick={() => toggleFolder(folder.id)}>
                      <span className="eks-tree-folder-icon">{expanded ? '▼' : '▶'}</span>
                      <span className="eks-tree-folder-name">{folder.name}</span>
                      <span className="eks-tree-folder-count">{folder.children.length}</span>
                      <button
                        className="eks-tree-folder-delete"
                        onClick={(e) => { e.stopPropagation(); handleDeleteFolder(folder.id); }}
                        title="Delete folder"
                      >
                        ×
                      </button>
                    </div>
                    {expanded && (
                      <SortableContext items={folder.children} strategy={verticalListSortingStrategy}>
                        <div className="eks-tree-folder-children">
                          {folder.children.map(cid => renderPresetNode(cid))}
                          {folder.children.length === 0 && (
                            <div className="eks-tree-empty-folder">Drop presets here</div>
                          )}
                        </div>
                      </SortableContext>
                    )}
                  </DroppableFolder>
                );
              }
              return renderPresetNode(node.id);
            })}
            <RootDropZone id="__root__" />
          </div>
        </SortableContext>

        <DragOverlay>
          {dragActiveId && presetsMap.current[dragActiveId] ? (
            <div className="eks-tree-preset drag-overlay">
              <span className="eks-tree-preset-name">{presetsMap.current[dragActiveId].name}</span>
            </div>
          ) : null}
        </DragOverlay>

        {presets.length === 0 && (
          <div className="eks-manage-loading">No presets found</div>
        )}
      </DndContext>
    );
  };

  const renderEditorTab = () => {
    if (!editorPreset) {
      return (
        <div className="eks-editor-layout">
          <div className="eks-editor-empty">
            Select a preset from the Presets tab to edit its files.
          </div>
        </div>
      );
    }

    const readonly = isOotb(editorPreset);

    return (
      <div className="eks-editor-layout">
        <div className="eks-editor-sidebar">
          <div className="eks-editor-sidebar-title">
            {editorPreset}
            {readonly && <span className="eks-ootb-badge">OOTB</span>}
          </div>
          <div className="eks-editor-description-field">
            <input
              type="text"
              className={`eks-editor-desc-input ${readonly ? 'readonly' : ''}`}
              value={editorDescription}
              onChange={e => { if (!readonly) { setEditorDescription(e.target.value); setEditorDescDirty(true); } }}
              readOnly={readonly}
              placeholder="Description"
            />
            {!readonly && editorDescDirty && (
              <button className="eks-btn-save eks-desc-save" onClick={handleSaveManifest} disabled={cmdSaving}>
                {cmdSaving ? 'Saving...' : 'Save'}
              </button>
            )}
          </div>
          <div className="eks-editor-mode-toggle">
            <button
              className={`eks-mode-btn ${editorMode === 'files' ? 'active' : ''}`}
              onClick={() => setEditorMode('files')}
            >
              Files
            </button>
            <button
              className={`eks-mode-btn ${editorMode === 'commands' ? 'active' : ''}`}
              onClick={() => setEditorMode('commands')}
            >
              Commands
            </button>
          </div>
          {editorMode === 'files' && editorFiles.map(f => (
            <div
              key={f}
              className={`eks-file-item ${editorActiveFile === f ? 'active' : ''}`}
              onClick={() => handleFileSelect(f)}
            >
              {f}
            </div>
          ))}
          {editorMode === 'files' && !readonly && (
            <button className="eks-btn-add-file" onClick={handleAddFile}>+ Add File</button>
          )}
          {readonly && (
            <button className="eks-btn-clone sidebar-clone" onClick={() => handleClonePreset(editorPreset)}>
              Clone to Edit
            </button>
          )}
        </div>
        <div className="eks-editor-main">
          {editorMode === 'files' ? (
            editorActiveFile ? (
              <>
                <div className="eks-editor-toolbar">
                  <span className="eks-editor-filename">{editorActiveFile}</span>
                  {!readonly && (
                    <button
                      className="eks-btn-save"
                      onClick={handleSaveFile}
                      disabled={!editorDirty || editorSaving}
                    >
                      {editorSaving ? 'Saving...' : 'Save'}
                    </button>
                  )}
                </div>
                <div className="eks-code-editor">
                  <pre className="eks-code-highlight" ref={highlightRef} aria-hidden="true">
                    <code dangerouslySetInnerHTML={{ __html: highlightYaml(editorContent) + '\n' }} />
                  </pre>
                  <textarea
                    className={`eks-editor-textarea ${readonly ? 'readonly' : ''}`}
                    value={editorContent}
                    onChange={e => { if (!readonly) { setEditorContent(e.target.value); setEditorDirty(true); } }}
                    onKeyDown={readonly ? undefined : handleEditorKeyDown}
                    onScroll={e => { if (highlightRef.current) { highlightRef.current.scrollTop = e.currentTarget.scrollTop; highlightRef.current.scrollLeft = e.currentTarget.scrollLeft; } }}
                    readOnly={readonly}
                    spellCheck={false}
                  />
                </div>
              </>
            ) : (
              <div className="eks-editor-empty">Select a file to view</div>
            )
          ) : (
            <div className="eks-commands-editor">
              <div className="eks-editor-toolbar">
                <span className="eks-editor-filename">Command Definitions</span>
                {!readonly && (
                  <button
                    className="eks-btn-save"
                    onClick={handleSaveManifest}
                    disabled={(!cmdDirty && !editorDescDirty) || cmdSaving}
                  >
                    {cmdSaving ? 'Saving...' : 'Save'}
                  </button>
                )}
              </div>
              <div className="eks-cmd-sections">
                <div className="eks-cmd-section">
                  <label>deploy_commands</label>
                  <textarea
                    className={`eks-cmd-textarea ${readonly ? 'readonly' : ''}`}
                    value={cmdDeploy}
                    onChange={e => { if (!readonly) { setCmdDeploy(e.target.value); setCmdDirty(true); } }}
                    readOnly={readonly}
                    spellCheck={false}
                    placeholder="helm repo add datadog https://helm.datadoghq.com&#10;helm upgrade --install datadog-agent datadog/datadog -f values.yaml"
                  />
                </div>
                <div className="eks-cmd-section">
                  <label>update_commands</label>
                  <textarea
                    className={`eks-cmd-textarea ${readonly ? 'readonly' : ''}`}
                    value={cmdUpdate}
                    onChange={e => { if (!readonly) { setCmdUpdate(e.target.value); setCmdDirty(true); } }}
                    readOnly={readonly}
                    spellCheck={false}
                    placeholder="helm repo update&#10;helm upgrade datadog-agent datadog/datadog -f values.yaml"
                  />
                </div>
                <div className="eks-cmd-section">
                  <label>undeploy_commands</label>
                  <textarea
                    className={`eks-cmd-textarea ${readonly ? 'readonly' : ''}`}
                    value={cmdUndeploy}
                    onChange={e => { if (!readonly) { setCmdUndeploy(e.target.value); setCmdDirty(true); } }}
                    readOnly={readonly}
                    spellCheck={false}
                    placeholder="helm uninstall datadog-agent"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const PRESET_COMMANDS = [
    { label: 'Get Pods', cmd: 'kubectl get pods -A' },
    { label: 'Get Nodes', cmd: 'kubectl get nodes -o wide' },
    { label: 'Get Services', cmd: 'kubectl get svc -A' },
    { label: 'Get Namespaces', cmd: 'kubectl get namespaces' },
    { label: 'Get Events', cmd: 'kubectl get events -A --sort-by=.lastTimestamp' },
    { label: 'Get Deployments', cmd: 'kubectl get deployments -A' },
    { label: 'Get DaemonSets', cmd: 'kubectl get daemonsets -A' },
    { label: 'Get ConfigMaps', cmd: 'kubectl get configmaps -A' },
    { label: 'Get Webhooks', cmd: 'kubectl get mutatingwebhookconfigurations,validatingwebhookconfigurations' },
  ];

  const executeRunCommand = async (cmd: string) => {
    if (!cmd.trim() || runRunning) return;
    setRunRunning(true);
    setRunOutput('');
    setRunStatus('running');
    setRunHistory(prev => {
      const next = prev.filter(h => h !== cmd.trim());
      next.unshift(cmd.trim());
      return next.slice(0, 50);
    });
    setRunHistoryIdx(-1);
    runAbortRef.current = new AbortController();
    try {
      await eksManageApi.streamKubectl(
        cmd.trim(),
        (chunk) => {
          setRunOutput(prev => prev + chunk);
          if (runLogRef.current) runLogRef.current.scrollTop = runLogRef.current.scrollHeight;
        },
        (success) => {
          setRunStatus(success ? 'success' : 'error');
          setRunRunning(false);
        },
        runAbortRef.current.signal,
      );
    } catch (e) {
      setRunStatus('error');
      setRunRunning(false);
      setRunOutput(prev => prev + `\nError: ${e}\n`);
    }
  };

  const handleRunKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeRunCommand(runCommand);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (runHistory.length > 0) {
        const next = Math.min(runHistoryIdx + 1, runHistory.length - 1);
        setRunHistoryIdx(next);
        setRunCommand(runHistory[next]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (runHistoryIdx > 0) {
        const next = runHistoryIdx - 1;
        setRunHistoryIdx(next);
        setRunCommand(runHistory[next]);
      } else {
        setRunHistoryIdx(-1);
        setRunCommand('');
      }
    }
  };

  const renderRunTab = () => (
    <div className="eks-run-section">
      <div className="eks-run-presets">
        {PRESET_COMMANDS.map(({ label, cmd }) => (
          <button
            key={cmd}
            className={`eks-run-preset-btn ${runRunning ? 'disabled' : ''}`}
            onClick={() => { setRunCommand(cmd); executeRunCommand(cmd); }}
            disabled={runRunning}
            title={cmd}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="eks-run-input-row">
        <span className="eks-run-prompt">$</span>
        <input
          type="text"
          className="eks-run-input"
          value={runCommand}
          onChange={e => setRunCommand(e.target.value)}
          onKeyDown={handleRunKeyDown}
          placeholder="kubectl get pods -n default"
          disabled={runRunning}
          spellCheck={false}
          autoComplete="off"
        />
        <button
          className="eks-run-exec-btn"
          onClick={() => executeRunCommand(runCommand)}
          disabled={runRunning || !runCommand.trim()}
        >
          {runRunning ? 'Running...' : 'Run'}
        </button>
        {runRunning && (
          <button
            className="eks-run-stop-btn"
            onClick={() => runAbortRef.current?.abort()}
          >
            Stop
          </button>
        )}
      </div>
      {runStatus !== 'idle' && (
        <div className={`eks-deploy-status ${runStatus}`}>
          {runStatus === 'running' && 'Running...'}
          {runStatus === 'success' && 'Completed'}
          {runStatus === 'error' && 'Failed'}
        </div>
      )}
      <div className="eks-deploy-log" ref={runLogRef}>
        {runOutput || 'Select a preset command or type your own and press Run.'}
      </div>
    </div>
  );

  const deployedNames = Object.keys(deployedPresets);

  const renderDeployTab = () => {
    const currentPreset = presets.find(p => p.name === deployPreset);
    const hasUpdateCmds = (currentPreset?.update_commands?.length || 0) > 0;

    return (
      <div className="eks-deploy-section">
        {deployedNames.length > 0 && (
          <div className="eks-deployed-list">
            <div className="eks-deployed-header">Deployed Presets</div>
            <div className="eks-deployed-items">
              {deployedNames.map(name => (
                <div
                  key={name}
                  className={`eks-deployed-item ${deployPreset === name ? 'selected' : ''}`}
                  onClick={() => { setDeployPreset(name); localStorage.setItem(STORAGE_KEY, name); }}
                >
                  <span className="eks-deployed-name">{name}</span>
                  <span className="eks-deployed-time">
                    {new Date(deployedPresets[name].deployed_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="eks-deploy-preset-select">
          <label>Preset</label>
          <select value={deployPreset} onChange={e => { setDeployPreset(e.target.value); localStorage.setItem(STORAGE_KEY, e.target.value); }} disabled={deploying}>
            {presets.map(p => (
              <option key={p.name} value={p.name}>{p.name}</option>
            ))}
          </select>
        </div>
        <div className="eks-deploy-actions">
          <button className="eks-btn-deploy" onClick={handleDeploy} disabled={deploying || !deployPreset}>
            {deploying ? 'Running...' : 'Deploy'}
          </button>
          <button
            className="eks-btn-update"
            onClick={handleUpdate}
            disabled={deploying || !deployPreset || !hasUpdateCmds}
            title={hasUpdateCmds ? 'Update existing deployment' : 'No update commands defined'}
          >
            Update
          </button>
          <button className="eks-btn-undeploy" onClick={handleUndeploy} disabled={deploying || !deployPreset}>
            Undeploy
          </button>
        </div>
        {deployStatus !== 'idle' && (
          <div className={`eks-deploy-status ${deployStatus}`}>
            {deployStatus === 'running' && 'Running...'}
            {deployStatus === 'success' && 'Completed successfully'}
            {deployStatus === 'error' && 'Failed'}
          </div>
        )}
        <div className="eks-deploy-log" ref={deployLogRef}>
          {deployLog || 'Select a preset and click Deploy, Update, or Undeploy to begin.'}
        </div>
      </div>
    );
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="eks-manage-modal" onClick={e => e.stopPropagation()}>
        <div className="eks-manage-header">
          <h2>EKS Connect & Manage</h2>
          <button className="eks-manage-close" onClick={onClose}>&times;</button>
        </div>
        <div className="eks-manage-tabs">
          {(['connection', 'presets', 'editor', 'deploy', 'run'] as TabId[]).map(tab => (
            <button
              key={tab}
              className={`eks-manage-tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {{ connection: 'Connection', presets: 'Presets', editor: 'Editor', deploy: 'Deploy', run: 'Run' }[tab]}
            </button>
          ))}
        </div>
        <div className="eks-manage-body">
          {activeTab === 'connection' && renderConnectionTab()}
          {activeTab === 'presets' && renderPresetsTab()}
          {activeTab === 'editor' && renderEditorTab()}
          {activeTab === 'deploy' && renderDeployTab()}
          {activeTab === 'run' && renderRunTab()}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default EKSManageModal;
