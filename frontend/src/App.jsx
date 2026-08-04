import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth.jsx';
import IntakeForm from './components/IntakeForm.jsx';
import ResultView from './components/ResultView.jsx';
import Login from './pages/Login.jsx';
import Register from './pages/Register.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import { submitClaim } from './services/claimsService';
import './styles/app.css';

function IntakePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handleSubmit(intake, recordFile, deidentifiedText, tokenMap) {
    setLoading(true);
    setError(null);
    try {
      const result = await submitClaim(intake, recordFile, deidentifiedText, tokenMap);
      navigate('/results', { state: { result } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return <IntakeForm onSubmit={handleSubmit} loading={loading} error={error} />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<ProtectedRoute><IntakePage /></ProtectedRoute>} />
          <Route path="/results" element={<ProtectedRoute><ResultView /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}