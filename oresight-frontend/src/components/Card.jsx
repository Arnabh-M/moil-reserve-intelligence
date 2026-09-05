import React from 'react';

export default function Card({
  children,
  title,
  subtitle,
  action,
  className = '',
  noPadding = false,
}) {
  return (
    <div
      className={`bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] transition-colors duration-150 ${
        noPadding ? 'p-0' : 'p-6'
      } ${className}`}
    >
      {(title || subtitle || action) && (
        <div className="flex items-start justify-between gap-4 pb-4 mb-5 border-b border-[var(--divider)]">
          <div className="min-w-0">
            {title && (
              <h3 className="font-heading font-semibold text-[var(--text-primary)] leading-tight text-sm">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-[var(--text-muted)] mt-1 font-body leading-relaxed">
                {subtitle}
              </p>
            )}
          </div>
          {action && <div className="shrink-0 flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div>{children}</div>
    </div>
  );
}

