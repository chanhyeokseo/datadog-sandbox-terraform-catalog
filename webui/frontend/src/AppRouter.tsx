import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App';
import Terminal from './components/Terminal';
import OnboardingPage from './components/OnboardingPage';

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/" element={<App />} />
        <Route path="/terminal/:connectionId" element={<Terminal />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRouter;
