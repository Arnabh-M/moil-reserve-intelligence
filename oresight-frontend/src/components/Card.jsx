import React from 'react';

export default function Card({ children, title, subtitle, action, className = '', noPadding = false }) {
  return (
    <div
      className={`bg-white rounded-xl border border-border shadow-sm transition-shadow duration-200 hover:shadow-md ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <div>
            {title && <h3 className="text-sm font-semibold text-text-primary">{title}</h3>}
            {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      <div className={noPadding ? '' : 'px-5 pb-4'}>{children}</div>
    </div>
  );
}
