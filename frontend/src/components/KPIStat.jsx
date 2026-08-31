import Card from './Card'

function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

export default function KPIStat({ icon: Icon, value, label, accent = 'navy' }) {
  return (
    <Card className="flex flex-col gap-3">
      <div
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-sm',
          accent === 'orange' && 'bg-orange/10 text-orange',
          accent === 'teal' && 'bg-teal/10 text-teal',
          accent === 'navy' && 'bg-navy/5 text-navy2'
        )}
      >
        {Icon && <Icon size={18} strokeWidth={2} />}
      </div>
      <div>
        <div className="font-heading text-3xl font-semibold text-navy tracking-tight">{value}</div>
        <div className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      </div>
    </Card>
  )
}
