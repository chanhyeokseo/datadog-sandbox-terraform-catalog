import { useState, useEffect, useCallback, useRef } from 'react';
import '../styles/Tutorial.css';

export interface TutorialStep {
  target: string;
  title: string;
  description: string;
  placement: 'top' | 'bottom' | 'left' | 'right';
  advanceOn?: 'click' | 'action-complete';
  waitForSelector?: string;
}

interface TutorialProps {
  steps: TutorialStep[];
  isActive: boolean;
  actionCompleted?: string;
  onComplete: () => void;
  onSkip: () => void;
}

interface SpotlightRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const TOOLTIP_WIDTH = 340;
const GAP = 16;
const MARGIN = 12;

function Tutorial({ steps, isActive, actionCompleted, onComplete, onSkip }: TutorialProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [spotlightRect, setSpotlightRect] = useState<SpotlightRect | null>(null);
  const prevActionRef = useRef<string | undefined>(undefined);
  const rafRef = useRef<number>(0);
  const scrolledRef = useRef(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number } | null>(null);
  const [waitingForAction, setWaitingForAction] = useState(false);

  const step = steps[currentStep];

  const advance = useCallback(() => {
    setCurrentStep(prev => {
      const next = prev + 1;
      if (next >= steps.length) {
        onComplete();
        return prev;
      }
      return next;
    });
  }, [steps.length, onComplete]);

  useEffect(() => {
    scrolledRef.current = false;
    setTooltipPos(null);
    setWaitingForAction(false);
  }, [currentStep]);

  const measureTarget = useCallback(() => {
    if (!step) return;
    const selector = step.waitForSelector || step.target;
    const el = document.querySelector(selector);
    if (!el) {
      const resourceMatch = step.target.match(/resource-(\w+)/);
      if (resourceMatch) {
        const resourceId = resourceMatch[1];
        const typeMap: Record<string, string> = {
          security_group: 'security_group',
          ec2_basic: 'ec2',
        };
        const sectionType = typeMap[resourceId] || resourceId.split('_')[0];
        const header = document.querySelector(`[data-tutorial-section="${sectionType}"]`) as HTMLElement | null;
        if (header) header.click();
      }
      setSpotlightRect(null);
      setTooltipPos(null);
      return;
    }

    if (!scrolledRef.current) {
      scrolledRef.current = true;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) {
      setSpotlightRect(null);
      return;
    }
    const pad = 6;
    const sr: SpotlightRect = {
      top: rect.top - pad,
      left: rect.left - pad,
      width: rect.width + pad * 2,
      height: rect.height + pad * 2,
    };
    setSpotlightRect(sr);

    const tip = tooltipRef.current;
    if (!tip) return;
    const tipRect = tip.getBoundingClientRect();
    const tipH = tipRect.height;
    const tipW = tipRect.width || TOOLTIP_WIDTH;
    const vh = window.innerHeight;
    const vw = window.innerWidth;

    let top: number;
    let left: number;

    const placement = step.placement;
    if (placement === 'right' || placement === 'left') {
      top = sr.top;
      left = placement === 'right'
        ? sr.left + sr.width + GAP
        : sr.left - tipW - GAP;

      if (left + tipW > vw - MARGIN) left = sr.left - tipW - GAP;
      if (left < MARGIN) left = sr.left + sr.width + GAP;
    } else if (placement === 'top') {
      top = sr.top - GAP - tipH;
      left = sr.left;
      if (top < MARGIN) top = sr.top + sr.height + GAP;
    } else {
      top = sr.top + sr.height + GAP;
      left = sr.left;
      if (top + tipH > vh - MARGIN) top = sr.top - GAP - tipH;
    }

    if (top + tipH > vh - MARGIN) top = vh - MARGIN - tipH;
    if (top < MARGIN) top = MARGIN;
    if (left + tipW > vw - MARGIN) left = vw - MARGIN - tipW;
    if (left < MARGIN) left = MARGIN;

    setTooltipPos({ top, left });
  }, [step]);

  useEffect(() => {
    if (!isActive || !step) return;
    const tick = () => {
      measureTarget();
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [isActive, step, measureTarget]);

  const handleClickTarget = useCallback(() => {
    if (!step) return;
    const el = document.querySelector(step.target) as HTMLElement | null;
    if (!el) return;
    el.click();
    if (step.advanceOn === 'click') {
      setTimeout(advance, 150);
    }
    if (step.advanceOn === 'action-complete') {
      setWaitingForAction(true);
    }
  }, [step, advance]);

  useEffect(() => {
    if (!isActive || !step || step.advanceOn !== 'action-complete') return;
    if (actionCompleted && actionCompleted !== prevActionRef.current) {
      prevActionRef.current = actionCompleted;
      advance();
    }
  }, [actionCompleted, isActive, step, advance]);

  useEffect(() => {
    prevActionRef.current = actionCompleted;
  }, [actionCompleted]);

  useEffect(() => {
    if (!isActive) {
      setCurrentStep(0);
      setSpotlightRect(null);
      setTooltipPos(null);
      setWaitingForAction(false);
      scrolledRef.current = false;
    }
  }, [isActive]);

  if (!isActive || !step) return null;
  if (waitingForAction) return null;

  const isCentered = !spotlightRect;
  const tooltipClass = `tutorial-tooltip${isCentered ? ' tutorial-tooltip-centered' : ''}`;
  const tooltipStyle: React.CSSProperties = isCentered
    ? { maxWidth: 400 }
    : tooltipPos
      ? { top: tooltipPos.top, left: tooltipPos.left, maxWidth: TOOLTIP_WIDTH }
      : { top: -9999, left: -9999, maxWidth: TOOLTIP_WIDTH };

  const isObservationStep = step.advanceOn === 'action-complete' && step.target.includes('results-panel');
  const allowClick = !!spotlightRect && !isObservationStep && (step.advanceOn === 'click' || step.advanceOn === 'action-complete');

  return (
    <div className="tutorial-overlay">
      {spotlightRect && (
        <div
          className="tutorial-spotlight"
          style={{
            top: spotlightRect.top,
            left: spotlightRect.left,
            width: spotlightRect.width,
            height: spotlightRect.height,
          }}
        />
      )}
      {spotlightRect && allowClick && (
        <div
          className="tutorial-click-target"
          style={{
            top: spotlightRect.top,
            left: spotlightRect.left,
            width: spotlightRect.width,
            height: spotlightRect.height,
          }}
          onClick={handleClickTarget}
        />
      )}
      {!spotlightRect && <div className="tutorial-overlay-dim" />}

      <div ref={tooltipRef} className={tooltipClass} style={tooltipStyle}>
        <div className="tutorial-tooltip-header">
          <span className="tutorial-step-badge">
            {currentStep + 1} / {steps.length}
          </span>
          <button className="tutorial-btn-skip" onClick={onSkip}>
            Skip Tutorial
          </button>
        </div>
        <h3 className="tutorial-tooltip-title">{step.title}</h3>
        <p className="tutorial-tooltip-desc">{step.description}</p>
        {!spotlightRect && (
          <p className="tutorial-tooltip-hint">
            Searching for: {step.target}
          </p>
        )}
        {spotlightRect && !step.advanceOn && (
          <div className="tutorial-tooltip-actions">
            <button className="tutorial-btn-next" onClick={advance}>
              {currentStep >= steps.length - 1 ? 'Finish' : 'Next'}
            </button>
          </div>
        )}
        {spotlightRect && step.advanceOn === 'action-complete' && (
          <p className="tutorial-tooltip-hint">Waiting for action to complete...</p>
        )}
      </div>
    </div>
  );
}

export default Tutorial;
