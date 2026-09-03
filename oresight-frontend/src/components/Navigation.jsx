import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  ChevronDown,
  Mountain,
  Search,
  Calendar,
  Bell,
  Server,
  Database,
  Map as MapIcon,
  Layers,
  MapPin,
  ClipboardEdit,
  Bomb,
  FlaskRound,
  Clock,
  Lightbulb,
  FileText,
} from 'lucide-react';
import { USE_MOCK, setUseMock, subscribeUseMock } from '../api/client';
import toast from 'react-hot-toast';
import ThemeToggle from './ThemeToggle';

const NAV_STRUCTURE = [
  {
    type: 'link',
    label: 'Dashboard',
    to: '/',
    exact: true,
  },
  {
    type: 'dropdown',
    label: 'Reserve & Geology',
    items: [
      {
        to: '/map',
        label: 'Reserve Intelligence Map',
        icon: MapIcon,
      },
      {
        to: '/geology',
        label: 'Geological Structure & Cross-Section',
        icon: Layers,
      },
    ],
  },
  {
    type: 'dropdown',
    label: 'Site Operations',
    items: [
      {
        to: '/site/balaghat',
        label: 'Site Performance',
        icon: MapPin,
      },
      {
        to: '/data-input',
        label: 'Field Data Entry',
        icon: ClipboardEdit,
      },
    ],
  },
  {
    type: 'dropdown',
    label: 'Planning & Simulation',
    items: [
      {
        to: '/blasting',
        label: 'Blast Schedule',
        icon: Bomb,
      },
      {
        to: '/simulator',
        label: 'Scenario Simulator',
        icon: FlaskRound,
      },
    ],
  },
  {
    type: 'dropdown',
    label: 'Risk & Reports',
    items: [
      {
        to: '/timeline',
        label: 'Risk Timeline',
        icon: Clock,
      },
      {
        to: '/recommendations',
        label: 'Corrective Actions',
        icon: Lightbulb,
      },
      {
        to: '/reports',
        label: 'Reports & Export',
        icon: FileText,
      },
    ],
  },
  {
    type: 'link',
    label: 'Settings',
    to: '/settings',
  },
];

export default function Navigation() {
  const location = useLocation();
  const [openDropdown, setOpenDropdown] = useState(null);
  const timeoutRef = useRef(null);
  const [mockActive, setMockActive] = useState(USE_MOCK);

  useEffect(() => {
    return subscribeUseMock(setMockActive);
  }, []);

  const handleMouseEnter = (label) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setOpenDropdown(label);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setOpenDropdown(null);
    }, 120);
  };

  const toggleMock = () => {
    const nextState = !mockActive;
    setUseMock(nextState);
    toast(
      <div>
        <p className="font-semibold text-xs">{nextState ? 'Mock Engine Active' : 'Live API Mode Active'}</p>
        <p className="text-[11px] opacity-80 mt-0.5">
          {nextState ? 'Simulating backend responses offline.' : 'Connecting to live FastAPI at http://localhost:8000.'}
        </p>
      </div>,
      { id: 'mode-toast' }
    );
  };

  const isCategoryActive = (category) => {
    if (category.type === 'link') {
      return category.exact ? location.pathname === category.to : location.pathname.startsWith(category.to);
    }
    return category.items.some((item) => {
      if (item.to.startsWith('/site/')) {
        return location.pathname.startsWith('/site/');
      }
      return location.pathname === item.to || (item.to === '/geology' && location.pathname === '/reserves');
    });
  };

  return (
    <header className="sticky top-0 z-50 bg-[var(--charcoal)] text-white border-b border-[var(--border)] shadow-xs transition-colors duration-180">
      <div className="max-w-[1560px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand Logo */}
        <NavLink to="/" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-8 h-8 rounded-[3px] bg-[var(--accent-primary)] flex items-center justify-center text-white shadow-xs group-hover:opacity-90 transition-opacity">
            <Mountain size={18} strokeWidth={2} />
          </div>
          <div className="leading-tight">
            <span className="font-heading font-bold text-base tracking-tight text-white block">OreSight</span>
            <span className="text-[9.5px] uppercase tracking-wider text-[var(--border)] block -mt-0.5 opacity-80">MOIL Intelligence</span>
          </div>
        </NavLink>

        {/* Center 6-Item Navigation Bar */}
        <nav className="hidden lg:flex items-center gap-1 h-full">
          {NAV_STRUCTURE.map((item) => {
            const active = isCategoryActive(item);

            if (item.type === 'link') {
              return (
                <NavLink
                  key={item.label}
                  to={item.to}
                  end={item.exact}
                  className={({ isActive }) =>
                    `relative px-4 py-2 text-xs font-semibold tracking-wide transition-colors flex items-center h-16 ${
                      isActive || active
                        ? 'text-white'
                        : 'text-[#D5CFBF] hover:text-white'
                    }`
                  }
                >
                  <span>{item.label}</span>
                  {active && (
                    <span className="absolute bottom-0 left-4 right-4 h-[2.5px] bg-[var(--accent-primary)]" />
                  )}
                </NavLink>
              );
            }

            const isOpen = openDropdown === item.label;

            return (
              <div
                key={item.label}
                className="relative h-16 flex items-center"
                onMouseEnter={() => handleMouseEnter(item.label)}
                onMouseLeave={handleMouseLeave}
              >
                <button
                  type="button"
                  className={`relative px-4 py-2 text-xs font-semibold tracking-wide transition-colors flex items-center gap-1.5 h-16 cursor-pointer ${
                    active || isOpen ? 'text-white' : 'text-[#D5CFBF] hover:text-white'
                  }`}
                  aria-expanded={isOpen}
                >
                  <span>{item.label}</span>
                  <ChevronDown
                    size={12}
                    className={`transition-transform duration-150 text-[#A5A096] ${
                      isOpen ? 'rotate-180 text-white' : ''
                    }`}
                  />
                  {active && (
                    <span className="absolute bottom-0 left-4 right-4 h-[2.5px] bg-[var(--accent-primary)]" />
                  )}
                </button>

                {/* Dropdown Menu (Label only, 12-16px breathing room, consistent 10px V / 16px H padding) */}
                {isOpen && (
                  <div
                    className="absolute top-full left-0 w-72 bg-[var(--bg-surface)] text-[var(--text-primary)] rounded-[3px] border border-[var(--border)] shadow-md p-3.5 z-50 animate-fade-in"
                    onMouseEnter={() => handleMouseEnter(item.label)}
                    onMouseLeave={handleMouseLeave}
                  >
                    <div className="space-y-1">
                      {item.items.map((sub) => {
                        const Icon = sub.icon;
                        const isSubActive =
                          location.pathname === sub.to ||
                          (sub.to.startsWith('/site/') && location.pathname.startsWith('/site/')) ||
                          (sub.to === '/geology' && location.pathname === '/reserves');

                        return (
                          <NavLink
                            key={sub.label}
                            to={sub.to}
                            onClick={() => setOpenDropdown(null)}
                            className={`flex items-center gap-3 px-4 py-2.5 h-10 min-h-[40px] rounded-[3px] text-xs font-semibold transition-colors duration-150 ${
                              isSubActive
                                ? 'bg-[var(--bg-primary)] text-[var(--accent-primary)] border-l-2 border-[var(--accent-primary)] font-bold'
                                : 'text-[var(--text-primary)] hover:bg-[var(--bg-primary)] hover:text-[var(--accent-primary)] border-l-2 border-transparent'
                            }`}
                          >
                            <Icon size={15} strokeWidth={1.75} className="shrink-0 text-[var(--text-muted)]" />
                            <span className="truncate text-left">{sub.label}</span>
                          </NavLink>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Right Chrome / Controls */}
        <div className="flex items-center gap-3">
          {/* Mock/Live API toggle */}
          <button
            onClick={toggleMock}
            title="Toggle between Mock and Live API (http://localhost:8000)"
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] border text-[11px] font-semibold transition-all duration-150 cursor-pointer ${
              mockActive
                ? 'bg-[var(--accent-primary)]/15 text-[#E08A97] border-[var(--accent-primary)]/40 hover:bg-[var(--accent-primary)]/25'
                : 'bg-[var(--success)]/20 text-[#A8C9A3] border-[var(--success)]/40 hover:bg-[var(--success)]/30'
            }`}
          >
            {mockActive ? <Database size={12} /> : <Server size={12} />}
            <span className="font-mono">{mockActive ? 'MOCK' : 'LIVE :8000'}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse ml-0.5" />
          </button>

          {/* Search */}
          <div className="hidden md:flex items-center gap-2 bg-[var(--bg-surface)] rounded-[3px] px-2.5 py-1.5 border border-[var(--border)]">
            <Search size={13} className="text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Search assets..."
              className="bg-transparent text-xs text-[var(--text-primary)] outline-none w-28 placeholder:text-[var(--text-muted)]"
            />
          </div>

          {/* Date Indicator */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-[var(--text-primary)] bg-[var(--bg-surface)] rounded-[3px] px-2.5 py-1.5 border border-[var(--border)]">
            <Calendar size={13} className="text-[var(--text-muted)]" />
            <span className="font-medium font-mono text-[11px]">Aug 2026</span>
          </div>

          {/* Theme Toggle (Light / Dark) */}
          <ThemeToggle />

          {/* Notifications */}
          <button className="relative p-2 rounded-[3px] text-[#D5CFBF] hover:text-white transition-colors cursor-pointer">
            <Bell size={16} strokeWidth={1.75} />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[var(--accent-primary)] rounded-full" />
          </button>

          {/* User Avatar */}
          <div className="w-7 h-7 rounded-[3px] bg-[var(--accent-secondary)] flex items-center justify-center text-white text-xs font-bold font-mono">
            TG
          </div>
        </div>
      </div>
    </header>
  );
}
