/**
 * CHC Pro AI — Login Page
 * Split-panel layout with company logo displayed on left hero panel and top of right form.
 */
import { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import OTPInput from '../components/OTPInput';
import { useAuth } from '../hooks/useAuth';
import { apiError } from '../services/authService';

const font  = "'IBM Plex Sans', sans-serif";
const navy  = '#003F87';
const teal  = '#0073CF';

const S = {
  page:  { display:'flex', minHeight:'100vh', fontFamily:font },
  left:  {
    flex:'0 0 45%',
    background:`linear-gradient(160deg,${navy} 0%,${teal} 100%)`,
    display:'flex', flexDirection:'column',
    justifyContent:'center', alignItems:'center',
    padding:48, color:'#fff',
  },
  logoWrap: {
    background:'rgba(255,255,255,0.1)',
    borderRadius:20, padding:24,
    marginBottom:28,
    display:'flex', alignItems:'center', justifyContent:'center',
  },
  logo: { width:160, height:160, objectFit:'contain' },
  brand: { fontSize:26, fontWeight:700, letterSpacing:'-0.01em', marginBottom:6 },
  tagline: { fontSize:13, opacity:0.82, textAlign:'center', maxWidth:260, lineHeight:1.6, marginBottom:36 },
  features: { display:'flex', flexDirection:'column', gap:12, width:'100%', maxWidth:240 },
  feat: { display:'flex', gap:10, alignItems:'center', fontSize:13, opacity:0.9 },
  right: {
    flex:1, display:'flex', alignItems:'center',
    justifyContent:'center', background:'#F8FAFC', padding:32,
  },
  card:  { width:'100%', maxWidth:400 },
  logoSmall: {
    display:'flex', alignItems:'center', gap:10, marginBottom:24,
  },
  logoSmallImg: { width:40, height:40, objectFit:'contain' },
  logoSmallText: { fontSize:16, fontWeight:700, color:navy },
  logoSmallSub: { fontSize:11, color:'#64748B', marginTop:1 },
  label: { display:'block', fontSize:13, fontWeight:500, color:'#374151', marginBottom:4 },
  input: {
    width:'100%', padding:'11px 13px',
    border:'1.5px solid #CBD5E1', borderRadius:8,
    fontSize:14, fontFamily:font, outline:'none',
    color:'#0F172A', background:'#fff',
    boxSizing:'border-box', marginBottom:16,
  },
  btn: {
    width:'100%', padding:13, background:navy, color:'#fff',
    border:'none', borderRadius:8, fontSize:15,
    fontWeight:600, cursor:'pointer', fontFamily:font,
  },
  btnOutline: {
    width:'100%', padding:12, background:'transparent', color:navy,
    border:`1.5px solid ${navy}`, borderRadius:8, fontSize:14,
    fontWeight:500, cursor:'pointer', fontFamily:font, marginTop:8,
  },
  err: {
    background:'#FEE2E2', border:'1px solid #FECACA', borderRadius:8,
    padding:'10px 14px', color:'#991B1B', fontSize:13, marginBottom:14,
  },
  ok: {
    background:'#D1FAE5', border:'1px solid #6EE7B7', borderRadius:8,
    padding:'10px 14px', color:'#065F46', fontSize:13, marginBottom:14,
  },
};

export default function Login() {
  const navigate         = useNavigate();
  const location         = useLocation();
  const { login, mfa }   = useAuth();

  const [stage,    setStage]    = useState('credentials');
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [info,     setInfo]     = useState('');

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [totp,     setTotp]     = useState('');

  const [resetEmail,  setResetEmail]  = useState('');
  const [resetCode,   setResetCode]   = useState('');
  const [newPwd,      setNewPwd]      = useState('');
  const [confirmPwd,  setConfirmPwd]  = useState('');
  const [resetStage,  setResetStage]  = useState('init');

  const registered = new URLSearchParams(location.search).get('registered');
  const from       = location.state?.from?.pathname || '/dashboard';

  async function handleLogin(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const r = await login(email, password);
      if (r.requires_2fa) setStage('mfa');
      else                navigate(from, { replace:true });
    } catch(ex) { setError(apiError(ex)); }
    finally { setLoading(false); }
  }

  async function handleMFA(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await mfa(totp);
      navigate(from, { replace:true });
    } catch(ex) { setError(apiError(ex)); }
    finally { setLoading(false); }
  }

  async function handleResetInit(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const { resetPassword } = await import('../services/authService');
      await resetPassword(resetEmail);
      setResetStage('confirm');
      setInfo('If an account exists, a reset code has been sent to your email.');
    } catch(ex) { setError(apiError(ex)); }
    finally { setLoading(false); }
  }

  async function handleResetConfirm(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const { confirmReset } = await import('../services/authService');
      await confirmReset(resetEmail, resetCode, newPwd, confirmPwd);
      setStage('credentials');
      setInfo('Password updated. Please log in.');
    } catch(ex) { setError(apiError(ex)); }
    finally { setLoading(false); }
  }

  return (
    <div style={S.page}>

      {/* ── Left hero panel ── */}
      <div style={S.left}>
        {/* Logo */}
        <div style={S.logoWrap}>
          <img
            src="/logo.webp"
            alt="CHC Pro AI Logo"
            style={S.logo}
            onError={e => { e.target.style.display='none'; }}
          />
        </div>

        <div style={S.brand}>CHC Pro AI</div>
        <div style={S.tagline}>
          Healthcare Revenue &amp; Coding Solutions —
          HIPAA-compliant AI medical coding built for independent practices.
        </div>

        <div style={S.features}>
          {[
            'ICD-10-CM / PCS coding',
            'CPT & HCPCS assignment',
            'MS-DRG grouper',
            'NCCI edit validation',
            'Denial risk scoring',
          ].map(f => (
            <div key={f} style={S.feat}>
              <span style={{ color:'#6EE7B7', fontSize:16 }}>✓</span>
              {f}
            </div>
          ))}
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div style={S.right}>
        <div style={S.card}>

          {/* Logo + brand name at top of form */}
          <div style={S.logoSmall}>
            <img
              src="/logo.webp"
              alt="CHC Pro AI"
              style={S.logoSmallImg}
              onError={e => { e.target.style.display='none'; }}
            />
            <div>
              <div style={S.logoSmallText}>CHC Pro AI</div>
              <div style={S.logoSmallSub}>Healthcare Revenue &amp; Coding Solutions</div>
            </div>
          </div>

          {registered && !info && (
            <div style={S.ok} data-testid="registered-success">
              Account created! Please log in.
            </div>
          )}
          {info  && <div style={S.ok}  data-testid="info-msg">{info}</div>}
          {error && <div style={S.err} data-testid="error-message">{error}</div>}

          {/* ── Credentials ── */}
          {stage === 'credentials' && (
            <>
              <h2 style={{ fontSize:22, fontWeight:600, color:navy, marginBottom:4 }}>Sign in</h2>
              <p style={{ fontSize:13, color:'#64748B', marginBottom:22 }}>
                New here? <Link to="/register" style={{ color:teal }}>Create an account</Link>
              </p>
              <form onSubmit={handleLogin}>
                <label style={S.label}>Email address</label>
                <input data-testid="email-input" type="email" style={S.input}
                  value={email} onChange={e=>setEmail(e.target.value)}
                  autoComplete="email" required />

                <label style={S.label}>Password</label>
                <input data-testid="password-input" type="password" style={S.input}
                  value={password} onChange={e=>setPassword(e.target.value)}
                  autoComplete="current-password" required />

                <div style={{ textAlign:'right', marginTop:-12, marginBottom:16 }}>
                  <button type="button"
                    onClick={()=>{ setStage('reset'); setError(''); }}
                    style={{ background:'none', border:'none', color:teal, fontSize:13, cursor:'pointer' }}
                    data-testid="forgot-password-link">
                    Forgot password?
                  </button>
                </div>

                <button type="submit" style={S.btn} disabled={loading} data-testid="login-btn">
                  {loading ? 'Signing in…' : 'Sign in'}
                </button>
              </form>
            </>
          )}

          {/* ── MFA ── */}
          {stage === 'mfa' && (
            <>
              <h2 style={{ fontSize:22, fontWeight:600, color:navy, marginBottom:4 }}>
                Two-factor authentication
              </h2>
              <p style={{ fontSize:13, color:'#64748B', marginBottom:22 }}>
                Enter the 6-digit code from your authenticator app.
              </p>
              <form onSubmit={handleMFA}>
                <div style={{ marginBottom:24 }}>
                  <OTPInput value={totp} onChange={setTotp} />
                </div>
                <button type="submit" style={S.btn}
                  disabled={loading || totp.length < 6} data-testid="mfa-submit-btn">
                  {loading ? 'Verifying…' : 'Verify code'}
                </button>
                <button type="button" style={S.btnOutline}
                  onClick={()=>{ setStage('credentials'); setTotp(''); }}
                  data-testid="mfa-back-btn">
                  ← Back to sign in
                </button>
              </form>
            </>
          )}

          {/* ── Password reset init ── */}
          {stage === 'reset' && resetStage === 'init' && (
            <>
              <h2 style={{ fontSize:22, fontWeight:600, color:navy, marginBottom:4 }}>Reset password</h2>
              <p style={{ fontSize:13, color:'#64748B', marginBottom:22 }}>
                Enter your email and we'll send a reset code.
              </p>
              <form onSubmit={handleResetInit}>
                <label style={S.label}>Email address</label>
                <input data-testid="reset-email" type="email" style={S.input}
                  value={resetEmail} onChange={e=>setResetEmail(e.target.value)} required />
                <button type="submit" style={S.btn} disabled={loading} data-testid="reset-send-btn">
                  {loading ? 'Sending…' : 'Send reset code'}
                </button>
                <button type="button" style={S.btnOutline} onClick={()=>setStage('credentials')}>
                  ← Back to sign in
                </button>
              </form>
            </>
          )}

          {/* ── Password reset confirm ── */}
          {stage === 'reset' && resetStage === 'confirm' && (
            <>
              <h2 style={{ fontSize:22, fontWeight:600, color:navy, marginBottom:4 }}>Set new password</h2>
              <p style={{ fontSize:13, color:'#64748B', marginBottom:22 }}>
                Enter the code from your email and your new password.
              </p>
              <form onSubmit={handleResetConfirm}>
                <label style={S.label}>Reset code</label>
                <input data-testid="reset-code" style={S.input}
                  value={resetCode} onChange={e=>setResetCode(e.target.value)} required />
                <label style={S.label}>New password</label>
                <input data-testid="new-password" type="password" style={S.input}
                  value={newPwd} onChange={e=>setNewPwd(e.target.value)} required />
                <label style={S.label}>Confirm new password</label>
                <input data-testid="confirm-new-password" type="password" style={S.input}
                  value={confirmPwd} onChange={e=>setConfirmPwd(e.target.value)} required />
                <button type="submit" style={S.btn} disabled={loading} data-testid="reset-confirm-btn">
                  {loading ? 'Updating…' : 'Update password'}
                </button>
              </form>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
