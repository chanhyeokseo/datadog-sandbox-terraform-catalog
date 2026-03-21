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
import { ecsManageApi, EKSPreset, TreeNode, TreeFolder, DeploymentInfo } from '../services/api';
import '../styles/EKSManageModal.css';

interface ECSManageModalProps {
  onClose: () => void;
  connectInfo: {
    clusterName: string;
    clusterArn: string;
    region: string;
  } | null;
}

type TabId = 'connection' | 'presets' | 'editor' | 'deploy' | 'run';

const STORAGE_KEY = 'ecs-last-preset';

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

const highlightJson = (text: string): string => {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return text.split('\n').map(line => {
    return esc(line)
      .replace(/("(?:[^"\\]|\\.)*")(\s*:)/g, '<span class="hl-key">$1</span>$2')
      .replace(/(:\s*)("(?:[^"\\]|\\.)*")/g, '$1<span class="hl-string">$2</span>')
      .replace(/^\s*("(?:[^"\\]|\\.)*")\s*[,]?\s*$/gm, (match) =>
        match.replace(/("(?:[^"\\]|\\.)*")/, '<span class="hl-string">$1</span>'))
      .replace(/\b(true|false|null)\b/g, '<span class="hl-bool">$1</span>')
      .replace(/(:\s*)(-?\d+(?:\.\d+)?)\b/g, '$1<span class="hl-number">$2</span>');
  }).join('\n');
};

const highlightCode = (text: string, filename: string, viewAs?: 'json' | 'yaml'): string => {
  if (viewAs === 'yaml') return highlightYaml(text);
  if (viewAs === 'json') return highlightJson(text);
  if (filename.endsWith('.json')) return highlightJson(text);
  return highlightYaml(text);
};

const jsonToYaml = (data: unknown, indent = 0): string => {
  const pad = '  '.repeat(indent);
  if (data === null || data === undefined) return 'null';
  if (typeof data === 'boolean') return data ? 'true' : 'false';
  if (typeof data === 'number') return String(data);
  if (typeof data === 'string') {
    if (data === '' || /[:{}\[\],&*#?|<>=!%@`\n]/.test(data) || /^\s|\s$/.test(data)
      || /^(true|false|null|yes|no|on|off)$/i.test(data) || /^[\d.+-]/.test(data))
      return JSON.stringify(data);
    return data;
  }
  if (Array.isArray(data)) {
    if (data.length === 0) return '[]';
    return data.map(item => {
      const inner = jsonToYaml(item, indent + 1);
      if (typeof item === 'object' && item !== null) {
        return `${pad}-\n${inner.split('\n').map(l => pad + '  ' + l.trimStart()).join('\n')}`;
      }
      return `${pad}- ${inner.trimStart()}`;
    }).join('\n');
  }
  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>);
    if (entries.length === 0) return '{}';
    return entries.map(([k, v]) => {
      const needsQuote = /[:{}\[\],&*#?|<>=!%@`]/.test(k) || k === '';
      const keyStr = needsQuote ? JSON.stringify(k) : k;
      if (typeof v === 'object' && v !== null &&
          ((Array.isArray(v) && v.length > 0) || (!Array.isArray(v) && Object.keys(v).length > 0))) {
        return `${pad}${keyStr}:\n${jsonToYaml(v, indent + 1)}`;
      }
      return `${pad}${keyStr}: ${jsonToYaml(v, indent + 1).trimStart()}`;
    }).join('\n');
  }
  return String(data);
};

const yamlToJson = (text: string): unknown => {
  const lines = text.split('\n');
  let pos = 0;

  const peekIndent = (): number => {
    while (pos < lines.length && /^\s*(#|$)/.test(lines[pos])) pos++;
    if (pos >= lines.length) return -1;
    return lines[pos].search(/\S/);
  };

  const parseValue = (raw: string): unknown => {
    const s = raw.trim();
    if (s === '' || s === 'null' || s === '~') return null;
    if (s === 'true' || s === 'yes') return true;
    if (s === 'false' || s === 'no') return false;
    if (s === '[]') return [];
    if (s === '{}') return {};
    if (/^-?\d+$/.test(s)) return parseInt(s, 10);
    if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
    if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")))
      return s.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    if (s.startsWith('[') || s.startsWith('{')) return JSON.parse(s);
    return s;
  };

  const parseBlock = (minIndent: number): unknown => {
    const indent = peekIndent();
    if (indent < minIndent || pos >= lines.length) return null;

    const firstLine = lines[pos];
    const stripped = firstLine.trimStart();

    if (stripped.startsWith('- ') || stripped === '-') {
      const arr: unknown[] = [];
      while (pos < lines.length) {
        const ci = peekIndent();
        if (ci < indent || ci === -1) break;
        const ln = lines[pos].trimStart();
        if (!ln.startsWith('-')) break;
        const after = ln.slice(1).trim();
        pos++;
        if (after === '' || after.includes(':')) {
          if (after !== '' && after.includes(':')) {
            pos--;
            const fakeIndent = lines[pos].indexOf('-') + 2;
            const rebuilt = ' '.repeat(fakeIndent) + after;
            const origLine = lines[pos];
            lines[pos] = rebuilt;
            const saved = pos;
            const val = parseBlock(fakeIndent);
            if (pos === saved) pos++;
            lines[saved] = origLine;
            arr.push(val);
          } else {
            arr.push(parseBlock(indent + 1));
          }
        } else {
          arr.push(parseValue(after));
        }
      }
      return arr;
    }

    if (stripped.includes(':')) {
      const obj: Record<string, unknown> = {};
      while (pos < lines.length) {
        const ci = peekIndent();
        if (ci < indent || ci === -1) break;
        if (ci > indent) { pos++; continue; }
        const ln = lines[pos];
        const match = ln.match(/^(\s*)((?:"[^"]*"|'[^']*'|[^:#])+):\s*(.*)/);
        if (!match) { pos++; continue; }
        const key = match[2].trim().replace(/^["']|["']$/g, '');
        const rest = match[3].trim();
        pos++;
        if (rest === '' || rest === '|' || rest === '>') {
          obj[key] = parseBlock(indent + 1);
          if (obj[key] === null) obj[key] = rest === '' ? null : '';
        } else {
          obj[key] = parseValue(rest);
        }
      }
      return obj;
    }

    pos++;
    return parseValue(stripped);
  };

  return parseBlock(0);
};

const convertJsonToYaml = (jsonStr: string): string => {
  const data = JSON.parse(jsonStr);
  return jsonToYaml(data);
};

const convertYamlToJson = (yamlStr: string): string => {
  const data = yamlToJson(yamlStr);
  return JSON.stringify(data, null, 2);
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

const ECSManageModal = ({ onClose, connectInfo }: ECSManageModalProps) => {
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

  const [viewFormat, setViewFormat] = useState<'original' | 'json' | 'yaml'>('original');
  const [convertError, setConvertError] = useState<string | null>(null);

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
      const data = await ecsManageApi.getDeployments();
      setDeployedPresets(data);
    } catch (e) {
      console.error('Failed to load deployments:', e);
    }
  }, []);

  const loadPresets = useCallback(async () => {
    setLoadingPresets(true);
    try {
      const { presets: list } = await ecsManageApi.listPresets();
      setPresets(list);
      presetsMap.current = Object.fromEntries(list.map(p => [p.name, p]));
      const saved = localStorage.getItem(STORAGE_KEY);
      const fallback = saved && list.some(p => p.name === saved) ? saved : list[0]?.name || '';
      if (!deployPreset) setDeployPreset(fallback);
      try {
        const layout = await ecsManageApi.getLayout();
        setTreeLayout(layout);
      } catch { /* layout will be generated server-side on next call */ }
      await loadDeployments();
    } catch (e) {
      console.error('Failed to load presets:', e);
    } finally {
      setLoadingPresets(false);
    }
  }, [deployPreset, loadDeployments]);

  useEffect(() => { loadPresets(); }, [loadPresets]);

  useEffect(() => {
    if (presets.length === 0) return;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && presets.some(p => p.name === saved) && !editorPreset) {
      handleSelectPresetForEditor(saved);
    }
  }, [presets]);

  const copyToClipboard = (text: string) => { navigator.clipboard.writeText(text); };

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
      const preset = await ecsManageApi.getPreset(name);
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
      await ecsManageApi.updatePresetFile(editorPreset, filename.trim(), '');
      const preset = await ecsManageApi.getPreset(editorPreset);
      setEditorFiles(preset.files || []);
      await loadFile(editorPreset, filename.trim());
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to add file');
    }
  };

  const loadFile = async (preset: string, filename: string) => {
    try {
      const { content } = await ecsManageApi.getPresetFile(preset, filename);
      setEditorActiveFile(filename);
      setEditorContent(content);
      setEditorDirty(false);
      setViewFormat('original');
      setConvertError(null);
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
      await ecsManageApi.updatePresetManifest(editorPreset, data);
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
      await ecsManageApi.createPreset({ name: createName.trim(), description: createDesc });
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
      await ecsManageApi.deletePreset(name);
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
      await ecsManageApi.clonePreset(name, targetName.trim());
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
      await ecsManageApi.streamDeploy(
        deployPreset,
        (chunk) => { setDeployLog(prev => prev + chunk); if (deployLogRef.current) deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight; },
        (success) => { setDeployStatus(success ? 'success' : 'error'); setDeploying(false); if (success) loadDeployments(); },
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
    if (!window.confirm(`Delete preset "${deployPreset}" from the cluster?`)) return;
    setDeploying(true);
    setDeployLog('');
    setDeployStatus('running');
    abortRef.current = new AbortController();
    try {
      await ecsManageApi.streamUndeploy(
        deployPreset,
        (chunk) => { setDeployLog(prev => prev + chunk); if (deployLogRef.current) deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight; },
        (success) => { setDeployStatus(success ? 'success' : 'error'); setDeploying(false); if (success) loadDeployments(); },
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
      await ecsManageApi.streamUpdate(
        deployPreset,
        (chunk) => { setDeployLog(prev => prev + chunk); if (deployLogRef.current) deployLogRef.current.scrollTop = deployLogRef.current.scrollHeight; },
        (success) => { setDeployStatus(success ? 'success' : 'error'); setDeploying(false); },
        abortRef.current.signal,
      );
    } catch (e) {
      setDeployStatus('error');
      setDeploying(false);
      setDeployLog(prev => prev + `\nError: ${e}\n`);
    }
  };

  const isConvertible = (filename: string) => filename.endsWith('.json') || filename.endsWith('.yaml') || filename.endsWith('.yml');

  const getEffectiveFormat = (): 'json' | 'yaml' => {
    if (viewFormat !== 'original') return viewFormat;
    return editorActiveFile.endsWith('.json') ? 'json' : 'yaml';
  };

  const handleFormatToggle = () => {
    setConvertError(null);
    const current = getEffectiveFormat();
    const target = current === 'json' ? 'yaml' : 'json';
    try {
      const converted = target === 'yaml'
        ? convertJsonToYaml(editorContent)
        : convertYamlToJson(editorContent);
      setEditorContent(converted);
      setEditorDirty(true);
      setViewFormat(target);
    } catch (e) {
      setConvertError(`Conversion failed: ${(e as Error).message}`);
    }
  };

  const handleSaveFileWithConvert = async () => {
    if (!editorPreset || !editorActiveFile) return;
    setEditorSaving(true);
    try {
      let contentToSave = editorContent;
      if (editorActiveFile.endsWith('.json') && viewFormat === 'yaml') {
        contentToSave = convertYamlToJson(editorContent);
      } else if ((editorActiveFile.endsWith('.yaml') || editorActiveFile.endsWith('.yml')) && viewFormat === 'json') {
        contentToSave = convertJsonToYaml(JSON.parse(editorContent));
      }
      await ecsManageApi.updatePresetFile(editorPreset, editorActiveFile, contentToSave);
      setEditorDirty(false);
      setConvertError(null);
    } catch (e) {
      setConvertError(`Save failed: ${(e as Error).message}`);
    } finally {
      setEditorSaving(false);
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
      requestAnimationFrame(() => { target.selectionStart = target.selectionEnd = start + 2; });
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      handleSaveFileWithConvert();
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
      setTreeLayout(prev => { ecsManageApi.saveLayout(prev).catch(() => {}); return prev; });
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
          if (oldIdx >= 0 && newIdx >= 0) { const [item] = next.splice(oldIdx, 1); next.splice(newIdx, 0, item); }
        } else {
          const folder = next.find(n => n.id === activeContainer) as TreeFolder | undefined;
          if (folder) {
            const oldIdx = folder.children.indexOf(activeId);
            const newIdx = folder.children.indexOf(overId);
            if (oldIdx >= 0 && newIdx >= 0) folder.children = arrayMove(folder.children, oldIdx, newIdx);
          }
        }
        ecsManageApi.saveLayout(next).catch(() => {});
        return next;
      });
    } else {
      setTreeLayout(prev => { ecsManageApi.saveLayout(prev).catch(() => {}); return prev; });
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
    ecsManageApi.saveLayout(next).catch(() => {});
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
    ecsManageApi.saveLayout(next).catch(() => {});
  };

  const renderConnectionTab = () => {
    if (!connectInfo) {
      return (
        <div className="eks-manage-loading">
          No connection info available. Deploy the ECS cluster first and fetch outputs.
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
        <div className="eks-connect-field">
          <label>Region</label>
          <div className="eks-connect-value-row">
            <code>{connectInfo.region}</code>
            <button className="eks-copy-btn" onClick={() => copyToClipboard(connectInfo.region)}>Copy</button>
          </div>
        </div>
        <div className="eks-connect-field">
          <label>List Services</label>
          <div className="hint">Check running services in the cluster:</div>
          <div className="eks-connect-value-row">
            <code>aws ecs list-services --cluster {connectInfo.clusterName}</code>
            <button className="eks-copy-btn" onClick={() => copyToClipboard(`aws ecs list-services --cluster ${connectInfo.clusterName}`)}>Copy</button>
          </div>
        </div>
        <div className="eks-connect-field">
          <label>Describe Cluster</label>
          <div className="hint">Get detailed cluster information:</div>
          <div className="eks-connect-value-row">
            <code>aws ecs describe-clusters --clusters {connectInfo.clusterName}</code>
            <button className="eks-copy-btn" onClick={() => copyToClipboard(`aws ecs describe-clusters --clusters ${connectInfo.clusterName}`)}>Copy</button>
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
    if (loadingPresets) return <div className="eks-manage-loading">Loading presets...</div>;
    return (
      <DndContext sensors={dndSensors} collisionDetection={closestCorners} onDragStart={handleTreeDragStart} onDragOver={handleTreeDragOver} onDragEnd={handleTreeDragEnd}>
        <div className="eks-presets-toolbar">
          <button className="eks-btn-create" onClick={() => setShowCreateForm(!showCreateForm)}>
            {showCreateForm ? 'Cancel' : '+ New Preset'}
          </button>
          <button className="eks-btn-create" onClick={handleCreateFolder} style={{ marginLeft: 8 }}>+ New Folder</button>
        </div>
        {showCreateForm && (
          <div className="eks-create-form">
            <h4>Create New Preset</h4>
            <input type="text" placeholder="Preset name (e.g. my-task-definition)" value={createName} onChange={e => setCreateName(e.target.value)} />
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
                      <button className="eks-tree-folder-delete" onClick={(e) => { e.stopPropagation(); handleDeleteFolder(folder.id); }} title="Delete folder">×</button>
                    </div>
                    {expanded && (
                      <SortableContext items={folder.children} strategy={verticalListSortingStrategy}>
                        <div className="eks-tree-folder-children">
                          {folder.children.map(cid => renderPresetNode(cid))}
                          {folder.children.length === 0 && <div className="eks-tree-empty-folder">Drop presets here</div>}
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
            <div className="eks-tree-preset drag-overlay"><span className="eks-tree-preset-name">{presetsMap.current[dragActiveId].name}</span></div>
          ) : null}
        </DragOverlay>
        {presets.length === 0 && <div className="eks-manage-loading">No presets found</div>}
      </DndContext>
    );
  };

  const renderEditorTab = () => {
    if (!editorPreset) {
      return (
        <div className="eks-editor-layout">
          <div className="eks-editor-empty">Select a preset from the Presets tab to edit its files.</div>
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
            <button className={`eks-mode-btn ${editorMode === 'files' ? 'active' : ''}`} onClick={() => setEditorMode('files')}>Files</button>
            <button className={`eks-mode-btn ${editorMode === 'commands' ? 'active' : ''}`} onClick={() => setEditorMode('commands')}>Commands</button>
          </div>
          {editorMode === 'files' && editorFiles.map(f => (
            <div key={f} className={`eks-file-item ${editorActiveFile === f ? 'active' : ''}`} onClick={() => handleFileSelect(f)}>{f}</div>
          ))}
          {editorMode === 'files' && !readonly && (
            <button className="eks-btn-add-file" onClick={handleAddFile}>+ Add File</button>
          )}
          {readonly && (
            <button className="eks-btn-clone sidebar-clone" onClick={() => handleClonePreset(editorPreset)}>Clone to Edit</button>
          )}
        </div>
        <div className="eks-editor-main">
          {editorMode === 'files' ? (
            editorActiveFile ? (
              <>
                <div className="eks-editor-toolbar">
                  <span className="eks-editor-filename">{editorActiveFile}</span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginLeft: 'auto' }}>
                    {isConvertible(editorActiveFile) && (
                      <div
                        onClick={handleFormatToggle}
                        title={`Switch to ${getEffectiveFormat() === 'json' ? 'YAML' : 'JSON'}`}
                        style={{
                          display: 'inline-flex', cursor: 'pointer', borderRadius: '4px', overflow: 'hidden',
                          border: '1px solid var(--border-color, #444)', fontSize: '11px', fontWeight: 600, lineHeight: '22px',
                        }}
                      >
                        <span style={{
                          padding: '0 8px',
                          background: getEffectiveFormat() === 'json' ? 'var(--accent-color, #4f8ff7)' : 'transparent',
                          color: getEffectiveFormat() === 'json' ? '#fff' : 'var(--text-secondary, #aaa)',
                        }}>JSON</span>
                        <span style={{
                          padding: '0 8px',
                          background: getEffectiveFormat() === 'yaml' ? 'var(--accent-color, #4f8ff7)' : 'transparent',
                          color: getEffectiveFormat() === 'yaml' ? '#fff' : 'var(--text-secondary, #aaa)',
                        }}>YAML</span>
                      </div>
                    )}
                    {!readonly && (
                      <button className="eks-btn-save" onClick={handleSaveFileWithConvert} disabled={!editorDirty || editorSaving}>
                        {editorSaving ? 'Saving...' : 'Save'}
                      </button>
                    )}
                  </div>
                </div>
                {convertError && (
                  <div style={{ padding: '6px 12px', background: '#3a1c1c', color: '#f87171', fontSize: '12px', borderBottom: '1px solid #5c2020' }}>
                    {convertError}
                  </div>
                )}
                <div className="eks-code-editor">
                  <pre className="eks-code-highlight" ref={highlightRef} aria-hidden="true">
                    <code dangerouslySetInnerHTML={{ __html: highlightCode(editorContent, editorActiveFile, viewFormat !== 'original' ? viewFormat : undefined) + '\n' }} />
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
                  <button className="eks-btn-save" onClick={handleSaveManifest} disabled={(!cmdDirty && !editorDescDirty) || cmdSaving}>
                    {cmdSaving ? 'Saving...' : 'Save'}
                  </button>
                )}
              </div>
              <div className="eks-cmd-sections">
                <div className="eks-cmd-section">
                  <label>deploy_commands</label>
                  <textarea className={`eks-cmd-textarea ${readonly ? 'readonly' : ''}`} value={cmdDeploy}
                    onChange={e => { if (!readonly) { setCmdDeploy(e.target.value); setCmdDirty(true); } }} readOnly={readonly} spellCheck={false}
                    placeholder="aws ecs register-task-definition --cli-input-json file://task-definition.json&#10;aws ecs create-service --cluster {{cluster_name}} --service-name my-svc --task-definition my-task" />
                </div>
                <div className="eks-cmd-section">
                  <label>update_commands</label>
                  <textarea className={`eks-cmd-textarea ${readonly ? 'readonly' : ''}`} value={cmdUpdate}
                    onChange={e => { if (!readonly) { setCmdUpdate(e.target.value); setCmdDirty(true); } }} readOnly={readonly} spellCheck={false}
                    placeholder="aws ecs update-service --cluster {{cluster_name}} --service my-svc --force-new-deployment" />
                </div>
                <div className="eks-cmd-section">
                  <label>undeploy_commands</label>
                  <textarea className={`eks-cmd-textarea ${readonly ? 'readonly' : ''}`} value={cmdUndeploy}
                    onChange={e => { if (!readonly) { setCmdUndeploy(e.target.value); setCmdDirty(true); } }} readOnly={readonly} spellCheck={false}
                    placeholder="aws ecs delete-service --cluster {{cluster_name}} --service my-svc --force" />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const PRESET_COMMANDS = [
    { label: 'List Services', cmd: 'aws ecs list-services --cluster {{cluster_name}}' },
    { label: 'List Tasks', cmd: 'aws ecs list-tasks --cluster {{cluster_name}}' },
    { label: 'Describe Cluster', cmd: 'aws ecs describe-clusters --clusters {{cluster_name}}' },
    { label: 'List Task Defs', cmd: 'aws ecs list-task-definitions' },
    { label: 'List Containers', cmd: 'aws ecs list-container-instances --cluster {{cluster_name}}' },
    { label: 'List Clusters', cmd: 'aws ecs list-clusters' },
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
      await ecsManageApi.streamRun(
        cmd.trim(),
        (chunk) => { setRunOutput(prev => prev + chunk); if (runLogRef.current) runLogRef.current.scrollTop = runLogRef.current.scrollHeight; },
        (success) => { setRunStatus(success ? 'success' : 'error'); setRunRunning(false); },
        runAbortRef.current.signal,
      );
    } catch (e) {
      setRunStatus('error');
      setRunRunning(false);
      setRunOutput(prev => prev + `\nError: ${e}\n`);
    }
  };

  const handleRunKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { e.preventDefault(); executeRunCommand(runCommand); }
    else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (runHistory.length > 0) {
        const next = Math.min(runHistoryIdx + 1, runHistory.length - 1);
        setRunHistoryIdx(next);
        setRunCommand(runHistory[next]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (runHistoryIdx > 0) { const next = runHistoryIdx - 1; setRunHistoryIdx(next); setRunCommand(runHistory[next]); }
      else { setRunHistoryIdx(-1); setRunCommand(''); }
    }
  };

  const renderRunTab = () => (
    <div className="eks-run-section">
      <div className="eks-run-presets">
        {PRESET_COMMANDS.map(({ label, cmd }) => (
          <button key={cmd} className={`eks-run-preset-btn ${runRunning ? 'disabled' : ''}`}
            onClick={() => { setRunCommand(cmd); executeRunCommand(cmd); }} disabled={runRunning} title={cmd}>
            {label}
          </button>
        ))}
      </div>
      <div className="eks-run-input-row">
        <span className="eks-run-prompt">$</span>
        <input type="text" className="eks-run-input" value={runCommand} onChange={e => setRunCommand(e.target.value)}
          onKeyDown={handleRunKeyDown} placeholder="aws ecs list-services --cluster my-cluster" disabled={runRunning} spellCheck={false} autoComplete="off" />
        <button className="eks-run-exec-btn" onClick={() => executeRunCommand(runCommand)} disabled={runRunning || !runCommand.trim()}>
          {runRunning ? 'Running...' : 'Run'}
        </button>
        {runRunning && <button className="eks-run-stop-btn" onClick={() => runAbortRef.current?.abort()}>Stop</button>}
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
                <div key={name} className={`eks-deployed-item ${deployPreset === name ? 'selected' : ''}`}
                  onClick={() => { setDeployPreset(name); localStorage.setItem(STORAGE_KEY, name); }}>
                  <span className="eks-deployed-name">{name}</span>
                  <span className="eks-deployed-time">{new Date(deployedPresets[name].deployed_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="eks-deploy-preset-select">
          <label>Preset</label>
          <select value={deployPreset} onChange={e => { setDeployPreset(e.target.value); localStorage.setItem(STORAGE_KEY, e.target.value); }} disabled={deploying}>
            {presets.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        </div>
        <div className="eks-deploy-actions">
          <button className="eks-btn-deploy" onClick={handleDeploy} disabled={deploying || !deployPreset}>
            {deploying ? 'Running...' : 'Deploy'}
          </button>
          <button className="eks-btn-update" onClick={handleUpdate} disabled={deploying || !deployPreset || !hasUpdateCmds}
            title={hasUpdateCmds ? 'Update existing deployment' : 'No update commands defined'}>Update</button>
          <button className="eks-btn-undeploy" onClick={handleUndeploy} disabled={deploying || !deployPreset}>Delete</button>
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
          <h2>ECS Connect & Manage</h2>
          <button className="eks-manage-close" onClick={onClose}>&times;</button>
        </div>
        <div className="eks-manage-tabs">
          {(['connection', 'presets', 'editor', 'deploy', 'run'] as TabId[]).map(tab => (
            <button key={tab} className={`eks-manage-tab ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
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

export default ECSManageModal;
