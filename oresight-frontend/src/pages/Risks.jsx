import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  ShieldAlert, AlertTriangle, Zap, Link2, CheckCircle2, MapPin, Loader2,
} from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState, ErrorState, SkeletonKPIRow, SkeletonCard } from '../components';
import CausalGraph from '../components/CausalGraph';
import { getRiskEvents, getCausalGraph, SITE_NAME_MAP, USE_MOCK } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';

const COLORS = {
  orange: '#e0793a',
  teal: '#2a7f8c',
  muted: '#8896a8',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
};

// Ordered worst-to-best so the bar chart reads as a severity ramp.
const SEVERITY_LEVELS = [
  { level: 'critical', label: 'Critical', color: COLORS.danger },
  { level: 'high', label: 'High', color: COLORS.orange },
  { level: 'medium', label: 'Medium', color: COLORS.warning },
  { level: 'low', label: 'Low', color: COLORS.success },
];

// Same severity->Badge-variant mapping RecentRiskEvents.jsx uses on the
// Dashboard, so a risk reads the same color everywhere in the app.
function severityVariant(severity) {
  const s = (severity || '').toLowerCase();
  if (s === 'high' || s === 'critical') return 'critical';
  if (s === 'medium') return 'warning';
  if (s === 'low') return 'confirmed';
  return 'info';
}

function riskTypeLabel(riskType) {
  if (!riskType) return 'Unknown';
  return riskType.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

export default function Risks() {
  const [riskEvents, setRiskEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [expandedRisk, setExpandedRisk] = useState(null);
  const [causalGraphs, setCausalGraphs] = useState({}); // risk id -> graph
  const [graphLoadingId, setGraphLoadingId] = useState(null);
  const [graphErrors, setGraphErrors] = useState({}); // risk id -> message

  const loadRisks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRiskEvents();
      setRiskEvents(data || []);
    } catch (err) {
      console.error('[Risks] Failed to load risk events:', err);
      setError(err.message || 'Failed to load risk events.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRisks();
  }, [loadRisks]);

  const loadCausalGraph = (riskId) => {
    setGraphLoadingId(riskId);
    setGraphErrors(prev => ({ ...prev, [riskId]: null }));
    getCausalGraph(riskId)
      .then(graph => setCausalGraphs(prev => ({ ...prev, [riskId]: graph })))
      .catch(err => setGraphErrors(prev => ({ ...prev, [riskId]: err.message || 'Failed to load causal graph.' })))
      .finally(() => setGraphLoadingId(null));
  };

  const toggleExpand = (riskId) => {
    if (expandedRisk === riskId) {
      setExpandedRisk(null);
      return;
    }
    setExpandedRisk(riskId);
    if (!causalGraphs[riskId] && graphLoadingId !== riskId) {
      loadCausalGraph(riskId);
    }
  };

  // ── Derived, all from the real /risk-events response ─────────────────
  const activeRisks = riskEvents.filter(r => r.resolved === false).length;
  const resolvedRisks = riskEvents.filter(r => r.resolved === true).length;
  const highestScore = riskEvents.length ? Math.max(...riskEvents.map(r => r.score ?? 0)) : 0;
  const sitesAffected = new Set(riskEvents.filter(r => !r.resolved).map(r => r.site_id)).size;

  const severityCounts = SEVERITY_LEVELS.map(({ level, label, color }) => ({
    level, label, color,
    count: riskEvents.filter(r => (r.severity || '').toLowerCase() === level).length,
  }));

  const typeCounts = riskEvents.reduce((acc, r) => {
    const key = r.risk_type || 'unknown';
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const typeCountsSorted = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
  const maxTypeCount = typeCountsSorted.length ? typeCountsSorted[0][1] : 0;

  // ── Error state: entire page failed ──────────────────────────────────
  if (!loading && error) {
    return (
      <div className="page-container">
        <ErrorState title="Failed to load risk events" message={error} onRetry={loadRisks} />
      </div>
    );
  }

  // ── Loading state ────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="page-container">
        <div className="h-8 bg-border/70 rounded w-56 mb-2 animate-pulse" />
        <div className="h-4 bg-border/50 rounded w-96 mb-6 animate-pulse" />
        <SkeletonKPIRow count={4} />
        <div className="grid-2 mt-6">
          <SkeletonCard lines={5} />
          <SkeletonCard lines={5} />
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="flex items-start justify-between mb-1">
        <div>
          <h2 className="page-title">Risk &amp; Alerts</h2>
          <p className="page-subtitle">Live risk intelligence across mine sites</p>
        </div>
        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs font-bold shadow-xs animate-fade-in shrink-0">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            USE_MOCK = true (Simulated API)
          </div>
        )}
      </div>

      {/* KPI Row */}
      <div className="grid-kpi stagger-children">
        <KPIStat
          label="Active Risks"
          value={activeRisks}
          delta={null}
          deltaLabel="requires attention"
          icon={ShieldAlert}
          color="danger"
        />
        <KPIStat
          label="Highest Risk Score"
          value={highestScore.toFixed(2)}
          delta={null}
          deltaLabel="out of 1.00"
          icon={AlertTriangle}
          color="warning"
        />
        <KPIStat
          label="Resolved Risks"
          value={resolvedRisks}
          delta={null}
          deltaLabel={`of ${riskEvents.length} total`}
          icon={CheckCircle2}
          color="success"
        />
        <KPIStat
          label="Sites Affected"
          value={sitesAffected}
          delta={null}
          deltaLabel="with an active risk"
          icon={MapPin}
          color="teal"
        />
      </div>

      {/* Risk Events + Severity Breakdown */}
      <div className="grid-2">
        {/* Risk Events */}
        <Card title="Risk Events" subtitle="Active and historical risk alerts">
          {riskEvents.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="No risk events"
              message="No risk events recorded yet."
              tone="positive"
            />
          ) : (
            <div className="space-y-3">
              {riskEvents.map(risk => {
                const isSevere = ['critical', 'high'].includes((risk.severity || '').toLowerCase());
                const siteLabel = risk.site_name || SITE_NAME_MAP[risk.site_id] || `Site ${risk.site_id}`;
                const graph = causalGraphs[risk.id];
                const isExpanded = expandedRisk === risk.id;

                return (
                  <div
                    key={risk.id}
                    className={`p-4 rounded-lg border transition-all duration-200 ${
                      !risk.resolved
                        ? 'bg-danger/5 border-danger/20 hover:border-danger/40'
                        : 'bg-bg border-border hover:border-success/30'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className={`p-1.5 rounded-lg ${isSevere ? 'bg-danger/10 text-danger' : 'bg-warning/10 text-warning'}`}>
                          <Zap size={14} />
                        </div>
                        <div>
                          <span className="text-sm font-semibold text-text-primary">{riskTypeLabel(risk.risk_type)}</span>
                          <span className="text-xs text-text-muted ml-2">{siteLabel}</span>
                        </div>
                      </div>
                      <Badge variant={severityVariant(risk.severity)} dot>{risk.severity || 'unknown'}</Badge>
                    </div>
                    <p className="text-xs text-text-secondary mb-2 leading-relaxed">{risk.description}</p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] text-text-muted">Score: <strong className="text-text-primary">{risk.score}</strong></span>
                        <span className="text-[10px] text-text-muted" title={risk.detected_at}>
                          Detected: {formatRelativeTime(getEventTimestamp(risk))}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleExpand(risk.id)}
                          className="flex items-center gap-1 text-[10px] font-medium text-teal hover:underline"
                        >
                          <Link2 size={11} />
                          {isExpanded ? 'Hide causal graph' : 'View causal graph'}
                        </button>
                        <Badge variant={risk.resolved ? 'operational' : 'down'} dot>
                          {risk.resolved ? 'resolved' : 'active'}
                        </Badge>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-border">
                        {graphLoadingId === risk.id && (
                          <div className="flex items-center justify-center gap-2 py-6 text-xs text-text-muted">
                            <Loader2 size={14} className="animate-spin" /> Loading causal graph…
                          </div>
                        )}
                        {graphErrors[risk.id] && (
                          <ErrorState
                            compact
                            title="Graph unavailable"
                            message={graphErrors[risk.id]}
                            onRetry={() => loadCausalGraph(risk.id)}
                          />
                        )}
                        {graphLoadingId !== risk.id && graph && (
                          <>
                            {graph.graph_source === 'postgres_fallback' && (
                              <div className="mb-3 text-[11px] text-warning bg-warning/10 border border-warning/20 rounded-lg px-3 py-2">
                                {graph.note || 'This risk event has no full causal graph yet — showing a single-node fallback.'}
                              </div>
                            )}
                            <CausalGraph graph={graph} height={240} />
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Severity Breakdown */}
        <Card title="Risk Severity Distribution" subtitle="All recorded risk events, by severity">
          {riskEvents.length === 0 ? (
            <EmptyState title="No data yet" message="Severity breakdown will appear once risk events exist." tone="neutral" compact />
          ) : (
            <div style={{ width: '100%', height: 200 }}>
              <ResponsiveContainer>
                <BarChart data={severityCounts} layout="vertical" margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <CartesianGrid horizontal={false} stroke="var(--border)" strokeOpacity={0.6} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10, fill: COLORS.muted }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} label={{ value: 'Events', position: 'insideBottom', offset: -2, fontSize: 10, fill: COLORS.muted }} />
                  <YAxis type="category" dataKey="label" tick={{ fontSize: 10, fill: COLORS.muted }} axisLine={false} tickLine={false} width={60} />
                  <Tooltip
                    contentStyle={{ background: '#101a2b', border: 'none', borderRadius: 8, color: '#fff', fontSize: 11 }}
                    formatter={(value) => [value, 'Events']}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={22}>
                    {severityCounts.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* By risk type */}
          <div className="space-y-2 mt-4">
            <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">By Risk Type</p>
            {typeCountsSorted.length === 0 ? (
              <p className="text-xs text-text-muted">No risk events recorded.</p>
            ) : (
              typeCountsSorted.map(([type, count]) => (
                <div key={type} className="flex items-center gap-3">
                  <span className="text-xs text-text-secondary w-32 shrink-0 truncate">{riskTypeLabel(type)}</span>
                  <div className="flex-1 bg-bg rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-teal"
                      style={{ width: `${maxTypeCount ? (count / maxTypeCount) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-text-primary w-5 text-right">{count}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
