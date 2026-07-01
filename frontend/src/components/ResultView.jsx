import React, { useState, useRef } from 'react'

function LetterBlock({ title, letter, printId }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(letter)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  function printLetter() {
    const win = window.open('', '_blank')
    win.document.write(`
      <html><head><title>${title}</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 13px; line-height: 1.6; padding: 40px; color: #1a1a1a; }
        pre { white-space: pre-wrap; font-family: Arial, sans-serif; font-size: 13px; }
        h1 { font-size: 16px; border-bottom: 1px solid #ccc; padding-bottom: 8px; margin-bottom: 20px; }
      </style></head>
      <body>
        <h1>${title}</h1>
        <pre>${letter.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
      </body></html>
    `)
    win.document.close()
    win.focus()
    setTimeout(() => { win.print(); win.close(); }, 500)
  }

  return (
    <div className="letter-block">
      <div className="letter-header">
        <h2>{title}</h2>
        <div className="letter-actions">
          <button type="button" className="btn-ghost-sm" onClick={copy}>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" className="btn-ghost-sm" onClick={printLetter}>
            Print / PDF
          </button>
        </div>
      </div>
      <pre className="letter-body" id={printId}>{letter}</pre>
    </div>
  )
}

function PhiReportSection({ report }) {
  const [expanded, setExpanded] = useState(false)

  if (!report || report.total_entities === 0) {
    return (
      <section className="ledger-section">
        <h2>PHI Detection Report</h2>
        <div className="phi-safe-banner">
          ✓ No PHI identifiers detected in uploaded record. Text sent to AI as-is.
        </div>
      </section>
    )
  }

  const typeLabels = {
    PATIENT_NAME: 'Patient Names',
    PROVIDER_NAME: 'Provider Names',
    FACILITY_NAME: 'Facility Names',
    DOB: 'Dates of Birth',
    DATE: 'Dates',
    SSN: 'Social Security Numbers',
    MRN: 'Medical Record Numbers',
    PHONE: 'Phone Numbers',
    FAX: 'Fax Numbers',
    EMAIL: 'Email Addresses',
    ADDRESS: 'Addresses',
    ZIP: 'ZIP Codes',
    AGE: 'Ages (90+)',
    PROVIDER_NPI: 'NPI Numbers',
    ACCOUNT_NUMBER: 'Account Numbers',
    INSURANCE_ID: 'Insurance IDs',
    URL: 'URLs / IP Addresses',
    DEVICE_ID: 'Device Identifiers',
    CERT_NUMBER: 'Certificate Numbers',
  }

  return (
    <section className="ledger-section">
      <h2>PHI Detection Report</h2>
      <div className="phi-report-banner">
        <span className="phi-shield">🔒</span>
        <div>
          <div className="phi-report-title">
            {report.total_entities} PHI identifier{report.total_entities !== 1 ? 's' : ''} detected and removed
          </div>
          <div className="phi-report-sub">{report.summary}</div>
        </div>
        <button
          type="button"
          className="btn-ghost-sm"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Hide details' : 'View details'}
        </button>
      </div>

      {expanded && (
        <div className="phi-details">
          {Object.entries(report.by_type).map(([type, values]) => (
            <div key={type} className="phi-type-block">
              <div className="phi-type-label">
                {typeLabels[type] || type} ({values.length})
              </div>
              <div className="phi-values">
                {values.map((v, i) => (
                  <span key={i} className="phi-value-tag">
                    {v} <span className="phi-arrow">→</span>
                    <span className="phi-token">[{type}_{i + 1}]</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function MNSection({ mn }) {
  const { training_status, logic_path, policy, record, corrected_claim } = mn

  const logicLabels = {
    policy_supports_reprocess: { label: 'Policy Supports — Reprocess Path', color: 'teal' },
    record_supports_corrected_claim: { label: 'Record Supports — Corrected Claim Path', color: 'amber' },
    record_supports_appeal_only: { label: 'Record Supports — Appeal Path', color: 'amber' },
    no_support_appeal_only: { label: 'No Policy/Record Support — Appeal Only', color: 'rust' },
  }
  const pathInfo = logicLabels[logic_path] || { label: logic_path, color: 'teal' }

  return (
    <>
      {training_status === 'general_mn_logic' && (
        <div className="training-banner">
          ⚠ Running general medical necessity logic — scenario-specific training pending for this denial code.
        </div>
      )}

      <section className="ledger-section">
        <h2>Medical Necessity Analysis</h2>
        <div className={`logic-path-badge logic-path-${pathInfo.color}`}>
          {pathInfo.label}
        </div>

        <div className="mn-grid">
          <div className="mn-card">
            <div className="mn-card-title">CMS Policy (LCD/NCD)</div>
            {policy.cms_policy_name ? (
              <>
                <div className="mn-card-status">
                  <span className={`badge badge-${policy.cms_supports ? 'add' : 'remove'}`}>
                    {policy.cms_supports ? 'SUPPORTS' : 'CONTRADICTS'}
                  </span>
                </div>
                <div className="mn-policy-name">
                  {policy.cms_policy_name} {policy.cms_policy_number && `(${policy.cms_policy_number})`}
                </div>
                <p className="mn-policy-summary">{policy.cms_policy_summary}</p>
              </>
            ) : (
              <p className="mn-none">No specific CMS LCD/NCD identified</p>
            )}
          </div>

          <div className="mn-card">
            <div className="mn-card-title">Payer Policy</div>
            {policy.payer_policy_name ? (
              <>
                <div className="mn-card-status">
                  <span className={`badge badge-${policy.payer_supports ? 'add' : 'remove'}`}>
                    {policy.payer_supports ? 'SUPPORTS' : 'CONTRADICTS'}
                  </span>
                </div>
                <div className="mn-policy-name">
                  {policy.payer_policy_name} {policy.payer_policy_number && `(${policy.payer_policy_number})`}
                </div>
                <p className="mn-policy-summary">{policy.payer_policy_summary}</p>
              </>
            ) : (
              <p className="mn-none">No specific payer policy identified</p>
            )}
          </div>
        </div>

        {policy.policy_reasoning && (
          <p className="mn-reasoning">{policy.policy_reasoning}</p>
        )}

        {policy.required_conditions && policy.required_conditions.length > 0 && (
          <div className="mn-conditions">
            <div className="mn-conditions-title">Required Conditions for Medical Necessity</div>
            <ul>{policy.required_conditions.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </div>
        )}

        {policy.missing_conditions && policy.missing_conditions.length > 0 && (
          <div className="mn-conditions mn-conditions-missing">
            <div className="mn-conditions-title">Missing from Claim as Submitted</div>
            <ul>{policy.missing_conditions.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </div>
        )}
      </section>

      <section className="ledger-section">
        <h2>Medical Record Analysis</h2>
        <div className="mn-record-status">
          <span className={`badge badge-${record.record_supports_mn ? 'add' : 'remove'}`}>
            {record.record_supports_mn ? 'RECORD SUPPORTS MN' : 'RECORD INSUFFICIENT'}
          </span>
        </div>
        <p className="mn-reasoning">{record.record_summary}</p>

        {record.documented_conditions && record.documented_conditions.length > 0 && (
          <div className="mn-conditions">
            <div className="mn-conditions-title">Documented Conditions Supporting Medical Necessity</div>
            <ul>{record.documented_conditions.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </div>
        )}

        {record.missing_documentation && record.missing_documentation.length > 0 && (
          <div className="mn-conditions mn-conditions-missing">
            <div className="mn-conditions-title">Missing or Insufficient Documentation</div>
            <ul>{record.missing_documentation.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </div>
        )}
      </section>

      {corrected_claim && corrected_claim.has_corrections && (
        <section className="ledger-section">
          <h2>Corrected Claim Suggestions</h2>
          {corrected_claim.cpt_changes.length > 0 && (
            <div className="coding-block">
              <h3>CPT / HCPCS Changes</h3>
              <table className="coding-table">
                <thead><tr><th>Current</th><th>Suggested</th><th>Reason</th></tr></thead>
                <tbody>
                  {corrected_claim.cpt_changes.map((c, i) => (
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
          {corrected_claim.dx_changes.length > 0 && (
            <div className="coding-block">
              <h3>Diagnosis Code Changes</h3>
              <table className="coding-table">
                <thead><tr><th>Action</th><th>Code</th><th>Description</th><th>Reason</th></tr></thead>
                <tbody>
                  {corrected_claim.dx_changes.map((d, i) => (
                    <tr key={i}>
                      <td><span className={`badge badge-${d.action}`}>{d.action && d.action.toUpperCase()}</span></td>
                      <td><code>{d.code}</code></td>
                      <td>{d.description}</td>
                      <td>{d.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {corrected_claim.modifier_changes.length > 0 && (
            <div className="coding-block">
              <h3>Modifier Changes</h3>
              <table className="coding-table">
                <thead><tr><th>Action</th><th>Modifier</th><th>Reason</th></tr></thead>
                <tbody>
                  {corrected_claim.modifier_changes.map((m, i) => (
                    <tr key={i}>
                      <td><span className={`badge badge-${m.action}`}>{m.action && m.action.toUpperCase()}</span></td>
                      <td><code>{m.modifier}</code></td>
                      <td>{m.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {corrected_claim.revenue_code_changes.length > 0 && (
            <div className="coding-block">
              <h3>Revenue Code Changes</h3>
              <table className="coding-table">
                <thead><tr><th>Current</th><th>Suggested</th><th>Reason</th></tr></thead>
                <tbody>
                  {corrected_claim.revenue_code_changes.map((r, i) => (
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
        </section>
      )}
    </>
  )
}

export default function ResultView({ result, onReset }) {
  const [copied, setCopied] = useState(false)
  const {
    classification, denial_valid, policy_findings, letter,
    reasoning_summary, coding_recommendations, medical_necessity, phi_report
  } = result

  const isMN = !!medical_necessity
  const hasCoding = coding_recommendations && coding_recommendations.has_recommendations

  function copyLetter() {
    navigator.clipboard.writeText(letter)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  function printLetter() {
    const win = window.open('', '_blank')
    win.document.write(`
      <html><head><title>${denial_valid ? 'Reconsideration Letter' : 'Appeal Letter'}</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 13px; line-height: 1.6; padding: 40px; }
        pre { white-space: pre-wrap; font-family: Arial, sans-serif; font-size: 13px; }
        h1 { font-size: 16px; border-bottom: 1px solid #ccc; padding-bottom: 8px; }
      </style></head>
      <body>
        <h1>${denial_valid ? 'Reconsideration Letter' : 'Appeal Letter'}</h1>
        <pre>${letter.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
      </body></html>
    `)
    win.document.close()
    win.focus()
    setTimeout(() => { win.print(); win.close(); }, 500)
  }

  return (
    <div className="result">

      {/* Stamp + meta */}
      <div className="result-top">
        <div className={`stamp ${denial_valid ? 'stamp-valid' : 'stamp-invalid'}`}>
          {denial_valid ? 'DENIAL UPHELD' : 'DENIAL OVERTURNABLE'}
        </div>
        <div className="result-meta">
          <div><span className="meta-label">Category</span> {classification.category.replace(/_/g, ' ')}</div>
          {classification.carc_description && (
            <div><span className="meta-label">CARC</span> {classification.carc_description}</div>
          )}
          {isMN && (
            <div><span className="meta-label">Scenario</span> Medical Necessity</div>
          )}
        </div>
      </div>

      {/* PHI Report — always first after stamp */}
      <PhiReportSection report={phi_report} />

      {/* Reasoning */}
      <section className="ledger-section">
        <h2>Reasoning</h2>
        <p>{reasoning_summary}</p>
      </section>

      {/* Policy findings */}
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

      {/* MN section */}
      {isMN && <MNSection mn={medical_necessity} />}

      {/* Standard coding recommendations */}
      {hasCoding && !isMN && (
        <section className="ledger-section">
          <h2>Corrected Claim Recommendations</h2>
          <p style={{ marginBottom: '1rem', color: 'var(--text-muted, #555)' }}>
            {coding_recommendations.summary}
          </p>
          {coding_recommendations.cpt_changes.length > 0 && (
            <div className="coding-block">
              <h3>CPT / HCPCS Changes</h3>
              <table className="coding-table">
                <thead><tr><th>Current</th><th>Suggested</th><th>Reason</th></tr></thead>
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
                <thead><tr><th>Action</th><th>Code</th><th>Description</th><th>Reason</th></tr></thead>
                <tbody>
                  {coding_recommendations.dx_changes.map((d, i) => (
                    <tr key={i}>
                      <td><span className={`badge badge-${d.action}`}>{d.action && d.action.toUpperCase()}</span></td>
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
                <thead><tr><th>Action</th><th>Modifier</th><th>Reason</th></tr></thead>
                <tbody>
                  {coding_recommendations.modifier_changes.map((m, i) => (
                    <tr key={i}>
                      <td><span className={`badge badge-${m.action}`}>{m.action && m.action.toUpperCase()}</span></td>
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
                <thead><tr><th>Current</th><th>Suggested</th><th>Reason</th></tr></thead>
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

      {/* Letters */}
      {isMN ? (
        <>
          <section className="ledger-section">
            <LetterBlock
              title="Reprocess Request Letter"
              letter={medical_necessity.reprocess_letter}
              printId="reprocess-letter-body"
            />
          </section>
          <section className="ledger-section">
            <LetterBlock
              title="Appeal Letter (Backup)"
              letter={medical_necessity.appeal_letter}
              printId="appeal-letter-body"
            />
          </section>
        </>
      ) : (
        <section className="ledger-section">
          <div className="letter-header">
            <h2>{denial_valid ? 'Reconsideration Letter' : 'Appeal Letter'}</h2>
            <div className="letter-actions">
              <button type="button" className="btn-ghost-sm" onClick={copyLetter}>
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button type="button" className="btn-ghost-sm" onClick={printLetter}>
                Print / PDF
              </button>
            </div>
          </div>
          <pre className="letter-body">{letter}</pre>
        </section>
      )}

      <div className="ledger-actions">
        <button type="button" className="btn-primary" onClick={onReset}>Start a new claim</button>
      </div>
    </div>
  )
}
