import React, { useState, useMemo } from 'react';
import {
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { Factory, Target, Trophy, TrendingDown } from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState, SectionDivider } from '../components';
import { productionHistory, siteProductionSummary, dailyTotals } from '../data/mockData';

const SITE_COLORS = {
  balaghat: '#C1571E', // warm terracotta
  nagpur: '#706B62',   // slate neutral
  bhandara: '#4A7A4E', // sage green
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
    <div className="bg-[var(--bg-elevated)] text-[var(--text-primary)] px-3 py-2 rounded-lg border border-[var(--divider)] shadow-md text-xs">
      <p className="font-semibold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: p.color }} />
          <span>{p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : p.value} t</span>
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
      <div className="mb-10">
        <h1 className="page-title">Production Analytics</h1>
        <p className="page-subtitle">Output trends, target tracking, and deviation analysis across mine sites</p>
      </div>

      {isEmpty ? (
        <EmptyState
          title="No production data yet"
          message="Daily production entries will appear here once recorded."
          tone="neutral"
        />
      ) : (
        <>
          {/* Stacked KPI Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-12">
            <KPIStat
              label="Total Output (MTD)"
              value={`${totalOutput.toLocaleString()} t`}
              delta={3.2}
              deltaLabel="vs last month"
              icon={Factory}
            />
            <KPIStat
              label="Target Achievement"
              value={`${overallAchievement}%`}
              delta={parseFloat(overallAchievement) > 100 ? 1.2 : -0.8}
              deltaLabel="month-over-month"
              icon={Target}
            />
            <KPIStat
              label="Top Performing Site"
              value={topSite.name.replace(' Mine', '')}
              deltaLabel={`${topSite.achievement}% achievement`}
              icon={Trophy}
            />
            <KPIStat
              label="Deviation Days"
              value={deviations.length}
              deltaLabel="days >5% off target"
              icon={TrendingDown}
            />
          </div>

          <SectionDivider />

          {/* Tab Selector */}
          <div className="flex items-center gap-1.5 mb-6">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setSelectedSite(tab.id)}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  selectedSite === tab.id
                    ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Charts Row */}
          <div className="grid-2 mb-10">
            {/* Main production chart */}
            <Card
              title={selectedSite === 'all' ? 'Daily Output by Site' : `Daily Output — ${tabs.find(t => t.id === selectedSite)?.label}`}
              subtitle="Actual production output telemetry (tonnes/day)"
            >
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer>
                  {selectedSite === 'all' && multiSiteData ? (
                    <LineChart data={multiSiteData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                      <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.7} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} tickFormatter={v => v.slice(5)} interval={4} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} axisLine={false} tickLine={false} width={38} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontFamily: 'Inter, sans-serif' }} />
                      <Line type="monotone" dataKey="balaghat" stroke={SITE_COLORS.balaghat} strokeWidth={2} dot={false} name="Balaghat" />
                      <Line type="monotone" dataKey="nagpur" stroke={SITE_COLORS.nagpur} strokeWidth={2} dot={false} name="Nagpur" />
                      <Line type="monotone" dataKey="bhandara" stroke={SITE_COLORS.bhandara} strokeWidth={2} dot={false} name="Bhandara" />
                    </LineChart>
                  ) : (
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                      <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.7} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} tickFormatter={v => v.slice(5)} interval={4} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} axisLine={false} tickLine={false} width={38} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontFamily: 'Inter, sans-serif' }} />
                      <Line type="monotone" dataKey="actual" stroke="#C1571E" strokeWidth={2} dot={false} name="Actual" />
                      <Line type="monotone" dataKey="target" stroke="#8A8578" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="Target" />
                    </LineChart>
                  )}
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Site comparison */}
            <Card title="Site Performance Comparison" subtitle="Target achievement rate and daily average">
              <div className="space-y-4 pt-1">
                {siteProductionSummary.map(site => {
                  const pct = site.achievement;
                  return (
                    <div key={site.id}>
                      <div className="flex items-center justify-between mb-1.5 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] }} />
                          <span className="font-medium text-[var(--text-primary)]">{site.name}</span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <span className="text-[var(--text-muted)]">{site.avgDaily} t/day</span>
                          <Badge variant={pct >= 100 ? 'operational' : pct >= 95 ? 'warning' : 'down'}>
                            {pct}%
                          </Badge>
                        </div>
                      </div>
                      <div className="w-full bg-[var(--divider)]/40 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${Math.min(pct, 100)}%`,
                            backgroundColor: SITE_COLORS[site.id],
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Summary table */}
              <div className="mt-8 pt-4 border-t border-[var(--divider)]">
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

          <SectionDivider />

          {/* Deviation Table */}
          {deviations.length > 0 && (
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1">Production Deviations</h3>
              <p className="text-xs text-[var(--text-muted)] mb-4">Daily logs with &gt;5% deviation from scheduled targets</p>
              <div className="max-h-72 overflow-y-auto">
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
                          <span className={`font-semibold ${d.deviation > 0 ? 'text-[var(--success)]' : 'text-[var(--critical)]'}`}>
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
            </div>
          )}
        </>
      )}
    </div>
  );
}


