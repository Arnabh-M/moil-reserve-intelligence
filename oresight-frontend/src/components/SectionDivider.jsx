import React from 'react';

export default function SectionDivider({ label, className = '' }) {
  if (label) {
    return (
      <div className={`flex items-center my-8 ${className}`} role="separator">
        <div className="flex-1 border-t border-[var(--divider)]" />
        <span className="px-3 text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wider">
          {label}
        </span>
        <div className="flex-1 border-t border-[var(--divider)]" />
      </div>
    );
  }

  return <div className={`my-8 border-t border-[var(--divider)] ${className}`} role="separator" />;
}
