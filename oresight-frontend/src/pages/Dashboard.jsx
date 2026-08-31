import React, { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  Factory, Activity, ShieldAlert, Gem, AlertTriangle, ArrowRight,
  Gauge, Eye, RefreshCw, AlertCircle,
} from 'lucide-react';
import { Card, KPIStat, Badge } from '../components';
import LiveEventFeed from '../components/LiveEventFeed';
import {
  dailyTotals, siteProductionSummary, equipment, riskEvents,
  weatherEvents, blastPlans,
} from '../data/mockData';
import { getSites, getRiskEvents } from '../api/client';
import { getEventTimestamp, formatRelativeTime } from '../lib/time';
import { estimateReserveConfidence } from '../lib/metrics';

// Chart color tokens
const COLORS = {
  orange: '#e0793a',
  orangeSoft: '#f2a768',
  teal: '#2a7f8c',
  navy: '#101a2b',
  navy2: '#16233a',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
  muted: '#8896a8',
};

const SITE_COLORS = {
  balaghat: COLORS.orange,
  nagpur: COLORS.teal,
  bhandara: COLORS.navy2,
};

// Equipment status counts
const eqUp = equipment.filter(e => e.status === 'up').length;
const eqDown = equipment.filter(e => e.status === 'down').length;
const pieData = [
  { name: 'Operational', value: eqUp, color: COLORS.success },
  { name: 'Down', value: eqDown, color: COLORS.danger },
];

// Site bar data
const siteBarData = siteProductionSummary.map(s => ({
  name: s.name.replace(' Mine', ''),
  actual: s.avgDaily,
  target: s.totalTarget / 30,
}));

// Recent alerts (combine risk + weather)
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
    <div className="bg-navy text-white px-3 py-2 rounded-lg shadow-lg text-xs">
      <p className="font-semibold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : p.value} t
        </p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  // Live twin-state KPIs (ported from the old CommandCenter page) — these
  // hit the real API/mock-fallback client, independent of the static
  // mockData.js the charts below use.
  const [liveSites, setLiveSites] = useState([]);
  const [liveRiskEvents, setLiveRiskEvents] = useState([]);
  const [liveStatus, setLiveStatus] = useState('loading'); // 'loading' | 'ready' | 'error'

  useEffect(() => {
    let cancelled = false;

    async function load() {
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
  }, []);

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
      <h2 className="page-title">Executive Overview</h2>
      <p className="page-subtitle">Real-time mine production intelligence across all MOIL sites</p>

      {/* Live Twin State Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <KPIStat
          icon={ShieldAlert}
          value={liveKpiValue(String(activeRiskEvents).padStart(2, '0'))}
          label="Active Risk Events (Live)"
          color="orange"
        />
        <KPIStat
          icon={Gauge}
          value={liveKpiValue(`${(avgReserveConfidence * 100).toFixed(1)}%`)}
          label="Avg Reserve Confidence (Live)"
          color="teal"
        />
        <KPIStat
          icon={Eye}
          value={liveKpiValue(String(sitesUnderWatch).padStart(2, '0'))}
          label="Sites Under Watch (Live)"
          color="navy"
        />
        <KPIStat
          icon={RefreshCw}
          value={liveKpiValue(latestUpdateDate ? formatRelativeTime(latestUpdateDate) : 'no data')}
          label="Twin Last Updated (Live)"
          color="teal"
        />
      </div>

      {liveStatus === 'error' && (
        <div className="flex items-center gap-2 rounded-sm border border-orange/30 bg-orange/5 px-4 py-3 text-xs text-orange mb-4">
          <AlertCircle size={14} className="shrink-0" />
          Unable to reach the backend at http://localhost:8000 — live KPI row above is showing unavailable data.
        </div>
      )}

      {/* KPI Row (sample/demo data driving the charts below) */}
      <div className="grid-kpi stagger-children">
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

      {/* Charts Row */}
      <div className="grid-2">
        {/* Production Trend */}
        <Card title="Production Trend" subtitle="Daily output vs target (all sites combined)">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <AreaChart data={dailyTotals} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.orange} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={COLORS.orange} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradTarget" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.teal} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={COLORS.teal} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: COLORS.muted }}
                  tickFormatter={v => v.slice(5)}
                  interval={4}
                />
                <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="target" stroke={COLORS.teal} strokeWidth={2} fill="url(#gradTarget)" name="Target" dot={false} />
                <Area type="monotone" dataKey="actual" stroke={COLORS.orange} strokeWidth={2} fill="url(#gradActual)" name="Actual" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Site Comparison */}
        <Card title="Output by Site" subtitle="Average daily output (tonnes)">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={siteBarData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: COLORS.muted }} />
                <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="actual" name="Actual" fill={COLORS.orange} radius={[6, 6, 0, 0]} barSize={36} />
                <Bar dataKey="target" name="Target" fill={COLORS.teal} radius={[6, 6, 0, 0]} barSize={36} opacity={0.6} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid-3">
        {/* Recent Alerts */}
        <Card title="Recent Alerts" subtitle="Active risk events and weather alerts">
          <div className="space-y-3">
            {recentAlerts.map(alert => (
              <div
                key={alert.id}
                className="flex items-start gap-3 p-3 rounded-lg bg-bg border border-border transition-all duration-200 hover:border-orange/30"
              >
                <div className={`mt-0.5 p-1.5 rounded-lg ${
                  alert.severity === 'critical' ? 'bg-danger/10 text-danger' : 'bg-warning/10 text-warning'
                }`}>
                  <AlertTriangle size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-text-primary">{alert.title}</span>
                    <Badge variant={alert.severity} dot>{alert.severity}</Badge>
                  </div>
                  <p className="text-xs text-text-secondary line-clamp-2">{alert.description}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-[10px] text-text-muted capitalize">{alert.site}</span>
                    <span className="text-[10px] text-text-muted">•</span>
                    <span className="text-[10px] text-text-muted">{alert.time}</span>
                  </div>
                </div>
                <ArrowRight size={14} className="text-text-muted shrink-0 mt-1" />
              </div>
            ))}
          </div>
        </Card>

        {/* Live Event Feed (real backend, polls every 15s) */}
        <LiveEventFeed />

        {/* Equipment Status */}
        <Card title="Equipment Overview" subtitle="Fleet status across all sites">
          <div className="flex items-center gap-8">
            <div style={{ width: 160, height: 160 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={70}
                    paddingAngle={4}
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
            <div className="flex-1 space-y-3">
              {pieData.map(d => (
                <div key={d.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                    <span className="text-sm text-text-secondary">{d.name}</span>
                  </div>
                  <span className="text-sm font-bold text-text-primary">{d.value}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-border">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Total Fleet</span>
                  <span className="text-sm font-bold text-text-primary">{equipment.length}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Per-site mini stats */}
          <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-border">
            {siteProductionSummary.map(site => (
              <div key={site.id} className="text-center">
                <p className="text-xs text-text-muted mb-1">{site.name.replace(' Mine', '')}</p>
                <p className="text-lg font-bold text-text-primary">{site.equipmentUp}/{site.equipmentTotal}</p>
                <p className="text-[10px] text-text-muted">online</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
