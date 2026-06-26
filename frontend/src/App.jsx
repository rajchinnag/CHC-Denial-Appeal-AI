import React, { useState } from 'react'
import IntakeForm from './components/IntakeForm.jsx'
import ResultView from './components/ResultView.jsx'
import './styles/app.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(intake, recordFile) {
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('intake_json', JSON.stringify(intake))
      if (recordFile) formData.append('medical_record', recordFile)

      const res = await fetch(`${API_BASE}/api/claims/submit`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Request failed (${res.status})`)
      }

      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message || 'Something went wrong submitting this claim.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-header-mark">CHC</div>
        <div>
          <h1>Denial Appeal AI</h1>
          <p>Coding &middot; Medical necessity &middot; Authorization &middot; Bill type</p>
        </div>
      </header>

      <main className="shell-main">
        {!result && (
          <IntakeForm onSubmit={handleSubmit} loading={loading} error={error} />
        )}
        {result && (
          <ResultView result={result} onReset={() => setResult(null)} />
        )}
      </main>
    </div>
  )
}
