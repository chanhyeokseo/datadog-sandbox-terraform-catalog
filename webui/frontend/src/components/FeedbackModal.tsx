import { useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';

const GITHUB_REPO_ISSUES = 'https://github.com/chanhyeokseo/dogstac/issues';
const FEEDBACK_EMAIL = 'chanhyeok.seo@datadoghq.com';

export interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  githubNewIssueUrl: string;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

const FeedbackModal = ({ isOpen, onClose, githubNewIssueUrl }: FeedbackModalProps) => {
  const panelRef = useRef<HTMLDivElement>(null);

  const getFocusable = useCallback(() => {
    const root = panelRef.current;
    if (!root) return [] as HTMLElement[];
    return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    if (import.meta.env.DEV) {
      console.debug('[FeedbackModal] open', { githubNewIssueUrlLength: githubNewIssueUrl.length });
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const list = getFocusable();
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first || !panelRef.current?.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    const t = window.setTimeout(() => getFocusable()[0]?.focus(), 0);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener('keydown', onKeyDown);
      if (import.meta.env.DEV) console.debug('[FeedbackModal] close');
    };
  }, [isOpen, onClose, getFocusable, githubNewIssueUrl]);

  const onOverlayMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      className="feedback-modal-overlay"
      role="presentation"
      onMouseDown={onOverlayMouseDown}
    >
      <div
        ref={panelRef}
        className="feedback-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="feedback-modal-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="feedback-modal-header">
          <h2 id="feedback-modal-title" className="feedback-modal-title">
            Send Feedback
          </h2>
          <p className="feedback-modal-subtitle">
            Have feedback, bugs, or suggestions? We&apos;d love to hear from you.
          </p>
        </div>
        <div className="feedback-modal-body">
          <section className="feedback-modal-section" aria-label="GitHub">
            <p className="feedback-modal-section-label">Create an issue on GitHub:</p>
            <a
              href={githubNewIssueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="feedback-btn feedback-btn-primary"
            >
              Open GitHub Issues
            </a>
            <p className="feedback-modal-url-hint">{GITHUB_REPO_ISSUES}</p>
          </section>
          <section className="feedback-modal-section" aria-label="Direct contact">
            <p className="feedback-modal-section-label">Or contact directly:</p>
            <p className="feedback-modal-contact-row">
              <span className="feedback-modal-contact-key">Email:</span>{' '}
              <a className="feedback-modal-link" href={`mailto:${FEEDBACK_EMAIL}`}>
                {FEEDBACK_EMAIL}
              </a>
            </p>
            <p className="feedback-modal-contact-row">
              <span className="feedback-modal-contact-key">Slack:</span> Reach out via Slack.
            </p>
          </section>
        </div>
        <div className="feedback-modal-footer">
          <button type="button" className="feedback-btn feedback-btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
};

export default FeedbackModal;
