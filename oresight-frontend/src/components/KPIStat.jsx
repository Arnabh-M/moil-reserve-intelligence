import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function KPIStat({ label, value, delta, deltaLabel, icon: Icon, color = 'teal', className = '' }) {
  const colorMap = {
    teal: 'bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)]',
    orange: 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]',
    navy: 'bg-[var(--charcoal)]/15 text-[var(--text-primary)]',
    success: 'bg-[var(--success)]/15 text-[var(--success)]',
    danger: 'bg-[var(--warning)]/15 text-[var(--warning)]',
    warning: 'bg-[var(--warning)]/15 text-[var(--warning)]',
  };

  const deltaColor =
    delta > 0 ? 'text-[var(--success)]' : delta < 0 ? 'text-[var(--warning)]' : 'text-[var(--text-muted)]';
  const DeltaIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;

  return (
    <div className={`bg-[var(--bg-surface)] rounded-[3px] border border-[var(--border)] p-5 transition-colors duration-180 hover:border-[var(--accent-primary)] ${className}`}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-wider">
          {label}
        </span>
        {Icon && (
          <div className={`p-1.5 rounded-[3px] ${colorMap[color] || colorMap.teal}`}>
            <Icon size={15} strokeWidth={1.75} />
          </div>
        )}
      </div>
      <div className="font-heading text-2xl font-bold text-[var(--text-primary)] tracking-tight">{value}</div>
      {(delta !== undefined || deltaLabel) && (
        <div className="flex items-center gap-1 mt-1 font-mono text-xs">
          {delta !== undefined && delta !== null && (
            <span className={`flex items-center gap-0.5 font-bold ${deltaColor}`}>
              <DeltaIcon size={12} strokeWidth={2} />
              {Math.abs(delta)}%
            </span>
          )}
          {deltaLabel && (
            <span className="text-[var(--text-muted)] font-sans">{deltaLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}
