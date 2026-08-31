function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

const VARIANTS = {
  primary: 'bg-orange text-white border-orange hover:bg-orange/90 shadow-subtle',
  secondary: 'bg-navy text-white border-navy hover:bg-navy2',
  ghost: 'bg-transparent text-navy border-transparent hover:bg-slate-100',
}

export default function Button({
  children,
  variant = 'primary',
  className = '',
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-semibold border transition-colors duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-teal',
        VARIANTS[variant] || VARIANTS.primary,
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
}
