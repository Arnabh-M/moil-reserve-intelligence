import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import Button from './Button';

export default function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  compact = false,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${compact ? 'py-6 px-4' : 'py-12 px-6'} ${className}`}
    >
      <div
        className={`flex items-center justify-center rounded-full bg-[var(--critical)]/12 text-[var(--critical)] mb-3 ${compact ? 'h-9 w-9' : 'h-11 w-11'}`}
      >
        <AlertTriangle size={compact ? 16 : 20} strokeWidth={2} />
      </div>
      <div className={`font-semibold text-[var(--text-primary)] ${compact ? 'text-xs' : 'text-sm'}`}>{title}</div>
      {message && (
        <p className={`mt-1 max-w-sm text-[var(--text-muted)] ${compact ? 'text-[11px]' : 'text-xs'}`}>{message}</p>
      )}
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          <RefreshCw size={13} />
          Retry
        </Button>
      )}
    </div>
  );
}

export function InlineError({ message, onRetry, className = '' }) {
  return (
    <div
      className={`flex items-center gap-2 rounded-lg bg-[var(--critical)]/10 px-4 py-2.5 text-xs text-[var(--critical)] ${className}`}
    >
      <AlertTriangle size={14} className="shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex shrink-0 items-center gap-1 font-semibold text-[var(--critical)] hover:opacity-80 transition-opacity cursor-pointer"
        >
          <RefreshCw size={12} />
          Retry
        </button>
      )}
    </div>
  );
}
