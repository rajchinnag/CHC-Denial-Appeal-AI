import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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
  const [result, setResult] = useState(null);

  async function handleSubmit(intake, recordFile, deidentifiedText, tokenMap) {
    setLoading(true);
    setError(null);
    try {
      const data = await submitClaim(intake, recordFile, deidentifiedText, tokenMap);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setResult(null);
    setError(null);
  }

  if (result) {
    return <ResultView result={result} onReset={handleReset} />;
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}