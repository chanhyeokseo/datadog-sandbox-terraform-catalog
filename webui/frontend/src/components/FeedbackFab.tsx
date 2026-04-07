import { useState, useMemo, useCallback } from 'react';
import FeedbackModal from './FeedbackModal';
import './FeedbackFab.css';

const GITHUB_NEW_ISSUE = 'https://github.com/chanhyeokseo/dogstac/issues/new';

export interface FeedbackFabProps {
  selectedResourceId: string | null;
  latestResultAction: string | null;
  latestResultStatus: 'running' | 'success' | 'error' | null;
  emphasizePulse: boolean;
  onOpenModal: () => void;
}

const MessageIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

function buildGithubNewIssueUrl(
  selectedResourceId: string | null,
  latestResultAction: string | null,
  latestResultStatus: string | null,
): string {
  const ts = new Date().toISOString();
  const title = `[DogSTAC] Feedback`;
  const lines = [
    '## Context (auto-filled)',
    `- Selected resource: ${selectedResourceId || 'none'}`,
    `- Latest panel action: ${latestResultAction || 'none'}`,
    `- Latest panel status: ${latestResultStatus || 'none'}`,
    `- Timestamp: ${ts}`,
    '',
    '## Description',
    '',
  ];
  const body = lines.join('\n');
  const params = new URLSearchParams({ title, body });
  return `${GITHUB_NEW_ISSUE}?${params.toString()}`;
}

const FeedbackFab = ({
  selectedResourceId,
  latestResultAction,
  latestResultStatus,
  emphasizePulse,
  onOpenModal,
}: FeedbackFabProps) => {
  const [isOpen, setIsOpen] = useState(false);

  const githubNewIssueUrl = useMemo(
    () => buildGithubNewIssueUrl(selectedResourceId, latestResultAction, latestResultStatus),
    [selectedResourceId, latestResultAction, latestResultStatus],
  );

  const open = useCallback(() => {
    if (import.meta.env.DEV) {
      console.debug('[FeedbackFab] open modal', {
        selectedResourceId,
        latestResultAction,
        latestResultStatus,
      });
    }
    onOpenModal();
    setIsOpen(true);
  }, [onOpenModal, selectedResourceId, latestResultAction, latestResultStatus]);

  const close = useCallback(() => setIsOpen(false), []);

  return (
    <>
      <button
        type="button"
        className={`feedback-fab${emphasizePulse ? ' feedback-fab-pulse' : ''}`}
        onClick={open}
        aria-label="Send Feedback"
        title={emphasizePulse ? 'Report an issue' : 'Send Feedback'}
      >
        <span className="feedback-fab-icon" aria-hidden>
          <MessageIcon />
        </span>
        <span className="feedback-fab-label">Send Feedback</span>
      </button>
      <FeedbackModal isOpen={isOpen} onClose={close} githubNewIssueUrl={githubNewIssueUrl} />
    </>
  );
};

export default FeedbackFab;
