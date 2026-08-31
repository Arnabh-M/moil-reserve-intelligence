import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Map as MapIcon,
  FlaskConical,
  ListTree,
  ClipboardList,
  FileInput,
  FileBarChart,
  Mountain,
} from 'lucide-react'

function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

const NAV_ITEMS = [
  { to: '/', label: 'Command Center', icon: LayoutDashboard, end: true },
  { to: '/map', label: 'Map', icon: MapIcon },
  { to: '/simulator', label: 'Simulator', icon: FlaskConical },
  { to: '/timeline', label: 'Timeline', icon: ListTree },
  { to: '/recommendations', label: 'Recommendations', icon: ClipboardList },
  { to: '/data-input', label: 'Data Input', icon: FileInput },
  { to: '/reports', label: 'Reports', icon: FileBarChart },
]

export default function Sidebar() {
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col bg-navy text-white/90">
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-white/10">
        <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-orange text-white">
          <Mountain size={18} strokeWidth={2.25} />
        </div>
        <div>
          <div className="font-heading text-[15px] font-semibold leading-none text-white">OreSight</div>
          <div className="text-[10px] uppercase tracking-wider text-white/50 mt-1">MOIL Reserve Intel</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-sm px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-white/10 text-white border-l-2 border-orange -ml-px pl-[11px]'
                  : 'text-white/60 hover:bg-white/5 hover:text-white/90'
              )
            }
          >
            <Icon size={17} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
