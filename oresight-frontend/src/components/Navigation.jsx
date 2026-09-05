import React, { useState, useRef } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  ChevronDown,
  Mountain,
  Map as MapIcon,
  Layers,
  MapPin,
  ClipboardEdit,
  Bomb,
  FlaskRound,
  Clock,
  Lightbulb,
  FileText,
  Compass,
  Radio,
} from 'lucide-react';
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
        label: 'Geological Structure & Deposit Cross-Section',
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
        label: 'Site Performance Telemetry',
        icon: MapPin,
      },
      {
        to: '/data-input',
        label: 'Field Operations Data Entry',
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
        label: 'Blast Schedule & Planning',
        icon: Bomb,
      },
      {
        to: '/simulator',
        label: 'Digital Twin Scenario Simulator',
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
        label: 'Risk Anomaly Timeline',
        icon: Clock,
      },
      {
        to: '/recommendations',
        label: 'AI Mitigation Recommendations',
        icon: Lightbulb,
      },
      {
        to: '/reports',
        label: 'Geological Reports & Export',
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
  const [selectedRegion, setSelectedRegion] = useState('All Sectors');
  const [showRegionDropdown, setShowRegionDropdown] = useState(false);
  const timeoutRef = useRef(null);

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
    <header className="sticky top-0 z-50 bg-[var(--bg-primary)]/95 backdrop-blur-md text-[var(--text-primary)] border-b border-[var(--divider)] transition-colors duration-150">
      <div className="max-w-[1600px] mx-auto px-8 h-[68px] flex items-center justify-between gap-6">
        
        {/* Left: Brand Identity + Region Selector */}
        <div className="flex items-center gap-6 shrink-0">
          <NavLink to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-lg bg-[var(--forest-primary)] text-white flex items-center justify-center shadow-xs group-hover:opacity-90 transition-opacity">
              <Mountain size={19} strokeWidth={2} />
            </div>
            <div className="leading-tight">
              <span className="font-mono font-bold text-sm tracking-tight text-[var(--text-primary)] block">OreSight</span>
              <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block font-medium">MOIL Intelligence</span>
            </div>
          </NavLink>

          {/* Region Selector */}
          <div className="relative hidden md:block border-l border-[var(--divider)] pl-6">
            <button
              type="button"
              onClick={() => setShowRegionDropdown(!showRegionDropdown)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)] text-xs font-medium text-[var(--text-primary)] hover:border-[var(--forest-secondary)] transition-colors cursor-pointer"
            >
              <Compass size={14} className="text-[var(--forest-secondary)]" />
              <span>{selectedRegion}</span>
              <ChevronDown size={12} className="text-[var(--text-muted)]" />
            </button>

            {showRegionDropdown && (
              <div className="absolute top-full left-6 mt-1 w-56 bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] shadow-lg p-1.5 z-50 animate-fade-in">
                {['All Sectors', 'Balaghat Manganese Belt', 'Nagpur-Bhandara Belt'].map((reg) => (
                  <button
                    key={reg}
                    onClick={() => {
                      setSelectedRegion(reg);
                      setShowRegionDropdown(false);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      selectedRegion === reg
                        ? 'bg-[var(--accent-soft)] text-[var(--forest-primary)] font-semibold'
                        : 'text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'
                    }`}
                  >
                    {reg}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Center Navigation Links */}
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
                    `relative px-3.5 py-2 text-xs font-medium transition-colors flex items-center h-[68px] ${
                      isActive || active
                        ? 'text-[var(--forest-primary)] font-semibold dark:text-[var(--forest-secondary)]'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`
                  }
                >
                  <span>{item.label}</span>
                  {active && (
                    <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-[var(--forest-primary)] dark:bg-[var(--forest-secondary)] rounded-full" />
                  )}
                </NavLink>
              );
            }

            const isOpen = openDropdown === item.label;

            return (
              <div
                key={item.label}
                className="relative h-[68px] flex items-center"
                onMouseEnter={() => handleMouseEnter(item.label)}
                onMouseLeave={handleMouseLeave}
              >
                <button
                  type="button"
                  className={`relative px-3.5 py-2 text-xs font-medium transition-colors flex items-center gap-1.5 h-[68px] cursor-pointer ${
                    active || isOpen
                      ? 'text-[var(--forest-primary)] font-semibold dark:text-[var(--forest-secondary)]'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                  aria-expanded={isOpen}
                >
                  <span>{item.label}</span>
                  <ChevronDown
                    size={13}
                    className={`transition-transform duration-150 text-[var(--text-muted)] ${
                      isOpen ? 'rotate-180 text-[var(--text-primary)]' : ''
                    }`}
                  />
                  {active && (
                    <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-[var(--forest-primary)] dark:bg-[var(--forest-secondary)] rounded-full" />
                  )}
                </button>

                {/* Dropdown Menu */}
                {isOpen && (
                  <div
                    className="absolute top-full left-0 w-72 bg-[var(--bg-surface)] text-[var(--text-primary)] rounded-xl border border-[var(--border)] shadow-xl p-2 z-50 animate-fade-in"
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
                            className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                              isSubActive
                                ? 'bg-[var(--accent-soft)] text-[var(--forest-primary)] font-semibold dark:text-[var(--forest-secondary)]'
                                : 'text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'
                            }`}
                          >
                            <Icon
                              size={16}
                              className={`shrink-0 ${
                                isSubActive ? 'text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]' : 'text-[var(--text-muted)]'
                              }`}
                            />
                            <span className="truncate">{sub.label}</span>
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

        {/* Right Controls: Freshness Indicator, Theme Toggle, User Profile */}
        <div className="flex items-center gap-4 shrink-0">
          <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--bg-secondary)] border border-[var(--border)] text-[11px] font-mono text-[var(--text-muted)]">
            <Radio size={12} className="text-[var(--success)] animate-pulse" />
            <span>Telemetry Active</span>
          </div>
          <ThemeToggle />
          <div className="w-8 h-8 rounded-lg bg-[var(--forest-primary)] text-white flex items-center justify-center text-xs font-mono font-bold">
            MO
          </div>
        </div>

      </div>
    </header>
  );
}

