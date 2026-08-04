import { tokens } from './authService';

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function submitClaim(intake, recordFile, deidentifiedText, tokenMap) {
  const formData = new FormData();
  formData.append('intake_json', JSON.stringify(intake));
  formData.append('deidentified_text', deidentifiedText || '');
  formData.append('token_map_json', JSON.stringify(tokenMap || {}));
  if (recordFile) {
    formData.append('medical_record', recordFile);
  }

  const token = tokens.getAccess();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}/api/claims/submit`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    let detail = 'Submission failed';
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch {}
    throw new Error(detail);
  }

  return res.json();
}