import React, { useState, useMemo } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { Wrench, CheckCircle, XCircle, Clock, ArrowRightLeft } from 'lucide-react';
import { Card, KPIStat, Badge, Button, EmptyState, SectionDivider } from '../components';
import {
  equipment, downtimeLog, downtimeByReason, monthlyDowntime,
  redeploySuggestions, sites,
} from '../data/mockData';

const REASON_COLORS = {
  'Weather Delay': '#C1571E',
  'Scheduled Maintenance': '#4A7A4E',
  'Hydraulic Leak': '#B23B2E',
  'Electrical Fault': '#E07B3F',
  'Mechanical Failure': '#706B62',
  'Operator Shift Gap': '#8A8578',
  'Spare Parts Unavailable': '#EBE8E1',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[var(--bg-elevated)] text-[var(--text-primary)] px-3 py-2 rounded-lg border border-[var(--divider)] shadow-md text-xs">
      {label && <p className="font-semibold mb-1 text-[var(--text-primary)]">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill }} className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: p.color || p.fill }} />
          <span>{p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value} hrs</span>
        </p>
      ))}
    </div>
  );
};

export default function Equipment() {
  const [filterSite, setFilterSite] = useState('all');

  const upCount = equipment.filter(e => e.status === 'up').length;
  const downCount = equipment.filter(e => e.status === 'down').length;
  const avgDowntime = (downtimeLog.reduce((s, d) => s + d.duration_hours, 0) / downtimeLog.length).toFixed(1);
  const totalDowntimeHours = downtimeLog.reduce((s, d) => s + d.duration_hours, 0).toFixed(0);

  const filteredEquipment = useMemo(() => {
    return filterSite === 'all' ? equipment : equipment.filter(e => e.site_id === filterSite);
  }, [filterSite]);

  const pieData = downtimeByReason.map(d => ({
    name: d.reason,
    value: d.hours,
    color: REASON_COLORS[d.reason] || '#8A8578',
  }));

  const allReasons = [...new Set(downtimeLog.map(d => d.reason))];

  return (
    <div className="page-container">
      <div className="mb-10">
        <h1 className="page-title">Equipment Management</h1>
        <p className="page-subtitle">Fleet operational telemetry, downtime root-cause analysis, and AI redeployment dispatch</p>
      </div>

      {/* Stacked KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-12">
        <KPIStat
          label="Total Equipment"
          value={equipment.length}
          deltaLabel="across 3 sites"
          icon={Wrench}
        />
        <KPIStat
          label="Operational"
          value={upCount}
          deltaLabel={`${Math.round((upCount / equipment.length) * 100)}% uptime`}
          icon={CheckCircle}
        />
        <KPIStat
          label="Down"
          value={downCount}
          deltaLabel="active repair / delay"
          icon={XCircle}
        />
        <KPIStat
          label="Avg Downtime"
          value={`${avgDowntime} hrs`}
          deltaLabel={`${totalDowntimeHours} hrs total`}
          icon={Clock}
        />
      </div>

      <SectionDivider />

      {/* Equipment Fleet Table + Downtime Pie Chart */}
      <div className="grid-2 mb-10">
        {/* Equipment Fleet List */}
        <Card
          title="Equipment Fleet"
          subtitle={`${filteredEquipment.length} units in active monitoring`}
          action={
            <div className="flex items-center gap-1">
              {['all', ...sites.map(s => s.id)].map(s => (
                <button
                  key={s}
                  onClick={() => setFilterSite(s)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                    filterSite === s
                      ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          }
        >
          <div className="max-h-96 overflow-y-auto">
            {equipment.length === 0 ? (
              <EmptyState
                title="No equipment on record"
                message="Equipment status will appear here once added."
                tone="neutral"
              />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Asset Name</th>
                    <th>Type</th>
                    <th>Site</th>
                    <th>Status</th>
                    <th>Last Sync</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEquipment.map(eq => (
                    <tr key={eq.id}>
                      <td>
                        <div>
                          <p className="font-medium text-[var(--text-primary)]">{eq.name}</p>
                          <p className="text-[10px] text-[var(--text-muted)] font-mono">{eq.id}</p>
                        </div>
                      </td>
                      <td className="text-[var(--text-muted)]">{eq.type}</td>
                      <td className="capitalize text-[var(--text-muted)]">{eq.site_id}</td>
                      <td>
                        <Badge variant={eq.status} dot>{eq.status === 'up' ? 'Operational' : 'Down'}</Badge>
                      </td>
                      <td className="text-xs text-[var(--text-muted)]">
                        {new Date(eq.lastChange).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>

        {/* Downtime by Reason Pie */}
        <Card title="Downtime by Reason" subtitle="Cumulative hours breakdown across all fleets">
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                  stroke="none"
                >
                  {pieData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2.5 mt-3 pt-3 border-t border-[var(--divider)]">
            {pieData.map(d => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 truncate">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                  <span className="text-[var(--text-muted)] truncate">{d.name}</span>
                </div>
                <span className="font-semibold text-[var(--text-primary)] ml-2">{d.value.toFixed(0)}h</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <SectionDivider />

      {/* Monthly Downtime Stacked Bar */}
      <div className="mb-10">
        <Card title="Monthly Downtime Trends" subtitle="Hours categorized by reason category per month">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={monthlyDowntime} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.7} />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={v => {
                    const [, m] = v.split('-');
                    return ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(m)];
                  }}
                />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} axisLine={false} tickLine={false} width={36} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--divider)', fillOpacity: 0.3 }} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontFamily: 'Inter, sans-serif' }} />
                {allReasons.map(reason => (
                  <Bar
                    key={reason}
                    dataKey={reason}
                    stackId="a"
                    fill={REASON_COLORS[reason] || '#8A8578'}
                    radius={0}
                    barSize={24}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <SectionDivider />

      {/* AI Redeployment Opportunities */}
      <div className="space-y-4">
        <h3 className="text-base font-semibold text-[var(--text-primary)]">AI Fleet Dispatch &amp; Optimization</h3>
        {redeploySuggestions.map(suggestion => (
          <div key={suggestion.downEquipment.id} className="bg-[var(--bg-elevated)]/50 rounded-xl p-5 border border-[var(--divider)]">
            <div className="flex items-start gap-4">
              <div className="p-2.5 rounded-lg bg-[var(--accent-soft)] text-[var(--accent-primary)] shrink-0">
                <ArrowRightLeft size={20} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-xs font-semibold text-[var(--text-primary)]">Redeployment Opportunity</h4>
                  <Badge variant="orange">AI Recommended</Badge>
                </div>
                <p className="text-xs text-[var(--text-muted)] mb-3 leading-relaxed">{suggestion.reason}</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                  <div className="p-3 rounded-lg bg-[var(--critical)]/8 text-xs">
                    <p className="text-[10px] uppercase font-semibold text-[var(--critical)] mb-0.5">Down Equipment</p>
                    <p className="font-semibold text-[var(--text-primary)]">{suggestion.downEquipment.name}</p>
                    <p className="text-[11px] text-[var(--text-muted)]">{suggestion.downEquipment.site} • {suggestion.downEquipment.type}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--success)]/8 text-xs">
                    <p className="text-[10px] uppercase font-semibold text-[var(--success)] mb-0.5">Replacement Candidate</p>
                    <p className="font-semibold text-[var(--text-primary)]">{suggestion.candidate.name}</p>
                    <p className="text-[11px] text-[var(--text-muted)]">{suggestion.candidate.site} • {suggestion.candidate.type}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="primary" size="sm">Approve Redeployment</Button>
                  <Button variant="ghost" size="sm">Dismiss</Button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


