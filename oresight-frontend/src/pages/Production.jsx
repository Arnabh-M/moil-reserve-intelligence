import React, { useState, useMemo } from 'react';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { Factory, Target, Trophy, TrendingDown } from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState } from '../components';
import { productionHistory, siteProductionSummary, dailyTotals } from '../data/mockData';

const COLORS = {
  orange: '#e0793a',
  orangeSoft: '#f2a768',
  teal: '#2a7f8c',
  navy: '#101a2b',
  navy2: '#16233a',
  muted: '#8896a8',
  danger: '#ef4444',
};

const SITE_COLORS = {
  balaghat: '#e0793a',
  nagpur: '#2a7f8c',
  bhandara: '#16233a',
};

const tabs = [
  { id: 'all', label: 'All Sites' },
  { id: 'balaghat', label: 'Balaghat' },
  { id: 'nagpur', label: 'Nagpur' },
  { id: 'bhandara', label: 'Bhandara' },
];

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

export default function Production() {
  const [selectedSite, setSelectedSite] = useState('all');

  // Filter production data by site
  const chartData = useMemo(() => {
    if (selectedSite === 'all') {
      return dailyTotals;
    }
    return productionHistory
      .filter(p => p.site_id === selectedSite)
      .map(p => ({ date: p.date, actual: p.actual_output, target: p.target_output }));
  }, [selectedSite]);

  // KPI calculations
  const totalOutput = siteProductionSummary.reduce((s, p) => s + p.totalActual, 0);
  const totalTarget = siteProductionSummary.reduce((s, p) => s + p.totalTarget, 0);
  const overallAchievement = ((totalOutput / totalTarget) * 100).toFixed(1);
  const topSite = [...siteProductionSummary].sort((a, b) => b.achievement - a.achievement)[0];

  // Deviation data: days where actual deviated >5% from target
  const deviations = useMemo(() => {
    const data = selectedSite === 'all'
      ? dailyTotals.map(d => ({ ...d, site_id: 'all' }))
      : productionHistory
          .filter(p => p.site_id === selectedSite)
          .map(p => ({ date: p.date, actual: p.actual_output, target: p.target_output, site_id: p.site_id }));

    return data
      .map(d => {
        const deviation = ((d.actual - d.target) / d.target) * 100;
        return { ...d, deviation: Math.round(deviation * 10) / 10 };
      })
      .filter(d => Math.abs(d.deviation) > 5)
      .sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation));
  }, [selectedSite]);

  // Per-site daily breakdown for multi-line chart
  const multiSiteData = useMemo(() => {
    if (selectedSite !== 'all') return null;
    const dateMap = {};
    productionHistory.forEach(p => {
      if (!dateMap[p.date]) dateMap[p.date] = { date: p.date };
      dateMap[p.date][p.site_id] = p.actual_output;
    });
    return Object.values(dateMap);
  }, [selectedSite]);

  const isEmpty = productionHistory.length === 0 || siteProductionSummary.length === 0;

  return (
    <div className="page-container">
      <h2 className="page-title">Production Analytics</h2>
      <p className="page-subtitle">Output trends, target tracking, and deviation analysis across mine sites</p>

      {isEmpty ? (
        <EmptyState
          title="No production data yet"
          message="Daily production entries will appear here once recorded."
          tone="neutral"
        />
      ) : (
      <>
      {/* KPI Row */}
      <div className="grid-kpi stagger-children">
        <KPIStat
          label="Total Output (MTD)"
          value={`${totalOutput.toLocaleString()} t`}
          delta={3.2}
          deltaLabel="vs last month"
          icon={Factory}
          color="orange"
        />
        <KPIStat
          label="Target Achievement"
          value={`${overallAchievement}%`}
          delta={parseFloat(overallAchievement) > 100 ? 1.2 : -0.8}
          deltaLabel="month-over-month"
          icon={Target}
          color={parseFloat(overallAchievement) >= 100 ? 'success' : 'warning'}
        />
        <KPIStat
          label="Top Performing Site"
          value={topSite.name.replace(' Mine', '')}
          delta={null}
          deltaLabel={`${topSite.achievement}% achievement`}
          icon={Trophy}
          color="teal"
        />
        <KPIStat
          label="Deviation Days"
          value={deviations.length}
          delta={null}
          deltaLabel="days with >5% deviation"
          icon={TrendingDown}
          color="danger"
        />
      </div>

      {/* Tab Selector */}
      <div className="flex gap-1 mb-4 p-1 bg-white rounded-lg border border-border w-fit">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setSelectedSite(tab.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
              selectedSite === tab.id
                ? 'bg-orange text-white shadow-sm'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Charts */}
      <div className="grid-2">
        {/* Main production chart */}
        <Card
          title={selectedSite === 'all' ? 'Daily Output by Site' : `Daily Output — ${tabs.find(t => t.id === selectedSite)?.label}`}
          subtitle="Actual production output (tonnes/day)"
        >
          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer>
              {selectedSite === 'all' && multiSiteData ? (
                <LineChart data={multiSiteData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: COLORS.muted }} tickFormatter={v => v.slice(5)} interval={4} />
                  <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="balaghat" stroke={SITE_COLORS.balaghat} strokeWidth={2} dot={false} name="Balaghat" />
                  <Line type="monotone" dataKey="nagpur" stroke={SITE_COLORS.nagpur} strokeWidth={2} dot={false} name="Nagpur" />
                  <Line type="monotone" dataKey="bhandara" stroke={SITE_COLORS.bhandara} strokeWidth={2} dot={false} name="Bhandara" />
                </LineChart>
              ) : (
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: COLORS.muted }} tickFormatter={v => v.slice(5)} interval={4} />
                  <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="actual" stroke={COLORS.orange} strokeWidth={2} dot={false} name="Actual" />
                  <Line type="monotone" dataKey="target" stroke={COLORS.teal} strokeWidth={2} dot={false} strokeDasharray="6 3" name="Target" />
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Site comparison */}
        <Card title="Site Performance Comparison" subtitle="Achievement rate and daily averages">
          <div className="space-y-4 mt-2">
            {siteProductionSummary.map(site => {
              const pct = site.achievement;
              return (
                <div key={site.id}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] }} />
                      <span className="text-sm font-medium text-text-primary">{site.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-muted">{site.avgDaily} t/day avg</span>
                      <Badge variant={pct >= 100 ? 'operational' : pct >= 95 ? 'warning' : 'down'}>
                        {pct}%
                      </Badge>
                    </div>
                  </div>
                  <div className="w-full bg-bg rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.min(pct, 105)}%`,
                        backgroundColor: SITE_COLORS[site.id],
                        maxWidth: '100%',
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Summary table */}
          <div className="mt-6 pt-4 border-t border-border">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Site</th>
                  <th>Total (MTD)</th>
                  <th>Target</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {siteProductionSummary.map(site => (
                  <tr key={site.id}>
                    <td className="font-medium">{site.name.replace(' Mine', '')}</td>
                    <td>{site.totalActual.toLocaleString()} t</td>
                    <td>{site.totalTarget.toLocaleString()} t</td>
                    <td>
                      <Badge variant={site.achievement >= 100 ? 'operational' : 'warning'}>
                        {site.achievement >= 100 ? 'On Track' : 'Below Target'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Deviation Table */}
      {deviations.length > 0 && (
        <Card title="Production Deviations" subtitle="Days with >5% deviation from target" className="mt-1.5">
          <div className="max-h-64 overflow-y-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  {selectedSite === 'all' && <th>Scope</th>}
                  <th>Actual</th>
                  <th>Target</th>
                  <th>Deviation</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {deviations.slice(0, 15).map((d, i) => (
                  <tr key={i}>
                    <td className="font-medium">{d.date}</td>
                    {selectedSite === 'all' && <td className="capitalize">{d.site_id}</td>}
                    <td>{d.actual.toLocaleString()} t</td>
                    <td>{d.target.toLocaleString()} t</td>
                    <td>
                      <span className={`font-semibold ${d.deviation > 0 ? 'text-success' : 'text-danger'}`}>
                        {d.deviation > 0 ? '+' : ''}{d.deviation}%
                      </span>
                    </td>
                    <td>
                      <Badge variant={d.deviation > 0 ? 'operational' : 'down'}>
                        {d.deviation > 0 ? 'Over' : 'Under'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      </>
      )}
    </div>
  );
}
