import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '../components';
import CausalGraph from '../components/CausalGraph';
import { getRiskEvents, getCausalGraph } from '../api/client';

const SEVERITY_STYLE = {
  critical: { dot: 'bg-danger', badge: 'critical' },
  high: { dot: 'bg-danger', badge: 'critical' },
  medium: { dot: 'bg-warning', badge: 'warning' },
  low: { dot: 'bg-text-muted', badge: 'unconfirmed' },
};

const FILTERS = [
  { value: 'all', label: 'All' },
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
      <div className="flex items-start justify-between gap-4 flex-wrap mb-1">
        <div>
          <h2 className="page-title">Event Timeline</h2>
          <p className="page-subtitle">
            Chronological record of disruptions, resolutions, and milestones across all mine sites
          </p>
        </div>

        <div className="flex items-center gap-1.5 bg-white border border-border rounded-lg p-1">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors duration-150 ${
                filter === f.value
                  ? 'bg-navy text-white'
                  : 'text-text-secondary hover:bg-bg'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="mt-8 text-sm text-text-muted">Loading risk events…</div>
      )}

      {!loading && error && (
        <div className="mt-8 p-4 rounded-lg border border-danger/20 bg-danger/5 text-sm text-danger">
          {error}
        </div>
      )}

      {!loading && !error && filteredEvents.length === 0 && (
        <div className="mt-8 text-sm text-text-muted">No events match this filter.</div>
      )}

      {!loading && !error && filteredEvents.length > 0 && (
        <div className="relative ml-4 mt-6">
          <div
            className="absolute left-[7px] top-3 bottom-3 w-[2px] bg-border"
            aria-hidden="true"
          />

          <div className="space-y-0">
            {filteredEvents.map((event, idx) => {
              const style = SEVERITY_STYLE[event.severity] || SEVERITY_STYLE.low;
              const isExpanded = expandedId === event.id;
              const graphState = graphsById[event.id];

              return (
                <div
                  key={event.id}
                  className="relative flex items-start gap-5 pb-8 group animate-fade-in"
                  style={{ animationDelay: `${idx * 0.04}s` }}
                >
                  <div className="relative z-10 shrink-0 mt-1">
                    <span
                      className={`block w-4 h-4 rounded-full border-[3px] border-white shadow-sm ${style.dot}`}
                    />
                  </div>

                  <div className="flex-1 bg-white rounded-xl border border-border p-4 transition-all duration-200 hover:shadow-md hover:border-teal/20">
                    <div className="flex items-start justify-between gap-3 mb-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-sm font-semibold text-text-primary capitalize">
                          {event.risk_type.replace(/_/g, ' ')}
                        </h4>
                        <Badge variant={style.badge} dot>{event.severity}</Badge>
                        {event.resolved && <Badge variant="operational">resolved</Badge>}
                      </div>
                      <span className="text-[11px] text-text-muted whitespace-nowrap shrink-0">
                        {formatTimestamp(event.detected_at)}
                      </span>
                    </div>

                    <p className="text-xs text-text-secondary leading-relaxed mb-2">
                      {event.description}
                    </p>

                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-medium text-text-muted uppercase tracking-wide">
                        {event.site_name}
                      </span>
                      <button
                        onClick={() => toggleExpand(event)}
                        className="flex items-center gap-1 text-xs text-teal font-medium hover:text-teal/80 transition-colors duration-150"
                      >
                        {isExpanded ? 'Hide causal graph' : 'View causal graph'}
                        {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-border">
                        {graphState?.status === 'loading' && (
                          <div className="h-[200px] flex items-center justify-center text-xs text-text-muted border border-dashed border-border rounded-lg">
                            Loading causal graph…
                          </div>
                        )}
                        {graphState?.status === 'error' && (
                          <div className="h-[120px] flex items-center justify-center text-xs text-danger border border-dashed border-danger/30 rounded-lg">
                            {graphState.message}
                          </div>
                        )}
                        {graphState?.status === 'ready' && (
                          <>
                            {graphState.graph.graph_source === 'postgres_fallback' && (
                              <div className="mb-2 text-[11px] text-warning bg-warning/10 border border-warning/20 rounded-lg px-2.5 py-1.5">
                                {graphState.graph.note || 'This event has no causal graph yet.'}
                              </div>
                            )}
                            <CausalGraph graph={graphState.graph} height={260} />
                          </>
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
