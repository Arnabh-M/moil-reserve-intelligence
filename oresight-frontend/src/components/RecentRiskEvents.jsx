import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, ChevronRight, ChevronDown, ExternalLink } from 'lucide-react';
import Card from './Card';
import Badge from './Badge';
import { SkeletonRow } from './Skeleton';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import CausalGraph from './CausalGraph';
import { getRiskEvents, getCausalGraph, SITE_NAME_MAP } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';

const POLL_INTERVAL_MS = 15000;
const MAX_EVENTS = 5;

function severityVariant(event) {
  const severity = (event.severity || '').toLowerCase();
  if (severity === 'high' || severity === 'critical') return 'critical';
  if (severity === 'medium') return 'warning';
  if (severity === 'low' || severity === 'info') return 'confirmed';

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

function resolveSiteSlug(siteId, siteName) {
  if (siteName) {
    const s = siteName.toLowerCase();
    if (s.includes('balaghat')) return 'balaghat';
    if (s.includes('nagpur')) return 'nagpur';
    if (s.includes('bhandara')) return 'bhandara';
  }
  if (siteId === 1 || siteId === '1') return 'balaghat';
  if (siteId === 2 || siteId === '2') return 'nagpur';
  if (siteId === 3 || siteId === '3') return 'bhandara';
  return String(siteId || 'balaghat').toLowerCase();
}

export default function RecentRiskEvents() {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const [expandedId, setExpandedId] = useState(null);
  const [graphsById, setGraphsById] = useState({});
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

  const toggleExpand = (event) => {
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
  };

  return (
    <Card
      title="Projects & Active Risks"
      subtitle="Live polled telemetry and anomaly logs across all sectors"
      action={<Badge variant="confirmed" dot>Live Sync</Badge>}
    >
      {status === 'loading' && (
        <div className="space-y-4 py-2">
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
        <div className="space-y-1">
          {/* Table Header Row */}
          <div className="grid grid-cols-12 gap-2 text-[11px] font-semibold text-[var(--text-muted)] pb-2 border-b border-[var(--divider)]">
            <div className="col-span-6 sm:col-span-7">Location / Anomaly</div>
            <div className="col-span-3 sm:col-span-3 text-center">Severity</div>
            <div className="col-span-3 sm:col-span-2 text-right">Action</div>
          </div>

          {events.map((event) => {
            const site = event.site_name || SITE_NAME_MAP[event.site_id] || event.site_id;
            const siteSlug = resolveSiteSlug(event.site_id, event.site_name);
            const isExpanded = expandedId === event.id;
            const graphState = graphsById[event.id];

            return (
              <div
                key={event.id}
                className={`py-3 transition-colors duration-120 border-b border-[var(--divider)] last:border-b-0 ${
                  freshIds.has(event.id) ? 'animate-fade-in' : ''
                }`}
              >
                <div
                  onClick={() => toggleExpand(event)}
                  className="grid grid-cols-12 gap-2 items-center cursor-pointer group hover:opacity-95"
                >
                  {/* Left: Icon/Thumbnail + Title + Subtitle */}
                  <div className="col-span-6 sm:col-span-7 flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-[var(--accent-soft)] text-[var(--accent-primary)] flex items-center justify-center shrink-0">
                      <AlertTriangle size={16} strokeWidth={2} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-[var(--text-primary)] truncate leading-tight group-hover:text-[var(--accent-primary)] transition-colors">
                        {eventTitle(event)}
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)] truncate leading-normal mt-0.5">
                        {site ? `${site} • ` : ''}{formatRelativeTime(getEventTimestamp(event))}
                      </div>
                    </div>
                  </div>

                  {/* Center: Severity Badge */}
                  <div className="col-span-3 sm:col-span-3 flex justify-center">
                    <Badge variant={severityVariant(event)}>{severityLabel(event)}</Badge>
                  </div>

                  {/* Right: Expand Trigger */}
                  <div className="col-span-3 sm:col-span-2 flex items-center justify-end gap-1 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-colors">
                    <span className="text-[11px] font-medium hidden sm:inline">
                      {isExpanded ? 'Hide' : 'Details'}
                    </span>
                    {isExpanded ? (
                      <ChevronDown size={14} strokeWidth={2} />
                    ) : (
                      <ChevronRight size={14} strokeWidth={2} />
                    )}
                  </div>
                </div>

                {/* Inline Accordion Expansion */}
                {isExpanded && (
                  <div className="mt-3 pt-3 pl-12 text-xs animate-fade-in">
                    <div className="bg-[var(--bg-primary)] rounded-xl p-3.5 mb-3 border border-[var(--divider)]">
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-[11px] font-semibold text-[var(--text-primary)] uppercase tracking-wider">
                          Full Incident Details
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/site/${siteSlug}`);
                          }}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--accent-primary)] hover:underline cursor-pointer"
                        >
                          <span>Open Site Dashboard</span>
                          <ExternalLink size={11} />
                        </button>
                      </div>
                      <p className="text-xs text-[var(--text-primary)] leading-relaxed mb-2.5">
                        {event.description || 'No detailed log provided for this risk event.'}
                      </p>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-[var(--divider)] text-[11px]">
                        <div>
                          <span className="text-[var(--text-muted)] block">Event ID:</span>
                          <span className="font-mono font-medium text-[var(--text-primary)]">{event.id}</span>
                        </div>
                        <div>
                          <span className="text-[var(--text-muted)] block">Severity:</span>
                          <span className="font-medium capitalize text-[var(--text-primary)]">{event.severity || 'Medium'}</span>
                        </div>
                        <div>
                          <span className="text-[var(--text-muted)] block">Risk Type:</span>
                          <span className="font-medium capitalize text-[var(--text-primary)]">{(event.risk_type || '').replace(/_/g, ' ')}</span>
                        </div>
                      </div>
                    </div>

                    {/* Causal Graph visualization */}
                    {graphState?.status === 'loading' && (
                      <div className="h-28 flex items-center justify-center text-xs text-[var(--text-muted)] rounded-xl border border-[var(--divider)]">
                        Loading causal graph analysis…
                      </div>
                    )}
                    {graphState?.status === 'ready' && graphState.graph && (
                      <div className="mt-2">
                        <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                          Causal Root-Cause Graph
                        </div>
                        <CausalGraph graph={graphState.graph} height={200} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Bottom View More Link matching Inspiration */}
          <div className="pt-3 text-center border-t border-[var(--divider)]">
            <button
              type="button"
              onClick={() => navigate('/timeline')}
              className="text-xs font-semibold text-[var(--accent-primary)] hover:underline cursor-pointer inline-flex items-center gap-1 py-1"
            >
              + View more
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
