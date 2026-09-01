import React, { useState, useMemo } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { Wrench, CheckCircle, XCircle, Clock, ArrowRightLeft, AlertTriangle } from 'lucide-react';
import { Card, KPIStat, Badge, Button, EmptyState } from '../components';
import {
  equipment, downtimeLog, downtimeByReason, monthlyDowntime,
  redeploySuggestions, sites,
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

const REASON_COLORS = {
  'Weather Delay': '#2a7f8c',
  'Scheduled Maintenance': '#22c55e',
  'Hydraulic Leak': '#e0793a',
  'Electrical Fault': '#f59e0b',
  'Mechanical Failure': '#ef4444',
  'Operator Shift Gap': '#16233a',
  'Spare Parts Unavailable': '#f2a768',
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-navy text-white px-3 py-2 rounded-lg shadow-lg text-xs">
      {label && <p className="font-semibold mb-1">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value} hrs
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
    color: REASON_COLORS[d.reason] || COLORS.muted,
  }));

  // All unique reasons for stacked bar
  const allReasons = [...new Set(downtimeLog.map(d => d.reason))];

  return (
    <div className="page-container">
      <h2 className="page-title">Equipment Management</h2>
      <p className="page-subtitle">Fleet status, downtime analytics, and redeployment intelligence</p>

      {/* KPI Row */}
      <div className="grid-kpi stagger-children">
        <KPIStat
          label="Total Equipment"
          value={equipment.length}
          delta={null}
          deltaLabel="across 3 sites"
          icon={Wrench}
          color="navy"
        />
        <KPIStat
          label="Operational"
          value={upCount}
          delta={null}
          deltaLabel={`${Math.round((upCount / equipment.length) * 100)}% uptime`}
          icon={CheckCircle}
          color="success"
        />
        <KPIStat
          label="Down"
          value={downCount}
          delta={null}
          deltaLabel="requires attention"
          icon={XCircle}
          color="danger"
        />
        <KPIStat
          label="Avg Downtime"
          value={`${avgDowntime} hrs`}
          delta={null}
          deltaLabel={`${totalDowntimeHours} hrs total`}
          icon={Clock}
          color="warning"
        />
      </div>

      {/* Equipment Table + Pie Chart */}
      <div className="grid-2">
        {/* Equipment Table */}
        <Card
          title="Equipment Fleet"
          subtitle={`${filteredEquipment.length} units`}
          action={
            <div className="flex gap-1 p-0.5 bg-bg rounded-lg border border-border">
              {['all', ...sites.map(s => s.id)].map(s => (
                <button
                  key={s}
                  onClick={() => setFilterSite(s)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors duration-150 ${
                    filterSite === s ? 'bg-white text-text-primary shadow-sm' : 'text-text-muted hover:text-text-primary'
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
                    <th>Name</th>
                    <th>Type</th>
                    <th>Site</th>
                    <th>Status</th>
                    <th>Last Change</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEquipment.map(eq => (
                    <tr key={eq.id}>
                      <td>
                        <div>
                          <p className="font-medium text-text-primary">{eq.name}</p>
                          <p className="text-[10px] text-text-muted font-mono">{eq.id}</p>
                        </div>
                      </td>
                      <td>{eq.type}</td>
                      <td className="capitalize">{eq.site_id}</td>
                      <td>
                        <Badge variant={eq.status} dot>{eq.status === 'up' ? 'Operational' : 'Down'}</Badge>
                      </td>
                      <td className="text-xs text-text-muted">
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
        <Card title="Downtime by Reason" subtitle="Total hours breakdown">
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  stroke="none"
                >
                  {pieData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => `${value.toFixed(1)} hrs`}
                  contentStyle={{ background: '#101a2b', border: 'none', borderRadius: 8, color: '#fff', fontSize: 11 }}
                  itemStyle={{ color: '#fff' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {pieData.map(d => (
              <div key={d.name} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                <span className="text-xs text-text-secondary truncate">{d.name}</span>
                <span className="text-xs font-semibold text-text-primary ml-auto">{d.value.toFixed(0)}h</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Monthly Downtime Stacked Bar */}
      <Card title="Monthly Downtime Trends" subtitle="Hours by reason category per month" className="mb-6">
        <div style={{ width: '100%', height: 300 }}>
          <ResponsiveContainer>
            <BarChart data={monthlyDowntime} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
              <XAxis
                dataKey="month"
                tick={{ fontSize: 10, fill: COLORS.muted }}
                tickFormatter={v => {
                  const [, m] = v.split('-');
                  return ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(m)];
                }}
              />
              <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
              {allReasons.map(reason => (
                <Bar
                  key={reason}
                  dataKey={reason}
                  stackId="a"
                  fill={REASON_COLORS[reason] || COLORS.muted}
                  radius={0}
                  barSize={28}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Redeploy Suggestion */}
      {redeploySuggestions.map(suggestion => (
        <Card key={suggestion.downEquipment.id} className="mb-6">
          <div className="flex items-start gap-4 p-2">
            <div className="p-3 rounded-xl bg-orange/10 text-orange shrink-0">
              <ArrowRightLeft size={24} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="text-sm font-bold text-text-primary">Redeployment Opportunity</h4>
                <Badge variant="orange">AI Suggested</Badge>
              </div>
              <p className="text-sm text-text-secondary mb-3">{suggestion.reason}</p>
              <div className="flex items-center gap-4">
                <div className="flex-1 p-3 rounded-lg bg-danger/5 border border-danger/20">
                  <p className="text-[10px] text-text-muted uppercase tracking-wide mb-0.5">Down Equipment</p>
                  <p className="text-sm font-semibold text-danger">{suggestion.downEquipment.name}</p>
                  <p className="text-xs text-text-muted">{suggestion.downEquipment.site} • {suggestion.downEquipment.type}</p>
                </div>
                <ArrowRightLeft size={18} className="text-text-muted shrink-0" />
                <div className="flex-1 p-3 rounded-lg bg-success/5 border border-success/20">
                  <p className="text-[10px] text-text-muted uppercase tracking-wide mb-0.5">Redeploy Candidate</p>
                  <p className="text-sm font-semibold text-success">{suggestion.candidate.name}</p>
                  <p className="text-xs text-text-muted">{suggestion.candidate.site} • {suggestion.candidate.type}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <Button variant="primary" size="sm">Approve Redeployment</Button>
                <Button variant="ghost" size="sm">Dismiss</Button>
              </div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
