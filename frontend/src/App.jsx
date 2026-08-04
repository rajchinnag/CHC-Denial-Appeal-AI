import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import IntakeForm from './components/IntakeForm.jsx';
import ResultView from './components/ResultView.jsx';
import Login from './pages/Login.jsx';
import Register from './pages/Register.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import './styles/app.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<ProtectedRoute><IntakeForm /></ProtectedRoute>} />
        <Route path="/results" element={<ProtectedRoute><ResultView /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
