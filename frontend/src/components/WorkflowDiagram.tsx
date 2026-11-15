import { Fragment } from 'react'

type Tone = 'brand' | 'gold' | 'charcoal'

interface Node {
  title: string
  person: string
  action: string
  icon: 'pencil' | 'shield' | 'eye' | 'stamp'
  tone: Tone
}

const NODES: Node[] = [
  {
    title: 'Creator',
    person: 'Priya Raman',
    action: 'Writes the draft',
    icon: 'pencil',
    tone: 'brand',
  },
  {
    title: 'BrandShield AI',
    person: 'Automatic check',
    action: 'Finds issues + sources',
    icon: 'shield',
    tone: 'gold',
  },
  {
    title: 'Manager',
    person: 'Arun Mehta',
    action: 'Reviews & edits',
    icon: 'eye',
    tone: 'brand',
  },
  {
    title: 'Approver',
    person: 'Rohan Iyer',
    action: 'Approves or rejects',
    icon: 'stamp',
    tone: 'charcoal',
  },
]

const TONE_BG: Record<Tone, string> = {
  brand: 'bg-brand-700',
  gold: 'bg-gold-500',
  charcoal: 'bg-charcoal',
}

const TONE_RING: Record<Tone, string> = {
  brand: 'ring-brand-200',
  gold: 'ring-gold-400/60',
  charcoal: 'ring-gray-300',
}

function Icon({ name }: { name: Node['icon'] }) {
  const common = {
    className: 'h-5 w-5',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  if (name === 'pencil') {
    return (
      <svg {...common}>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
      </svg>
    )
  }
  if (name === 'shield') {
    return (
      <svg {...common}>
        <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    )
  }
  if (name === 'eye') {
    return (
      <svg {...common}>
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    )
  }
  return (
    <svg {...common}>
      <path d="M9 12l2 2 4-4" />
      <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function Arrow() {
  return (
    <div className="flex items-center justify-center py-1 sm:px-1 sm:py-0" aria-hidden="true">
      <svg
        className="h-6 w-6 rotate-90 text-brand-400 sm:rotate-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M5 12h14" />
        <path d="M13 6l6 6-6 6" />
      </svg>
    </div>
  )
}

function NodeCard({ node, index }: { node: Node; index: number }) {
  return (
    <div
      className={`relative flex h-full flex-col rounded-xl border border-brand-100 bg-white p-3.5 shadow-sm ring-1 ${TONE_RING[node.tone]}`}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${TONE_BG[node.tone]} text-white`}
        >
          <Icon name={node.icon} />
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold text-gray-400">{index + 1}</span>
            <span className="truncate text-sm font-bold text-charcoal">{node.title}</span>
          </div>
          <div className="truncate text-[11px] text-gray-500">{node.person}</div>
        </div>
      </div>
      <p className="mt-2 text-[13px] leading-snug text-gray-700">{node.action}</p>
    </div>
  )
}

export default function WorkflowDiagram() {
  return (
    <div className="rounded-2xl border border-brand-100 bg-white/70 p-4 sm:p-6">
      {/* --- the main flow --- */}
      <div className="grid gap-1 sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:items-stretch sm:gap-0">
        {NODES.map((node, i) => (
          <Fragment key={node.title}>
            <NodeCard node={node} index={i} />
            {i < NODES.length - 1 && <Arrow />}
          </Fragment>
        ))}
      </div>

      {/* --- outcome --- */}
      <div className="mt-3 flex items-center justify-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-center">
        <svg
          className="h-4 w-4 shrink-0 text-brand-700"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M20 6L9 17l-5-5" />
        </svg>
        <span className="text-xs font-semibold text-brand-900">
          Approved version is ready to publish — a human made that call
        </span>
      </div>

      {/* --- loop back --- */}
      <div className="mt-3 flex items-start gap-2 rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-2">
        <svg
          className="mt-0.5 h-4 w-4 shrink-0 text-amber-700"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M3 12a9 9 0 019-9 9 9 0 018 5" />
          <path d="M20 3v5h-5" />
        </svg>
        <p className="text-xs text-amber-900">
          <strong className="font-semibold">Changes requested?</strong> The version goes back to
          the Creator. Any edit creates a new version, so the old approval no longer applies.
        </p>
      </div>
    </div>
  )
}
