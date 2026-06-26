import React, { useState } from 'react'

export default function ResultView({ result, onReset }) {
  const [copied, setCopied] = useState(false)
  const { classification, denial_valid, policy_findings, letter, reasoning_summary, coding_recommendations } = result

  function copyLetter() {
    navigator.clipboard.writeText(letter)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  const hasCoding = coding_recommendations && coding_recommendations.has_recommendations

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

      {hasCoding && (
        <section className="ledger-section">
          <h2>Corrected Claim Recommendations</h2>
          <p style={{ marginBottom: '1rem', color: 'var(--text-muted, #555)' }}>
            {coding_recommendations.summary}
          </p>

          {coding_recommendations.cpt_changes.length > 0 && (
            <div className="coding-block">
              <h3>CPT / HCPCS Changes</h3>
              <table className="coding-table">
                <thead>
                  <tr><th>Current</th><th>Suggested</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {coding_recommendations.cpt_changes.map((c, i) => (
                    <tr key={i}>
                      <td><code>{c.current}</code></td>
                      <td><code className="code-suggested">{c.suggested}</code></td>
                      <td>{c.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {coding_recommendations.dx_changes.length > 0 && (
            <div className="coding-block">
              <h3>Diagnosis Code Changes</h3>
              <table className="coding-table">
                <thead>
                  <tr><th>Action</th><th>Code</th><th>Description</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {coding_recommendations.dx_changes.map((d, i) => (
                    <tr key={i}>
                      <td><span className={`badge badge-${d.action}`}>{d.action.toUpperCase()}</span></td>
                      <td><code>{d.code}</code></td>
                      <td>{d.description}</td>
                      <td>{d.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {coding_recommendations.modifier_changes.length > 0 && (
            <div className="coding-block">
              <h3>Modifier Changes</h3>
              <table className="coding-table">
                <thead>
                  <tr><th>Action</th><th>Modifier</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {coding_recommendations.modifier_changes.map((m, i) => (
                    <tr key={i}>
                      <td><span className={`badge badge-${m.action}`}>{m.action.toUpperCase()}</span></td>
                      <td><code>{m.modifier}</code></td>
                      <td>{m.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {coding_recommendations.revenue_code_changes.length > 0 && (
            <div className="coding-block">
              <h3>Revenue Code Changes</h3>
              <table className="coding-table">
                <thead>
                  <tr><th>Current</th><th>Suggested</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {coding_recommendations.revenue_code_changes.map((r, i) => (
                    <tr key={i}>
                      <td><code>{r.current}</code></td>
                      <td><code className="code-suggested">{r.suggested}</code></td>
                      <td>{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {coding_recommendations.other_recommendations.length > 0 && (
            <div className="coding-block">
              <h3>Other Recommendations</h3>
              <ul className="policy-list">
                {coding_recommendations.other_recommendations.map((o, i) => (
                  <li key={i}>
                    <div className="policy-name">{o.recommendation}</div>
                    <p>{o.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
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
