import Card from '../components/Card'

export default function PlaceholderPage({ title, description }) {
  return (
    <Card className="flex min-h-[420px] flex-col items-center justify-center text-center gap-2">
      <h2 className="font-heading text-lg font-semibold text-navy">{title}</h2>
      <p className="max-w-sm text-sm text-slate-500">{description}</p>
    </Card>
  )
}
