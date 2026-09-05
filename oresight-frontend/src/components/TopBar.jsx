import React from 'react';
import { useLocation } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';

const pageTitles = {
  '/': 'Dashboard',
  '/production': 'Production',
  '/reserves': 'Reserves & Deposits',
  '/equipment': 'Equipment',
  '/risks': 'Risk & Alerts',
  '/simulator': 'What-If Simulator',
  '/recommendations': 'AI Recommendations',
  '/timeline': 'Event Timeline',
  '/data-input': 'Data Input',
  '/map': 'Reserve Intelligence Map',
  '/blasting': 'Blast Planning',
  '/geology': 'Geology & Exploration',
  '/reports': 'Reports',
  '/settings': 'Settings',
};

export default function TopBar() {
  const location = useLocation();
  const title = pageTitles[location.pathname]
    || (location.pathname.startsWith('/site/') ? 'Site Detail' : 'OreSight');

  return (
    <header className="sticky top-0 z-40 h-16 bg-[var(--bg-primary)]/90 backdrop-blur-md border-b border-[var(--divider)] flex items-center justify-between px-8 transition-colors duration-150">
      <div>
        <h1 className="text-base font-semibold text-[var(--text-primary)]">{title}</h1>
        <p className="text-[11px] text-[var(--text-muted)] -mt-0.5">MOIL Manganese Reserve Intelligence</p>
      </div>

      <div className="flex items-center gap-4">
        <ThemeToggle />
        <div className="w-8 h-8 rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)] flex items-center justify-center text-xs font-semibold">
          TG
        </div>
      </div>
    </header>
  );
}
