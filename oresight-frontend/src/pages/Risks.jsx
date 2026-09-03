import React, { useState } from 'react';
import {
  BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  ShieldAlert, AlertTriangle, CloudRain, Bomb,
  ArrowRight, Zap, Link2, CheckCircle2,
} from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState } from '../components';
import {
  riskEvents, weatherEvents, blastPlans, oreZones, sites,
} from '../data/mockData';

const COLORS = {
  orange: '#e0793a',
  orangeSoft: '#f2a768',
  teal: '#2a7f8c',
  navy: '#101a2b',
  navy2: '#16233a',
  muted: '#8896a8',
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f59e0b',
};

const SEVERITY_COLORS = [
  '#22c55e', // 1
  '#2a7f8c', // 2
  '#f59e0b', // 3
  '#e0793a', // 4
  '#ef4444', // 5
];

// Weather chart data
const weatherChartData = weatherEvents.map(w => ({
  name: `${w.type} (${w.site_id})`,
  severity: w.severity,
  site: w.site_id,
  duration: Math.round(
    (new Date(w.end).getTime() - new Date(w.start).getTime()) / (1000 * 60 * 60 * 24)
  ),
}));

// Causal chain detail available for risk events that trace back through a
// weather → blast-plan → ore-zone chain (currently only re_bal_01). Shown as
// an inline expansion on the risk card itself, rather than a separate
// duplicate widget repeating the same event.
const CAUSAL_CHAINS = {
  re_bal_01: {
    label: 'Weather → Blast Delay → OreZone impact',
    correlation: 'WeatherEvent we_bal_01 → DELAYS → bp_bal_01 → AFFECTS → oz_bal_01 | CORRELATES_WITH → re_bal_01',
  },
};

export default function Risks() {
  const [expandedRisk, setExpandedRisk] = useState(null);
  const activeRisks = riskEvents.filter(r => r.status === 'active').length;
  const highestScore = Math.max(...riskEvents.map(r => r.score));
  const delayedBlasts = blastPlans.filter(b => b.status === 'delayed').length;

  return (
    <div className="page-container">
      <h2 className="page-title">Risk & Alerts</h2>
      <p className="page-subtitle">Weather events, blast delays, and risk intelligence across mine sites</p>

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
          label="Delayed Blast Plans"
          value={delayedBlasts}
          delta={null}
          deltaLabel={`of ${blastPlans.length} total`}
          icon={Bomb}
          color="orange"
        />
        <KPIStat
          label="Weather Events"
          value={weatherEvents.length}
          delta={null}
          deltaLabel={`${weatherEvents.filter(w => w.status === 'active').length} active`}
          icon={CloudRain}
          color="teal"
        />
      </div>

      {/* Risk Events + Weather */}
      <div className="grid-2">
        {/* Risk Events */}
        <Card title="Risk Events" subtitle="Active and historical risk alerts">
          {activeRisks === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="No active risks"
              message="All sites operating normally"
              tone="positive"
            />
          ) : (
            <div className="space-y-3">
              {riskEvents.map(risk => (
                <div
                  key={risk.id}
                  className={`p-4 rounded-lg border transition-all duration-200 ${
                    risk.status === 'active'
                      ? 'bg-danger/5 border-danger/20 hover:border-danger/40'
                      : 'bg-bg border-border hover:border-success/30'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`p-1.5 rounded-lg ${
                        risk.severity === 'critical' ? 'bg-danger/10 text-danger' : 'bg-warning/10 text-warning'
                      }`}>
                        <Zap size={14} />
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-text-primary">{risk.risk_type}</span>
                        <span className="text-xs text-text-muted ml-2 capitalize">{risk.site_id}</span>
                      </div>
                    </div>
                    <Badge variant={risk.severity} dot>{risk.severity}</Badge>
                  </div>
                  <p className="text-xs text-text-secondary mb-2 leading-relaxed">{risk.description}</p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-text-muted">Score: <strong className="text-text-primary">{risk.score}</strong></span>
                      <span className="text-[10px] text-text-muted">Detected: {risk.detected_at}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {CAUSAL_CHAINS[risk.id] && (
                        <button
                          onClick={() => setExpandedRisk(expandedRisk === risk.id ? null : risk.id)}
                          className="flex items-center gap-1 text-[10px] font-medium text-teal hover:underline"
                        >
                          <Link2 size={11} />
                          {expandedRisk === risk.id ? 'Hide causal chain' : 'View causal chain'}
                        </button>
                      )}
                      <Badge variant={risk.status === 'active' ? 'down' : 'operational'} dot>
                        {risk.status}
                      </Badge>
                    </div>
                  </div>

                  {CAUSAL_CHAINS[risk.id] && expandedRisk === risk.id && (
                    <div className="mt-3 pt-3 border-t border-border">
                      <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-2">{CAUSAL_CHAINS[risk.id].label}</p>
                      <div className="flex items-center gap-2 overflow-x-auto pb-1">
                        <div className="shrink-0 p-2.5 rounded-lg bg-teal/10 border border-teal/20 min-w-[120px]">
                          <div className="flex items-center gap-1.5 mb-1">
                            <CloudRain size={11} className="text-teal" />
                            <span className="text-[9px] font-semibold text-teal uppercase">Weather</span>
                          </div>
                          <p className="text-[11px] font-semibold text-text-primary">Heavy Rain</p>
                          <p className="text-[9px] text-text-muted">Severity 5 • Balaghat</p>
                        </div>
                        <ArrowRight size={14} className="text-text-muted shrink-0" />
                        <div className="shrink-0 p-2.5 rounded-lg bg-warning/10 border border-warning/20 min-w-[120px]">
                          <div className="flex items-center gap-1.5 mb-1">
                            <Bomb size={11} className="text-warning" />
                            <span className="text-[9px] font-semibold text-warning uppercase">Blast Plan</span>
                          </div>
                          <p className="text-[11px] font-semibold text-text-primary">bp_bal_01</p>
                          <Badge variant="delayed" className="mt-1">Delayed</Badge>
                        </div>
                        <ArrowRight size={14} className="text-text-muted shrink-0" />
                        <div className="shrink-0 p-2.5 rounded-lg bg-orange/10 border border-orange/20 min-w-[120px]">
                          <div className="flex items-center gap-1.5 mb-1">
                            <Zap size={11} className="text-orange" />
                            <span className="text-[9px] font-semibold text-orange uppercase">Ore Zone</span>
                          </div>
                          <p className="text-[11px] font-semibold text-text-primary">oz_bal_01</p>
                          <p className="text-[9px] text-text-muted">Grade: 38.5% Mn</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-2 p-2 rounded-lg bg-bg border border-border border-dashed">
                        <Link2 size={11} className="text-text-muted shrink-0" />
                        <span className="text-[9.5px] text-text-muted">{CAUSAL_CHAINS[risk.id].correlation}</span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Weather Events */}
        <Card title="Weather Events" subtitle="Impact on operations by severity">
          <div style={{ width: '100%', height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={weatherChartData} layout="vertical" margin={{ top: 10, right: 10, left: 30, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke="var(--border)" strokeOpacity={0.6} />
                <XAxis type="number" tick={{ fontSize: 10, fill: COLORS.muted }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} label={{ value: 'Severity', position: 'insideBottom', offset: -2, fontSize: 10, fill: COLORS.muted }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: COLORS.muted }} axisLine={false} tickLine={false} width={120} />
                <Tooltip
                  contentStyle={{ background: '#101a2b', border: 'none', borderRadius: 8, color: '#fff', fontSize: 11 }}
                  formatter={(value, name) => [value, name]}
                />
                <Bar dataKey="severity" radius={[0, 6, 6, 0]} barSize={18}>
                  {weatherChartData.map((entry, idx) => (
                    <Cell key={idx} fill={SEVERITY_COLORS[entry.severity - 1] || COLORS.muted} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Weather detail list */}
          <div className="space-y-2 mt-4">
            {weatherEvents.map(w => (
              <div key={w.id} className="flex items-center justify-between p-2.5 rounded-lg bg-bg border border-border">
                <div className="flex items-center gap-2.5">
                  <CloudRain size={14} className="text-teal" />
                  <div>
                    <p className="text-xs font-semibold text-text-primary">{w.type}</p>
                    <p className="text-[10px] text-text-muted capitalize">{w.site_id} • {w.start} → {w.end}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex gap-0.5">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <span
                        key={i}
                        className={`w-1.5 h-4 rounded-full ${
                          i < w.severity ? '' : 'bg-border'
                        }`}
                        style={i < w.severity ? { backgroundColor: SEVERITY_COLORS[w.severity - 1] } : {}}
                      />
                    ))}
                  </div>
                  <Badge variant={w.status === 'active' ? 'down' : 'operational'} dot>{w.status}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Blast Plans — the Causal Chain widget that used to sit here duplicated
          the re_bal_01 risk event already shown in the Risk Events card above,
          so it's now an inline expansion on that card instead of a separate panel. */}
      <div>
        <Card title="Blast Plan Status" subtitle={`${blastPlans.length} plans across all sites`}>
          <div className="space-y-2.5">
            {blastPlans.map(bp => {
              const zone = oreZones.find(z => z.id === bp.affectsZone);
              const weather = weatherEvents.find(w => w.id === bp.delayedBy);
              const siteName = sites.find(s => s.id === bp.site_id)?.name || bp.site_id;

              return (
                <div
                  key={bp.id}
                  className={`p-3 rounded-lg border transition-all duration-200 ${
                    bp.status === 'delayed'
                      ? 'bg-warning/5 border-warning/20 hover:border-warning/40'
                      : bp.status === 'completed'
                        ? 'bg-success/5 border-success/20 hover:border-success/40'
                        : 'bg-bg border-border hover:border-teal/30'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <Bomb size={13} className={
                        bp.status === 'delayed' ? 'text-warning' :
                        bp.status === 'completed' ? 'text-success' : 'text-teal'
                      } />
                      <span className="text-sm font-semibold text-text-primary font-mono">{bp.id}</span>
                      <span className="text-xs text-text-muted">— {siteName.replace(' Mine', '')}</span>
                    </div>
                    <Badge variant={bp.status}>{bp.status}</Badge>
                  </div>
                  <div className="flex items-center gap-4 text-[10px] text-text-muted">
                    <span>📅 {bp.scheduled_date}</span>
                    {zone && <span>🎯 Zone: {zone.id} ({zone.grade_estimate}% Mn)</span>}
                    {weather && <span>⛈️ Delayed by: {weather.type}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
