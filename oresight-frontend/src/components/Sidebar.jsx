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
  Map as MapIcon,
} from 'lucide-react';

const navSections = [
  {
    title: 'Core Telemetry',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/production', icon: Factory, label: 'Production' },
      { to: '/reserves', icon: Mountain, label: 'Reserves' },
      { to: '/equipment', icon: Wrench, label: 'Equipment' },
      { to: '/risks', icon: ShieldAlert, label: 'Risk & Alerts' },
      { to: '/map', icon: MapIcon, label: 'Map View' },
    ],
  },
  {
    title: 'Intelligence & Sim',
    items: [
      { to: '/simulator', icon: FlaskRound, label: 'Simulator' },
      { to: '/recommendations', icon: Lightbulb, label: 'AI Insights' },
      { to: '/timeline', icon: Clock, label: 'Event Timeline' },
      { to: '/site/balaghat', icon: MapPin, label: 'Site Detail' },
      { to: '/data-input', icon: ClipboardEdit, label: 'Field Data Input' },
    ],
  },
  {
    title: 'Operations & Reports',
    items: [
      { to: '/blasting', icon: Bomb, label: 'Blast Planning' },
      { to: '/geology', icon: FlaskConical, label: 'Geology' },
      { to: '/reports', icon: FileText, label: 'Reports' },
      { to: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
];

export default function Sidebar({ collapsed, onToggle }) {
  return (
    <aside
      className={`fixed top-0 left-0 h-screen bg-[var(--bg-surface)] border-r border-[var(--divider)] flex flex-col transition-all duration-300 z-50 shadow-sm ${
        collapsed ? 'w-[72px]' : 'w-[260px]'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 h-20 border-b border-[var(--divider)] shrink-0">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shrink-0 shadow-md shadow-blue-500/20">
          <Mountain size={20} className="text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <span className="text-[var(--text-primary)] font-bold text-base tracking-tight font-mono">OreSight</span>
            <span className="block text-[11px] text-[var(--text-muted)] font-mono leading-tight mt-0.5">MOIL Intelligence</span>
          </div>
        )}
      </div>

      {/* Nav links grouped by section */}
      <nav className="flex-1 py-6 px-3 space-y-6 overflow-y-auto custom-scrollbar">
        {navSections.map((section, sIdx) => (
          <div key={sIdx} className="space-y-1.5">
            {!collapsed && (
              <div className="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-[var(--text-subtle)] font-mono">
                {section.title}
              </div>
            )}
            {section.items.map((item) => {
              const { to, icon: Icon, label } = item;
              return (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3.5 px-3.5 py-3 rounded-xl text-sm font-medium transition-all duration-150 font-mono group ${
                      isActive
                        ? 'bg-[var(--accent-primary)] text-white shadow-md shadow-blue-500/20 font-semibold'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--accent-soft)]'
                    }`
                  }
                >
                  <Icon size={19} className="shrink-0 transition-transform duration-150 group-hover:scale-105" />
                  {!collapsed && <span className="truncate leading-normal">{label}</span>}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="p-3 border-t border-[var(--divider)] shrink-0">
        <button
          onClick={onToggle}
          className="flex items-center justify-center w-full h-10 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--accent-soft)] transition-all duration-200 cursor-pointer"
          title={collapsed ? "Expand menu" : "Collapse menu"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
  );
}
