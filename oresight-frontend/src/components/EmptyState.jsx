import React from 'react';
import { CheckCircle2 } from 'lucide-react';

// 'positive' reads as reassuring good news (e.g. "all sites operating
// normally"); 'neutral' is for a plain absence of data.
const TONE_CLASSES = {
  neutral: 'bg-bg border border-border text-text-muted',
  positive: 'bg-teal/10 text-teal',
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
      className={`flex flex-col items-center justify-center text-center ${compact ? 'py-6 px-4' : 'py-10 px-6'} ${className}`}
    >
      <div
        className={`flex items-center justify-center rounded-xl mb-3 ${compact ? 'h-9 w-9' : 'h-12 w-12'} ${TONE_CLASSES[tone] || TONE_CLASSES.neutral}`}
      >
        <Icon size={compact ? 18 : 22} strokeWidth={2} />
      </div>
      <div className={`font-semibold text-text-primary ${compact ? 'text-xs' : 'text-sm'}`}>{title}</div>
      {message && (
        <p className={`mt-1 max-w-sm text-text-muted ${compact ? 'text-[11px]' : 'text-xs'}`}>{message}</p>
      )}
    </div>
  );
}
