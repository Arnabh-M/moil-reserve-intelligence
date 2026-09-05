import React from 'react';

const base =
  'inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 cursor-pointer text-xs disabled:opacity-50 disabled:cursor-not-allowed';

const variantClasses = {
  primary:
    'bg-[var(--accent-primary)] text-white hover:opacity-90 active:opacity-80 rounded-md px-3.5 py-2 shadow-2xs font-medium',
  secondary:
    'bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--divider)] hover:border-[var(--text-muted)] active:bg-[var(--divider)]/40 rounded-md px-3.5 py-2',
  ghost:
    'bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--divider)]/40 active:bg-[var(--divider)]/70 rounded-md px-2.5 py-1.5',
};

const sizeClasses = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-3.5 py-2 text-xs',
  lg: 'px-4.5 py-2.5 text-sm',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  children,
  className = '',
  icon: Icon,
  ...props
}) {
  return (
    <button
      className={`${base} ${variantClasses[variant] || variantClasses.primary} ${sizeClasses[size] || sizeClasses.md} ${className}`}
      {...props}
    >
      {Icon && <Icon size={size === 'sm' ? 13 : 15} strokeWidth={1.75} />}
      {children}
    </button>
  );
}
