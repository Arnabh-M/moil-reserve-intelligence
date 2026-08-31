import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function KPIStat({ label, value, delta, deltaLabel, icon: Icon, color = 'teal' }) {
  const colorMap = {
    teal: 'bg-teal/10 text-teal',
    orange: 'bg-orange/10 text-orange',
    navy: 'bg-navy/10 text-navy',
    success: 'bg-success/10 text-success',
    danger: 'bg-danger/10 text-danger',
    warning: 'bg-warning/10 text-warning',
  };

  const deltaColor =
    delta > 0 ? 'text-success' : delta < 0 ? 'text-danger' : 'text-text-muted';
  const DeltaIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;

  return (
    <div className="bg-white rounded-xl border border-border shadow-sm p-4 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
          {label}
        </span>
        {Icon && (
          <div className={`p-2 rounded-lg ${colorMap[color] || colorMap.teal}`}>
            <Icon size={16} />
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-text-primary tracking-tight">{value}</div>
      {(delta !== undefined || deltaLabel) && (
        <div className="flex items-center gap-1 mt-1.5">
          {delta !== undefined && (
            <span className={`flex items-center gap-0.5 text-xs font-semibold ${deltaColor}`}>
              <DeltaIcon size={12} />
              {Math.abs(delta)}%
            </span>
          )}
          {deltaLabel && (
            <span className="text-xs text-text-muted">{deltaLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}
