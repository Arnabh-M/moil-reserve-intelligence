import React from 'react';

const base =
  'inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-200 cursor-pointer text-sm hover:scale-[1.01] active:scale-[0.99] disabled:hover:scale-100';

const variantClasses = {
  primary:
    'bg-orange text-white hover:bg-orange/90 active:bg-orange/80 shadow-sm hover:shadow',
  secondary:
    'bg-navy text-white hover:bg-navy2 active:bg-navy/80 shadow-sm hover:shadow',
  ghost:
    'bg-transparent text-text-secondary hover:bg-border/50 active:bg-border',
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
      {Icon && <Icon size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  );
}
