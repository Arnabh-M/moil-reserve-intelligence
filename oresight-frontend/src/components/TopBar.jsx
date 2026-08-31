import React from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, Search, Calendar } from 'lucide-react';

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
    <header className="sticky top-0 z-40 h-16 bg-white/80 backdrop-blur-md border-b border-border flex items-center justify-between px-6">
      <div>
        <h1 className="text-lg font-bold text-text-primary">{title}</h1>
        <p className="text-[11px] text-text-muted -mt-0.5">MOIL Manganese Reserve Intelligence</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="flex items-center gap-2 bg-bg rounded-lg px-3 py-1.5 border border-border">
          <Search size={14} className="text-text-muted" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent text-sm text-text-primary outline-none w-40 placeholder:text-text-muted"
          />
        </div>

        {/* Date indicator */}
        <div className="flex items-center gap-1.5 text-xs text-text-muted bg-bg rounded-lg px-3 py-2 border border-border">
          <Calendar size={13} />
          <span>Aug 2026</span>
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-bg transition-colors">
          <Bell size={18} className="text-text-secondary" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-orange rounded-full" />
        </button>

        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal to-teal/70 flex items-center justify-center text-white text-xs font-bold">
          TG
        </div>
      </div>
    </header>
  );
}
