import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

interface Result {
  id: string;
  action: string;
  status: 'running' | 'success' | 'error';
  message: string;
  timestamp: Date;
  output?: string;
}

interface ResultsPanelProps {
  results: Result[];
  onClear: () => void;
}

const ResultsPanel = ({ results, onClear }: ResultsPanelProps) => {
  const outputRefs = useRef<{ [key: string]: HTMLPreElement | null }>({});
  const modalOutputRef = useRef<HTMLPreElement | null>(null);
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [modalStartPosition, setModalStartPosition] = useState<{ x: number; y: number } | null>(null);

  const selectedResult = selectedResultId 
    ? results.find(r => r.id === selectedResultId) || null 
    : null;

  useEffect(() => {
    results.forEach(result => {
      if (result.status === 'running' && result.output && outputRefs.current[result.id]) {
        const outputElement = outputRefs.current[result.id];
        if (outputElement) {
          outputElement.scrollTop = outputElement.scrollHeight;
        }
      }
    });

    if (selectedResult && selectedResult.status === 'running' && modalOutputRef.current) {
      modalOutputRef.current.scrollTop = modalOutputRef.current.scrollHeight;
    }
  }, [results, selectedResult]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && selectedResultId) {
        setSelectedResultId(null);
        setModalStartPosition(null);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [selectedResultId]);

  const toggleResultExpansion = (id: string) => {
    const newExpanded = new Set(expandedResults);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedResults(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return '⏳';
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      default:
        return '•';
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'running':
        return 'status-running';
      case 'success':
        return 'status-success';
      case 'error':
        return 'status-error';
      default:
        return '';
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      hour12: false 
    });
  };

  return (
    <div className="results-panel">
      <div className="results-header">
        <h2>Results</h2>
        <button onClick={onClear} className="btn-clear-small" disabled={results.length === 0}>
          Clear
        </button>
      </div>

      {results.some(r => r.status === 'running') && (
        <div className="running-indicator">
          <span className="spinner">⏳</span>
          <span>Operation in progress...</span>
        </div>
      )}

      {selectedResult && createPortal(
        <div 
          className="result-modal-overlay" 
          onClick={() => {
            setSelectedResultId(null);
            setModalStartPosition(null);
          }}
        >
          <div 
            className="result-modal" 
            onClick={(e) => e.stopPropagation()}
            style={{
              '--start-x': modalStartPosition ? `${modalStartPosition.x}px` : '50%',
              '--start-y': modalStartPosition ? `${modalStartPosition.y}px` : '50%'
            } as React.CSSProperties}
          >
            <div className="modal-header">
              <div className="modal-title">
                <span className="result-status-large">{getStatusIcon(selectedResult.status)}</span>
                <div>
                  <h3>{selectedResult.action}</h3>
                  <span className="modal-subtitle">
                    {formatTime(selectedResult.timestamp)} - {selectedResult.message}
                  </span>
                </div>
              </div>
              <button 
                onClick={() => {
                  setSelectedResultId(null);
                  setModalStartPosition(null);
                }} 
                className="btn-close-modal"
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <pre 
                className="modal-output-content"
                ref={modalOutputRef}
              >
                {selectedResult.output}
              </pre>
            </div>
          </div>
        </div>,
        document.body
      )}

      <div className="results-list">
        {results.length === 0 ? (
          <div className="no-results">
            <p>No actions performed yet</p>
            <p className="hint">Results will appear here when you run actions</p>
          </div>
        ) : (
          <>
            {results.map((result) => {
              const isExpanded = expandedResults.has(result.id);
              const hasOutput = result.output && result.output.trim().length > 0;
              
              return (
                <div key={result.id} className={`result-item ${getStatusClass(result.status)}`}>
                  <div className="result-header-item">
                    <span className="result-status">{getStatusIcon(result.status)}</span>
                    <span className="result-action">{result.action}</span>
                    <span className="result-time">{formatTime(result.timestamp)}</span>
                  </div>
                  
                  <div className="result-message">{result.message}</div>
                  
                  {hasOutput && (
                    <div className="result-output">
                      <div 
                        className="output-label clickable" 
                        onClick={() => toggleResultExpansion(result.id)}
                        title="Click to expand/collapse"
                      >
                        <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                        Output:
                      </div>
                      <pre 
                        className={`output-text ${isExpanded ? 'expanded' : 'collapsed'}`}
                        ref={(el) => {
                          outputRefs.current[result.id] = el;
                        }}
                        onClick={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setModalStartPosition({
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2
                          });
                          setSelectedResultId(result.id);
                        }}
                        title="Click to view in full screen"
                      >
                        {result.output}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
};

export default ResultsPanel;
