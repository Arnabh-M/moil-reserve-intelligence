function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

export default function Card({ children, className = '', padded = true }) {
  return (
    <div
      className={cn(
        'bg-white border border-border rounded-md shadow-subtle',
        padded && 'p-5',
        className
      )}
    >
      {children}
    </div>
  )
}
