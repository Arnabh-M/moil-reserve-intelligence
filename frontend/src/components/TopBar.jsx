import { useLocation } from 'react-router-dom'
import { Bell, CircleUser, Radio } from 'lucide-react'

const TITLES = {
  '/': 'Command Center',
  '/map': 'Map',
  '/simulator': 'Simulator',
  '/timeline': 'Timeline',
  '/recommendations': 'Recommendations',
  '/data-input': 'Data Input',
  '/reports': 'Reports',
}

function resolveTitle(pathname) {
  if (TITLES[pathname]) return TITLES[pathname]
  if (pathname.startsWith('/site/')) return 'Site Detail'
  return 'OreSight'
}

export default function TopBar() {
  const location = useLocation()
  const title = resolveTitle(location.pathname)

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-white px-6">
      <h1 className="font-heading text-base font-semibold leading-none text-navy">{title}</h1>

      <div className="flex items-center gap-5">
        <div className="hidden sm:flex items-center gap-2 rounded-sm border border-border bg-bg px-3 py-2 text-xs font-medium text-slate-600">
          <Radio size={13} strokeWidth={2.5} className="text-teal" />
          Systems Nominal
        </div>

        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-9 w-9 items-center justify-center rounded-sm text-slate-500 hover:bg-slate-100 hover:text-navy transition-colors"
        >
          <Bell size={18} strokeWidth={2} />
          <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-orange" />
        </button>

        <div className="flex items-center gap-3 border-l border-border pl-4">
          <CircleUser size={28} strokeWidth={1.5} className="text-navy2" />
          <div className="hidden sm:block leading-tight">
            <div className="text-xs font-semibold text-navy">Production Planner</div>
            <div className="text-[11px] text-slate-500">MOIL Ops</div>
          </div>
        </div>
      </div>
    </header>
  )
}
