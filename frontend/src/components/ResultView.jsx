import React, { useState } from 'react'

export default function ResultView({ result, onReset }) {
  const [copied, setCopied] = useState(false)
  const { classification, denial_valid, policy_findings, letter, reasoning_summary } = result

  function copyLetter() {
    navigator.clipboard.writeText(letter)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="result">
      <div className="result-top">
        <div className={`stamp ${denial_valid ? 'stamp-valid' : 'stamp-invalid'}`}>
          {denial_valid ? 'DENIAL UPHELD' : 'DENIAL OVERTURNABLE'}
        </div>
        <div className="result-meta">
          <div><span className="meta-label">Category</span> {classification.category.replace('_', ' ')}</div>
          {classification.carc_description && (
            <div><span className="meta-label">CARC</span> {classification.carc_description}</div>
          )}
        </div>
      </div>

      <section className="ledger-section">
        <h2>Reasoning</h2>
        <p>{reasoning_summary}</p>
      </section>

      {policy_findings && policy_findings.length > 0 && (
        <section className="ledger-section">
          <h2>Policy Findings</h2>
          <ul className="policy-list">
            {policy_findings.map((f, i) => (
              <li key={i}>
                <div className="policy-name">{f.policy_name}</div>
                <p>{f.summary}</p>
                {f.source_url && <a href={f.source_url} target="_blank" rel="noreferrer">{f.source_url}</a>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="ledger-section">
        <div className="letter-header">
          <h2>{denial_valid ? 'Reconsideration Letter' : 'Appeal Letter'}</h2>
          <button type="button" className="btn-ghost-sm" onClick={copyLetter}>
            {copied ? 'Copied' : 'Copy letter'}
          </button>
        </div>
        <pre className="letter-body">{letter}</pre>
      </section>

      <div className="ledger-actions">
        <button type="button" className="btn-primary" onClick={onReset}>Start a new claim</button>
      </div>
    </div>
  )
}
