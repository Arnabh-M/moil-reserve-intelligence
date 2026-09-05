import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  ShieldAlert, AlertTriangle, Zap, Link2, CheckCircle2, MapPin, Loader2, ArrowRight, CornerDownRight, Activity, Wrench, CloudRain, TrendingDown
} from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState, ErrorState, SkeletonKPIRow, SkeletonCard, SectionDivider } from '../components';
import CausalGraph from '../components/CausalGraph';
import { getRiskEvents, getCausalGraph, SITE_NAME_MAP } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';

const SEVERITY_LEVELS = [
  { level: 'critical', label: 'Critical', color: '#B84A3A' },
  { level: 'high', label: 'High', color: '#C56A32' },
  { level: 'medium', label: 'Medium', color: '#C38A32' },
  { level: 'low', label: 'Low', color: '#2E7D5B' },
];

const DEVIATION_CATEGORIES = [
  { id: 'grade_drop', label: 'Grade Drop', icon: TrendingDown, desc: 'Ore grade anomaly (<32% Mn)' },
  { id: 'output_deficit', label: 'Output Deficit', icon: Activity, desc: 'Daily extraction under 90% target' },
  { id: 'machinery_down', label: 'Machinery Down', icon: Wrench, desc: 'Heavy fleet hydraulic breakdown' },
  { id: 'weather_interruption', label: 'Weather Interruption', icon: CloudRain, desc: 'Pit wall slope erosion / monsoon' },
];

function severityVariant(severity) {
  const s = (severity || '').toLowerCase();
  if (s === 'high' || s === 'critical') return 'critical';
  if (s === 'medium') return 'warning';
  if (s === 'low') return 'confirmed';
  return 'info';
}

function riskTypeLabel(riskType) {
  if (!riskType) return 'Unknown Risk';
  return riskType.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

export default function Risks() {
  const [riskEvents, setRiskEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [expandedRisk, setExpandedRisk] = useState(null);
  const [causalGraphs, setCausalGraphs] = useState({});
  const [graphLoadingId, setGraphLoadingId] = useState(null);

  const loadRisks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRiskEvents();
      setRiskEvents(data || []);
    } catch (err) {
      console.error('[Risks] Error fetching risk events:', err);
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
    getCausalGraph(riskId)
      .then(graph => setCausalGraphs(prev => ({ ...prev, [riskId]: graph })))
      .catch(() => {})
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

  const activeRisks = riskEvents.filter(r => !r.resolved).length;
  const resolvedRisks = riskEvents.filter(r => r.resolved).length;

  return (
    <div className="page-container space-y-8">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--divider)]">
        <h1 className="page-title">Risk Telemetry &amp; Downstream Dependency Cascades</h1>
        <p className="page-subtitle mb-0">
          Disruption severity classification, root-cause analysis, and downstream operational propagation chains
        </p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPIStat
          label="Active Risk Events"
          value={activeRisks}
          deltaLabel="unresolved pit disruptions"
          icon={AlertTriangle}
        />
        <KPIStat
          label="Highest Risk Index"
          value="94%"
          deltaLabel="Balaghat East slope wall"
          icon={ShieldAlert}
        />
        <KPIStat
          label="Affected Sectors"
          value="2"
          deltaLabel="Balaghat & Bhandara"
          icon={MapPin}
        />
        <KPIStat
          label="Mitigated Anomalies"
          value={resolvedRisks || 14}
          deltaLabel="closed & Actioned"
          icon={CheckCircle2}
        />
      </div>

      {/* 4 Deviation Categories Grid */}
      <div>
        <h3 className="text-xs font-heading font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">
          4-Pillar Deviation Categories
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {DEVIATION_CATEGORIES.map(cat => {
            const Icon = cat.icon;
            return (
              <div key={cat.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] font-body">
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-7 h-7 rounded-lg bg-[var(--accent-soft)] text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] flex items-center justify-center">
                    <Icon size={15} />
                  </div>
                  <span className="font-heading font-semibold text-xs text-[var(--text-primary)]">{cat.label}</span>
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">{cat.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cascade Schedule: Downstream Dependency Chain */}
      <Card title="Downstream Dependency Cascade Schedule" subtitle="Propagated impact across mining operations pipeline">
        <div className="p-4 rounded-xl bg-[var(--bg-secondary)]/50 border border-[var(--border)] space-y-4 font-body">
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-[var(--mineral-orange)] uppercase">
            <Zap size={15} />
            <span>Active Cascade: Heavy Pit Wall Rainfall Disruption</span>
          </div>

          <div className="flex flex-col md:flex-row items-stretch gap-3 text-xs">
            <div className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)] flex-1">
              <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block mb-1">Disruption</span>
              <p className="font-semibold text-[var(--critical)]">Pit Wall Slope Runoff</p>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">Saturated clay stratum</p>
            </div>

            <div className="hidden md:flex items-center text-[var(--text-muted)]">
              <ArrowRight size={16} />
            </div>

            <div className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)] flex-1">
              <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block mb-1">Affected Operation</span>
              <p className="font-semibold text-[var(--text-primary)]">Haul Road Access</p>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">Speed reduced by 60%</p>
            </div>

            <div className="hidden md:flex items-center text-[var(--text-muted)]">
              <ArrowRight size={16} />
            </div>

            <div className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)] flex-1">
              <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block mb-1">Dependent Operation</span>
              <p className="font-semibold text-[var(--text-primary)]">Crusher Plant B</p>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">Ore feed delay 2.5h</p>
            </div>

            <div className="hidden md:flex items-center text-[var(--text-muted)]">
              <ArrowRight size={16} />
            </div>

            <div className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)] flex-1">
              <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block mb-1">Revised Action</span>
              <p className="font-semibold text-[var(--success)]">Reroute via South Ramp</p>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">Recovers 85% throughput</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Main Grid: Progressive Disclosure Risk Feed */}
      <Card title="Active Risk Telemetry Feed" subtitle="Risk → Severity → Cause → Impact → Recommended Action">
        <div className="space-y-4">
          {riskEvents.map(risk => {
            const isExpanded = expandedRisk === risk.id;
            const siteLabel = risk.site_name || SITE_NAME_MAP[risk.site_id] || `Site ${risk.site_id}`;

            return (
              <div key={risk.id} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] font-body space-y-3">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2.5">
                    <Zap size={16} className="text-[var(--mineral-orange)]" />
                    <span className="font-heading font-bold text-sm text-[var(--text-primary)]">
                      {riskTypeLabel(risk.risk_type)}
                    </span>
                    <span className="text-xs text-[var(--text-muted)]">• {siteLabel}</span>
                  </div>
                  <Badge variant={severityVariant(risk.severity)}>{risk.severity || 'high'}</Badge>
                </div>

                <p className="text-xs text-[var(--text-muted)] leading-relaxed">{risk.description}</p>

                {/* Progressive Disclosure Action Header */}
                <div className="flex items-center justify-between pt-2 border-t border-[var(--divider)] text-xs">
                  <span className="font-mono text-[11px] text-[var(--text-subtle)]">
                    Score: <strong className="text-[var(--text-primary)]">{risk.score || 0.82}</strong> • Logged {formatRelativeTime(getEventTimestamp(risk))}
                  </span>
                  <button
                    type="button"
                    onClick={() => toggleExpand(risk.id)}
                    className="font-semibold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] hover:underline inline-flex items-center gap-1 cursor-pointer"
                  >
                    <span>{isExpanded ? 'Hide Deep Analysis' : 'Expand Cause, Impact & Actions'}</span>
                    <CornerDownRight size={13} />
                  </button>
                </div>

                {/* Progressive Disclosure Expanded Content */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-[var(--divider)] space-y-3 animate-fade-in text-xs">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                        <span className="font-bold text-[var(--mineral-orange)] block mb-1">Root Cause</span>
                        <p className="text-[var(--text-muted)]">Sub-surface hydraulic pressure buildup along structural joint bedding.</p>
                      </div>
                      <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                        <span className="font-bold text-[var(--critical)] block mb-1">Estimated Impact</span>
                        <p className="text-[var(--text-muted)]">-150 tonnes/day extraction slowdown if unmitigated for 48 hours.</p>
                      </div>
                      <div className="p-3 rounded-lg bg-[var(--accent-soft)] border border-[var(--border)]">
                        <span className="font-bold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] block mb-1">Recommended Action</span>
                        <p className="text-[var(--text-primary)]">Deploy auxiliary dewatering pump &amp; shift haulage to East Pit Ramp B.</p>
                      </div>
                    </div>

                    {causalGraphs[risk.id] && (
                      <div className="pt-2">
                        <p className="text-[11px] font-heading font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                          Associated Causal Topological Graph
                        </p>
                        <CausalGraph graph={causalGraphs[risk.id]} height={220} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}



