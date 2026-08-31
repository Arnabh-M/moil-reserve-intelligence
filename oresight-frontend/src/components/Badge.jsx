import React from 'react';

const variants = {
  operational: 'bg-success/10 text-success border-success/20',
  up: 'bg-success/10 text-success border-success/20',
  completed: 'bg-success/10 text-success border-success/20',
  confirmed: 'bg-success/10 text-success border-success/20',
  planned: 'bg-teal/10 text-teal border-teal/20',
  delayed: 'bg-warning/10 text-warning border-warning/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  down: 'bg-danger/10 text-danger border-danger/20',
  critical: 'bg-danger/10 text-danger border-danger/20',
  unconfirmed: 'bg-text-muted/10 text-text-muted border-text-muted/20',
  info: 'bg-teal/10 text-teal border-teal/20',
  orange: 'bg-orange/10 text-orange border-orange/20',
};

export default function Badge({ variant = 'info', children, dot = false }) {
  const classes = variants[variant] || variants.info;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${classes}`}
    >
      {dot && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {children}
    </span>
  );
}
