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
import { eksManageApi, clusterShareApi, EKSPreset, TreeNode, TreeFolder, DeploymentInfo } from '../services/api';
import '../styles/EKSManageModal.css';

interface EKSManageModalProps {
  onClose: () => void;
  connectInfo: {
    kubeconfigCommand: string;
    clusterName: string;
    ssoCommand: string;
  } | null;
  sharedClusterName?: string;
  sharedOwnerPrefix?: string;
}

type TabId = 'connection' | 'presets' | 'editor' | 'deploy' | 'run';

const STORAGE_KEY = 'eks-last-preset';

const CREDENTIAL_ERROR_PATTERNS = [
  'no valid credential', 'cached sso token is expired',
  'refresh cached credentials', 'unable to locate credentials',
  'expired token', 'token has expired', 'invalidclienttokenid',
  'security token included in the request is expired',
];

const hasCredentialError = (text: string): boolean => {
  const lower = text.toLowerCase();
  return CREDENTIAL_ERROR_PATTERNS.some(p => lower.includes(p));
};

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

const EKSManageModal = ({ onClose, connectInfo, sharedClusterName, sharedOwnerPrefix }: EKSManageModalProps) => {
  const isShared = !!sharedClusterName;
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
  const deployPresetRef = useRef(deployPreset);
  deployPresetRef.current = deployPreset;
  const [deployLog, setDeployLog] = useState<string>('');
  const [deploying, setDeploying] = useState(false);
  const [deployStatus, setDeployStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [deployedPresets, setDeployedPresets] = useState<Record<string, DeploymentInfo>>({});
  const [deploymentWarnings, setDeploymentWarnings] = useState<string[]>([]);
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
  const credErrorRef = useRef(false);

  const [sharedPresets, setSharedPresets] = useState<EKSPreset[]>([]);
  const [presetSource, setPresetSource] = useState<'my' | 'shared' | 'connected'>('my');
  const [editorIsShared, setEditorIsShared] = useState(false);
  const [connectedUsers, setConnectedUsers] = useState<string[]>([]);
  const [connectedOwnerPrefix, setConnectedOwnerPrefix] = useState('');
  const [clusterMembers, setClusterMembers] = useState<string[]>([]);
  const [memberPresets, setMemberPresets] = useState<Record<string, EKSPreset[]>>({});

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');

  const [treeLayout, setTreeLayout] = useState<TreeNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['ootb-agent', 'ootb-istio', 'ootb-nginx', 'ootb-redis']));
  const [dragActiveId, setDragActiveId] = useState<string | null>(null);
  const presetsMap = useRef<Record<string, EKSPreset>>({});
  const dndSensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const cancelledRef = useRef(false);

  const loadDeployments = useCallback(async (force = false) => {
    try {
      if (isShared && sharedOwnerPrefix) {
        const sharedResult = await eksManageApi.listSharedDeployments(sharedOwnerPrefix, force);
        if (cancelledRef.current) return;
        setDeployedPresets(sharedResult.deployments);
        setDeploymentWarnings(sharedResult.warnings || []);
      } else {
        const result = await eksManageApi.getDeployments(force);
        if (cancelledRef.current) return;
        setDeployedPresets(result.deployments);
        setDeploymentWarnings(result.warnings || []);
      }
    } catch (e) {
      console.error('Failed to load deployments:', e);
    }
  }, [isShared, sharedOwnerPrefix]);

  const loadPresets = useCallback(async () => {
    setLoadingPresets(true);
    try {
      const { presets: list } = await eksManageApi.listPresets();
      if (cancelledRef.current) return;
      const safeList = Array.isArray(list) ? list : [];
      setPresets(safeList);
      presetsMap.current = Object.fromEntries(safeList.map(p => [p.name, p]));
      const saved = localStorage.getItem(STORAGE_KEY);
      const fallback = saved && safeList.some(p => p.name === saved) ? saved : safeList[0]?.name || '';
      if (!deployPresetRef.current) setDeployPreset(fallback);
      try {
        const layout = await eksManageApi.getLayout();
        if (!cancelledRef.current && Array.isArray(layout)) setTreeLayout(layout);
      } catch { /* layout will be generated server-side on next call */ }
    } catch (e) {
      console.error('Failed to load presets:', e);
    } finally {
      if (!cancelledRef.current) setLoadingPresets(false);
    }
  }, []);

  const loadMemberPresets = useCallback(async (members: string[]) => {
    const result: Record<string, EKSPreset[]> = {};
    const allShared: EKSPreset[] = [];
    await Promise.all(members.map(async (prefix) => {
      try {
        const data = await eksManageApi.listSharedPresets(prefix);
        const tagged = Array.isArray(data.presets) ? data.presets.map(p => ({ ...p, owner_prefix: prefix })) : [];
        result[prefix] = tagged;
        allShared.push(...tagged);
      } catch (e) {
        console.error(`Failed to load presets for member ${prefix}:`, e);
        result[prefix] = [];
      }
    }));
    if (cancelledRef.current) return;
    setMemberPresets(result);
    setSharedPresets(allShared);
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    loadPresets();
    loadDeployments();
    if (isShared && sharedOwnerPrefix) {
      clusterShareApi.getClusterMembers(sharedOwnerPrefix)
        .then(members => {
          if (cancelledRef.current) return;
          setClusterMembers(members);
          loadMemberPresets(members);
        })
        .catch(e => console.error('Failed to load cluster members:', e));
    }
    if (!isShared) {
      clusterShareApi.getConnectedUsers()
        .then(users => {
          if (cancelledRef.current) return;
          setConnectedUsers(users);
          loadMemberPresets(users);
        })
        .catch(e => console.error('Failed to load connected users:', e));
    }
    return () => { cancelledRef.current = true; };
  }, [loadPresets, loadDeployments, isShared, sharedOwnerPrefix, loadMemberPresets]);


  useEffect(() => {
    if (activeTab !== 'deploy') return;
    const id = setInterval(loadDeployments, 15000);
    return () => clearInterval(id);
  }, [activeTab, loadDeployments]);

  const handleHeaderRefresh = useCallback(() => {
    if (activeTab === 'deploy') loadDeployments(true);
    else if (activeTab === 'presets') loadPresets();
  }, [activeTab, loadDeployments, loadPresets]);

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
    setEditorIsShared(false);
    setConnectedOwnerPrefix('');
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

  const handleSelectSharedPreset = async (name: string, ownerPrefix?: string) => {
    const prefix = ownerPrefix || sharedOwnerPrefix;
    if (!prefix) return;
    if (editorDirty || cmdDirty || editorDescDirty) {
      if (!window.confirm('Unsaved changes will be lost. Continue?')) return;
    }
    setEditorPreset(name);
    setDeployPreset(name);
    setEditorIsShared(true);
    setConnectedOwnerPrefix(prefix);
    localStorage.setItem(STORAGE_KEY, name);
    setEditorActiveFile('');
    setEditorContent('');
    setEditorDirty(false);
    setCmdDirty(false);
    setEditorDescDirty(false);
    try {
      const preset = await eksManageApi.getSharedPreset(name, prefix);
      setEditorDescription(preset.description || '');
      setEditorFiles(preset.files || []);
      setCmdDeploy((preset.deploy_commands || []).join('\n'));
      setCmdUpdate((preset.update_commands || []).join('\n'));
      setCmdUndeploy((preset.undeploy_commands || []).join('\n'));
      if (preset.files?.length > 0) {
        await loadSharedFile(name, preset.files[0], prefix);
      }
    } catch (e) {
      console.error('Failed to load shared preset for editing:', e);
    }
  };

  const loadSharedFile = async (preset: string, filename: string, explicitPrefix?: string) => {
    const prefix = explicitPrefix || connectedOwnerPrefix || sharedOwnerPrefix;
    if (!prefix) return;
    try {
      const { content } = await eksManageApi.getSharedPresetFile(preset, filename, prefix);
      setEditorActiveFile(filename);
      setEditorContent(content);
      setEditorDirty(false);
    } catch (e) {
      console.error('Failed to load shared file:', e);
      setEditorContent(`Error loading file: ${filename}`);
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
    if (editorIsShared) {
      await loadSharedFile(editorPreset, filename);
    } else {
      await loadFile(editorPreset, filename);
    }
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

  const handleDeleteFile = async (filename: string) => {
    if (!editorPreset) return;
    if (!window.confirm(`Delete "${filename}"?`)) return;
    try {
      await eksManageApi.deletePresetFile(editorPreset, filename);
      const preset = await eksManageApi.getPreset(editorPreset);
      setEditorFiles(preset.files || []);
      if (editorActiveFile === filename) {
        setEditorActiveFile('');
        setEditorContent('');
        setEditorDirty(false);
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to delete file');
    }
  };

  const handleRenameFile = async (filename: string) => {
    if (!editorPreset) return;
    const newName = window.prompt('New file name:', filename);
    if (!newName?.trim() || newName.trim() === filename) return;
    try {
      await eksManageApi.renamePresetFile(editorPreset, filename, newName.trim());
      const preset = await eksManageApi.getPreset(editorPreset);
      setEditorFiles(preset.files || []);
      if (editorActiveFile === filename) {
        setEditorActiveFile(newName.trim());
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to rename file');
    }
  };

  const dragCounter = useRef(0);

  const handleFileDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    e.currentTarget.classList.remove('drag-over');
    if (!editorPreset || isOotb(editorPreset) || editorIsShared) return;
    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      const content = await file.text();
      try {
        await eksManageApi.updatePresetFile(editorPreset, file.name, content);
      } catch (err: any) {
        alert(err.response?.data?.detail || `Failed to upload ${file.name}`);
      }
    }
    const preset = await eksManageApi.getPreset(editorPreset);
    setEditorFiles(preset.files || []);
    if (files.length === 1) {
      await loadFile(editorPreset, files[0].name);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (dragCounter.current === 1) e.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) e.currentTarget.classList.remove('drag-over');
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

  const onStreamChunk = (chunk: string) => {
    setDeployLog(prev => prev + chunk);
    if (deployLogRef.current) deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight;
    if (hasCredentialError(chunk)) credErrorRef.current = true;
  };

  const onStreamDone = (success: boolean, opts?: { onSuccess?: () => void }) => {
    setDeployStatus(success ? 'success' : 'error');
    setDeploying(false);
    if (success && opts?.onSuccess) opts.onSuccess();
    if (!success && credErrorRef.current) {
      window.dispatchEvent(new CustomEvent('sso-credential-expired'));
      credErrorRef.current = false;
    }
  };

  const getClusterOwnerPrefix = (): string | undefined => {
    if (isShared) return sharedOwnerPrefix;
    if (connectedOwnerPrefix) return connectedOwnerPrefix;
    return undefined;
  };

  const getPresetOwnerPrefix = (): string | undefined => {
    if (connectedOwnerPrefix) return connectedOwnerPrefix;
    if (isShared) return sharedOwnerPrefix;
    return undefined;
  };

  const handleDeploy = async () => {
    if (!deployPreset || deploying) return;
    setDeploying(true);
    setDeployLog('');
    setDeployStatus('running');
    credErrorRef.current = false;
    abortRef.current = new AbortController();
    const clusterOwner = getClusterOwnerPrefix();
    const presetOwner = getPresetOwnerPrefix();
    try {
      await eksManageApi.streamDeploy(
        deployPreset, onStreamChunk,
        (success) => onStreamDone(success, { onSuccess: loadDeployments }),
        abortRef.current.signal,
        sharedClusterName,
        clusterOwner,
        presetOwner !== clusterOwner ? presetOwner : undefined,
      );
    } catch (e) {
      setDeployStatus('error');
      setDeploying(false);
      setDeployLog(prev => prev + `\nError: ${e}\n`);
    }
  };

  const handleUndeploy = async () => {
    if (!deployPreset || deploying) return;
    if (!window.confirm(`Delete preset "${deployPreset}" from the cluster?`)) return;
    setDeploying(true);
    setDeployLog('');
    setDeployStatus('running');
    credErrorRef.current = false;
    abortRef.current = new AbortController();
    const clusterOwner = getClusterOwnerPrefix();
    const presetOwner = getPresetOwnerPrefix();
    try {
      await eksManageApi.streamUndeploy(
        deployPreset, onStreamChunk,
        (success) => onStreamDone(success, { onSuccess: loadDeployments }),
        abortRef.current.signal,
        sharedClusterName,
        clusterOwner,
        presetOwner !== clusterOwner ? presetOwner : undefined,
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
    credErrorRef.current = false;
    abortRef.current = new AbortController();
    const clusterOwner = getClusterOwnerPrefix();
    const presetOwner = getPresetOwnerPrefix();
    try {
      await eksManageApi.streamUpdate(
        deployPreset, onStreamChunk,
        (success) => onStreamDone(success),
        abortRef.current.signal,
        sharedClusterName,
        clusterOwner,
        presetOwner !== clusterOwner ? presetOwner : undefined,
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
    if (isShared) {
      return (
        <div className="eks-connect-section">
          <div className="eks-connect-field">
            <label>Shared Cluster</label>
            <div className="eks-connect-value-row">
              <code>{sharedClusterName}</code>
              <button className="eks-copy-btn" onClick={() => copyToClipboard(sharedClusterName || '')}>Copy</button>
            </div>
          </div>
          <div className="eks-connect-field">
            <label>Owner</label>
            <code>{sharedOwnerPrefix}</code>
          </div>
          <div className="hint" style={{ marginTop: 8 }}>
            Kubeconfig is automatically configured when you use the Run or Deploy tabs.
          </div>
        </div>
      );
    }
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

    if ((isShared && presetSource === 'shared') || (!isShared && connectedUsers.length > 0 && presetSource === 'connected')) {
      const members = isShared ? clusterMembers : connectedUsers;
      return (
        <div>
          <div className="eks-presets-toolbar">
            <div className="eks-preset-source-toggle">
              <button className="" onClick={() => setPresetSource('my')}>My Presets</button>
              <button className="active" onClick={() => setPresetSource(isShared ? 'shared' : 'connected')}>
                {isShared ? 'Shared Presets' : 'Connected Presets'}
              </button>
            </div>
          </div>
          {members.length === 0 ? (
            <div className="eks-manage-loading">No shared members found.</div>
          ) : (
            <div className="eks-tree">
              {members.map(prefix => {
                const mp = memberPresets[prefix] || [];
                return (
                  <div key={prefix} className="eks-member-group">
                    <div className="eks-member-group-header">{prefix}</div>
                    {mp.length === 0 ? (
                      <div className="eks-manage-loading">No presets</div>
                    ) : mp.map(p => (
                      <div
                        key={`${prefix}/${p.name}`}
                        className={`eks-tree-preset ${editorPreset === p.name && connectedOwnerPrefix === prefix && editorIsShared ? 'selected' : ''}`}
                        onClick={() => { handleSelectSharedPreset(p.name, prefix); setActiveTab('editor'); }}
                      >
                        <span className="eks-tree-preset-name">{p.name}</span>
                        <span className="eks-preset-badge member">{prefix}</span>
                        <span className={`eks-preset-badge ${p.built_in ? 'built-in' : 'custom'}`}>
                          {p.built_in ? 'OOTB' : 'Custom'}
                        </span>
                        <span className="eks-tree-preset-desc">{p.description}</span>
                        <span className="eks-tree-actions">
                          <button onClick={(e) => {
                            e.stopPropagation();
                            setDeployPreset(p.name);
                            setConnectedOwnerPrefix(prefix);
                            localStorage.setItem(STORAGE_KEY, p.name);
                            setActiveTab('deploy');
                          }}>Deploy</button>
                          <button onClick={(e) => { e.stopPropagation(); handleClonePreset(p.name); }}>Clone</button>
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
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
          {isShared && (
            <div className="eks-preset-source-toggle">
              <button className={presetSource === 'my' ? 'active' : ''} onClick={() => setPresetSource('my')}>My Presets</button>
              <button className={presetSource === 'shared' ? 'active' : ''} onClick={() => setPresetSource('shared')}>Shared Presets</button>
            </div>
          )}
          {!isShared && connectedUsers.length > 0 && (
            <div className="eks-preset-source-toggle">
              <button className={presetSource === 'my' ? 'active' : ''} onClick={() => setPresetSource('my')}>My Presets</button>
              <button className={presetSource === 'connected' ? 'active' : ''} onClick={() => setPresetSource('connected')}>Connected Presets</button>
            </div>
          )}
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

        <SortableContext items={(Array.isArray(treeLayout) ? treeLayout : []).filter(n => n.type === 'preset').map(n => n.id)} strategy={verticalListSortingStrategy}>
          <div className="eks-tree">
            {(Array.isArray(treeLayout) ? treeLayout : []).map(node => {
              if (node.type === 'folder') {
                const folder = node as TreeFolder;
                const expanded = expandedFolders.has(folder.id);
                const children = Array.isArray(folder.children) ? folder.children : [];
                return (
                  <DroppableFolder key={folder.id} id={folder.id}>
                    <div className="eks-tree-folder-header" onClick={() => toggleFolder(folder.id)}>
                      <span className="eks-tree-folder-icon">{expanded ? '▼' : '▶'}</span>
                      <span className="eks-tree-folder-name">{folder.name}</span>
                      <span className="eks-tree-folder-count">{children.length}</span>
                      <button
                        className="eks-tree-folder-delete"
                        onClick={(e) => { e.stopPropagation(); handleDeleteFolder(folder.id); }}
                        title="Delete folder"
                      >
                        ×
                      </button>
                    </div>
                    {expanded && (
                      <SortableContext items={children} strategy={verticalListSortingStrategy}>
                        <div className="eks-tree-folder-children">
                          {children.map(cid => renderPresetNode(cid))}
                          {children.length === 0 && (
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

    const readonly = isOotb(editorPreset) || editorIsShared;

    return (
      <div className="eks-editor-layout" onDrop={handleFileDrop} onDragOver={handleDragOver} onDragEnter={handleDragEnter} onDragLeave={handleDragLeave}>
        <div className="eks-editor-sidebar">
          <div className="eks-editor-sidebar-title">
            {editorPreset}
            {editorIsShared ? <span className="eks-ootb-badge">Shared</span> : readonly && <span className="eks-ootb-badge">OOTB</span>}
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
          {editorMode === 'files' && (
            <div className="eks-file-list-drop-zone">
              {editorFiles.map(f => (
                <div
                  key={f}
                  className={`eks-file-item ${editorActiveFile === f ? 'active' : ''}`}
                  onClick={() => handleFileSelect(f)}
                >
                  <span className="eks-file-item-name">{f}</span>
                  {!readonly && (
                    <span className="eks-file-item-actions">
                      <button
                        className="eks-file-action-btn"
                        title="Rename"
                        onClick={(e) => { e.stopPropagation(); handleRenameFile(f); }}
                      >
                        ✏
                      </button>
                      <button
                        className="eks-file-action-btn eks-file-action-delete"
                        title="Delete"
                        onClick={(e) => { e.stopPropagation(); handleDeleteFile(f); }}
                      >
                        ✕
                      </button>
                    </span>
                  )}
                </div>
              ))}
              {!readonly && (
                <button className="eks-btn-add-file" onClick={handleAddFile}>+ Add File</button>
              )}
            </div>
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
    credErrorRef.current = false;
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
          if (hasCredentialError(chunk)) credErrorRef.current = true;
        },
        (success) => {
          setRunStatus(success ? 'success' : 'error');
          setRunRunning(false);
          if (!success && credErrorRef.current) {
            window.dispatchEvent(new CustomEvent('sso-credential-expired'));
            credErrorRef.current = false;
          }
        },
        runAbortRef.current.signal,
        sharedClusterName,
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
        {deploymentWarnings.length > 0 && (
          <div className="eks-ownership-warning">
            {deploymentWarnings.map((w, i) => (
              <div key={i} className="eks-ownership-warning-item">⚠ {w}</div>
            ))}
          </div>
        )}
        {deployedNames.length > 0 && (
          <div className="eks-deployed-list">
            <div className="eks-deployed-header">
              Deployed Presets
            </div>
            <div className="eks-deployed-items">
              {deployedNames.map(name => (
                <div
                  key={name}
                  className={`eks-deployed-item ${deployPreset === name ? 'selected' : ''}`}
                  onClick={() => { setDeployPreset(name); localStorage.setItem(STORAGE_KEY, name); }}
                >
                  <span className="eks-deployed-name">{name}</span>
                  <span className="eks-deployed-meta">
                    {deployedPresets[name].deployed_by && (
                      <span className="eks-deployed-by">by {deployedPresets[name].deployed_by}</span>
                    )}
                    <span className="eks-deployed-time">
                      {new Date(deployedPresets[name].deployed_at).toLocaleString()}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="eks-deploy-preset-select">
          <label>Preset</label>
          <select value={deployPreset} onChange={e => {
            const val = e.target.value;
            setDeployPreset(val);
            const memberMatch = sharedPresets.find(p => p.name === val);
            setConnectedOwnerPrefix(memberMatch?.owner_prefix || '');
            localStorage.setItem(STORAGE_KEY, val);
          }} disabled={deploying}>
            {presets.map(p => (
              <option key={p.name} value={p.name}>{p.name}</option>
            ))}
            {(Object.entries(memberPresets) as [string, EKSPreset[]][]).map(([prefix, mp]) =>
              mp.length > 0 ? (
                <optgroup key={prefix} label={prefix}>
                  {mp.map(p => (
                    <option key={`${prefix}/${p.name}`} value={p.name}>{p.name}</option>
                  ))}
                </optgroup>
              ) : null
            )}
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
            Delete
          </button>
          <button
            className="eks-btn-force-delete"
            disabled={deploying || !deployPreset || !deployedPresets[deployPreset]}
            onClick={async () => {
              if (!deployPreset) return;
              if (!window.confirm(`Force remove "${deployPreset}" from deployed list?\n(No undeploy commands will be executed)`)) return;
              try {
                await eksManageApi.forceDelete(deployPreset, getClusterOwnerPrefix(), sharedClusterName);
                loadDeployments();
              } catch {}
            }}
          >
            Force Delete
          </button>
        </div>
        <div className="eks-deploy-hint">
          Force Delete removes the preset from the deployed list only, without executing any undeploy commands.
        </div>
        {deployStatus !== 'idle' && (
          <div className={`eks-deploy-status ${deployStatus}`}>
            {deployStatus === 'running' && 'Running...'}
            {deployStatus === 'success' && 'Completed successfully'}
            {deployStatus === 'error' && 'Failed'}
          </div>
        )}
        <div className="eks-deploy-log" ref={deployLogRef}>
          {deployLog || 'Select a preset and click Deploy, Update, or Delete to begin.'}
        </div>
      </div>
    );
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="eks-manage-modal" onClick={e => e.stopPropagation()}>
        <div className="eks-manage-header">
          <h2>{isShared ? `Shared EKS: ${sharedClusterName}` : 'EKS Connect & Manage'}</h2>
          <div className="eks-manage-header-actions">
            {(activeTab === 'deploy' || activeTab === 'presets') && (
              <button
                className="modal-header-refresh"
                onClick={handleHeaderRefresh}
                disabled={loadingPresets}
                title="Refresh"
              >
                ↻
              </button>
            )}
            <button className="eks-manage-close" onClick={onClose}>&times;</button>
          </div>
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
