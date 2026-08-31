import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, Search, Calendar, Server, Database } from 'lucide-react';
import { isMockEnabled, setMockEnabled, subscribeMockState } from '../api/config';
import { useToast } from '../context/ToastContext';

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

  const [mockActive, setMockActive] = useState(isMockEnabled());
  const { addToast } = useToast();

  useEffect(() => {
    return subscribeMockState(setMockActive);
  }, []);

  const toggleMock = () => {
    const nextState = !mockActive;
    setMockEnabled(nextState);
    addToast({
      type: nextState ? 'info' : 'success',
      title: nextState ? 'Mock Mode Enabled' : 'Live API Mode Enabled',
      message: nextState
        ? 'Using realistic seeded in-memory responses for offline testing.'
        : 'Connecting to live FastAPI backend at http://localhost:8000.',
    });
  };

  return (
    <header className="sticky top-0 z-40 h-16 bg-white/80 backdrop-blur-md border-b border-border flex items-center justify-between px-6">
      <div>
        <h1 className="text-lg font-bold text-text-primary">{title}</h1>
        <p className="text-[11px] text-text-muted -mt-0.5">MOIL Manganese Reserve Intelligence</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Mock/Live API toggle button */}
        <button
          onClick={toggleMock}
          title={`Click to switch between Mock and Live API (http://localhost:8000)`}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all duration-200 cursor-pointer ${
            mockActive
              ? 'bg-amber-500/10 text-amber-600 border-amber-500/20 hover:bg-amber-500/15'
              : 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/15'
          }`}
        >
          {mockActive ? <Database size={13} /> : <Server size={13} />}
          <span>{mockActive ? 'MOCK MODE' : 'LIVE API :8000'}</span>
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse ml-0.5" />
        </button>

        {/* Search */}
        <div className="flex items-center gap-2 bg-bg rounded-lg px-3 py-1.5 border border-border">
          <Search size={14} className="text-text-muted" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent text-sm text-text-primary outline-none w-36 placeholder:text-text-muted"
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
