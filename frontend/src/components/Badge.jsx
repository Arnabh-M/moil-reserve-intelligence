function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

const VARIANTS = {
  success: 'bg-teal/10 text-teal border-teal/30',
  warning: 'bg-orange-soft/20 text-orange border-orange-soft/50',
  danger: 'bg-orange/10 text-orange border-orange/40',
  info: 'bg-navy/5 text-navy2 border-navy/15',
  neutral: 'bg-slate-100 text-slate-600 border-slate-200',
}

export default function Badge({ variant = 'neutral', children, className = '' }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide',
        VARIANTS[variant] || VARIANTS.neutral,
        className
      )}
    >
      {children}
    </span>
  )
}
