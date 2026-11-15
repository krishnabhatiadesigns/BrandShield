import { useEffect, useRef } from 'react'

const WORKFLOW = [
  {
    n: '1',
    title: 'Submit',
    text: 'Paste a draft, upload a PDF or DOCX, or load one of the three sample drafts. Pick the content type — social post, ad, email or document — because that decides which disclaimer is required.',
  },
  {
    n: '2',
    title: 'Review findings',
    text: 'Every issue shows the exact affected text, the rule it breaks, why it matters, the approved source that backs it, and a suggested correction. Click a highlight in the draft to jump to its finding.',
  },
  {
    n: '3',
    title: 'Fix and approve',
    text: 'Accept, edit or reject each fix. Managers and approvers can also edit the draft text directly. Any edit creates a new version — never a silent rewrite. A human approver then approves or rejects that exact version, with explicit sign-off on any unresolved high-severity item.',
  },
]

const FEATURES = [
  {
    title: 'Evidence-backed findings',
    text: 'Each finding cites an approved passage from this workspace, or says "Needs human verification". A claim is only called contradicted when an approved source actually contradicts it.',
  },
  {
    title: 'Hybrid checks that never go blank',
    text: 'Deterministic rules (prohibited terms, wrong product names, fact mismatches, missing disclaimers) always run. AI analysis adds tone and messaging findings on top. If the AI is down, you still get results and a clear message.',
  },
  {
    title: 'Minimal, intent-preserving fixes',
    text: 'Suggestions replace only the problematic phrase, keep your wording, use approved terminology, and never introduce new unverified numbers.',
  },
  {
    title: 'Versioned approvals',
    text: 'An approval is tied to one version. Editing creates a new version and resets the status, so an old approval can never cover new text.',
  },
  {
    title: 'Roles enforced in the backend',
    text: 'Creators submit, managers review and can edit the draft directly, approvers decide. The server rejects actions your role does not allow — the UI is not the only guard.',
  },
  {
    title: 'Visual brand compliance',
    text: 'Palette similarity uses real CIE76 colour distance and contrast uses the WCAG 2.1 formula, so off-brand colours and unreadable text are caught with numbers, not guesses.',
  },
  {
    title: 'Workspace isolation',
    text: 'Every query is scoped to your workspace. Retrieval filters by workspace before ranking, so another team\'s guidelines can never leak into your results.',
  },
  {
    title: 'Full audit trail',
    text: 'Every submission, decision, comment and approval is recorded with who did it and when.',
  },
]

export default function HelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-brand-100 px-5 py-4">
          <div>
            <h2 id="help-title" className="text-lg font-bold text-brand-900">
              How BrandShield AI works
            </h2>
            <p className="mt-0.5 text-sm text-gray-600">
              A two-minute tour of the workflow, the features, and why it is different.
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="btn-ghost shrink-0 px-2 py-1 text-xl leading-none"
            aria-label="Close help"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-5">
          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              What this app does
            </h3>
            <p className="mt-2 text-sm text-gray-700">
              BrandShield AI checks content <em>before</em> it is published against an
              organisation's approved brand guidelines, approved facts, terminology and visual
              identity. It does not publish anything and it does not rewrite your draft behind
              your back. It shows you what is wrong, why, and where the rule comes from — then a
              human decides.
            </p>
          </section>

          <section className="mt-6">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              The workflow
            </h3>
            <ol className="mt-3 space-y-3">
              {WORKFLOW.map((step) => (
                <li key={step.n} className="flex gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-bold text-white">
                    {step.n}
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-charcoal">{step.title}</div>
                    <p className="mt-0.5 text-sm text-gray-600">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="mt-6">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Key features
            </h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {FEATURES.map((f) => (
                <div key={f.title} className="rounded-lg border border-brand-100 bg-brand-50/50 p-3">
                  <div className="text-sm font-semibold text-brand-900">{f.title}</div>
                  <p className="mt-1 text-sm text-gray-700">{f.text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-6 rounded-lg border border-gold-400/40 bg-amber-50 p-4">
            <h3 className="text-sm font-semibold text-amber-900">Why it stands out</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-amber-900">
              <li>
                • <strong>It shows its evidence.</strong> Most checkers give a verdict. This one
                gives the approved quote behind every finding, or admits it has none.
              </li>
              <li>
                • <strong>It degrades honestly.</strong> If the AI call fails or times out, the
                deterministic checks still return findings and the screen says exactly what
                happened — never a blank page.
              </li>
              <li>
                • <strong>It never overstates.</strong> Unsupported claims are marked "Needs
                human verification", not "false". Only a contradicting approved source earns the
                word "contradicted".
              </li>
              <li>
                • <strong>It respects the human.</strong> Every fix is a proposal. Nothing is
                auto-applied, and an approval covers one exact version only.
              </li>
              <li>
                • <strong>It is usable with no help.</strong> Three demo roles, pre-seeded data
                and sample drafts mean a stranger can run the whole loop in under two minutes.
              </li>
            </ul>
          </section>

          <section className="mt-6">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Try it in this order
            </h3>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-gray-700">
              <li>Click <strong>Try as Creator</strong>, then <strong>New submission</strong>.</li>
              <li>Load the <strong>LinkedIn launch post</strong> sample and press <strong>Run review</strong>.</li>
              <li>Click a highlight, then <strong>Accept fix</strong> on a few findings.</li>
              <li>Press <strong>Create revised draft</strong>, then <strong>Submit for approval</strong>.</li>
              <li>Switch to <strong>Try as Approver</strong> and approve that version.</li>
            </ol>
          </section>
        </div>

        <div className="border-t border-brand-100 px-5 py-3">
          <button type="button" className="btn-primary w-full sm:w-auto" onClick={onClose}>
            Got it — let me try
          </button>
        </div>
      </div>
    </div>
  )
}
