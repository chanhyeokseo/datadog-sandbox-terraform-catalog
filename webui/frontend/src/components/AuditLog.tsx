import { useState, useEffect, useCallback } from 'react';
import { AuditEntry, AuditSummary, AuditLogsResponse } from '../types';
import { auditApi } from '../services/api';
import '../styles/AuditLog.css';

interface AuditLogProps {
  refreshTrigger?: number;
}

const ACTOR_ICONS: Record<string, string> = {
  'cursor': '🖱️',
  'claude-code': '🤖',
  'claude-desktop': '🖥️',
  'mcp-client': '🔧',
  'web ui': '🌐',
};

function getActorIcon(actor: string): string {
  const lower = actor.toLowerCase();
  for (const [key, icon] of Object.entries(ACTOR_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return '🔧';
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

const AuditLog = ({ refreshTrigger }: AuditLogProps) => {
  const [logs, setLogs] = useState<AuditLogsResponse | null>(null);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const perPage = 25;

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [logsData, summaryData] = await Promise.all([
        auditApi.getLogs(page, perPage, statusFilter || undefined),
        auditApi.getSummary(),
      ]);
      setLogs(logsData);
      setSummary(summaryData);
    } catch (err) {
      console.error('Failed to load audit data:', err);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      setPage(1);
      fetchData();
    }
  }, [refreshTrigger]);

  const totalPages = logs?.total_pages ?? 1;

  const renderPagination = () => {
    if (totalPages <= 1) return null;
    const pages: (number | string)[] = [];
    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
        pages.push(i);
      } else if (pages[pages.length - 1] !== '...') {
        pages.push('...');
      }
    }

    return (
      <div className="audit-pagination">
        <span className="audit-pagination-info">
          {logs ? `${(page - 1) * perPage + 1}\u2013${Math.min(page * perPage, logs.total)} of ${logs.total}` : ''}
        </span>
        <div className="audit-pagination-controls">
          <button
            className="audit-page-btn"
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
          >
            &lt;
          </button>
          {pages.map((p, i) =>
            typeof p === 'number' ? (
              <button
                key={i}
                className={`audit-page-btn ${p === page ? 'active' : ''}`}
                onClick={() => setPage(p)}
              >
                {p}
              </button>
            ) : (
              <span key={i} className="audit-page-ellipsis">&hellip;</span>
            )
          )}
          <button
            className="audit-page-btn"
            disabled={page >= totalPages}
            onClick={() => setPage(p => p + 1)}
          >
            &gt;
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="audit-log-container">
      <div className="audit-log-header">
        <div>
          <h2 className="audit-log-title">Audit Log</h2>
          <p className="audit-log-subtitle">Complete visibility into all MCP actions and system operations.</p>
        </div>
        <div className="audit-log-actions">
          <select
            className="audit-filter-select"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Status</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
          <button className="audit-refresh-btn" onClick={fetchData}>
            Refresh
          </button>
        </div>
      </div>

      {summary && (
        <div className="audit-summary-cards">
          <div className="audit-summary-card">
            <div className="audit-summary-icon total">
              <span>📊</span>
            </div>
            <div className="audit-summary-content">
              <div className="audit-summary-value">{summary.total}</div>
              <div className="audit-summary-label">Total Actions</div>
            </div>
          </div>
          <div className="audit-summary-card">
            <div className="audit-summary-icon success">
              <span>✓</span>
            </div>
            <div className="audit-summary-content">
              <div className="audit-summary-value">{summary.successful}</div>
              <div className="audit-summary-label">Successful</div>
              <div className="audit-summary-sub">{summary.success_rate}%</div>
            </div>
          </div>
          <div className="audit-summary-card">
            <div className="audit-summary-icon failed">
              <span>!</span>
            </div>
            <div className="audit-summary-content">
              <div className="audit-summary-value">{summary.failed}</div>
              <div className="audit-summary-label">Failed</div>
            </div>
          </div>
          <div className="audit-summary-card">
            <div className="audit-summary-icon duration">
              <span>⏱</span>
            </div>
            <div className="audit-summary-content">
              <div className="audit-summary-value">{formatDuration(summary.avg_duration_ms)}</div>
              <div className="audit-summary-label">Avg Duration</div>
            </div>
          </div>
        </div>
      )}

      <div className="audit-table-wrapper">
        {loading && !logs ? (
          <div className="audit-loading">Loading audit logs...</div>
        ) : !logs || logs.entries.length === 0 ? (
          <div className="audit-empty">
            <div className="audit-empty-icon">📋</div>
            <div className="audit-empty-text">No audit log entries yet</div>
            <div className="audit-empty-sub">MCP server actions will appear here automatically.</div>
          </div>
        ) : (
          <>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Actor</th>
                  <th>Tool / Action</th>
                  <th>Resource</th>
                  <th>Status</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {logs.entries.map((entry: AuditEntry) => (
                  <tr key={entry.id} className={`audit-row ${entry.status}`}>
                    <td className="audit-cell-time">{formatTimestamp(entry.timestamp)}</td>
                    <td>
                      <div className="audit-cell-actor">
                        <span className="audit-actor-icon">{getActorIcon(entry.actor)}</span>
                        <span className="audit-actor-name">{entry.actor}</span>
                      </div>
                    </td>
                    <td>
                      <div className="audit-cell-action">
                        <span className="audit-action-name">{entry.tool_action}</span>
                        <span className="audit-action-method">{entry.method}</span>
                      </div>
                    </td>
                    <td className="audit-cell-resource">
                      {entry.resource || <span className="audit-no-resource">&mdash;</span>}
                    </td>
                    <td className="audit-cell-status">
                      <span className={`audit-status-badge ${entry.status}`}>
                        {entry.status === 'success' ? '✓' : '✕'} {entry.status}
                      </span>
                    </td>
                    <td className="audit-cell-duration">{formatDuration(entry.duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {renderPagination()}
          </>
        )}
      </div>
    </div>
  );
};

export default AuditLog;
