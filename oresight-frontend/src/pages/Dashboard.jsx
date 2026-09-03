import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  Factory, Activity, ShieldAlert, Gem, AlertTriangle, ArrowRight,
  Gauge, Eye, RefreshCw,
} from 'lucide-react';
import { Card, KPIStat, Badge, SkeletonKPIRow, InlineError, SectionDivider } from '../components';
import LiveEventFeed from '../components/LiveEventFeed';
import {
  dailyTotals, siteProductionSummary, equipment, riskEvents,
  weatherEvents,
} from '../data/mockData';
import { getSites, getRiskEvents } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';
import { estimateReserveConfidence } from '../lib/metrics';

// Institutional Survey Chart Colors
const COLORS = {
  oxblood: '#6B2737',      // Primary Accent
  slateNavy: '#2C3E50',    // Secondary Accent
  charcoal: '#1A1815',     // Ink Dark
  pineGreen: '#3E5C3A',    // Success
  rustRed: '#8C3B24',      // Warning / Danger
  parchment: '#DDD6C8',    // Border
  mutedGrey: '#6E695E',    // Text Muted
};

// Equipment status counts
const eqUp = equipment.filter(e => e.status === 'up').length;
const eqDown = equipment.filter(e => e.status === 'down').length;
const pieData = [
  { name: 'Operational', value: eqUp, color: COLORS.pineGreen },
  { name: 'Down', value: eqDown, color: COLORS.rustRed },
];

// Site bar data
const siteBarData = siteProductionSummary.map(s => ({
  name: s.name.replace(' Mine', ''),
  actual: s.avgDaily,
  target: s.totalTarget / 30,
}));

// Recent alerts
const recentAlerts = [
  ...riskEvents.map(r => ({
    id: r.id,
    title: r.risk_type,
    description: r.description,
    site: r.site_id,
    severity: r.severity,
    time: r.detected_at,
  })),
  ...weatherEvents
    .filter(w => w.status === 'active')
    .map(w => ({
      id: w.id,
      title: w.type,
      description: `${w.type} (severity ${w.severity}) at ${w.site_id} from ${w.start} to ${w.end}`,
      site: w.site_id,
      severity: w.severity >= 4 ? 'critical' : 'warning',
      time: w.start,
    })),
].sort((a, b) => b.time.localeCompare(a.time));

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[var(--bg-surface)] text-[var(--text-primary)] px-3 py-2 rounded-[3px] border border-[var(--border)] shadow-md text-xs font-mono">
      <p className="font-heading font-bold mb-1 text-[var(--text-primary)]">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : p.value} t
        </p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [liveSites, setLiveSites] = useState([]);
  const [liveRiskEvents, setLiveRiskEvents] = useState([]);
  const [liveStatus, setLiveStatus] = useState('loading');
  const [retryToken, setRetryToken] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLiveStatus('loading');
      try {
        const [sitesData, riskData] = await Promise.all([getSites(), getRiskEvents()]);
        if (cancelled) return;
        setLiveSites(sitesData);
        setLiveRiskEvents(riskData);
        setLiveStatus('ready');
      } catch {
        if (!cancelled) setLiveStatus('error');
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [retryToken]);

  const activeRiskEvents = liveRiskEvents.filter((e) => e.resolved === false).length;
  const avgReserveConfidence = liveSites.length
    ? liveSites.reduce((sum, s) => sum + estimateReserveConfidence(s), 0) / liveSites.length
    : 0;
  const sitesUnderWatch = liveSites.length;
  const latestUpdateDate = liveRiskEvents.reduce((latest, e) => {
    const ts = getEventTimestamp(e);
    if (!ts) return latest;
    return !latest || ts > latest ? ts : latest;
  }, null);
  const liveKpiValue = (value) => (liveStatus === 'ready' ? value : '—');

  const latestTotal = dailyTotals[dailyTotals.length - 1];
  const prevTotal = dailyTotals[dailyTotals.length - 2];
  const outputDelta = prevTotal
    ? Math.round(((latestTotal.actual - prevTotal.actual) / prevTotal.actual) * 1000) / 10
    : 0;

  const avgGrade = (siteProductionSummary.reduce((s, p) => s + p.achievement, 0) / 3).toFixed(1);

  return (
    <div className="page-container">
      {/* Topographic Contour Texture Hero Section */}
      <div className="contour-bg border border-[var(--border)] rounded-[3px] p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="page-title text-2xl font-bold">Operations Overview</h2>
            <p className="page-subtitle mb-0">Real-time mine production intelligence across all MOIL sites</p>
          </div>
          <div className="hidden sm:flex items-center gap-2 text-xs font-semibold px-3 py-1 bg-[var(--bg-surface)] border border-[var(--border)] rounded-[3px] text-[var(--text-muted)] font-mono">
            <span className="w-2 h-2 rounded-full bg-[var(--success)] animate-pulse" />
            LIVE TELEMETRY FEED
          </div>
        </div>

        {/* Asymmetric Live Twin State Row: Hero Card (Active Risk Events) sized ~1.5x */}
        {liveStatus === 'loading' ? (
          <SkeletonKPIRow count={4} className="mb-4" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
            {/* Larger Hero KPI Card (Roughly 1.5x to 2x width) */}
            <div className="xl:col-span-2">
              <KPIStat
                icon={ShieldAlert}
                value={liveKpiValue(String(activeRiskEvents).padStart(2, '0'))}
                label="Active Risk Events (Live Hero Metric)"
                color="orange"
                className="h-full border-l-4 border-l-[var(--accent-primary)]"
              />
            </div>
            <div className="xl:col-span-1">
              <KPIStat
                icon={Gauge}
                value={liveKpiValue(`${(avgReserveConfidence * 100).toFixed(1)}%`)}
                label="Avg Confidence"
                color="teal"
              />
            </div>
            <div className="xl:col-span-1">
              <KPIStat
                icon={Eye}
                value={liveKpiValue(String(sitesUnderWatch).padStart(2, '0'))}
                label="Sites Under Watch"
                color="navy"
              />
            </div>
            <div className="xl:col-span-1">
              <KPIStat
                icon={RefreshCw}
                value={liveKpiValue(latestUpdateDate ? formatRelativeTime(latestUpdateDate) : 'no data')}
                label="Twin Last Updated"
                color="teal"
              />
            </div>
          </div>
        )}

        {liveStatus === 'error' && (
          <InlineError
            className="mt-4"
            message="Unable to reach the backend at http://localhost:8000 — live KPI row above is showing offline fallback data."
            onRetry={() => setRetryToken((t) => t + 1)}
          />
        )}
      </div>

      {/* KPI Row (Sample/Demo metrics) */}
      <div className="grid-kpi stagger-children mb-6">
        <KPIStat
          label="Total Output (Today)"
          value={`${latestTotal.actual.toLocaleString()} t`}
          delta={outputDelta}
          deltaLabel="vs yesterday"
          icon={Factory}
          color="orange"
        />
        <KPIStat
          label="Equipment Uptime"
          value={`${Math.round((eqUp / equipment.length) * 100)}%`}
          delta={0}
          deltaLabel={`${eqUp}/${equipment.length} online`}
          icon={Activity}
          color="teal"
        />
        <KPIStat
          label="Active Risk Alerts"
          value={riskEvents.filter(r => r.status === 'active').length}
          delta={null}
          deltaLabel="requires attention"
          icon={AlertTriangle}
          color="danger"
        />
        <KPIStat
          label="Target Achievement"
          value={`${avgGrade}%`}
          delta={2.3}
          deltaLabel="vs last month"
          icon={Gem}
          color="success"
        />
      </div>

      <SectionDivider label="PRODUCTION ANALYTICS" />

      {/* Charts Row */}
      <div className="grid-2">
        {/* Production Trend */}
        <Card title="Production Trend" subtitle="Daily output vs target (all sites combined)">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <AreaChart data={dailyTotals} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.oxblood} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={COLORS.oxblood} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradTarget" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.slateNavy} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={COLORS.slateNavy} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: COLORS.mutedGrey, fontFamily: 'var(--font-mono)' }}
                  tickFormatter={v => v.slice(5)}
                  interval={4}
                />
                <YAxis tick={{ fontSize: 10, fill: COLORS.mutedGrey, fontFamily: 'var(--font-mono)' }} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="target" stroke={COLORS.slateNavy} strokeWidth={2} fill="url(#gradTarget)" name="Target" dot={false} />
                <Area type="monotone" dataKey="actual" stroke={COLORS.oxblood} strokeWidth={2} fill="url(#gradActual)" name="Actual" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Site Comparison */}
        <Card title="Output by Site" subtitle="Average daily output (tonnes)">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={siteBarData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: COLORS.mutedGrey, fontFamily: 'var(--font-body)' }} />
                <YAxis tick={{ fontSize: 10, fill: COLORS.mutedGrey, fontFamily: 'var(--font-mono)' }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="actual" name="Actual" fill={COLORS.oxblood} radius={[2, 2, 0, 0]} barSize={34} />
                <Bar dataKey="target" name="Target" fill={COLORS.slateNavy} radius={[2, 2, 0, 0]} barSize={34} opacity={0.65} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <SectionDivider label="OPERATIONAL FLEET & ALERTS" />

      {/* Bottom Row */}
      <div className="grid-3">
        {/* Recent Alerts */}
        <Card title="Recent Alerts" subtitle="Active risk events and weather alerts">
          <div className="space-y-3">
            {recentAlerts.map(alert => (
              <div
                key={alert.id}
                onClick={alert.site ? () => navigate(`/site/${alert.site}`) : undefined}
                className={`flex items-start gap-3 p-3 rounded-[3px] bg-[var(--bg-primary)] border border-[var(--border)] transition-colors duration-150 hover:border-[var(--accent-primary)] ${
                  alert.site ? 'cursor-pointer' : ''
                }`}
              >
                <div className={`mt-0.5 p-1.5 rounded-[3px] ${
                  alert.severity === 'critical' ? 'bg-[var(--warning)]/15 text-[var(--warning)]' : 'bg-[var(--warning)]/10 text-[var(--warning)]'
                }`}>
                  <AlertTriangle size={14} strokeWidth={1.75} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-bold text-[var(--text-primary)]">{alert.title}</span>
                    <Badge variant={alert.severity} dot>{alert.severity}</Badge>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] line-clamp-2">{alert.description}</p>
                  <div className="flex items-center gap-2 mt-1.5 font-mono">
                    <span className="text-[10px] text-[var(--text-muted)] capitalize">{alert.site}</span>
                    <span className="text-[10px] text-[var(--text-muted)]">•</span>
                    <span className="text-[10px] text-[var(--text-muted)]">{alert.time}</span>
                  </div>
                </div>
                <ArrowRight size={14} className="text-[var(--text-muted)] shrink-0 mt-1" />
              </div>
            ))}
          </div>
        </Card>

        {/* Live Event Feed */}
        <LiveEventFeed />

        {/* Equipment Status */}
        <Card title="Equipment Overview" subtitle="Fleet status across all sites">
          <div className="flex items-center gap-6">
            <div style={{ width: 150, height: 150 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={42}
                    outerRadius={65}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-2.5">
              {pieData.map(d => (
                <div key={d.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-[2px]" style={{ backgroundColor: d.color }} />
                    <span className="text-xs text-[var(--text-muted)]">{d.name}</span>
                  </div>
                  <span className="font-mono text-sm font-bold text-[var(--text-primary)]">{d.value}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-[var(--border)]">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-muted)]">Total Fleet</span>
                  <span className="font-mono text-sm font-bold text-[var(--text-primary)]">{equipment.length}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Per-site mini stats */}
          <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-[var(--border)]">
            {siteProductionSummary.map(site => (
              <div key={site.id} className="text-center">
                <p className="text-[11px] text-[var(--text-muted)] mb-0.5">{site.name.replace(' Mine', '')}</p>
                <p className="font-mono text-base font-bold text-[var(--text-primary)]">{site.equipmentUp}/{site.equipmentTotal}</p>
                <p className="text-[9.5px] text-[var(--text-muted)] uppercase tracking-wider font-mono">online</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
