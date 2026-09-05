import React from 'react';
import { CheckCircle2 } from 'lucide-react';

const TONE_CLASSES = {
  neutral: 'bg-[var(--bg-elevated)] text-[var(--text-muted)]',
  positive: 'bg-[var(--success)]/12 text-[var(--success)]',
};

export default function EmptyState({
  icon: Icon = CheckCircle2,
  title = 'Nothing to show',
  message,
  tone = 'neutral',
  compact = false,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${compact ? 'py-6 px-4' : 'py-12 px-6'} ${className}`}
    >
      <div
        className={`flex items-center justify-center rounded-full mb-3 ${compact ? 'h-9 w-9' : 'h-11 w-11'} ${TONE_CLASSES[tone] || TONE_CLASSES.neutral}`}
      >
        <Icon size={compact ? 16 : 20} strokeWidth={2} />
      </div>
      <div className={`font-semibold text-[var(--text-primary)] ${compact ? 'text-xs' : 'text-sm'}`}>{title}</div>
      {message && (
        <p className={`mt-1 max-w-sm text-[var(--text-muted)] ${compact ? 'text-[11px]' : 'text-xs'}`}>{message}</p>
      )}
    </div>
  );
}
