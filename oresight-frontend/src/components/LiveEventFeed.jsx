import { useEffect, useRef, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import Card from './Card';
import Badge from './Badge';
import { SkeletonRow } from './Skeleton';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import { getRiskEvents } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';

const POLL_INTERVAL_MS = 15000;

function severityVariant(event) {
  const severity = (event.severity || '').toLowerCase();
  if (severity === 'high' || severity === 'critical') return 'critical';
  if (severity === 'medium') return 'warning';
  if (severity === 'low' || severity === 'info') return 'confirmed';

  // Fall back to the risk score when the backend has no severity field yet.
  if (typeof event.score === 'number') {
    if (event.score >= 0.7) return 'critical';
    if (event.score >= 0.4) return 'warning';
    return 'confirmed';
  }
  return 'info';
}

function severityLabel(event) {
  const severity = (event.severity || '').toLowerCase();
  if (severity) return severity;

  if (typeof event.score === 'number') {
    if (event.score >= 0.7) return 'high';
    if (event.score >= 0.4) return 'medium';
    return 'low';
  }
  return 'unknown';
}

function eventTitle(event) {
  if (event.risk_type) {
    return event.risk_type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
  return event.description || 'Risk event';
}

export default function LiveEventFeed() {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const knownIds = useRef(new Set());
  const [freshIds, setFreshIds] = useState(new Set());

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await getRiskEvents();
        if (cancelled) return;

        const top3 = [...data]
          .sort((a, b) => (getEventTimestamp(b)?.getTime() || 0) - (getEventTimestamp(a)?.getTime() || 0))
          .slice(0, 3);

        const newlySeen = new Set(
          top3.filter((e) => !knownIds.current.has(e.id)).map((e) => e.id)
        );
        top3.forEach((e) => knownIds.current.add(e.id));

        setFreshIds(newlySeen);
        setEvents(top3);
        setStatus('ready');
      } catch {
        if (!cancelled) setStatus('error');
      }
    }

    poll();
    const intervalId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  return (
    <Card noPadding className="flex flex-col">
      <div className="p-5 pb-3 border-b border-border flex items-center justify-between">
        <div>
          <h3 className="font-heading text-[15px] font-semibold text-navy">Live Event Feed</h3>
          <p className="text-xs text-text-muted mt-1">Most recent operational signals</p>
        </div>
        <Badge variant="confirmed" dot>Live</Badge>
      </div>

      <div className="flex-1 px-3 py-2">
        {status === 'loading' && (
          <>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        )}

        {status === 'error' && (
          <ErrorState
            compact
            title="Connection lost"
            message="Unable to reach the risk-events service. Retrying every 15s."
          />
        )}

        {status === 'ready' && events.length === 0 && (
          <EmptyState
            icon={CheckCircle2}
            title="No active risks"
            message="All sites operating normally"
            tone="positive"
            compact
          />
        )}

        {status === 'ready' &&
          events.map((event) => (
            <div
              key={event.id}
              className={`flex items-start gap-3 rounded-sm px-2 py-3 ${
                freshIds.has(event.id) ? 'animate-fade-in' : ''
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[13px] font-semibold text-navy">{eventTitle(event)}</span>
                  <Badge variant={severityVariant(event)}>{severityLabel(event)}</Badge>
                </div>
                {event.description && (
                  <p className="mt-1 text-xs text-text-muted">{event.description}</p>
                )}
                <div className="mt-2 flex items-center gap-2 text-[11px] text-text-muted">
                  {event.site_id && <span className="font-medium text-text-secondary">{event.site_id}</span>}
                  {event.site_id && <span>&middot;</span>}
                  <span>{formatRelativeTime(getEventTimestamp(event))}</span>
                </div>
              </div>
            </div>
          ))}
      </div>
    </Card>
  );
}
