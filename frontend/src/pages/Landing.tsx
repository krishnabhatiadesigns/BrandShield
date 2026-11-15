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
    blurb: 'Review the queue, read findings, and send a version back with comments.',
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

export default function Landing() {
  const { enterDemo, waking, error, me } = useAuth()
  const navigate = useNavigate()
  const [helpOpen, setHelpOpen] = useState(false)

  const start = async (role: 'creator' | 'manager' | 'approver') => {
    await enterDemo(role)
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen bg-cream">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
        <header className="text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-semibold text-brand-800">
            <span className="h-2 w-2 rounded-full bg-brand-500" />
            Live demo · no sign-in · fictional brand data
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-brand-900 sm:text-5xl">
            BrandShield <span className="text-gold-500">AI</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-gray-700 sm:text-lg">
            Check content against your approved brand guidelines, facts and terminology
            <em> before</em> it goes out. Every issue shows the exact text, the rule, why it
            matters, the approved source, and a suggested fix.
          </p>
          <button
            type="button"
            onClick={() => setHelpOpen(true)}
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-gold-500 px-5 py-2.5 text-sm font-bold text-charcoal shadow-md ring-2 ring-gold-400/50 transition-all hover:-translate-y-0.5 hover:bg-gold-400 hover:shadow-lg"
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
        </header>

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
          Optional email sign-up is supported through Supabase Auth, but the demo path above
          never requires it.
        </p>
      </div>

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
