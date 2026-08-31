import React from 'react';
import { useLocation } from 'react-router-dom';
import { Construction } from 'lucide-react';

const pageTitles = {
  '/map': 'Operational Map',
  '/blasting': 'Blast Planning',
  '/geology': 'Geology & Exploration',
  '/settings': 'Settings',
};

export default function ComingSoon() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Coming Soon';

  return (
    <div className="page-container flex items-center justify-center min-h-[calc(100vh-8rem)]">
      <div className="text-center animate-fade-in">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-orange/10 flex items-center justify-center">
          <Construction size={28} className="text-orange" />
        </div>
        <h2 className="text-xl font-bold text-text-primary mb-2">{title}</h2>
        <p className="text-sm text-text-secondary max-w-md mx-auto">
          This module is under active development and will be available in the next sprint.
          Your teammates are building this right now!
        </p>
        <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-bg border border-border text-xs text-text-muted">
          <span className="w-2 h-2 rounded-full bg-orange animate-pulse" />
          Day 2-3 deliverable
        </div>
      </div>
    </div>
  );
}
