// Shared helpers for turning backend timestamps into "2 hrs ago" style text.

export function getEventTimestamp(event) {
  const raw = event.detected_at || event.timestamp || event.created_at
  return raw ? new Date(raw) : null
}

export function formatRelativeTime(date) {
  if (!date || Number.isNaN(date.getTime())) return 'unknown time'

  const diffMs = Date.now() - date.getTime()
  const diffMin = Math.round(diffMs / 60000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin} min ago`

  const diffHrs = Math.round(diffMin / 60)
  if (diffHrs < 24) return `${diffHrs} hr${diffHrs !== 1 ? 's' : ''} ago`

  const diffDays = Math.round(diffHrs / 24)
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
}
