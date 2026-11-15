import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import HelpDialog from './HelpDialog'

const ROLE_LABEL: Record<string, string> = {
  creator: 'Creator',
  manager: 'Manager',
  approver: 'Approver',
  admin: 'Admin',
}

export default function Layout() {
  const { me, signOut } = useAuth()
  const navigate = useNavigate()
  const [helpOpen, setHelpOpen] = useState(false)

  const canReview = me?.role === 'manager' || me?.role === 'approver' || me?.role === 'admin'
  const canCreate = me?.role === 'creator' || me?.role === 'admin'

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
      isActive ? 'bg-brand-100 text-brand-900' : 'text-brand-800 hover:bg-brand-50'
    }`

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-brand-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-left"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700 text-sm font-bold text-white">
              BS
            </span>
            <span className="text-base font-bold tracking-tight text-brand-900">
              BrandShield <span className="text-gold-500">AI</span>
            </span>
          </button>

          <nav className="order-3 flex w-full flex-wrap items-center gap-1 sm:order-none sm:w-auto">
            <NavLink to="/dashboard" className={linkClass}>
              Dashboard
            </NavLink>
            {canCreate && (
              <NavLink to="/new" className={linkClass}>
                New submission
              </NavLink>
            )}
            {canReview && (
              <NavLink to="/queue" className={linkClass}>
                Review queue
              </NavLink>
            )}
            <NavLink to="/brand" className={linkClass}>
              Brand profile
            </NavLink>
            <NavLink to="/history" className={linkClass}>
              History
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {me && (
              <div className="hidden text-right sm:block">
                <div className="text-sm font-semibold leading-tight text-charcoal">
                  {me.display_name}
                </div>
                <div className="text-xs text-gray-500">
                  {ROLE_LABEL[me.role]} · {me.workspace_name}
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="btn-secondary h-10 w-10 justify-center px-0 text-xs sm:h-auto sm:w-auto sm:px-3 sm:py-2"
              aria-haspopup="dialog"
              aria-label="Help — how BrandShield AI works"
              title="How BrandShield AI works"
            >
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-700 text-[11px] font-bold text-white"
                aria-hidden="true"
              >
                ?
              </span>
              <span className="hidden sm:inline">Help</span>
            </button>

            <button
              type="button"
              className="btn-secondary h-10 w-10 justify-center px-0 text-xs sm:h-auto sm:w-auto sm:px-3 sm:py-2"
              onClick={() => {
                signOut()
                navigate('/')
              }}
              aria-label="Switch role — leave this role and pick another demo role"
              title="Leave this role and pick another demo role"
            >
              <svg
                className="h-5 w-5 sm:h-4 sm:w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M16 3h5v5" />
                <path d="M21 3l-7 7" />
                <path d="M8 21H3v-5" />
                <path d="M3 21l7-7" />
              </svg>
              <span className="hidden sm:inline">Switch role</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-brand-100 bg-white px-4 py-4 text-center text-xs text-gray-500">
        BrandShield AI · demo workspace with fictional data · nothing is auto-published
      </footer>

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
