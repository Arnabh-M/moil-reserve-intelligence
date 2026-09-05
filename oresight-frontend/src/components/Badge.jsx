import React from 'react';

const variants = {
  operational: 'bg-[var(--success)]/12 text-[var(--success)]',
  up: 'bg-[var(--success)]/12 text-[var(--success)]',
  completed: 'bg-[var(--success)]/12 text-[var(--success)]',
  confirmed: 'bg-[var(--success)]/12 text-[var(--success)]',
  planned: 'bg-[var(--accent-soft)] text-[var(--accent-primary)]',
  delayed: 'bg-[var(--warning-medium)]/12 text-[var(--warning-medium)]',
  warning: 'bg-[var(--warning-medium)]/12 text-[var(--warning-medium)]',
  medium: 'bg-[var(--warning-medium)]/12 text-[var(--warning-medium)]',
  down: 'bg-[var(--critical)]/12 text-[var(--critical)]',
  critical: 'bg-[var(--critical)]/12 text-[var(--critical)]',
  high: 'bg-[var(--critical)]/12 text-[var(--critical)]',
  low: 'bg-[var(--text-muted)]/12 text-[var(--text-muted)]',
  unconfirmed: 'bg-[var(--text-muted)]/12 text-[var(--text-muted)]',
  info: 'bg-[var(--accent-soft)] text-[var(--accent-primary)]',
  orange: 'bg-[var(--accent-soft)] text-[var(--accent-primary)]',
};

export default function Badge({ variant = 'info', children, dot = false, className = '' }) {
  const classes = variants[variant] || variants.info;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium transition-colors ${classes} ${className}`}
    >
      {dot && (
        <span className="w-1.5 h-1.5 rounded-full bg-current opacity-90 animate-pulse" />
      )}
      {children}
    </span>
  );
}
