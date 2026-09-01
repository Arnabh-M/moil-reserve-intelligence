import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import Button from './Button';

// Full centered card, for when there's nothing else useful to show below it.
export default function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  compact = false,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${compact ? 'py-6 px-4' : 'py-10 px-6'} ${className}`}
    >
      <div
        className={`flex items-center justify-center rounded-xl bg-danger/10 text-danger mb-3 ${compact ? 'h-9 w-9' : 'h-12 w-12'}`}
      >
        <AlertTriangle size={compact ? 18 : 22} strokeWidth={2} />
      </div>
      <div className={`font-semibold text-text-primary ${compact ? 'text-xs' : 'text-sm'}`}>{title}</div>
      {message && (
        <p className={`mt-1 max-w-sm text-text-muted ${compact ? 'text-[11px]' : 'text-xs'}`}>{message}</p>
      )}
      {onRetry && (
        <Button variant="ghost" size="sm" className="mt-3" onClick={onRetry}>
          <RefreshCw size={14} />
          Retry
        </Button>
      )}
    </div>
  );
}

// Thin inline banner for partial failures where the rest of the page still
// has useful content to show beneath it (don't hide good data behind a
// full-page error).
export function InlineError({ message, onRetry, className = '' }) {
  return (
    <div
      className={`flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger ${className}`}
    >
      <AlertTriangle size={14} className="shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex shrink-0 items-center gap-1 font-semibold text-danger hover:text-danger/80 transition-colors duration-150 cursor-pointer"
        >
          <RefreshCw size={12} />
          Retry
        </button>
      )}
    </div>
  );
}
