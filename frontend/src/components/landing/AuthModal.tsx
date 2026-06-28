import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import {
  signIn,
  signUp,
  confirmSignUp,
  signInWithRedirect,
  resendSignUpCode,
  resetPassword,
  confirmResetPassword,
} from 'aws-amplify/auth'

type View = 'login' | 'signup' | 'confirm' | 'forgot' | 'forgot-sent'

interface Props {
  initialView?: 'login' | 'signup'
  // When true, renders as a modal overlay on top of the landing page.
  // When false (standalone route / hard refresh), renders full-page.
  isModal?: boolean
}

const inp =
  'w-full px-4 py-3 rounded-xl text-sm text-white placeholder-gray-500 outline-none transition-all ' +
  'focus:ring-2 focus:ring-indigo-500/60 ' +
  'border border-white/8 focus:border-indigo-500/40'

const inpStyle = { background: 'rgba(255,255,255,0.04)' }

const primaryBtn =
  'w-full py-3 rounded-xl font-semibold text-white text-sm transition-all ' +
  'hover:opacity-90 hover:scale-[1.01] active:scale-[0.99] ' +
  'disabled:opacity-40 disabled:cursor-not-allowed disabled:scale-100'

const primaryStyle = { background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }

// Google SVG mark (official brand colors, no license issues for auth button)
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  )
}

export default function AuthModal({ initialView = 'login', isModal = false }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as any)?.from?.pathname ?? '/dashboard'

  const [view, setView] = useState<View>(initialView)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [pendingEmail, setPendingEmail] = useState('')

  const clearError = () => setError('')

  // ── Redirect after successful auth ──────────────────────────────────────────
  const onSuccess = () => {
    // Use replace so the back button doesn't return to /login
    navigate(from, { replace: true })
  }

  // ── Google OAuth ─────────────────────────────────────────────────────────────
  const handleGoogle = async () => {
    setLoading(true)
    setError('')
    try {
      await signInWithRedirect({ provider: 'Google' })
      // Browser navigates away to Cognito Hosted UI - no further code runs here.
      // AuthCallback in App.tsx handles the return.
    } catch (e: any) {
      setError(e.message ?? 'Google sign-in failed. Please try again.')
      setLoading(false)
    }
  }

  // ── Email / password sign-in ─────────────────────────────────────────────────
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!email || !password) { setError('Email and password are required.'); return }
    setLoading(true)
    try {
      const result = await signIn({ username: email, password })
      if (result.isSignedIn) {
        onSuccess()
      } else if (result.nextStep?.signInStep === 'CONFIRM_SIGN_UP') {
        // User signed up but never confirmed - send them to confirm view
        setPendingEmail(email)
        setView('confirm')
      }
    } catch (e: any) {
      const msg: Record<string, string> = {
        NotAuthorizedException: 'Incorrect email or password.',
        UserNotFoundException: 'No account found with that email.',
        UserNotConfirmedException: 'Please confirm your email first.',
      }
      setError(msg[e.name] ?? e.message ?? 'Sign-in failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // ── Email sign-up ─────────────────────────────────────────────────────────────
  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!email || !password) { setError('Email and password are required.'); return }
    if (password !== confirmPassword) { setError('Passwords do not match.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (!/[A-Z]/.test(password)) { setError('Password must contain at least one uppercase letter.'); return }
    if (!/[0-9]/.test(password)) { setError('Password must contain at least one number.'); return }
    setLoading(true)
    try {
      const result = await signUp({ username: email, password, options: { userAttributes: { email } } })
      if (result.nextStep?.signUpStep === 'CONFIRM_SIGN_UP') {
        setPendingEmail(email)
        setView('confirm')
      } else if (result.isSignUpComplete) {
        // Auto-confirmed (rare in sandbox) - go straight to sign-in
        await signIn({ username: email, password })
        onSuccess()
      }
    } catch (e: any) {
      const msg: Record<string, string> = {
        UsernameExistsException: 'An account with that email already exists.',
        InvalidPasswordException: 'Password does not meet requirements.',
      }
      setError(msg[e.name] ?? e.message ?? 'Sign-up failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // ── Confirm code ──────────────────────────────────────────────────────────────
  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!code) { setError('Please enter the 6-digit code.'); return }
    setLoading(true)
    try {
      await confirmSignUp({ username: pendingEmail, confirmationCode: code })
      // Auto sign-in after confirmation
      await signIn({ username: pendingEmail, password })
      onSuccess()
    } catch (e: any) {
      const msg: Record<string, string> = {
        CodeMismatchException: 'Incorrect code. Please check and try again.',
        ExpiredCodeException: 'Code has expired. Request a new one below.',
      }
      setError(msg[e.name] ?? e.message ?? 'Confirmation failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    setError('')
    try {
      await resendSignUpCode({ username: pendingEmail })
      setError('') // clear any previous error
    } catch (e: any) {
      setError(e.message ?? 'Could not resend code.')
    }
  }

  // ── Forgot password ───────────────────────────────────────────────────────────
  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!email) { setError('Please enter your email address.'); return }
    setLoading(true)
    try {
      await resetPassword({ username: email })
      setPendingEmail(email)
      setView('forgot-sent')
    } catch (e: any) {
      setError(e.message ?? 'Could not send reset code.')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!code || !newPassword) { setError('Code and new password are required.'); return }
    setLoading(true)
    try {
      await confirmResetPassword({ username: pendingEmail, confirmationCode: code, newPassword })
      // Sign in with new password
      await signIn({ username: pendingEmail, password: newPassword })
      onSuccess()
    } catch (e: any) {
      const msg: Record<string, string> = {
        CodeMismatchException: 'Incorrect code.',
        ExpiredCodeException: 'Code has expired. Request a new one.',
      }
      setError(msg[e.name] ?? e.message ?? 'Reset failed.')
    } finally {
      setLoading(false)
    }
  }

  // ── Shared container styles ───────────────────────────────────────────────────
  const containerCls = isModal
    ? 'fixed inset-0 z-50 flex items-center justify-center p-4'
    : 'min-h-screen flex items-center justify-center p-4'

  const overlayStyle = isModal
    ? { background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }
    : { background: '#0a0a0f' }

  // ── Shared card ───────────────────────────────────────────────────────────────
  const card = (children: React.ReactNode) => (
    <div className={containerCls} style={overlayStyle}
         onClick={isModal ? (e) => { if (e.target === e.currentTarget) navigate(-1) } : undefined}>
      <div
        className="w-full max-w-md rounded-2xl p-8 relative"
        style={{
          background: 'rgba(12,12,20,0.95)',
          border: '1px solid rgba(99,102,241,0.2)',
          boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{ background: '#534ab7' }}>
            <span className="text-white font-bold text-base leading-none">A</span>
          </div>
          <span className="text-white font-semibold text-lg"
                style={{ fontFamily: 'Syne, sans-serif' }}>
            applytic
          </span>
        </div>

        {children}
      </div>
    </div>
  )

  // ── Error box ─────────────────────────────────────────────────────────────────
  const ErrorBox = () => error ? (
    <div className="mb-4 px-4 py-3 rounded-xl text-xs text-red-300"
         style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
      {error}
    </div>
  ) : null

  // ── Divider ───────────────────────────────────────────────────────────────────
  const Divider = () => (
    <div className="flex items-center gap-3 my-5">
      <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
      <span className="text-xs text-gray-600">or</span>
      <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
    </div>
  )

  // ── Google button ─────────────────────────────────────────────────────────────
  const GoogleBtn = ({ label }: { label: string }) => (
    <button
      type="button"
      onClick={handleGoogle}
      disabled={loading}
      className="w-full flex items-center justify-center gap-3 py-3 rounded-xl text-sm font-medium text-white transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
      style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
    >
      <GoogleMark />
      {label}
    </button>
  )

  // ── Eye toggle ────────────────────────────────────────────────────────────────
  const EyeToggle = () => (
    <button
      type="button"
      onClick={() => setShowPassword(s => !s)}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
      tabIndex={-1}
    >
      {showPassword ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
          <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
          <line x1="1" y1="1" x2="23" y2="23"/>
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      )}
    </button>
  )

  // ─────────────────────────────────────────────────────────────────────────────
  // Views
  // ─────────────────────────────────────────────────────────────────────────────

  if (view === 'login') return card(
    <>
      <h1 className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: 'Syne, sans-serif' }}>Welcome back</h1>
      <p className="text-sm text-gray-500 mb-6">
        No account?{' '}
        <button onClick={() => { clearError(); setView('signup') }}
                className="text-indigo-400 hover:text-indigo-300 transition-colors">
          Sign up free
        </button>
      </p>

      <GoogleBtn label="Continue with Google" />
      <Divider />
      <ErrorBox />

      <form onSubmit={handleLogin} className="space-y-3">
        <input
          type="email" placeholder="Email address" value={email} autoComplete="email"
          onChange={e => { setEmail(e.target.value); clearError() }}
          className={inp} style={inpStyle}
        />
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'} placeholder="Password" value={password}
            autoComplete="current-password"
            onChange={e => { setPassword(e.target.value); clearError() }}
            className={inp + ' pr-10'} style={inpStyle}
          />
          <EyeToggle />
        </div>
        <div className="flex justify-end">
          <button type="button" onClick={() => { clearError(); setView('forgot') }}
                  className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">
            Forgot password?
          </button>
        </div>
        <button type="submit" disabled={loading} className={primaryBtn} style={primaryStyle}>
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </>
  )

  if (view === 'signup') return card(
    <>
      <h1 className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: 'Syne, sans-serif' }}>Create your account</h1>
      <p className="text-sm text-gray-500 mb-6">
        Already have one?{' '}
        <button onClick={() => { clearError(); setView('login') }}
                className="text-indigo-400 hover:text-indigo-300 transition-colors">
          Sign in
        </button>
      </p>

      <GoogleBtn label="Sign up with Google" />
      <Divider />
      <ErrorBox />

      <form onSubmit={handleSignUp} className="space-y-3">
        <input
          type="email" placeholder="Email address" value={email} autoComplete="email"
          onChange={e => { setEmail(e.target.value); clearError() }}
          className={inp} style={inpStyle}
        />
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'} placeholder="Password (min 8 chars, 1 uppercase, 1 number)"
            value={password} autoComplete="new-password"
            onChange={e => { setPassword(e.target.value); clearError() }}
            className={inp + ' pr-10'} style={inpStyle}
          />
          <EyeToggle />
        </div>
        <input
          type={showPassword ? 'text' : 'password'} placeholder="Confirm password"
          value={confirmPassword} autoComplete="new-password"
          onChange={e => { setConfirmPassword(e.target.value); clearError() }}
          className={inp} style={inpStyle}
        />
        <button type="submit" disabled={loading} className={primaryBtn} style={primaryStyle}>
          {loading ? 'Creating account...' : 'Get Started Free'}
        </button>
      </form>

      {/* Fix: was <a href="/terms"> and <a href="/privacy"> - broken on GitHub Pages
          because bare href ignores BrowserRouter basename (/applytic/).
          Link to="/terms" respects basename automatically. */}
      <p className="mt-4 text-xs text-gray-600 text-center">
        By signing up you agree to our{' '}
        <Link to="/terms" className="text-gray-500 hover:text-indigo-400 transition-colors">Terms</Link>
        {' '}and{' '}
        <Link to="/privacy" className="text-gray-500 hover:text-indigo-400 transition-colors">Privacy Policy</Link>.
      </p>
    </>
  )

  if (view === 'confirm') return card(
    <>
      <h1 className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: 'Syne, sans-serif' }}>Check your email</h1>
      <p className="text-sm text-gray-500 mb-6">
        We sent a 6-digit code to <span className="text-gray-300">{pendingEmail}</span>.
        Enter it below to confirm your account.
      </p>

      <ErrorBox />

      <form onSubmit={handleConfirm} className="space-y-3">
        <input
          type="text" inputMode="numeric" maxLength={6} placeholder="6-digit code"
          value={code} autoComplete="one-time-code"
          onChange={e => { setCode(e.target.value.replace(/\D/g, '')); clearError() }}
          className={inp + ' tracking-[0.5em] text-center text-lg'} style={inpStyle}
        />
        <button type="submit" disabled={loading} className={primaryBtn} style={primaryStyle}>
          {loading ? 'Confirming...' : 'Confirm account'}
        </button>
      </form>

      <div className="mt-4 text-center">
        <button onClick={handleResendCode}
                className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">
          Resend code
        </button>
        <span className="text-gray-700 mx-2">-</span>
        <button onClick={() => { clearError(); setView('login') }}
                className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">
          Back to sign in
        </button>
      </div>

      <p className="mt-5 text-xs text-gray-600 text-center">
        You will also receive a separate email from AWS to verify your address for the weekly digest.
        Click the link in that email too.
      </p>
    </>
  )

  if (view === 'forgot') return card(
    <>
      <h1 className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: 'Syne, sans-serif' }}>Reset password</h1>
      <p className="text-sm text-gray-500 mb-6">
        Enter your email and we will send a reset code.
      </p>

      <ErrorBox />

      <form onSubmit={handleForgot} className="space-y-3">
        <input
          type="email" placeholder="Email address" value={email} autoComplete="email"
          onChange={e => { setEmail(e.target.value); clearError() }}
          className={inp} style={inpStyle}
        />
        <button type="submit" disabled={loading} className={primaryBtn} style={primaryStyle}>
          {loading ? 'Sending...' : 'Send reset code'}
        </button>
      </form>

      <div className="mt-4 text-center">
        <button onClick={() => { clearError(); setView('login') }}
                className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">
          Back to sign in
        </button>
      </div>
    </>
  )

  if (view === 'forgot-sent') return card(
    <>
      <h1 className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: 'Syne, sans-serif' }}>Check your email</h1>
      <p className="text-sm text-gray-500 mb-6">
        Sent a reset code to <span className="text-gray-300">{pendingEmail}</span>.
        Enter the code and your new password below.
      </p>

      <ErrorBox />

      <form onSubmit={handleConfirmReset} className="space-y-3">
        <input
          type="text" inputMode="numeric" maxLength={6} placeholder="6-digit code"
          value={code} autoComplete="one-time-code"
          onChange={e => { setCode(e.target.value.replace(/\D/g, '')); clearError() }}
          className={inp + ' tracking-[0.5em] text-center text-lg'} style={inpStyle}
        />
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'} placeholder="New password"
            value={newPassword} autoComplete="new-password"
            onChange={e => { setNewPassword(e.target.value); clearError() }}
            className={inp + ' pr-10'} style={inpStyle}
          />
          <EyeToggle />
        </div>
        <button type="submit" disabled={loading} className={primaryBtn} style={primaryStyle}>
          {loading ? 'Resetting...' : 'Set new password'}
        </button>
      </form>

      <div className="mt-4 text-center">
        <button onClick={() => handleForgot({ preventDefault: () => {} } as any)}
                className="text-xs text-gray-500 hover:text-indigo-400 transition-colors">
          Resend code
        </button>
      </div>
    </>
  )

  return null
}
