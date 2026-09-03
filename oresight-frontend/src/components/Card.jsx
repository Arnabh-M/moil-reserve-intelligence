import React from 'react';

export default function Card({ children, title, subtitle, action, className = '', noPadding = false }) {
  return (
    <div
      className={`bg-[var(--bg-surface)] rounded-[3px] border border-[var(--border)] transition-colors duration-180 hover:border-[var(--accent-primary)] ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-[var(--border)]/60 mb-3">
          <div>
            {title && <h3 className="font-heading text-sm font-bold text-[var(--text-primary)]">{title}</h3>}
            {subtitle && <p className="text-xs text-[var(--text-muted)] mt-1">{subtitle}</p>}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      <div className={noPadding ? '' : `px-5 pb-5 ${title || action ? '' : 'pt-5'}`}>{children}</div>
    </div>
  );
}
