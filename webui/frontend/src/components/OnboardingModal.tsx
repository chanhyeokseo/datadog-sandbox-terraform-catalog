import { useState } from 'react';
import { OnboardingStatus } from '../services/api';

interface OnboardingModalProps {
  status: OnboardingStatus;
  onClose: () => void;
  onSelectShared: () => void;
}

function OnboardingModal({ status, onClose, onSelectShared }: OnboardingModalProps) {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const handleClose = () => {
    if (dontShowAgain) {
      localStorage.setItem('onboarding_dismissed', 'true');
    }
    onClose();
  };

  const handleDeployShared = () => {
    if (dontShowAgain) {
      localStorage.setItem('onboarding_dismissed', 'true');
    }
    
    onSelectShared();
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="onboarding-modal" onClick={(e) => e.stopPropagation()}>
        <div className="onboarding-header">
          <h2>🚀 Welcome to Terraform WebUI</h2>
        </div>

        <div className="onboarding-content">
          <div className="onboarding-alert">
            <div className="alert-icon">⚠️</div>
            <div className="alert-message">
              <strong>Action Required:</strong> Shared resources must be deployed first
            </div>
          </div>

          <div className="onboarding-explanation">
            <h3>Why is this needed?</h3>
            <p>
              The <strong>shared</strong> resource contains the Security Group and other
              common infrastructure that all other resources depend on.
            </p>
            <p>
              Without it, other resources cannot be deployed.
            </p>
          </div>

          <div className="onboarding-steps">
            <h3>Quick Start Steps:</h3>
            <ol>
              {status.next_steps?.map((step, index) => (
                <li key={index}>{step}</li>
              )) || (
                <>
                  <li>Select <strong>shared</strong> resource from the list</li>
                  <li>Click <strong>PLAN</strong> to preview changes</li>
                  <li>Click <strong>APPLY</strong> to deploy shared resources</li>
                  <li>Wait for deployment to complete</li>
                  <li>You can then deploy other resources</li>
                </>
              )}
            </ol>
          </div>

          <div className="onboarding-note">
            <p>
              💡 <strong>Note:</strong> This only needs to be done once. After the shared
              resources are deployed, you can deploy any other resource in any order.
            </p>
          </div>
        </div>

        <div className="onboarding-footer">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span>Don't show this again</span>
          </label>

          <div className="onboarding-actions">
            <button onClick={handleClose} className="btn-secondary">
              Close
            </button>
            <button onClick={handleDeployShared} className="btn-primary">
              Deploy Shared Resources
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingModal;
