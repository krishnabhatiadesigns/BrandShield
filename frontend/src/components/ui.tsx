import type { ReactNode } from 'react'
import type { EvidenceStatus, Severity } from '../types'

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  )
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-gray-500" role="status">
      <Spinner className="h-5 w-5 text-brand-600" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div
      className="flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn-secondary shrink-0" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-14 text-center">
      <h3 className="text-base font-semibold text-charcoal">{title}</h3>
      {children && <p className="max-w-md text-sm text-gray-600">{children}</p>}
      {action}
    </div>
  )
}

const SEVERITY_STYLES: Record<Severity, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-sky-100 text-sky-800',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`badge ${SEVERITY_STYLES[severity]}`}>
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  )
}

const EVIDENCE_STYLES: Record<EvidenceStatus, { cls: string; label: string }> = {
  supported: { cls: 'bg-brand-100 text-brand-800', label: 'Supported' },
  contradicted: { cls: 'bg-red-100 text-red-800', label: 'Contradicted' },
  unsupported: { cls: 'bg-orange-100 text-orange-800', label: 'Unsupported' },
  needs_verification: { cls: 'bg-purple-100 text-purple-800', label: 'Needs human verification' },
}

export function EvidenceBadge({ status }: { status: EvidenceStatus }) {
  const style = EVIDENCE_STYLES[status] ?? EVIDENCE_STYLES.needs_verification
  return <span className={`badge ${style.cls}`}>{style.label}</span>
}

const STATUS_STYLES: Record<string, string> = {
  Draft: 'bg-gray-100 text-gray-700',
  'AI Review Complete': 'bg-sky-100 text-sky-800',
  'Changes Required': 'bg-amber-100 text-amber-800',
  Resubmitted: 'bg-indigo-100 text-indigo-800',
  'Manager Review': 'bg-indigo-100 text-indigo-800',
  'Approver Review': 'bg-purple-100 text-purple-800',
  Approved: 'bg-brand-100 text-brand-800',
  Rejected: 'bg-red-100 text-red-800',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-700'}`}>
      {status}
    </span>
  )
}

export function Diff({ before, after }: { before: string; after: string }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <div className="rounded-lg border border-red-200 bg-red-50 p-2.5">
        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-red-700">
          Before
        </div>
        <p className="whitespace-pre-wrap break-words text-sm text-red-900">{before}</p>
      </div>
      <div className="rounded-lg border border-brand-200 bg-brand-50 p-2.5">
        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-brand-700">
          After
        </div>
        <p className="whitespace-pre-wrap break-words text-sm text-brand-900">{after}</p>
      </div>
    </div>
  )
}
