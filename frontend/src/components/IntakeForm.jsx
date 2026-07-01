import React, { useState } from 'react'

const VISIT_TYPES = ['Inpatient', 'Outpatient', 'Emergency Department', 'Office Visit', 'Ambulatory Surgery', 'Telehealth']
const SPECIALTY_DENIAL_CODES = ['B7']

function splitCodes(str) {
  return str.split(',').map(s => s.trim()).filter(Boolean)
}

const SECTIONS = [
  { key: 'claim', label: 'Claim & Denial' },
  { key: 'codes', label: 'Billed Codes' },
  { key: 'context', label: 'Visit Context' },
  { key: 'record', label: 'Medical Record' },
]

function PhiScanReport({ report, onConfirm, onRescan, scanning }) {
  const [expanded, setExpanded] = useState(false)

  const typeLabels = {
    PATIENT_NAME: 'Patient Names', PROVIDER_NAME: 'Provider Names',
    FACILITY_NAME: 'Facility Names', DOB: 'Dates of Birth', DATE: 'Dates',
    SSN: 'Social Security Numbers', MRN: 'Medical Record Numbers',
    PHONE: 'Phone Numbers', FAX: 'Fax Numbers', EMAIL: 'Email Addresses',
    ADDRESS: 'Addresses', ZIP: 'ZIP Codes', AGE: 'Ages (90+)',
    PROVIDER_NPI: 'NPI Numbers', ACCOUNT_NUMBER: 'Account Numbers',
    INSURANCE_ID: 'Insurance IDs', URL: 'URLs / IP Addresses',
    DEVICE_ID: 'Device Identifiers', CERT_NUMBER: 'Certificate Numbers',
  }

  return (
    <div className="phi-scan-result">
      <div className="phi-scan-header">
        <span className="phi-shield">🔒</span>
        <div className="phi-scan-info">
          <div className="phi-scan-title">
            PHI Scan Complete — {report.total_entities} identifier{report.total_entities !== 1 ? 's' : ''} detected and removed
          </div>
          <div className="phi-scan-sub">{report.summary}</div>
        </div>
      </div>

      <div className="phi-scan-actions">
        <button type="button" className="btn-ghost-sm" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Hide details' : 'Review what was redacted'}
        </button>
        <button type="button" className="btn-ghost-sm" onClick={onRescan}>
          Replace file
        </button>
      </div>

      {expanded && report.by_type && Object.keys(report.by_type).length > 0 && (
        <div className="phi-details">
          {Object.entries(report.by_type).map(([type, values]) => (
            <div key={type} className="phi-type-block">
              <div className="phi-type-label">{typeLabels[type] || type} ({values.length})</div>
              <div className="phi-values">
                {values.map((v, i) => (
                  <span key={i} className="phi-value-tag">
                    {v}
                    <span className="phi-arrow">→</span>
                    <span className="phi-token">[{type}_{i + 1}]</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {report.total_entities === 0 && (
        <div className="phi-none-found">
          ✓ No PHI identifiers detected. Record appears clean.
        </div>
      )}

      <div className="phi-confirm-bar">
        <div className="phi-confirm-note">
          ✓ All detected PHI has been replaced with tokens. Gemini will only see the redacted version.
        </div>
        <button type="button" className="btn-primary" onClick={onConfirm}>
          Confirm &amp; Proceed to Analysis →
        </button>
      </div>
    </div>
  )
}

export default function IntakeForm({ onSubmit, loading, error }) {
  const [activeSection, setActiveSection] = useState('claim')

  const [claimPayor, setClaimPayor] = useState('')
  const [denialCode, setDenialCode] = useState('')
  const [denialReasonCode, setDenialReasonCode] = useState('')
  const [billedCodes, setBilledCodes] = useState('')
  const [dxCodes, setDxCodes] = useState('')
  const [revenueCodes, setRevenueCodes] = useState('')
  const [conditionCodes, setConditionCodes] = useState('')
  const [occurrenceCodes, setOccurrenceCodes] = useState('')
  const [valueCodes, setValueCodes] = useState([{ code: '', amount: '' }])
  const [drgCode, setDrgCode] = useState('')
  const [typeOfBill, setTypeOfBill] = useState('')
  const [visitType, setVisitType] = useState('')
  const [specialtyType, setSpecialtyType] = useState('')
  const [taxonomyCode, setTaxonomyCode] = useState('')

  const [recordFile, setRecordFile] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState(null)
  const [phiReport, setPhiReport] = useState(null)
  const [deidentifiedText, setDeidentifiedText] = useState('')
  const [tokenMap, setTokenMap] = useState({})
  const [scanConfirmed, setScanConfirmed] = useState(false)

  const needsTaxonomy = SPECIALTY_DENIAL_CODES.includes(denialCode.trim().toUpperCase().replace('CO-', ''))

  function updateValueCode(idx, field, val) {
    setValueCodes(vc => vc.map((row, i) => i === idx ? { ...row, [field]: val } : row))
  }
  function addValueCodeRow() { setValueCodes(vc => [...vc, { code: '', amount: '' }]) }
  function removeValueCodeRow(idx) { setValueCodes(vc => vc.filter((_, i) => i !== idx)) }

  function handleFileChange(e) {
    const file = e.target.files[0] || null
    setRecordFile(file)
    setPhiReport(null)
    setDeidentifiedText('')
    setTokenMap({})
    setScanConfirmed(false)
    setScanError(null)
  }

  function handleRescan() {
    setRecordFile(null)
    setPhiReport(null)
    setDeidentifiedText('')
    setTokenMap({})
    setScanConfirmed(false)
    setScanError(null)
  }

  async function handleScan() {
    if (!recordFile) return
    setScanning(true)
    setScanError(null)
    try {
      const formData = new FormData()
      formData.append('medical_record', recordFile)
      const res = await fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/api/claims/scan`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Scan failed')
      }
      const data = await res.json()
      setPhiReport(data.phi_report)
      setDeidentifiedText(data.deidentified_text)
      setTokenMap(data.token_map)
    } catch (err) {
      setScanError(err.message)
    } finally {
      setScanning(false)
    }
  }

  function handleConfirm() {
    setScanConfirmed(true)
  }

  function handleSubmit(e) {
    e.preventDefault()
    const intake = {
      claim_payor: claimPayor,
      denial_code: denialCode,
      denial_reason_code: denialReasonCode || null,
      billed_codes: splitCodes(billedCodes),
      dx_codes: splitCodes(dxCodes),
      revenue_codes: splitCodes(revenueCodes),
      condition_codes: splitCodes(conditionCodes),
      occurrence_codes: splitCodes(occurrenceCodes),
      value_codes: valueCodes
        .filter(v => v.code && v.amount)
        .map(v => ({ code: v.code, amount: parseFloat(v.amount) })),
      drg_code: drgCode || null,
      type_of_bill: typeOfBill || null,
      visit_type: visitType || null,
      specialty_type: specialtyType || null,
      taxonomy_code: taxonomyCode || null,
    }
    onSubmit(intake, recordFile, deidentifiedText, tokenMap)
  }

  return (
    <div className="ledger">
      <nav className="ledger-rail" aria-label="Form sections">
        {SECTIONS.map((s, i) => (
          <button
            key={s.key}
            type="button"
            className={`rail-step ${activeSection === s.key ? 'is-active' : ''}`}
            onClick={() => setActiveSection(s.key)}
          >
            <span className="rail-step-index">{String(i + 1).padStart(2, '0')}</span>
            <span>{s.label}</span>
          </button>
        ))}
      </nav>

      <form className="ledger-form" onSubmit={handleSubmit}>

        {activeSection === 'claim' && (
          <section className="ledger-section">
            <h2>Claim &amp; Denial</h2>
            <div className="field">
              <label>Claim Payor</label>
              <input value={claimPayor} onChange={e => setClaimPayor(e.target.value)} placeholder="e.g. UnitedHealthcare" required />
            </div>
            <div className="field-row">
              <div className="field code-field">
                <label>Denial Code (CARC)</label>
                <input value={denialCode} onChange={e => setDenialCode(e.target.value)} placeholder="e.g. 50" required />
              </div>
              <div className="field code-field">
                <label>Denial Reason Code (RARC)</label>
                <input value={denialReasonCode} onChange={e => setDenialReasonCode(e.target.value)} placeholder="e.g. N115" />
              </div>
            </div>
          </section>
        )}

        {activeSection === 'codes' && (
          <section className="ledger-section">
            <h2>Billed Codes</h2>
            <div className="field code-field">
              <label>CPT / HCPCS Codes <span className="hint">comma-separated</span></label>
              <input value={billedCodes} onChange={e => setBilledCodes(e.target.value)} placeholder="99214, 93000" />
            </div>
            <div className="field code-field">
              <label>Dx Codes <span className="hint">comma-separated</span></label>
              <input value={dxCodes} onChange={e => setDxCodes(e.target.value)} placeholder="I10, E11.9" />
            </div>
            <div className="field-row">
              <div className="field code-field">
                <label>Revenue Codes <span className="hint">comma-separated</span></label>
                <input value={revenueCodes} onChange={e => setRevenueCodes(e.target.value)} placeholder="0450, 0250" />
              </div>
              <div className="field code-field">
                <label>DRG Code</label>
                <input value={drgCode} onChange={e => setDrgCode(e.target.value)} placeholder="e.g. 470" />
              </div>
            </div>
            <div className="field-row">
              <div className="field code-field">
                <label>Condition Codes <span className="hint">comma-separated</span></label>
                <input value={conditionCodes} onChange={e => setConditionCodes(e.target.value)} placeholder="A1, A2" />
              </div>
              <div className="field code-field">
                <label>Occurrence Codes <span className="hint">comma-separated</span></label>
                <input value={occurrenceCodes} onChange={e => setOccurrenceCodes(e.target.value)} placeholder="11, 24" />
              </div>
            </div>
            <div className="field">
              <label>Value Codes &amp; Amounts</label>
              {valueCodes.map((row, idx) => (
                <div className="value-code-row" key={idx}>
                  <input className="code-field" placeholder="Code" value={row.code} onChange={e => updateValueCode(idx, 'code', e.target.value)} />
                  <input className="code-field" placeholder="Amount" type="number" step="0.01" value={row.amount} onChange={e => updateValueCode(idx, 'amount', e.target.value)} />
                  {valueCodes.length > 1 && (
                    <button type="button" className="btn-ghost-sm" onClick={() => removeValueCodeRow(idx)}>Remove</button>
                  )}
                </div>
              ))}
              <button type="button" className="btn-ghost-sm" onClick={addValueCodeRow}>+ Add value code</button>
            </div>
          </section>
        )}

        {activeSection === 'context' && (
          <section className="ledger-section">
            <h2>Visit Context</h2>
            <div className="field-row">
              <div className="field code-field">
                <label>Type of Bill</label>
                <input value={typeOfBill} onChange={e => setTypeOfBill(e.target.value)} placeholder="e.g. 131" />
              </div>
              <div className="field">
                <label>Visit Type</label>
                <select value={visitType} onChange={e => setVisitType(e.target.value)}>
                  <option value="">Select&hellip;</option>
                  {VISIT_TYPES.map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
            </div>
            <div className="field">
              <label>Specialty Type</label>
              <input value={specialtyType} onChange={e => setSpecialtyType(e.target.value)} placeholder="e.g. Cardiology" />
            </div>
            {needsTaxonomy && (
              <div className="field taxonomy-field">
                <label>Taxonomy Code <span className="hint">required for specialty/NPI denials</span></label>
                <input value={taxonomyCode} onChange={e => setTaxonomyCode(e.target.value)} placeholder="e.g. 207RC0000X" required />
              </div>
            )}
          </section>
        )}

        {activeSection === 'record' && (
          <section className="ledger-section">
            <h2>Medical Record</h2>

            {!phiReport && (
              <>
                <p className="section-note">
                  Your record will be scanned locally for PHI before anything is sent to AI.
                  You will see exactly what was redacted and must confirm before analysis begins.
                </p>
                <div className="field">
                  <label>Upload Record (PDF, DOCX, or TXT)</label>
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileChange}
                  />
                </div>
                {recordFile && !phiReport && (
                  <div className="phi-scan-prompt">
                    <div className="phi-scan-filename">📄 {recordFile.name}</div>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={handleScan}
                      disabled={scanning}
                    >
                      {scanning ? 'Scanning for PHI…' : '🔍 Scan for PHI'}
                    </button>
                  </div>
                )}
                {scanError && <div className="alert-error">{scanError}</div>}
              </>
            )}

            {phiReport && !scanConfirmed && (
              <PhiScanReport
                report={phiReport}
                onConfirm={handleConfirm}
                onRescan={handleRescan}
                scanning={scanning}
              />
            )}

            {scanConfirmed && (
              <div className="phi-confirmed-banner">
                ✓ PHI scan confirmed — {phiReport.total_entities} identifier{phiReport.total_entities !== 1 ? 's' : ''} redacted.
                Gemini will only see the cleaned record.
                <button type="button" className="btn-ghost-sm" onClick={handleRescan} style={{ marginLeft: '12px' }}>
                  Replace file
                </button>
              </div>
            )}
          </section>
        )}

        {error && <div className="alert-error">{error}</div>}

        <div className="ledger-actions">
          {activeSection === 'record' && recordFile && !scanConfirmed ? (
            <span className="hint" style={{ fontSize: '13px', color: 'var(--ink-soft)' }}>
              Complete PHI scan and confirm before submitting
            </span>
          ) : (
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Processing claim…' : 'Generate appeal analysis'}
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
