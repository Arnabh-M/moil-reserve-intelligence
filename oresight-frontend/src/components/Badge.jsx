import React from 'react';

const variants = {
  operational: 'bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/30',
  up: 'bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/30',
  completed: 'bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/30',
  confirmed: 'bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/30',
  planned: 'bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)] border-[var(--accent-secondary)]/30',
  delayed: 'bg-[var(--warning)]/15 text-[var(--warning)] border-[var(--warning)]/30',
  warning: 'bg-[var(--warning)]/15 text-[var(--warning)] border-[var(--warning)]/30',
  down: 'bg-[var(--warning)]/20 text-[var(--warning)] border-[var(--warning)]/40',
  critical: 'bg-[var(--warning)]/20 text-[var(--warning)] border-[var(--warning)]/40',
  unconfirmed: 'bg-[var(--text-muted)]/15 text-[var(--text-muted)] border-[var(--border)]',
  info: 'bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)] border-[var(--accent-secondary)]/30',
  orange: 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)] border-[var(--accent-primary)]/30',
};

export default function Badge({ variant = 'info', children, dot = false, className = '' }) {
  const classes = variants[variant] || variants.info;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[3px] text-xs font-semibold border ${classes} ${className}`}
    >
      {dot && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {children}
    </span>
  );
}
