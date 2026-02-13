import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import App from './App';
import Terminal from './components/Terminal';
import OnboardingPage from './components/OnboardingPage';

// Component to check onboarding status and redirect
function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkOnboardingStatus = async () => {
      try {
        const response = await fetch('/api/backend/onboarding/status');
        const data = await response.json();

        setLoading(false);

        // If onboarding is not complete and we're on main page, redirect to onboarding
        if (!data.onboarding_complete && window.location.pathname === '/') {
          navigate('/onboarding');
        }
        // If onboarding is complete and we're on onboarding page, redirect to main
        else if (data.onboarding_complete && window.location.pathname === '/onboarding') {
          navigate('/');
        }
      } catch (error) {
        console.error('Failed to check onboarding status:', error);
        // On error, allow access (fail open)
        setLoading(false);
      }
    };

    checkOnboardingStatus();
  }, [navigate]);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        background: '#1a1a1a',
        color: '#fff'
      }}>
        <div>Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}

function AppRouter() {
  return (
    <BrowserRouter>
      <OnboardingGuard>
        <Routes>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/" element={<App />} />
          <Route path="/terminal/:connectionId" element={<Terminal />} />
        </Routes>
      </OnboardingGuard>
    </BrowserRouter>
  );
}

export default AppRouter;
