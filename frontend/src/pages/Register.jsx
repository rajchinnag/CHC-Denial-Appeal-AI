/**
 * CHC Pro AI — Registration Wizard (5 steps)
 * Fully wired to backend API. Design per design_guidelines.json.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import WizardStepper from '../components/WizardStepper';
import OTPInput      from '../components/OTPInput';
import SignatureCanvas from '../components/SignatureCanvas';
import * as auth from '../services/authService';
import { apiError } from '../services/authService';

const SPECIALTIES = [
  'internal_medicine','family_medicine','cardiology','orthopedics',
  'neurology','oncology','radiology','pathology','emergency_medicine',
  'general_surgery','psychiatry','obstetrics_gynecology','pediatrics',
  'urology','gastroenterology','pulmonology','nephrology','other',
];

const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID',
  'IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS',
  'MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK',
  'OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV',
  'WI','WY','DC',
];

// ── Shared styles ──────────────────────────────────────────────────────────
const font = "'IBM Plex Sans', sans-serif";
const navy = '#003F87';
const teal = '#0073CF';
const S = {
  wrap: { minHeight: '100vh', background: '#F8FAFC', fontFamily: font },
  card: { maxWidth: 560, margin: '0 auto', padding: '32px 24px 48px' },
  label: { display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 },
  input: {
    width: '100%', padding: '10px 12px', border: '1.5px solid #CBD5E1',
    borderRadius: 8, fontSize: 14, fontFamily: font, outline: 'none',
    color: '#0F172A', background: '#fff', boxSizing: 'border-box',
  },
  inputFocus: { borderColor: navy },
  btn: {
    width: '100%', padding: '12px', background: navy, color: '#fff',
    border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 600,
    cursor: 'pointer', fontFamily: font, marginTop: 8,
  },
  btnSecondary: {
    width: '100%', padding: '11px', background: 'transparent', color: navy,
    border: `1.5px solid ${navy}`, borderRadius: 8, fontSize: 14,
    fontWeight: 500, cursor: 'pointer', fontFamily: font, marginTop: 8,
  },
  error: {
    background: '#FEE2E2', border: '1px solid #FECACA', borderRadius: 8,
    padding: '10px 14px', color: '#991B1B', fontSize: 13, marginBottom: 12,
  },
  success: {
    background: '#D1FAE5', border: '1px solid #6EE7B7', borderRadius: 8,
    padding: '10px 14px', color: '#065F46', fontSize: 13, marginBottom: 12,
  },
  field: { marginBottom: 16 },
  h2: { fontSize: 22, fontWeight: 600, color: navy, marginBottom: 4, marginTop: 24 },
  sub: { fontSize: 13, color: '#64748B', marginBottom: 20 },
  check: { display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 12 },
};

export default function Register() {
  const navigate   = useNavigate();
  const [step,     setStep]    = useState(1);
  const [loading,  setLoading] = useState(false);
  const [error,    setError]   = useState('');
  const [session,  setSession] = useState('');

  // Step 1
  const [f1, setF1] = useState({
    first_name:'', last_name:'', email:'', phone:'',
    organization:'', provider_type:'individual',
    specialty:'', state:'',
  });

  // Step 2
  const [f2, setF2]     = useState({ npi:'', tax_id:'', entity_type:'1' });
  const [npiResult, setNpiResult] = useState(null);

  // Step 3
  const [otpCode,   setOtpCode]  = useState('');
  const [otpSent,   setOtpSent]  = useState(false);
  const [otpTimer,  setOtpTimer] = useState(0);

  // Step 4a
  const [f4a, setF4a] = useState({ password:'', confirm_password:'' });
  const [pwStrength, setPwStrength] = useState([]);

  // Step 4b
  const [qrUrl,   setQrUrl]   = useState('');
  const [manKey,  setManKey]  = useState('');
  const [totp,    setTotp]    = useState('');

  // Step 5
  const [f5, setF5] = useState({
    full_legal_name:'', agreed_to_terms:false,
    agreed_to_hipaa_baa:false, agreed_to_privacy:false,
    signature_data:'',
  });

  const go = (fn) => async () => {
    setError('');
    setLoading(true);
    try { await fn(); }
    catch (e) { setError(apiError(e)); }
    finally   { setLoading(false); }
  };

  // ── Step 1 submit ──────────────────────────────────────────
  const submitStep1 = go(async () => {
    const d = await auth.registerStep1(f1);
    setSession(d.session_token);
    setStep(2);
  });

  // ── Step 2 submit ──────────────────────────────────────────
  const submitStep2 = go(async () => {
    const d = await auth.verifyNPI(session, f2.npi, f2.tax_id, f2.entity_type);
    setNpiResult(d);
    setStep(3);
    // Auto-send OTP on entering step 3
    const otp = await auth.sendOTP(session, 'email');
    setOtpSent(true);
    startTimer(otp.expires_in);
  });

  // ── Step 3 OTP ─────────────────────────────────────────────
  function startTimer(secs) {
    setOtpTimer(secs);
    const iv = setInterval(() => {
      setOtpTimer(t => { if (t <= 1) { clearInterval(iv); return 0; } return t - 1; });
    }, 1000);
  }

  const resendOTP = go(async () => {
    const d = await auth.sendOTP(session, 'email');
    setOtpSent(true);
    setOtpCode('');
    startTimer(d.expires_in);
  });

  const submitStep3 = go(async () => {
    await auth.verifyOTP(session, otpCode);
    setStep(4);
  });

  // ── Step 4a password ───────────────────────────────────────
  function checkStrength(pwd) {
    return [
      { ok: pwd.length >= 12,           label: '12+ characters' },
      { ok: /[A-Z]/.test(pwd),          label: 'Uppercase letter' },
      { ok: /[a-z]/.test(pwd),          label: 'Lowercase letter' },
      { ok: /\d/.test(pwd),             label: 'Number' },
      { ok: /[^A-Za-z0-9]/.test(pwd),   label: 'Special character' },
    ];
  }

  const submitStep4a = go(async () => {
    await auth.setPassword(session, f4a.password, f4a.confirm_password);
    // Get QR code
    const d = await auth.setup2FA(session);
    setQrUrl(d.qr_code_url);
    setManKey(d.manual_key);
    setStep(5); // Sub-step 4b
  });

  // ── Step 4b TOTP ───────────────────────────────────────────
  const submitStep4b = go(async () => {
    await auth.verify2FA(session, totp);
    setStep(6); // Step 5 (e-signature)
  });

  // ── Step 5 e-sig ───────────────────────────────────────────
  const submitStep5 = go(async () => {
    await auth.submitSignature({ session_token: session, ...f5 });
    navigate('/login?registered=1');
  });

  // ── Visual step mapping ────────────────────────────────────
  const wizardStep = step <= 2 ? step : step <= 3 ? 3 : step <= 5 ? 4 : 5;

  // ── Render ─────────────────────────────────────────────────
  return (
    <div style={S.wrap}>
      <WizardStepper currentStep={wizardStep} />
      <div style={S.card}>
        {error && <div style={S.error} data-testid="reg-error">{error}</div>}

        {/* ── STEP 1: Basic info ── */}
        {step === 1 && (
          <div data-testid="step-1">
            <h2 style={S.h2}>Create your account</h2>
            <p style={S.sub}>Enter your details to get started.</p>

            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
              <div style={S.field}>
                <label style={S.label}>First name *</label>
                <input data-testid="first-name" style={S.input} value={f1.first_name}
                  onChange={e=>setF1({...f1,first_name:e.target.value})} />
              </div>
              <div style={S.field}>
                <label style={S.label}>Last name *</label>
                <input data-testid="last-name" style={S.input} value={f1.last_name}
                  onChange={e=>setF1({...f1,last_name:e.target.value})} />
              </div>
            </div>

            <div style={S.field}>
              <label style={S.label}>Email address *</label>
              <input data-testid="email" type="email" style={S.input} value={f1.email}
                onChange={e=>setF1({...f1,email:e.target.value})} />
            </div>

            <div style={S.field}>
              <label style={S.label}>Phone number (10 digits, US) *</label>
              <input data-testid="phone" type="tel" style={S.input} value={f1.phone}
                onChange={e=>setF1({...f1,phone:e.target.value})} placeholder="5551234567" />
            </div>

            <div style={S.field}>
              <label style={S.label}>Organization (optional)</label>
              <input data-testid="organization" style={S.input} value={f1.organization}
                onChange={e=>setF1({...f1,organization:e.target.value})} />
            </div>

            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
              <div style={S.field}>
                <label style={S.label}>Specialty *</label>
                <select data-testid="specialty" style={S.input} value={f1.specialty}
                  onChange={e=>setF1({...f1,specialty:e.target.value})}>
                  <option value="">Select…</option>
                  {SPECIALTIES.map(s=><option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
                </select>
              </div>
              <div style={S.field}>
                <label style={S.label}>Practice state *</label>
                <select data-testid="state" style={S.input} value={f1.state}
                  onChange={e=>setF1({...f1,state:e.target.value})}>
                  <option value="">Select…</option>
                  {US_STATES.map(s=><option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>

            <div style={S.field}>
              <label style={S.label}>Provider type *</label>
              <div style={{ display:'flex', gap:24 }}>
                {['individual','organization'].map(t=>(
                  <label key={t} style={{ display:'flex', gap:8, alignItems:'center', cursor:'pointer', fontSize:14 }}>
                    <input type="radio" name="provider_type" value={t}
                      checked={f1.provider_type===t}
                      onChange={()=>setF1({...f1,provider_type:t})}
                      data-testid={`provider-type-${t}`} />
                    {t.charAt(0).toUpperCase()+t.slice(1)}
                  </label>
                ))}
              </div>
            </div>

            <button style={S.btn} onClick={submitStep1} disabled={loading} data-testid="step1-next">
              {loading ? 'Please wait…' : 'Continue →'}
            </button>
            <div style={{ textAlign:'center', marginTop:16, fontSize:13, color:'#64748B' }}>
              Already have an account?{' '}
              <a href="/login" style={{ color:teal }}>Sign in</a>
            </div>
          </div>
        )}

        {/* ── STEP 2: NPI ── */}
        {step === 2 && (
          <div data-testid="step-2">
            <h2 style={S.h2}>Verify your NPI</h2>
            <p style={S.sub}>Your National Provider Identifier will be verified against the NPPES registry.</p>

            <div style={S.field}>
              <label style={S.label}>NPI number (10 digits) *</label>
              <input data-testid="npi-input" style={S.input} value={f2.npi} maxLength={10}
                onChange={e=>setF2({...f2,npi:e.target.value.replace(/\D/,'')})} placeholder="0000000000" />
            </div>

            <div style={S.field}>
              <label style={S.label}>Tax ID / EIN (9 digits) *</label>
              <input data-testid="tax-id-input" type="password" style={S.input} value={f2.tax_id}
                onChange={e=>setF2({...f2,tax_id:e.target.value.replace(/\D/,'')})} maxLength={9}
                placeholder="••••••••• (stored as last 4 only)" />
            </div>

            <div style={S.field}>
              <label style={S.label}>Entity type *</label>
              <div style={{ display:'flex', gap:24 }}>
                {[['1','Individual'],['2','Organization']].map(([v,l])=>(
                  <label key={v} style={{ display:'flex', gap:8, alignItems:'center', cursor:'pointer', fontSize:14 }}>
                    <input type="radio" name="entity_type" value={v}
                      checked={f2.entity_type===v}
                      onChange={()=>setF2({...f2,entity_type:v})}
                      data-testid={`entity-type-${v}`} />
                    {l}
                  </label>
                ))}
              </div>
            </div>

            <button style={S.btn} onClick={submitStep2} disabled={loading} data-testid="step2-verify">
              {loading ? 'Verifying with NPPES…' : 'Verify NPI'}
            </button>
            <button style={S.btnSecondary} onClick={()=>setStep(1)} data-testid="step2-back">← Back</button>
          </div>
        )}

        {/* ── STEP 3: OTP ── */}
        {step === 3 && (
          <div data-testid="step-3">
            <h2 style={S.h2}>Verify your email</h2>
            <p style={S.sub}>
              We sent a 6-digit code to <strong>{f1.email}</strong>
              {otpTimer > 0 && <span style={{ color:'#64748B' }}> — expires in {otpTimer}s</span>}
            </p>

            <div style={{ margin:'24px 0' }}>
              <OTPInput value={otpCode} onChange={setOtpCode} />
            </div>

            <button style={S.btn} onClick={submitStep3}
              disabled={loading || otpCode.length < 6} data-testid="otp-submit">
              {loading ? 'Verifying…' : 'Verify code'}
            </button>

            <button style={S.btnSecondary} onClick={resendOTP}
              disabled={loading || otpTimer > 0} data-testid="otp-resend">
              {otpTimer > 0 ? `Resend in ${otpTimer}s` : 'Resend code'}
            </button>
          </div>
        )}

        {/* ── STEP 4a: Password ── */}
        {step === 4 && (
          <div data-testid="step-4a">
            <h2 style={S.h2}>Create your password</h2>
            <p style={S.sub}>Must be at least 12 characters with uppercase, lowercase, number, and special character.</p>

            <div style={S.field}>
              <label style={S.label}>Password *</label>
              <input data-testid="password-input" type="password" style={S.input}
                value={f4a.password}
                onChange={e=>{
                  setF4a({...f4a,password:e.target.value});
                  setPwStrength(checkStrength(e.target.value));
                }} />
              {f4a.password && (
                <div style={{ marginTop:8, display:'flex', flexDirection:'column', gap:4 }}>
                  {pwStrength.map((r,i)=>(
                    <div key={i} style={{ display:'flex', gap:8, fontSize:12, alignItems:'center' }}>
                      <span style={{ color: r.ok ? '#059669':'#94A3B8' }}>{r.ok?'✓':'○'}</span>
                      <span style={{ color: r.ok ? '#059669':'#64748B' }}>{r.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={S.field}>
              <label style={S.label}>Confirm password *</label>
              <input data-testid="confirm-password-input" type="password" style={S.input}
                value={f4a.confirm_password}
                onChange={e=>setF4a({...f4a,confirm_password:e.target.value})} />
              {f4a.confirm_password && f4a.password !== f4a.confirm_password && (
                <p style={{ color:'#DC2626', fontSize:12, marginTop:4 }}>Passwords do not match</p>
              )}
            </div>

            <button style={S.btn} onClick={submitStep4a} disabled={loading} data-testid="step4a-next">
              {loading ? 'Setting up 2FA…' : 'Continue →'}
            </button>
          </div>
        )}

        {/* ── STEP 4b: 2FA ── */}
        {step === 5 && (
          <div data-testid="step-4b">
            <h2 style={S.h2}>Set up two-factor authentication</h2>
            <p style={S.sub}>Scan this QR code with Google Authenticator, Authy, or any TOTP app.</p>

            {qrUrl && (
              <div style={{ textAlign:'center', margin:'20px 0' }}>
                <img src={qrUrl} alt="2FA QR Code" data-testid="totp-qr"
                  style={{ width:200, height:200, border:'1px solid #E2E8F0', borderRadius:8 }} />
              </div>
            )}

            {manKey && (
              <div style={{
                background:'#F8FAFC', border:'1px solid #E2E8F0', borderRadius:8,
                padding:'10px 16px', marginBottom:20,
              }}>
                <p style={{ fontSize:12, color:'#64748B', marginBottom:4 }}>
                  Can't scan? Enter this key manually:
                </p>
                <code style={{ fontSize:13, color:navy, letterSpacing:2 }}
                  data-testid="totp-manual-key">{manKey}</code>
              </div>
            )}

            <p style={{ fontSize:13, color:'#64748B', marginBottom:8 }}>
              Enter the 6-digit code from your app to confirm:
            </p>
            <OTPInput value={totp} onChange={setTotp} />

            <button style={{ ...S.btn, marginTop:20 }} onClick={submitStep4b}
              disabled={loading || totp.length < 6} data-testid="totp-submit">
              {loading ? 'Confirming…' : 'Confirm 2FA →'}
            </button>
          </div>
        )}

        {/* ── STEP 5: E-Signature ── */}
        {step === 6 && (
          <div data-testid="step-5">
            <h2 style={S.h2}>Review & sign agreements</h2>
            <p style={S.sub}>Please read and sign the following agreements to complete your registration.</p>

            <div style={S.field}>
              <label style={S.label}>Full legal name (as it should appear on file) *</label>
              <input data-testid="legal-name" style={S.input} value={f5.full_legal_name}
                onChange={e=>setF5({...f5,full_legal_name:e.target.value})} />
            </div>

            {[
              ['agreed_to_terms',     'I agree to the Terms of Service (v2.1)'],
              ['agreed_to_hipaa_baa', 'I agree to the HIPAA Business Associate Agreement (v1.3)'],
              ['agreed_to_privacy',   'I agree to the Privacy Policy (v2.0)'],
            ].map(([key,label])=>(
              <div key={key} style={S.check}>
                <input type="checkbox" id={key} checked={f5[key]}
                  data-testid={`checkbox-${key}`}
                  onChange={e=>setF5({...f5,[key]:e.target.checked})}
                  style={{ marginTop:2, accentColor:navy, width:16, height:16 }} />
                <label htmlFor={key} style={{ fontSize:13, color:'#374151', cursor:'pointer' }}>
                  {label}
                </label>
              </div>
            ))}

            <div style={{ ...S.field, marginTop:20 }}>
              <label style={S.label}>Signature *</label>
              <SignatureCanvas
                onChange={sig=>setF5({...f5,signature_data:sig||''})}
                disabled={loading}
              />
            </div>

            <button style={S.btn} onClick={submitStep5} disabled={loading} data-testid="step5-submit">
              {loading ? 'Creating your account…' : '✓ Complete Registration'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
