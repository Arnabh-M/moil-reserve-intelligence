import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import Card from './Card';
import Badge from './Badge';
import { SkeletonRow } from './Skeleton';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import { getRiskEvents, SITE_NAME_MAP } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';

const POLL_INTERVAL_MS = 15000;
const MAX_EVENTS = 5;

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

/**
 * Single source of truth for "what risky things just happened" on the Dashboard.
 * Replaces the old separate "Recent Alerts" (static mock data) and "Live Event
 * Feed" (polled /risk-events) widgets, which showed the same underlying data twice.
 */
export default function RecentRiskEvents() {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const knownIds = useRef(new Set());
  const [freshIds, setFreshIds] = useState(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await getRiskEvents();
        if (cancelled) return;

        const topN = [...data]
          .sort((a, b) => (getEventTimestamp(b)?.getTime() || 0) - (getEventTimestamp(a)?.getTime() || 0))
          .slice(0, MAX_EVENTS);

        const newlySeen = new Set(
          topN.filter((e) => !knownIds.current.has(e.id)).map((e) => e.id)
        );
        topN.forEach((e) => knownIds.current.add(e.id));

        setFreshIds(newlySeen);
        setEvents(topN);
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
    <Card
      title="Recent Risk Events"
      subtitle="Live feed, polled every 15s"
      action={<Badge variant="confirmed" dot>Live</Badge>}
    >
      {status === 'loading' && (
        <div className="space-y-3">
          <SkeletonRow />
          <SkeletonRow />
          <SkeletonRow />
        </div>
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

      {status === 'ready' && events.length > 0 && (
        <div className="space-y-3">
          {events.map((event) => {
            const site = event.site_name || SITE_NAME_MAP[event.site_id] || event.site_id;
            return (
              <div
                key={event.id}
                onClick={event.site_id ? () => navigate(`/site/${event.site_id}`) : undefined}
                className={`flex items-start gap-3 p-3 rounded-[3px] bg-[var(--bg-primary)] border border-[var(--border)] transition-colors duration-150 hover:border-[var(--accent-primary)] ${
                  event.site_id ? 'cursor-pointer' : ''
                } ${freshIds.has(event.id) ? 'animate-fade-in' : ''}`}
              >
                <div className="mt-0.5 p-1.5 rounded-[3px] bg-[var(--warning)]/10 text-[var(--warning)]">
                  <AlertTriangle size={14} strokeWidth={1.75} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-bold text-[var(--text-primary)] truncate">{eventTitle(event)}</span>
                    <Badge variant={severityVariant(event)}>{severityLabel(event)}</Badge>
                  </div>
                  {event.description && (
                    <p className="text-xs text-[var(--text-muted)] line-clamp-2">{event.description}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1.5 font-mono">
                    {site && <span className="text-[10px] text-[var(--text-muted)] capitalize">{site}</span>}
                    {site && <span className="text-[10px] text-[var(--text-muted)]">•</span>}
                    <span className="text-[10px] text-[var(--text-muted)]">{formatRelativeTime(getEventTimestamp(event))}</span>
                  </div>
                </div>
                {event.site_id && <ArrowRight size={14} className="text-[var(--text-muted)] shrink-0 mt-1" />}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
