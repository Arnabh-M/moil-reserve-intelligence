import React from 'react';

const base =
  'inline-flex items-center justify-center gap-2 font-bold transition-all duration-150 cursor-pointer text-sm disabled:opacity-50 disabled:cursor-not-allowed font-body';

const variantClasses = {
  primary:
    'bg-[var(--accent-primary)] text-white hover:opacity-90 active:opacity-80 rounded-[8px] shadow-xs',
  secondary:
    'bg-transparent text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--accent-primary)] hover:bg-[var(--bg-surface)] active:bg-[var(--bg-primary)] rounded-[8px]',
  ghost:
    'bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--border)]/30 active:bg-[var(--border)]/50 rounded-[4px]',
};

const sizeClasses = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2',
  lg: 'px-5 py-2.5 text-base',
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
      {Icon && <Icon size={size === 'sm' ? 14 : 16} strokeWidth={1.75} />}
      {children}
    </button>
  );
}
