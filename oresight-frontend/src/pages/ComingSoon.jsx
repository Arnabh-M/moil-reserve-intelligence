import React from 'react';
import { useLocation } from 'react-router-dom';
import { Construction } from 'lucide-react';

const pageTitles = {
  '/map': 'Reserve Intelligence Map',
  '/blasting': 'Blast Schedule',
  '/geology': 'Geological Structure & Cross-Section',
  '/settings': 'Settings',
};

export default function ComingSoon() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Coming Soon';

  return (
    <div className="page-container flex items-center justify-center min-h-[calc(100vh-8rem)]">
      <div className="text-center animate-fade-in border border-border bg-bg-surface rounded-[3px] p-8 max-w-lg shadow-none">
        <div className="w-14 h-14 mx-auto mb-4 rounded-[3px] bg-[#B5651D]/10 flex items-center justify-center">
          <Construction size={26} className="text-[#B5651D]" strokeWidth={1.75} />
        </div>
        <h2 className="font-heading text-xl font-bold text-text-primary mb-2">{title}</h2>
        <p className="text-xs text-text-secondary max-w-md mx-auto leading-relaxed">
          This module is under active development and scheduled for deployment in the upcoming reserve modeling phase.
        </p>
        <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-[3px] bg-bg border border-border text-[11px] font-mono text-text-muted">
          <span className="w-2 h-2 rounded-full bg-[#B5651D] animate-pulse" />
          MOIL Sprint Phase 2
        </div>
      </div>
    </div>
  );
}
