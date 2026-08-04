/**
 * CHC Pro AI — useAuth Hook
 * Manages auth state across the app.
 * Wrap your app in <AuthProvider> and use useAuth() anywhere.
 */
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { getMe, login, loginMFA, logout as apiLogout, tokens } from '../services/authService';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user,        setUser]    = useState(null);
  const [loading,     setLoading] = useState(true);  // True on first load
  const [mfaSession,  setMfaSession] = useState(null);

  // On mount: check if we have a valid refresh token → restore session
  useEffect(() => {
    const refresh = tokens.getRefresh();
    if (!refresh) { setLoading(false); return; }
    getMe()
      .then(setUser)
      .catch(() => tokens.clearAll())
      .finally(() => setLoading(false));
  }, []);

  const doLogin = useCallback(async (email, password) => {
    const result = await login(email, password);
    if (result.requires_2fa) {
      setMfaSession(result.mfa_session);
      return { requires_2fa: true };
    }
    setUser(result.user);
    return { requires_2fa: false, user: result.user };
  }, []);

  const doMFA = useCallback(async (totp_code) => {
    if (!mfaSession) throw new Error('No MFA session. Please log in again.');
    const result = await loginMFA(mfaSession, totp_code);
    setMfaSession(null);
    setUser(result.user);
    return result.user;
  }, [mfaSession]);

  const doLogout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setMfaSession(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user, loading, mfaSession,
      login:  doLogin,
      mfa:    doMFA,
      logout: doLogout,
      isAuthenticated: !!user,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
