import React from 'react';

export function SkeletonBar({ width = 'w-full', height = 'h-3', className = '' }) {
  return <div className={`animate-pulse rounded bg-border/70 ${width} ${height} ${className}`} />;
}

export function SkeletonCircle({ size = 'h-9 w-9', className = '' }) {
  return <div className={`animate-pulse rounded-full bg-border/70 ${size} ${className}`} />;
}

// Matches Card's own shell (rounded-xl border border-border shadow-sm) so it
// swaps in for a real Card with no layout jump once data arrives.
export function SkeletonCard({ lines = 3, showIcon = true, className = '' }) {
  return (
    <div className={`bg-bg-surface rounded-xl border border-border shadow-sm p-4 ${className}`}>
      {showIcon && (
        <div className="flex items-center gap-3 mb-3">
          <SkeletonCircle />
          <SkeletonBar width="w-2/3" />
        </div>
      )}
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBar key={i} className="mb-2" width={i === lines - 1 ? 'w-1/2' : 'w-full'} />
      ))}
    </div>
  );
}

// Mirrors KPIStat's own markup (icon box + big value + label) at the same size.
export function SkeletonKPIRow({ count = 4 }) {
  return (
    <div className="grid-kpi">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-bg-surface rounded-xl border border-border shadow-sm p-4">
          <SkeletonCircle className="mb-3" />
          <SkeletonBar width="w-16" height="h-7" className="mb-2" />
          <SkeletonBar width="w-24" height="h-2.5" />
        </div>
      ))}
    </div>
  );
}

// For compact list rows, e.g. LiveEventFeed while its first poll is in flight.
export function SkeletonRow({ className = '' }) {
  return (
    <div className={`flex items-start gap-3 px-2 py-3 ${className}`}>
      <SkeletonCircle size="h-2 w-2" className="mt-1.5" />
      <div className="flex-1">
        <SkeletonBar width="w-3/4" className="mb-2" />
        <SkeletonBar width="w-1/3" height="h-2.5" />
      </div>
    </div>
  );
}
