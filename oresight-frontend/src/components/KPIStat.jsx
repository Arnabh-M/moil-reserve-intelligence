import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function KPIStat({
  label,
  value,
  delta,
  deltaLabel,
  icon: Icon,
  className = '',
}) {
  const isPositive = typeof delta === 'number' && delta > 0;
  const isNegative = typeof delta === 'number' && delta < 0;

  const deltaColor = isPositive
    ? 'text-[var(--success)]'
    : isNegative
    ? 'text-[var(--critical)]'
    : 'text-[var(--text-muted)]';

  const DeltaIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;

  return (
    <div
      className={`bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] p-4 flex flex-col justify-between transition-all duration-150 min-w-0 ${className}`}
    >
      {/* Top row: Small Inter Label + subtle icon */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] truncate">
          {label}
        </span>
        {Icon && (
          <div className="w-6 h-6 rounded-md bg-[var(--accent-soft)] flex items-center justify-center text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] shrink-0">
            <Icon size={13} strokeWidth={2} />
          </div>
        )}
      </div>

      {/* Middle row: Large Mono Stat Number */}
      <div className="flex items-baseline gap-2 flex-wrap my-1">
        <span className="font-mono text-2xl sm:text-3xl font-bold text-[var(--text-primary)] leading-none tracking-tight">
          {value}
        </span>
        {delta !== undefined && delta !== null && (
          <span className={`inline-flex items-center gap-0.5 text-xs font-semibold font-mono ${deltaColor}`}>
            {isPositive ? '+' : ''}
            {delta}%
            <DeltaIcon size={12} strokeWidth={2.5} />
          </span>
        )}
      </div>

      {/* Bottom row: Subtitle */}
      {deltaLabel && (
        <div className="text-[11px] text-[var(--text-subtle)] font-normal mt-1.5 leading-tight truncate">
          {deltaLabel}
        </div>
      )}
    </div>
  );
}

