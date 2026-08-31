import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Factory,
  Mountain,
  Wrench,
  ShieldAlert,
  Bomb,
  FlaskConical,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  FlaskRound,
  Lightbulb,
  Clock,
  MapPin,
  ClipboardEdit,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/production', icon: Factory, label: 'Production' },
  { to: '/reserves', icon: Mountain, label: 'Reserves' },
  { to: '/equipment', icon: Wrench, label: 'Equipment' },
  { to: '/risks', icon: ShieldAlert, label: 'Risk & Alerts' },
  { type: 'divider' },
  { to: '/simulator', icon: FlaskRound, label: 'Simulator' },
  { to: '/recommendations', icon: Lightbulb, label: 'Recommendations' },
  { to: '/timeline', icon: Clock, label: 'Timeline' },
  { to: '/site/balaghat', icon: MapPin, label: 'Site Detail' },
  { to: '/data-input', icon: ClipboardEdit, label: 'Data Input' },
  { type: 'divider' },
  { to: '/blasting', icon: Bomb, label: 'Blast Planning' },
  { to: '/geology', icon: FlaskConical, label: 'Geology' },
  { to: '/reports', icon: FileText, label: 'Reports' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar({ collapsed, onToggle }) {
  return (
    <aside
      className={`fixed top-0 left-0 h-screen bg-navy flex flex-col transition-all duration-300 z-50 ${
        collapsed ? 'w-[68px]' : 'w-[240px]'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-white/10 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange to-orange-soft flex items-center justify-center shrink-0">
          <Mountain size={18} className="text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <span className="text-white font-bold text-sm tracking-wide">OreSight</span>
            <span className="block text-[10px] text-white/50 leading-tight">MOIL Intelligence</span>
          </div>
        )}
      </div>

      {/* Nav links */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item, idx) => {
          if (item.type === 'divider') {
            return (
              <div key={`div-${idx}`} className="my-2 mx-3 border-t border-white/10" />
            );
          }

          const { to, icon: Icon, label } = item;
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                  isActive
                    ? 'bg-white/10 text-orange-soft'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex items-center justify-center h-10 mx-2 mb-3 rounded-lg text-white/40 hover:text-white/80 hover:bg-white/5 transition-all duration-200"
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}
