import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../components/AuthContext'
import HelpDialog from '../components/HelpDialog'
import WorkflowDiagram from '../components/WorkflowDiagram'
import { Spinner } from '../components/ui'

const ROLES = [
  {
    key: 'creator' as const,
    title: 'Try as Creator',
    blurb: 'Submit a draft, see every issue with its source, and accept or edit the fixes.',
    accent: 'bg-brand-700 hover:bg-brand-800',
  },
  {
    key: 'manager' as const,
    title: 'Try as Manager',
    blurb: 'Review the queue, read findings, and send a version back with a required note.',
    accent: 'bg-gold-500 hover:bg-gold-600',
  },
  {
    key: 'approver' as const,
    title: 'Try as Approver',
    blurb: 'Approve or reject one exact version, with explicit sign-off on high-severity items.',
    accent: 'bg-charcoal hover:bg-black',
  },
]

const STEPS = [
  { n: '1', title: 'Submit', text: 'Paste a draft or load a sample. Pick the content type.' },
  { n: '2', title: 'Review findings', text: 'Every issue cites an approved source, or says it needs verification.' },
  { n: '3', title: 'Approve', text: 'A human approves that exact version. Nothing publishes itself.' },
]

const USPS = [
  {
    title: 'A review loop that goes both ways',
    text: 'Creators, managers and approvers can move work forward. Reviewers can send it back with a required note, so feedback has a clear owner and next step.',
  },
  {
    title: 'Know exactly what changed',
    text: 'Compare version-by-version drafts, see who made each change, and inspect the audit trail. Approvers can verify edits before sign-off.',
  },
  {
    title: 'Grounded in your company knowledge',
    text: 'Add company context, approved guidelines, facts and terminology. Retrieval-augmented AI checks use relevant workspace knowledge as evidence instead of relying on generic answers.',
  },
  {
    title: 'AI plus dependable rule checks',
    text: 'AI can flag tone and messaging concerns while deterministic checks catch rules like prohibited terms, missing disclaimers and fact mismatches. Rule checks still run if AI is unavailable.',
  },
  {
    title: 'Useful fixes, not just a score',
    text: 'Each finding points to affected text, explains the issue, shows supporting evidence and suggests a focused correction. People choose to accept, edit or reject each fix.',
  },
  {
    title: 'People stay in control',
    text: 'Nothing is auto-published. Approval is tied to one exact version, and unresolved high-severity issues require explicit sign-off.',
  },
  {
    title: 'Brand checks beyond copy',
    text: 'Check visual palette similarity and text contrast using colour-distance and WCAG contrast calculations, alongside content review.',
  },
  {
    title: 'Workspace-specific and auditable',
    text: 'Checks use the right workspace’s approved sources, and actions are recorded with who did them and when.',
  },
]

export default function Landing() {
  const {
    enterDemo,
    waking,
    error,
    me,
    authEnabled,
    demoEnabled,
    signIn,
    sendPasswordReset,
    signOut,
    needsOrganizationSetup,
    organizationCreationEnabled,
    createOrganization,
  } = useAuth()
  const navigate = useNavigate()
  const [helpOpen, setHelpOpen] = useState(false)
  const [whyUsOpen, setWhyUsOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [resetNotice, setResetNotice] = useState<string | null>(null)
  const [resetMode, setResetMode] = useState(false)
  const [organizationName, setOrganizationName] = useState('')
  const [brandName, setBrandName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [organizationBusy, setOrganizationBusy] = useState(false)
  const [organizationError, setOrganizationError] = useState<string | null>(null)

  const submitOrganization = async (event: React.FormEvent) => {
    event.preventDefault()
    setOrganizationBusy(true)
    setOrganizationError(null)
    try {
      await createOrganization({
        name: organizationName.trim(),
        brand_name: brandName.trim() || undefined,
        display_name: displayName.trim(),
      })
      navigate('/dashboard')
    } catch (err) {
      setOrganizationError(err instanceof Error ? err.message : 'Could not create your organization.')
    } finally {
      setOrganizationBusy(false)
    }
  }

  const start = async (role: 'creator' | 'manager' | 'approver') => {
    if (await enterDemo(role)) navigate('/dashboard')
  }

  const submitSignIn = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoginError(null)
    setResetNotice(null)
    try {
      await signIn(email, password)
      navigate('/dashboard')
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Sign-in failed.')
    }
  }

  const submitPasswordReset = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoginError(null)
    setResetNotice(null)
    try {
      await sendPasswordReset(email)
      setResetNotice('If the account exists, a password recovery link will be sent to that email.')
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Could not request password recovery.')
    }
  }

  return (
    <div className="min-h-screen bg-cream">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
        <header className="text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-semibold text-brand-800">
            <span className="h-2 w-2 rounded-full bg-brand-500" />
            {demoEnabled ? 'Live demo · fictional brand data' : 'Secure team sign-in'}
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-brand-900 sm:text-5xl">
            BrandShield <span className="text-gold-500">AI</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-gray-700 sm:text-lg">
            Check content against your approved brand guidelines, facts and terminology
            <em> before</em> it goes out. Every issue shows the exact text, the rule, why it
            matters, the approved source, and a suggested fix. Reviews are bidirectional: a
            manager or approver can send a version back with a required note.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={() => setWhyUsOpen((open) => !open)}
              className="inline-flex items-center gap-2 rounded-full border-2 border-brand-700 bg-white px-5 py-2.5 text-sm font-bold text-brand-900 shadow-sm transition-all hover:-translate-y-0.5 hover:bg-brand-50 hover:shadow-md"
              aria-expanded={whyUsOpen}
              aria-controls="why-us-panel"
            >
              Why us?
              <span aria-hidden="true">{whyUsOpen ? '−' : '+'}</span>
            </button>
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="inline-flex items-center gap-2 rounded-full bg-gold-500 px-5 py-2.5 text-sm font-bold text-charcoal shadow-md ring-2 ring-gold-400/50 transition-all hover:-translate-y-0.5 hover:bg-gold-400 hover:shadow-lg"
              aria-haspopup="dialog"
            >
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full bg-charcoal text-[11px] font-bold text-white"
                aria-hidden="true"
              >
                ?
              </span>
              Need help? See how it works
            </button>
          </div>
        </header>

        {authEnabled && !me && (
          <form
            className="card mx-auto mt-8 max-w-xl space-y-4 p-5"
            onSubmit={(event) => void (resetMode ? submitPasswordReset(event) : submitSignIn(event))}
          >
            <div>
              <h2 className="text-lg font-bold text-brand-900">
                {resetMode ? 'Recover your password' : 'Employee sign-in'}
              </h2>
              <p className="mt-1 text-sm text-gray-600">
                {resetMode
                  ? 'We’ll email a secure link if the account is registered.'
                  : 'Use the invitation sent by your workspace administrator to set up your account.'}
              </p>
            </div>
            {loginError && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{loginError}</p>}
            {resetNotice && <p className="rounded-lg bg-brand-50 p-3 text-sm text-brand-900" role="status">{resetNotice}</p>}
            <label className="block">
              <span className="label">Work email</span>
              <input
                className="input"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            {!resetMode && (
              <label className="block">
                <span className="label">Password</span>
                <input
                  className="input"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <button type="submit" className="btn-primary" disabled={waking}>
                {resetMode ? 'Send recovery link' : 'Sign in'}
              </button>
              <button
                type="button"
                className="btn-ghost text-xs"
                onClick={() => {
                  setResetMode((value) => !value)
                  setLoginError(null)
                  setResetNotice(null)
                }}
              >
                {resetMode ? 'Back to sign in' : 'Forgot password?'}
              </button>
            </div>
          </form>
        )}
        {authEnabled && error && !me && (
          <div className="mx-auto mt-3 max-w-xl text-center">
            <button type="button" className="btn-ghost text-xs" onClick={signOut}>
              End this session
            </button>
          </div>
        )}
        {authEnabled && needsOrganizationSetup && organizationCreationEnabled && (
          <form
            className="card mx-auto mt-5 max-w-xl space-y-4 p-5"
            onSubmit={(event) => void submitOrganization(event)}
          >
            <div>
              <h2 className="text-lg font-bold text-brand-900">Create your organization</h2>
              <p className="mt-1 text-sm text-gray-600">
                This verified account will become its first administrator. You can invite your team
                and add more brands afterward.
              </p>
            </div>
            {organizationError && (
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">
                {organizationError}
              </p>
            )}
            <label className="block">
              <span className="label">Organization name</span>
              <input
                className="input"
                required
                minLength={2}
                maxLength={120}
                value={organizationName}
                onChange={(event) => setOrganizationName(event.target.value)}
              />
            </label>
            <label className="block">
              <span className="label">First brand name (optional)</span>
              <input
                className="input"
                maxLength={120}
                value={brandName}
                onChange={(event) => setBrandName(event.target.value)}
              />
            </label>
            <label className="block">
              <span className="label">Your name</span>
              <input
                className="input"
                required
                minLength={1}
                maxLength={120}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <button type="submit" className="btn-primary" disabled={organizationBusy}>
              {organizationBusy ? <Spinner /> : null}
              Create workspace
            </button>
          </form>
        )}

        {!authEnabled && !demoEnabled && !me && (
          <div className="mx-auto mt-8 max-w-xl rounded-lg border border-amber-200 bg-amber-50 p-4 text-center text-sm text-amber-900">
            Business sign-in is not configured. Contact the deployment administrator.
          </div>
        )}
        {authEnabled && needsOrganizationSetup && !organizationCreationEnabled && (
          <div className="mx-auto mt-5 max-w-xl rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            Your account is verified but is not assigned to a workspace. Ask an organization
            administrator for an invitation.
          </div>
        )}

        {whyUsOpen && (
          <section
            id="why-us-panel"
            className="mt-8 rounded-2xl border-2 border-brand-200 bg-white p-5 shadow-lg sm:p-7"
            aria-labelledby="why-us-title"
          >
            <div className="mx-auto max-w-3xl text-center">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-gold-600">
                Why teams choose BrandShield
              </p>
              <h2 id="why-us-title" className="mt-2 text-2xl font-bold tracking-tight text-brand-900">
                AI review you can verify, guide and trust
              </h2>
              <p className="mt-2 text-sm text-gray-600">
                We pair AI with company-specific evidence and a human-owned workflow—so teams can
                move quickly without losing accountability.
              </p>
            </div>
            <ul className="mt-6 grid gap-3 sm:grid-cols-2">
              {USPS.map((usp) => (
                <li key={usp.title} className="rounded-xl border border-brand-100 bg-cream/60 p-4">
                  <h3 className="font-semibold text-charcoal">{usp.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-gray-600">{usp.text}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {me && (
          <div className="mx-auto mt-6 max-w-xl rounded-lg border border-brand-200 bg-white p-3 text-center text-sm">
            You are already in the demo as <strong>{me.display_name}</strong>.{' '}
            <button className="font-semibold text-brand-700 underline" onClick={() => navigate('/dashboard')}>
              Continue to dashboard
            </button>
          </div>
        )}

        {error && (
          <div className="mx-auto mt-6 max-w-xl rounded-lg border border-red-200 bg-red-50 p-3 text-center text-sm text-red-800" role="alert">
            {error}
          </div>
        )}

        {waking && (
          <div className="mx-auto mt-6 flex max-w-xl items-center justify-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
            <Spinner className="h-4 w-4" />
            Waking up the server — this can take up to a minute on a free host.
          </div>
        )}

        {demoEnabled && (
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {ROLES.map((role) => (
            <button
              key={role.key}
              type="button"
              disabled={waking}
              onClick={() => void start(role.key)}
              className={`${role.accent} group flex flex-col items-start gap-2 rounded-xl p-5 text-left text-white shadow-sm transition-transform hover:-translate-y-0.5 disabled:opacity-60`}
            >
              <span className="text-lg font-bold">{role.title}</span>
              <span className="text-sm text-white/85">{role.blurb}</span>
              <span className="mt-2 text-xs font-semibold uppercase tracking-wide text-white/70 group-hover:text-white">
                Enter instantly →
              </span>
            </button>
            ))}
          </div>
        )}

        <section className="mt-12">
          <h2 className="text-center text-sm font-semibold uppercase tracking-wide text-gray-500">
            Who submits to whom
          </h2>
          <p className="mx-auto mt-1 max-w-xl text-center text-sm text-gray-600">
            Your draft passes through four steps. A person makes the final call — never the
            software.
          </p>
          <div className="mt-5">
            <WorkflowDiagram />
          </div>
        </section>

        <section className="mt-12">
          <h2 className="text-center text-sm font-semibold uppercase tracking-wide text-gray-500">
            How it works
          </h2>
          <ol className="mt-4 grid gap-4 sm:grid-cols-3">
            {STEPS.map((step) => (
              <li key={step.n} className="card p-5">
                <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-brand-700 text-sm font-bold text-white">
                  {step.n}
                </div>
                <h3 className="font-semibold text-charcoal">{step.title}</h3>
                <p className="mt-1 text-sm text-gray-600">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mt-12 grid gap-4 sm:grid-cols-2">
          <div className="card p-5">
            <h3 className="font-semibold text-charcoal">What is pre-loaded</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-gray-600">
              <li>• Northwind Foods brand voice guide and visual standards</li>
              <li>• Approved facts: protein, price, launch date, certifications</li>
              <li>• Approved and prohibited terminology, required disclaimers</li>
              <li>• Three sample drafts with real planted errors</li>
            </ul>
          </div>
          <div className="card p-5">
            <h3 className="font-semibold text-charcoal">What it will not do</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-gray-600">
              <li>• Publish anything automatically</li>
              <li>• Rewrite your draft without your decision on each fix</li>
              <li>• Call a claim false without an approved source that contradicts it</li>
              <li>• Hide a failure: if the AI is down, deterministic checks still run</li>
            </ul>
          </div>
        </section>

        <p className="mt-10 text-center text-xs text-gray-500">
          {demoEnabled
            ? 'Demo role selection is enabled for this deployment. Business accounts use invitation-based sign-in.'
            : 'Access is invitation-only. Contact your workspace administrator if you need an account.'}
        </p>
      </div>

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
