import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, SearchX } from 'lucide-react';
import { Badge, EmptyState, ErrorState, SkeletonCard, SectionDivider } from '../components';
import CausalGraph from '../components/CausalGraph';
import { getRiskEvents, getCausalGraph } from '../api/client';

const SEVERITY_STYLE = {
  critical: { dot: 'bg-[var(--critical)]', badge: 'critical' },
  high: { dot: 'bg-[var(--critical)]', badge: 'critical' },
  medium: { dot: 'bg-[var(--warning-medium)]', badge: 'warning' },
  low: { dot: 'bg-[var(--text-muted)]', badge: 'unconfirmed' },
};

const FILTERS = [
  { value: 'all', label: 'All Events' },
  { value: 'critical', label: 'Critical' },
  { value: 'resolved', label: 'Resolved' },
];

function formatTimestamp(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;

  const diffMs = Date.now() - date.getTime();
  const diffHrs = diffMs / (1000 * 60 * 60);

  if (diffHrs < 1) return 'just now';
  if (diffHrs < 24) return `${Math.round(diffHrs)} hr${Math.round(diffHrs) === 1 ? '' : 's'} ago`;
  const diffDays = Math.round(diffHrs / 24);
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;

  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function EventTimeline() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState(null);
  const [graphsById, setGraphsById] = useState({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getRiskEvents()
      .then((rows) => {
        if (cancelled) return;
        const sorted = [...rows].sort(
          (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
        );
        setEvents(sorted);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load risk events.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const retryLoad = () => {
    setLoading(true);
    setError(null);
    getRiskEvents()
      .then((rows) => {
        const sorted = [...rows].sort(
          (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
        );
        setEvents(sorted);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load risk events.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const filteredEvents = useMemo(() => {
    if (filter === 'critical') return events.filter((e) => e.severity === 'critical');
    if (filter === 'resolved') return events.filter((e) => e.resolved);
    return events;
  }, [events, filter]);

  function toggleExpand(event) {
    const isOpening = expandedId !== event.id;
    setExpandedId(isOpening ? event.id : null);

    if (isOpening && !graphsById[event.id]) {
      setGraphsById((prev) => ({ ...prev, [event.id]: { status: 'loading' } }));
      getCausalGraph(event.id)
        .then((graph) => {
          setGraphsById((prev) => ({ ...prev, [event.id]: { status: 'ready', graph } }));
        })
        .catch((err) => {
          setGraphsById((prev) => ({
            ...prev,
            [event.id]: { status: 'error', message: err.message || 'Failed to load causal graph.' },
          }));
        });
    }
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap mb-8">
        <div>
          <h1 className="page-title">Risk &amp; Incident Timeline</h1>
          <p className="page-subtitle">
            Chronological record of disruptions, resolutions, and operational milestones across all mine sites
          </p>
        </div>

        <div className="flex items-center gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                filter === f.value
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="mt-6 space-y-4">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
        </div>
      )}

      {!loading && error && (
        <div className="mt-6">
          <ErrorState
            title="Failed to load events"
            message={error}
            onRetry={retryLoad}
          />
        </div>
      )}

      {!loading && !error && filteredEvents.length === 0 && (
        <div className="mt-6">
          <EmptyState
            icon={SearchX}
            title="No events match this filter"
            message="Try adjusting the filter above, or check back later for new events."
            tone="neutral"
          />
        </div>
      )}

      {!loading && !error && filteredEvents.length > 0 && (
        <div className="relative ml-2 mt-6">
          {/* Vertical connecting line */}
          <div
            className="absolute left-[5px] top-2 bottom-2 w-[1px] bg-[var(--divider)]"
            aria-hidden="true"
          />

          <div className="space-y-6">
            {filteredEvents.map((event, idx) => {
              const style = SEVERITY_STYLE[event.severity] || SEVERITY_STYLE.low;
              const isExpanded = expandedId === event.id;
              const graphState = graphsById[event.id];

              return (
                <div
                  key={event.id}
                  className="relative flex items-start gap-4 animate-fade-in"
                  style={{ animationDelay: `${idx * 0.03}s` }}
                >
                  <div className="relative z-10 shrink-0 mt-1">
                    <span
                      className={`block w-2.5 h-2.5 rounded-full ${style.dot}`}
                    />
                  </div>

                  <div className="flex-1 min-w-0 pb-2">
                    <div className="flex items-start justify-between gap-3 mb-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-xs font-semibold text-[var(--text-primary)] capitalize">
                          {event.risk_type.replace(/_/g, ' ')}
                        </h4>
                        <Badge variant={style.badge}>{event.severity}</Badge>
                        {event.resolved && <Badge variant="operational">resolved</Badge>}
                      </div>
                      <span className="text-[11px] text-[var(--text-muted)] whitespace-nowrap shrink-0">
                        {formatTimestamp(event.detected_at)}
                      </span>
                    </div>

                    <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-2">
                      {event.description}
                    </p>

                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wider">
                        {event.site_name}
                      </span>
                      <button
                        type="button"
                        onClick={() => toggleExpand(event)}
                        className="inline-flex items-center gap-1 text-[11px] text-[var(--accent-primary)] font-medium hover:underline cursor-pointer"
                      >
                        {isExpanded ? 'Hide causal graph' : 'View causal graph'}
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-[var(--divider)] animate-fade-in">
                        {graphState?.status === 'loading' && (
                          <div className="h-32 flex items-center justify-center text-xs text-[var(--text-muted)]">
                            Loading causal graph…
                          </div>
                        )}
                        {graphState?.status === 'error' && (
                          <div className="h-24 flex items-center justify-center text-xs text-[var(--critical)]">
                            {graphState.message}
                          </div>
                        )}
                        {graphState?.status === 'ready' && (
                          <CausalGraph graph={graphState.graph} height={240} />
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


