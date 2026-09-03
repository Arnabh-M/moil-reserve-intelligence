import React from 'react';

export default function SectionDivider({ label, className = '' }) {
  return (
    <div className={`section-divider ${className}`} role="separator">
      <span className="section-divider-glyph font-mono">
        {label ? `◆ ${label} ◆` : '◆'}
      </span>
    </div>
  );
}
