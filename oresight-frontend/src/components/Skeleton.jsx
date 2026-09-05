import React from 'react';

export function SkeletonBar({ width = 'w-full', height = 'h-3', className = '' }) {
  return <div className={`animate-pulse rounded bg-[var(--divider)] ${width} ${height} ${className}`} />;
}

export function SkeletonCircle({ size = 'h-8 w-8', className = '' }) {
  return <div className={`animate-pulse rounded-full bg-[var(--divider)] ${size} ${className}`} />;
}

export function SkeletonCard({ lines = 3, showIcon = true, className = '' }) {
  return (
    <div className={`p-4 ${className}`}>
      {showIcon && (
        <div className="flex items-center gap-3 mb-3">
          <SkeletonCircle />
          <SkeletonBar width="w-1/2" />
        </div>
      )}
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBar key={i} className="mb-2" width={i === lines - 1 ? 'w-1/3' : 'w-full'} />
      ))}
    </div>
  );
}

// Stacked stats skeleton
export function SkeletonKPIRow({ count = 4 }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex flex-col gap-2">
          <SkeletonBar width="w-20" height="h-2.5" />
          <SkeletonBar width="w-16" height="h-8" />
          <SkeletonBar width="w-24" height="h-2.5" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonRow({ className = '' }) {
  return (
    <div className={`flex items-start gap-3 py-3 ${className}`}>
      <SkeletonCircle size="h-2 w-2" className="mt-1.5" />
      <div className="flex-1">
        <SkeletonBar width="w-3/4" className="mb-2" />
        <SkeletonBar width="w-1/3" height="h-2.5" />
      </div>
    </div>
  );
}
