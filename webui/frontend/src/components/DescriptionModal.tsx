import React, { useState, useEffect } from 'react';
import { terraformApi } from '../services/api';
import '../styles/DescriptionModal.css';

interface DescriptionModalProps {
  resourceId: string;
  resourceName: string;
  onClose: () => void;
}

function renderMarkdownLine(line: string, key: number): React.ReactNode {
  const trimmed = line.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('### ')) {
    return <h3 key={key}>{trimmed.slice(4)}</h3>;
  }
  if (trimmed.startsWith('## ')) {
    return <h2 key={key}>{trimmed.slice(3)}</h2>;
  }
  if (trimmed.startsWith('# ')) {
    return <h1 key={key}>{trimmed.slice(2)}</h1>;
  }
  if (trimmed.startsWith('- ')) {
    const rest = trimmed.slice(2).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    return <li key={key} dangerouslySetInnerHTML={{ __html: rest }} />;
  }
  const withBold = trimmed.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  return <p key={key} dangerouslySetInnerHTML={{ __html: withBold }} />;
}

function markdownToElements(content: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const lines = content.split('\n');
  let inList = false;
  let listItems: React.ReactNode[] = [];
  let key = 0;

  const flushList = () => {
    if (listItems.length > 0) {
      nodes.push(<ul key={key++}>{listItems}</ul>);
      listItems = [];
    }
    inList = false;
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('- ')) {
      if (!inList) inList = true;
      listItems.push(renderMarkdownLine(line, key++));
    } else {
      flushList();
      const el = renderMarkdownLine(line, key++);
      if (el != null) nodes.push(el);
    }
  }
  flushList();
  return nodes;
}

const DescriptionModal = ({ resourceId, resourceName, onClose }: DescriptionModalProps) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    terraformApi.getResourceDescription(resourceId)
      .then((res) => {
        if (!cancelled) {
          setContent(res.content);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.status === 404 ? 'No description available.' : (err.message || 'Failed to load description.'));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [resourceId]);

  return (
    <div className="modal-overlay description-modal-overlay" onClick={onClose}>
      <div className="description-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{resourceName}</h2>
          <button type="button" onClick={onClose} className="close-button" aria-label="Close">&times;</button>
        </div>
        <div className="description-content">
          {loading && <p className="description-loading">Loading...</p>}
          {error && <p className="description-error">{error}</p>}
          {!loading && !error && content && (
            <div className="description-body">
              {markdownToElements(content)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DescriptionModal;
